from datetime import date, timedelta
from io import BytesIO, StringIO
from importlib import import_module
import json
import tempfile
from types import SimpleNamespace
from unittest.mock import ANY, patch

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadhandler import StopUpload
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404, HttpResponse
from django.test import TestCase, Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from allauth.socialaccount.models import SocialAccount, SocialApp

from pickem.utils import get_season
from pickem_api.models import (
    currentSeason,
    Family,
    FamilyAuditLog,
    FamilyInvitation,
    FamilyMembership,
    GamePicks,
    GamesAndScores,
    GameWeeks,
    Pool,
    PoolSettings,
    Teams,
    userSeasonPoints,
    userStats,
    UserProfile,
)
from pickem_homepage.authz import family_member_required
from pickem.context_processors import footer_stats_context, site_banner_context
from pickem_homepage.models import (
    MessageBoardPost,
    MessageBoardComment,
    MessageBoardVote,
    SiteBanner,
)
from pickem_homepage.views import is_commissioner
from PIL import Image


class ViewSmokeTests(TestCase):
    """Smoke tests: anonymous GET requests to every public page."""

    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()

    # -- public pages (200) --

    def test_index_returns_200(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def assert_redirects_to_login(self, path):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])
        self.assertIn(f"next={path}", resp["Location"])

    def test_logged_out_web_app_routes_redirect_to_login(self):
        for path in [
            "/scores/",
            "/standings/",
            "/rules/",
            "/picks/",
            "/profile/",
            "/commissioners/",
            "/families/",
            "/families/create/",
            "/families/join/",
            "/families/smith-family/pools/main/",
            "/invites/example-code/",
            "/onboarding/",
            "/message-board/create-post/",
        ]:
            with self.subTest(path=path):
                self.assert_redirects_to_login(path)

    def test_accounts_routes_remain_public_for_login(self):
        resp = self.client.get("/accounts/login/")
        self.assertNotEqual(resp.status_code, 302)

    def test_logged_out_homepage_and_login_hide_internal_nav_links(self):
        for path in ["/", "/accounts/login/"]:
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 200)
                self.assertNotContains(resp, 'data-testid="app-primary-nav"')
                self.assertNotContains(resp, 'id="mobile-menu-btn"')

    def test_public_homepage_loads_gsap_landing_enhancement(self):
        resp = self.client.get("/")

        self.assertContains(resp, 'data-landing-page="public"')
        self.assertContains(resp, "gsap.min.js")
        self.assertContains(resp, "ScrollTrigger.min.js")
        self.assertContains(resp, "Make every game matter.")
        self.assertContains(resp, "broadcast-pick-slip")
        self.assertContains(resp, "/accounts/login/")
        self.assertNotContains(resp, "/accounts/google/login/")
        self.assertNotContains(resp, 'role="navigation"')
        self.assertNotContains(resp, "Today's Games")
        self.assertNotContains(resp, "Season Leaderboard")
        self.assertNotContains(resp, "NFL News")
        self.assertNotContains(resp, "By the Numbers")

    # -- API endpoints (AllowAny / IsAdminOrReadOnly at view level) --

    def test_api_currentseason_returns_200(self):
        resp = self.client.get("/api/currentseason")
        self.assertEqual(resp.status_code, 200)

    def test_api_games_returns_200(self):
        resp = self.client.get("/api/games")
        self.assertEqual(resp.status_code, 200)

    def test_api_weeks_returns_200(self):
        resp = self.client.get("/api/weeks")
        self.assertEqual(resp.status_code, 200)


class PostLoginTenantRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            "tenant-user", email="tenant@example.com", password="pass"
        )
        self.outsider = User.objects.create_user(
            "outsider-user", email="outsider@example.com", password="pass"
        )

    def _family_with_pool(self, name, slug, *, is_default=True):
        family = Family.objects.create(name=name, slug=slug)
        pool = Pool.objects.create(
            family=family,
            name="Main Pickem",
            slug="main",
            season=2526,
            competition="nfl",
            is_default=is_default,
        )
        return family, pool

    def _active_membership(self, user, family, role=FamilyMembership.Role.MEMBER):
        return FamilyMembership.objects.create(
            family=family,
            user=user,
            role=role,
            status=FamilyMembership.Status.ACTIVE,
        )

    def test_anonymous_root_still_renders_public_homepage(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/home.html")
        self.assertTemplateUsed(response, "pickem/home.html")

    def test_public_home_route_stays_public_for_signed_in_users(self):
        family, _pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.user, family)
        self.client.force_login(self.user)

        response = self.client.get(reverse("public_home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/home.html")
        self.assertContains(response, "Make every game matter.")

    def test_authenticated_user_with_no_active_membership_routes_to_onboarding(self):
        self.client.force_login(self.user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse("onboarding"),
            fetch_redirect_response=False,
        )

    def test_onboarding_has_no_global_private_home_data(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("onboarding"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/onboarding.html")
        self.assertContains(response, "Start your family pick'em league")
        self.assertNotContains(response, "Week 1 Points")
        self.assertNotContains(response, "League Accuracy")
        self.assertNotContains(response, "Message Board")

    def test_authenticated_user_with_one_active_membership_routes_to_default_pool(self):
        family, pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.user, family)
        self.client.force_login(self.user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse(
                "family_pool_home",
                kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
            ),
            fetch_redirect_response=False,
        )

    def test_authenticated_nav_logo_goes_public_and_lobby_icon_goes_lobby(self):
        family, pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.user, family)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "family_pool_home",
                kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("public_home")}"')
        self.assertContains(response, 'aria-label="Family Pick\'em Public Home"')
        self.assertContains(
            response,
            f'href="{reverse("family_pool_home", kwargs={"family_slug": family.slug, "pool_slug": pool.slug})}"',
        )
        self.assertContains(response, 'aria-label="Lobby"')
        self.assertContains(response, "fa-layer-group")
        self.assertNotContains(response, "fa-home")

    def test_authenticated_user_with_multiple_active_memberships_routes_to_picker(self):
        smith, _ = self._family_with_pool("Smith Family", "smith-family")
        jones, _ = self._family_with_pool("Jones Family", "jones-family")
        inactive, _ = self._family_with_pool("Inactive Family", "inactive-family")
        self._active_membership(self.user, smith)
        self._active_membership(self.user, jones)
        FamilyMembership.objects.create(
            family=inactive,
            user=self.user,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.INACTIVE,
        )
        self.client.force_login(self.user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse("family_picker"),
            fetch_redirect_response=False,
        )

        picker_response = self.client.get(reverse("family_picker"))
        self.assertEqual(picker_response.status_code, 200)
        self.assertTemplateUsed(picker_response, "pickem/family_picker.html")
        self.assertContains(picker_response, "Smith Family")
        self.assertContains(picker_response, "Jones Family")
        self.assertContains(picker_response, "Add a family")
        self.assertContains(picker_response, "images/logo.png")
        self.assertContains(picker_response, f'href="{reverse("create_family")}"')
        self.assertNotContains(picker_response, "Inactive Family")

    def test_outsider_direct_tenant_entry_is_denied(self):
        family, pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.user, family)
        self.client.force_login(self.outsider)

        response = self.client.get(
            reverse(
                "family_pool_home",
                kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
            )
        )

        self.assertEqual(response.status_code, 404)


class TenantDashboardIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")
        GameWeeks.objects.create(
            weekNumber=1,
            competition="nfl",
            date=timezone.localdate(),
            season=2526,
        )
        cls.game = GamesAndScores.objects.create(
            id=1001,
            slug="ari-atl-2025-week-1",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() + timedelta(days=1),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=1,
            homeTeamSlug="atl",
            homeTeamName="Atlanta Falcons",
            awayTeamId=2,
            awayTeamSlug="ari",
            awayTeamName="Arizona Cardinals",
        )

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            "smith-member", email="smith@example.com", password="pass"
        )
        self.smith_player = User.objects.create_user(
            "smith-player", email="smith-player@example.com", password="pass"
        )
        self.jones_player = User.objects.create_user(
            "jones-player", email="jones-player@example.com", password="pass"
        )
        self.outsider = User.objects.create_user(
            "dashboard-outsider", email="outsider@example.com", password="pass"
        )

    def _family_with_pool(self, name, slug, *, pool_slug="main"):
        family = Family.objects.create(name=name, slug=slug)
        pool = Pool.objects.create(
            family=family,
            name="Main Pickem",
            slug=pool_slug,
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        return family, pool

    def _active_membership(self, user, family, role=FamilyMembership.Role.MEMBER):
        return FamilyMembership.objects.create(
            family=family,
            user=user,
            role=role,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _tenant_url(self, family, pool):
        return reverse(
            "family_pool_home",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _dashboard_game(self, *, game_id, start_date, home="atl", away="ari", status="notstarted", title="Scheduled"):
        return GamesAndScores.objects.create(
            id=game_id,
            slug=f"{away}-{home}-2025-week-1-{game_id}",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.make_aware(
                timezone.datetime(start_date.year, start_date.month, start_date.day, 20, 0)
            ),
            statusType=status,
            statusTitle=title,
            homeTeamId=game_id + 1,
            homeTeamSlug=home,
            homeTeamName=f"{home.upper()} Home",
            homeTeamScore=21 if status == "finished" else None,
            awayTeamId=game_id + 2,
            awayTeamSlug=away,
            awayTeamName=f"{away.upper()} Away",
            awayTeamScore=17 if status == "finished" else None,
        )

    def _seed_dashboard_data(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        jones_family, jones_pool = self._family_with_pool("Jones Family", "jones-family")
        self._active_membership(self.member, smith_family)
        self._active_membership(self.smith_player, smith_family)
        self._active_membership(self.jones_player, jones_family)

        userSeasonPoints.objects.create(
            pool=smith_pool,
            userEmail=self.smith_player.email,
            userID=str(self.smith_player.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=1,
            week_1_winner=True,
            total_points=11,
        )
        userSeasonPoints.objects.create(
            pool=jones_pool,
            userEmail=self.jones_player.email,
            userID=str(self.jones_player.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=1,
            week_1_winner=True,
            total_points=99,
        )
        GamePicks.objects.create(
            id="smith-pick-1",
            pool=smith_pool,
            userEmail="legacy-email@example.com",
            uid=self.member.id,
            userID=str(self.member.id),
            slug=self.game.slug,
            competition=self.game.competition,
            gameWeek=self.game.gameWeek,
            gameyear=self.game.gameyear,
            gameseason=self.game.gameseason,
            pick_game_id=self.game.id,
            pick=self.game.homeTeamSlug,
        )
        GamePicks.objects.create(
            id="jones-pick-1",
            pool=jones_pool,
            userEmail=self.jones_player.email,
            uid=self.jones_player.id,
            userID=str(self.jones_player.id),
            slug=self.game.slug,
            competition=self.game.competition,
            gameWeek=self.game.gameWeek,
            gameyear=self.game.gameyear,
            gameseason=self.game.gameseason,
            pick_game_id=self.game.id,
            pick=self.game.awayTeamSlug,
        )
        MessageBoardPost.objects.create(
            family=smith_family,
            user=self.smith_player,
            title="Smith family update",
            content="Smith only message",
        )
        MessageBoardPost.objects.create(
            family=jones_family,
            user=self.jones_player,
            title="Jones family secret",
            content="Jones only message",
        )
        return smith_family, smith_pool, jones_family, jones_pool

    def test_anonymous_root_keeps_public_home_behavior(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/home.html")

    def test_signed_in_root_redirects_to_default_tenant_dashboard(self):
        family, pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, family)
        self.client.force_login(self.member)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            self._tenant_url(family, pool),
            fetch_redirect_response=False,
        )

    def test_signed_in_root_with_multiple_families_routes_to_picker(self):
        smith, _smith_pool = self._family_with_pool("Smith Family", "smith-family")
        jones, _jones_pool = self._family_with_pool("Jones Family", "jones-family")
        self._active_membership(self.member, smith)
        self._active_membership(self.member, jones)
        self.client.force_login(self.member)

        response = self.client.get("/")

        self.assertRedirects(response, reverse("family_picker"), fetch_redirect_response=False)

    def test_direct_tenant_dashboard_requires_membership(self):
        family, pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, family)
        self.client.force_login(self.outsider)

        response = self.client.get(self._tenant_url(family, pool))

        self.assertEqual(response.status_code, 404)

    def test_dashboard_scopes_private_widgets_to_current_family_and_pool(self):
        smith_family, smith_pool, _jones_family, _jones_pool = self._seed_dashboard_data()
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smith Family")
        self.assertContains(response, "Main Pickem")
        self.assertContains(response, "Smith-player")
        # The message board moved to its own page; the lobby no longer
        # surfaces post content (neither this family's nor another's).
        self.assertNotContains(response, "Smith family update")
        self.assertContains(response, "1 of 1")
        self.assertNotContains(response, "Jones Family")
        self.assertNotContains(response, "Jones-player")

    def test_dashboard_shows_condensed_week_points_for_current_pool_only(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        jones_family, jones_pool = self._family_with_pool("Jones Family", "jones-family")
        self._active_membership(self.member, smith_family)
        self._active_membership(self.smith_player, smith_family)
        self._active_membership(self.jones_player, jones_family)
        userSeasonPoints.objects.create(
            pool=smith_pool,
            userEmail=self.member.email,
            userID=str(self.member.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=2,
            total_points=2,
        )
        userSeasonPoints.objects.create(
            pool=smith_pool,
            userEmail=self.smith_player.email,
            userID=str(self.smith_player.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=4,
            total_points=4,
        )
        userSeasonPoints.objects.create(
            pool=jones_pool,
            userEmail=self.jones_player.email,
            userID=str(self.jones_player.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=99,
            total_points=99,
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url(smith_family, smith_pool))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Week Points")
        self.assertContains(response, "Week 1")
        self.assertContains(response, "Smith-player")
        self.assertContains(response, "4 pts")
        self.assertContains(response, "Smith-member")
        self.assertContains(response, "2 pts")
        self.assertNotContains(response, "Jones-player")
        # The games section heading is status-aware; assert against whatever
        # the view chose for this fixture's game states.
        games_heading = response.context["games_section_heading"]
        self.assertLess(content.index("Week Points"), content.index(games_heading))

    def test_pool_home_is_branded_as_lobby_with_gsap_polish(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        smith_pool.season = 2627
        smith_pool.save(update_fields=["season"])
        self._active_membership(self.member, smith_family)
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smith Family Lobby")
        self.assertContains(response, "Season 2026 - 2027")
        self.assertNotContains(response, "Season 2627")
        self.assertContains(response, "data-lobby-page")
        self.assertContains(response, "lobby-command-hero")
        self.assertContains(response, "data-lobby-action")
        self.assertContains(response, "lobby-action-sheen")
        self.assertContains(response, "lobbyActionHover")
        self.assertContains(response, "resetSheen")
        self.assertContains(response, "gsap.min.js")
        self.assertContains(response, "ScrollTrigger.min.js")

    def test_lobby_standings_hide_positions_until_first_game(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        self._active_membership(self.smith_player, smith_family)
        for user, pts in ((self.member, 0), (self.smith_player, 0)):
            userSeasonPoints.objects.create(
                pool=smith_pool, gameseason=2526, userID=str(user.id),
                userEmail=user.email, total_points=pts,
            )
        self.client.force_login(self.member)

        # No game scored yet: everyone even -> neutral marker, no numbers.
        response = self.client.get(self._tenant_url(smith_family, smith_pool))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["season_has_started"])
        self.assertTrue(all(row["rank"] is None for row in response.context["standings"]))

        # After a game is scored, real numbered positions return.
        GamesAndScores.objects.create(
            id=1099, slug="ne-mia-2025-week-1", competition="nfl", gameWeek="1",
            gameyear="2025", gameseason=2526, startTimestamp=timezone.now(),
            statusType="finished", statusTitle="Final", gameScored=True,
            homeTeamId=3, homeTeamSlug="ne", homeTeamName="New England",
            awayTeamId=4, awayTeamSlug="mia", awayTeamName="Miami",
        )
        response = self.client.get(self._tenant_url(smith_family, smith_pool))
        self.assertTrue(response.context["season_has_started"])
        self.assertEqual([row["rank"] for row in response.context["standings"]], [1, 2])

    def test_lobby_game_cards_show_weekday_and_date(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        GamesAndScores.objects.create(
            id=1098, slug="gb-chi-2025-week-1", competition="nfl", gameWeek="1",
            gameyear="2025", gameseason=2526,
            startTimestamp=timezone.make_aware(timezone.datetime(2025, 9, 7, 13, 0)),
            statusType="notstarted", statusTitle="Scheduled",
            homeTeamId=5, homeTeamSlug="chi", homeTeamName="Chicago Bears",
            awayTeamId=6, awayTeamSlug="gb", awayTeamName="Green Bay Packers",
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        # Sep 7 2025 is a Sunday; the card shows the weekday + date.
        self.assertContains(response, "Sun, Sep 7")

    def test_lobby_links_every_listed_player_to_their_profile(self):
        # Regression guard: any place the lobby lists a player's name must
        # link to that player's profile. Seeds standings, active members, a
        # finished game with picks (pool-picks groups + winner trophy), and a
        # weekly winner, then asserts each player's profile URL is present.
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        self._active_membership(self.smith_player, smith_family)
        finished = GamesAndScores.objects.create(
            id=1097, slug="ne-nyj-2025-week-1", competition="nfl", gameWeek="1",
            gameyear="2025", gameseason=2526,
            startTimestamp=timezone.make_aware(timezone.datetime(2025, 9, 7, 13, 0)),
            statusType="finished", statusTitle="Final", gameScored=True,
            gameWinner="ne", homeTeamId=7, homeTeamSlug="ne", homeTeamName="New England",
            awayTeamId=8, awayTeamSlug="nyj", awayTeamName="New York Jets",
        )
        for user, pts, winner in ((self.member, 5, True), (self.smith_player, 2, False)):
            usp = userSeasonPoints.objects.create(
                pool=smith_pool, gameseason=2526, userID=str(user.id),
                userEmail=user.email, total_points=pts,
            )
            usp.week_1_winner = winner
            usp.save(update_fields=["week_1_winner"])
            GamePicks.objects.create(
                id=f"{smith_pool.id}-{user.id}-{finished.id}", pool=smith_pool,
                userEmail=user.email, uid=user.id, userID=str(user.id),
                slug=finished.slug, competition="nfl", gameWeek="1", gameyear="2025",
                gameseason=2526, pick_game_id=finished.id, pick="ne",
            )
        self.client.force_login(self.member)

        with patch("pickem_homepage.views.timezone.localdate",
                   return_value=date(2025, 9, 7)):
            response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        for user in (self.member, self.smith_player):
            profile_url = reverse("family_pool_user_profile", kwargs={
                "family_slug": smith_family.slug,
                "pool_slug": smith_pool.slug,
                "user_id": user.id,
            })
            self.assertContains(
                response, f'href="{profile_url}"',
                msg_prefix=f"Lobby must link {user.username} to their profile",
            )

    def test_lobby_shows_viewer_avatar_and_favorite_team_logo(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        Teams.objects.create(
            id=90, gameseason=2526, teamNameSlug="ne",
            teamNameName="New England Patriots",
            teamLogo="https://example.test/ne.png",
            color="002244", alternateColor="c60c30",
        )
        UserProfile.objects.update_or_create(
            user=self.member, defaults={"favorite_team": "ne"}
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["viewer_favorite_team"].teamNameSlug, "ne")
        self.assertContains(response, 'data-testid="lobby-favorite-team"')
        self.assertContains(response, "https://example.test/ne.png")

    def test_lobby_renders_espn_news_tiles_and_hides_when_unavailable(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        self.client.force_login(self.member)
        fake_news = [{
            "headline": "Blockbuster trade shakes up the NFC",
            "description": "Details inside.",
            "url": "https://www.espn.com/nfl/story/x",
            "image": "https://a.espncdn.com/photo.jpg",
            "published": "2026-07-09T12:00:00Z",
        }]

        with patch("pickem_homepage.views.get_espn_nfl_news", return_value=fake_news):
            response = self.client.get(self._tenant_url(smith_family, smith_pool))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="espn-news"')
        self.assertContains(response, "Blockbuster trade shakes up the NFC")
        self.assertContains(response, "https://www.espn.com/nfl/story/x")

        # When ESPN is unavailable, the section is hidden (never breaks the lobby).
        with patch("pickem_homepage.views.get_espn_nfl_news", return_value=[]):
            response = self.client.get(self._tenant_url(smith_family, smith_pool))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-testid="espn-news"')

    def test_get_espn_nfl_news_fails_safe_on_error(self):
        from django.core.cache import cache
        from pickem_homepage.views import get_espn_nfl_news
        cache.clear()
        with patch("requests.get", side_effect=Exception("network down")):
            self.assertEqual(get_espn_nfl_news(3), [])
        cache.clear()

    def test_get_espn_nfl_news_survives_cache_backend_outage(self):
        # A cache backend failure must degrade to a miss, not 500 the lobby.
        from pickem_homepage.views import get_espn_nfl_news
        with patch("django.core.cache.cache.get", side_effect=Exception("cache down")), \
             patch("django.core.cache.cache.set", side_effect=Exception("cache down")), \
             patch("requests.get", side_effect=Exception("network down")):
            self.assertEqual(get_espn_nfl_news(3), [])

    def test_dashboard_shows_in_progress_current_week_games(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        GamesAndScores.objects.create(
            id=1002,
            slug="buf-nyj-2025-week-1",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() - timedelta(hours=1),
            statusType="inprogress",
            statusTitle="In Progress",
            homeTeamId=3,
            homeTeamSlug="nyj",
            homeTeamName="New York Jets",
            homeTeamScore=14,
            awayTeamId=4,
            awayTeamSlug="buf",
            awayTeamName="Buffalo Bills",
            awayTeamScore=17,
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live This Week")
        self.assertContains(response, "Buffalo Bills")
        self.assertContains(response, "New York Jets")
        self.assertContains(response, "In Progress")
        self.assertNotContains(response, "Jones family secret")
        self.assertNotContains(response, "2 of 1")

    def test_dashboard_snapshot_weekday_selection_rules(self):
        from pickem_homepage.views import select_dashboard_snapshot_games

        thursday_game = self._dashboard_game(game_id=1010, start_date=date(2025, 9, 4), home="atl", away="ari")
        saturday_game = self._dashboard_game(game_id=1011, start_date=date(2025, 9, 6), home="mia", away="buf")
        sunday_game = self._dashboard_game(game_id=1012, start_date=date(2025, 9, 7), home="nyj", away="ne")
        monday_game = self._dashboard_game(game_id=1013, start_date=date(2025, 9, 8), home="dal", away="phi")
        games = GamesAndScores.objects.filter(id__in=[1010, 1011, 1012, 1013]).order_by("startTimestamp", "id")

        cases = [
            (date(2025, 9, 2), [thursday_game.id, saturday_game.id, sunday_game.id, monday_game.id]),
            (date(2025, 9, 3), [thursday_game.id, saturday_game.id, sunday_game.id, monday_game.id]),
            (date(2025, 9, 4), [thursday_game.id]),
            (date(2025, 9, 5), [thursday_game.id]),
            (date(2025, 9, 6), [saturday_game.id]),
            (date(2025, 9, 7), [sunday_game.id]),
            (date(2025, 9, 8), [monday_game.id]),
        ]
        for today, expected_ids in cases:
            with self.subTest(today=today):
                selected = select_dashboard_snapshot_games(games, today=today)
                self.assertEqual(list(selected.values_list("id", flat=True)), expected_ids)

    def test_dashboard_snapshot_saturday_without_games_falls_back_to_full_week(self):
        from pickem_homepage.views import select_dashboard_snapshot_games

        thursday_game = self._dashboard_game(game_id=1020, start_date=date(2025, 9, 4), home="atl", away="ari")
        sunday_game = self._dashboard_game(game_id=1021, start_date=date(2025, 9, 7), home="nyj", away="ne")
        games = GamesAndScores.objects.filter(id__in=[1020, 1021]).order_by("startTimestamp", "id")

        selected = select_dashboard_snapshot_games(games, today=date(2025, 9, 6))

        self.assertEqual(list(selected.values_list("id", flat=True)), [thursday_game.id, sunday_game.id])

    def test_dashboard_snapshot_cards_show_current_pool_picks_grouped_by_team(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        jones_family, jones_pool = self._family_with_pool("Jones Family", "jones-family")
        self._active_membership(self.member, smith_family)
        self._active_membership(self.smith_player, smith_family)
        self._active_membership(self.jones_player, jones_family)
        game = self._dashboard_game(
            game_id=1030,
            start_date=date(2025, 9, 4),
            home="atl",
            away="ari",
            status="finished",
            title="Final",
        )
        GamePicks.objects.create(
            id=f"{smith_pool.id}-{self.member.id}-{game.id}",
            pool=smith_pool,
            userEmail=self.member.email,
            uid=self.member.id,
            userID=str(self.member.id),
            slug=game.slug,
            competition=game.competition,
            gameWeek=game.gameWeek,
            gameyear=game.gameyear,
            gameseason=game.gameseason,
            pick_game_id=game.id,
            pick=game.homeTeamSlug,
        )
        GamePicks.objects.create(
            id=f"{smith_pool.id}-{self.smith_player.id}-{game.id}",
            pool=smith_pool,
            userEmail=self.smith_player.email,
            uid=self.smith_player.id,
            userID=str(self.smith_player.id),
            slug=game.slug,
            competition=game.competition,
            gameWeek=game.gameWeek,
            gameyear=game.gameyear,
            gameseason=game.gameseason,
            pick_game_id=game.id,
            pick=game.awayTeamSlug,
        )
        GamePicks.objects.create(
            id=f"{jones_pool.id}-{self.jones_player.id}-{game.id}",
            pool=jones_pool,
            userEmail=self.jones_player.email,
            uid=self.jones_player.id,
            userID=str(self.jones_player.id),
            slug=game.slug,
            competition=game.competition,
            gameWeek=game.gameWeek,
            gameyear=game.gameyear,
            gameseason=game.gameseason,
            pick_game_id=game.id,
            pick=game.homeTeamSlug,
        )
        self.client.force_login(self.member)

        with patch("pickem_homepage.views.timezone.localdate", return_value=date(2025, 9, 4)):
            response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ATL Home")
        self.assertContains(response, "Smith-member")
        self.assertContains(response, "ARI Away")
        self.assertContains(response, "Smith-player")
        self.assertNotContains(response, "Jones-player")

    def test_dashboard_snapshot_hides_picks_for_scheduled_games(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        game = self._dashboard_game(
            game_id=1031,
            start_date=date(2025, 9, 4),
            home="atl",
            away="ari",
            status="notstarted",
            title="Scheduled",
        )
        GamePicks.objects.create(
            id=f"{smith_pool.id}-{self.member.id}-{game.id}",
            pool=smith_pool,
            userEmail=self.member.email,
            uid=self.member.id,
            userID=str(self.member.id),
            slug=game.slug,
            competition=game.competition,
            gameWeek=game.gameWeek,
            gameyear=game.gameyear,
            gameseason=game.gameseason,
            pick_game_id=game.id,
            pick=game.homeTeamSlug,
        )
        self.client.force_login(self.member)

        with patch("pickem_homepage.views.timezone.localdate", return_value=date(2025, 9, 4)):
            response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Scheduled")
        self.assertContains(response, "ATL Home")
        self.assertNotContains(response, "Pool picks")

    def test_final_game_shows_winner_trophy_and_highlights_winning_pickers(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        self._active_membership(self.smith_player, smith_family)
        game = self._dashboard_game(
            game_id=1041,
            start_date=date(2025, 9, 4),
            home="atl",
            away="ari",
            status="finished",
            title="Final",
        )
        game.gameWinner = game.homeTeamSlug  # ATL won 21-17
        game.save(update_fields=["gameWinner"])
        for user, pick in ((self.member, game.homeTeamSlug), (self.smith_player, game.awayTeamSlug)):
            GamePicks.objects.create(
                id=f"{smith_pool.id}-{user.id}-{game.id}",
                pool=smith_pool,
                userEmail=user.email,
                uid=user.id,
                userID=str(user.id),
                slug=game.slug,
                competition=game.competition,
                gameWeek=game.gameWeek,
                gameyear=game.gameyear,
                gameseason=game.gameseason,
                pick_game_id=game.id,
                pick=pick,
            )
        self.client.force_login(self.member)

        with patch("pickem_homepage.views.timezone.localdate", return_value=date(2025, 9, 4)):
            response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        markup = response.content.decode()
        # Trophy icon marks the winning team's score line.
        self.assertContains(response, 'title="ATL Home won"')
        # Winning pickers are subtly highlighted; losing group is dimmed.
        self.assertContains(response, 'data-testid="winning-pick-group"')
        winning_section = markup.split('data-testid="winning-pick-group"')[1][:600]
        self.assertIn("Smith-member", winning_section)
        self.assertNotIn("Smith-player", winning_section)

    def test_dashboard_snapshot_cards_show_team_logos(self):
        smith_family, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, smith_family)
        Teams.objects.create(
            id=9101,
            gameseason=2526,
            teamNameSlug="ari",
            teamNameName="ARI Away",
            teamLogo="https://example.test/ari.png",
            color="333333",
            alternateColor="666666",
        )
        Teams.objects.create(
            id=9102,
            gameseason=2526,
            teamNameSlug="atl",
            teamNameName="ATL Home",
            teamLogo="https://example.test/atl.png",
            color="333333",
            alternateColor="666666",
        )
        self._dashboard_game(
            game_id=1032,
            start_date=date(2025, 9, 4),
            home="atl",
            away="ari",
            status="finished",
            title="Final",
        )
        self.client.force_login(self.member)

        with patch("pickem_homepage.views.timezone.localdate", return_value=date(2025, 9, 4)):
            response = self.client.get(self._tenant_url(smith_family, smith_pool))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'src="https://example.test/ari.png"')
        self.assertContains(response, 'alt="ARI Away logo"')
        self.assertContains(response, 'src="https://example.test/atl.png"')
        self.assertContains(response, 'alt="ATL Home logo"')

    def test_dashboard_empty_states_do_not_link_to_global_gameplay_pages(self):
        family, pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, family)
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url(family, pool))

        self.assertEqual(response.status_code, 200)
        dashboard_markup = response.content.decode().split("<main", 1)[1].split("</main>", 1)[0]
        # Quick actions link to the tenant-scoped gameplay pages...
        base = self._tenant_url(family, pool)
        for suffix in ("picks/", "scores/", "standings/", "rules/"):
            self.assertIn(f'href="{base}{suffix}"', dashboard_markup)
        # ...and never to the global, non-tenant gameplay pages.
        self.assertNotIn('href="/picks/"', dashboard_markup)
        self.assertNotIn('href="/scores/"', dashboard_markup)
        self.assertNotIn('href="/standings/"', dashboard_markup)
        self.assertNotIn('href="/rules/"', dashboard_markup)


class TenantPickFlowIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")
        GameWeeks.objects.create(
            weekNumber=1,
            competition="nfl",
            date=timezone.localdate(),
            season=2526,
        )
        cls.game = GamesAndScores.objects.create(
            id=2001,
            slug="ari-atl-2025-week-1",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() + timedelta(days=1),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=1,
            homeTeamSlug="atl",
            homeTeamName="Atlanta Falcons",
            awayTeamId=2,
            awayTeamSlug="ari",
            awayTeamName="Arizona Cardinals",
        )
        cls.other_game = GamesAndScores.objects.create(
            id=2002,
            slug="buf-mia-2025-week-2",
            competition="nfl",
            gameWeek="2",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() + timedelta(days=8),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=3,
            homeTeamSlug="mia",
            homeTeamName="Miami Dolphins",
            awayTeamId=4,
            awayTeamSlug="buf",
            awayTeamName="Buffalo Bills",
        )
        for team_id, slug, name in [
            (1, "atl", "Atlanta Falcons"),
            (2, "ari", "Arizona Cardinals"),
            (3, "mia", "Miami Dolphins"),
            (4, "buf", "Buffalo Bills"),
        ]:
            Teams.objects.create(
                id=team_id,
                gameseason=2526,
                teamNameSlug=slug,
                teamNameName=name,
                color="333333",
                alternateColor="666666",
            )

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            "pick-member", email="pick-member@example.com", password="pass"
        )
        self.other_member = User.objects.create_user(
            "other-pick-member", email="other-pick-member@example.com", password="pass"
        )
        self.outsider = User.objects.create_user(
            "pick-outsider", email="pick-outsider@example.com", password="pass"
        )
        self.smith_family, self.smith_pool = self._family_with_pool(
            "Smith Family", "smith-family"
        )
        self.jones_family, self.jones_pool = self._family_with_pool(
            "Jones Family", "jones-family"
        )
        self._active_membership(self.member, self.smith_family)
        self._active_membership(self.other_member, self.jones_family)

    def _family_with_pool(self, name, slug, *, pool_slug="main"):
        family = Family.objects.create(name=name, slug=slug)
        pool = Pool.objects.create(
            family=family,
            name="Main Pickem",
            slug=pool_slug,
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        return family, pool

    def _active_membership(self, user, family, role=FamilyMembership.Role.MEMBER):
        return FamilyMembership.objects.create(
            family=family,
            user=user,
            role=role,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _tenant_picks_url(self, family=None, pool=None):
        family = family or self.smith_family
        pool = pool or self.smith_pool
        return reverse(
            "family_pool_game_picks",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _tenant_edit_url(self, family=None, pool=None):
        family = family or self.smith_family
        pool = pool or self.smith_pool
        return reverse(
            "family_pool_edit_game_pick",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _pick_payload(self, **overrides):
        payload = {
            "game_id": str(self.game.id),
            "pick": self.game.homeTeamSlug,
            "tieBreakerScore": "",
            "tieBreakerYards": "",
        }
        payload.update(overrides)
        return payload

    def _create_pick(self, *, user=None, pool=None, game=None, pick=None, pick_id=None):
        user = user or self.member
        pool = pool or self.smith_pool
        game = game or self.game
        pick = pick or game.homeTeamSlug
        return GamePicks.objects.create(
            id=pick_id or f"{pool.id}-{user.id}-{game.id}",
            pool=pool,
            userEmail=user.email,
            uid=user.id,
            userID=str(user.id),
            slug=game.slug,
            competition=game.competition,
            gameWeek=game.gameWeek,
            gameyear=game.gameyear,
            gameseason=game.gameseason,
            pick_game_id=game.id,
            pick=pick,
            pick_correct=True,
        )

    def test_tenant_get_picks_reads_only_current_pool_user_state(self):
        self._create_pick(user=self.member, pool=self.smith_pool, pick=self.game.homeTeamSlug)
        self._create_pick(
            user=self.other_member,
            pool=self.jones_pool,
            pick=self.game.awayTeamSlug,
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_picks_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/picks.html")
        self.assertEqual(list(response.context["picks"].values_list("pool_id", flat=True)), [self.smith_pool.id])
        self.assertEqual(list(response.context["picks"].values_list("userEmail", flat=True)), [self.member.email])
        self.assertContains(response, "Submitted Picks")
        # The submitted pick card must actually render (regression: pick id in
        # the template must include the pool prefix to match pick_ids).
        self.assertContains(response, "Your Pick")
        self.assertNotContains(response, self.other_member.email)

    def test_tenant_picks_page_lock_filter_called_once_per_game(self):
        # Regression guard for the picks.html N+1: `is_game_locked_for_pool`
        # was previously called ~8x per game (once per lock gate: LOCKED
        # badge, both team options, both tiebreaker inputs x2, locked
        # message), each re-running its own GamesAndScores/PoolSettings
        # queries. It must now be computed once per game via
        # `{% with locked=... %}` and reused. `is_pick_locked_for_pool` is
        # imported locally inside the filter on every call, so patching the
        # module attribute reliably intercepts every invocation regardless
        # of caller.
        for i in range(5):
            GamesAndScores.objects.create(
                id=2100 + i,
                slug=f"extra-game-{i}",
                competition="nfl",
                gameWeek="1",
                gameyear="2025",
                gameseason=2526,
                startTimestamp=timezone.now() + timedelta(days=1),
                statusType="notstarted",
                statusTitle="Scheduled",
                homeTeamId=1,
                homeTeamSlug="atl",
                homeTeamName="Atlanta Falcons",
                awayTeamId=2,
                awayTeamSlug="ari",
                awayTeamName="Arizona Cardinals",
            )
        self.client.force_login(self.member)

        from pickem import utils as pickem_utils

        with patch(
            "pickem.utils.is_pick_locked_for_pool",
            wraps=pickem_utils.is_pick_locked_for_pool,
        ) as mock_locked:
            response = self.client.get(self._tenant_picks_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["game_list"]), 6)
        # One call per game, not one per lock gate.
        self.assertEqual(mock_locked.call_count, 6)

    def test_tenant_picks_page_includes_compact_polish_hooks(self):
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_picks_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-picks-page")
        self.assertContains(response, "picks-scoreboard-header")
        self.assertContains(response, "picks-progress-strip")
        self.assertContains(response, "picks-games-section")
        self.assertContains(response, "picksCardMotion")
        self.assertContains(response, "gsap.min.js")

    def test_tenant_picks_page_uses_brand_presentation_hooks_for_cards_and_edit_modal(self):
        from pickem_homepage.templatetags.pickem_homepage_extras import (
            team_brand_presentation,
        )

        GamesAndScores.objects.create(
            id=2003,
            slug="ari-atl-2025-week-1-extra",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() + timedelta(days=2),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=5,
            homeTeamSlug="atl",
            homeTeamName="Atlanta Falcons",
            awayTeamId=6,
            awayTeamSlug="ari",
            awayTeamName="Arizona Cardinals",
        )
        Teams.objects.filter(teamNameSlug="ari", gameseason=2526).update(
            teamLogo="https://example.test/ari.png",
            color="224466",
            alternateColor="88AACC",
            logo_contrast_preset=Teams.LogoContrastPreset.WHITE_BURST,
        )
        Teams.objects.filter(teamNameSlug="atl", gameseason=2526).update(
            teamLogo="https://example.test/atl.png",
            color="003594",
            alternateColor="869397",
            logo_contrast_preset=Teams.LogoContrastPreset.REVERSE_GRADIENT,
        )
        self._create_pick(
            user=self.member,
            pool=self.smith_pool,
            game=self.game,
            pick=self.game.awayTeamSlug,
        )
        self.client.force_login(self.member)

        ari_brand = team_brand_presentation(
            Teams.objects.get(teamNameSlug="ari", gameseason=2526)
        )
        atl_brand = team_brand_presentation(
            Teams.objects.get(teamNameSlug="atl", gameseason=2526)
        )

        response = self.client.get(self._tenant_picks_url())

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertGreaterEqual(content.count(ari_brand["background_style"]), 3)
        self.assertGreaterEqual(content.count(atl_brand["background_style"]), 3)
        self.assertGreaterEqual(content.count(ari_brand["logo_style"]), 3)
        self.assertIn(
            f'data-away-background-style="{ari_brand["background_style"]}"',
            content,
        )
        self.assertIn('data-away-show-white-burst="true"', content)
        self.assertIn(
            f'data-away-logo-style="{ari_brand["logo_style"]}"',
            content,
        )
        self.assertIn(
            f'data-home-background-style="{atl_brand["background_style"]}"',
            content,
        )
        self.assertIn('data-home-show-white-burst="false"', content)
        self.assertIn('data-home-logo-style=""', content)
        self.assertIn('const awayBackgroundStyle = this.dataset.awayBackgroundStyle || \'\';', content)
        self.assertIn('const awayShowWhiteBurst = this.dataset.awayShowWhiteBurst === \'true\';', content)
        self.assertIn('const awayLogoStyle = this.dataset.awayLogoStyle || \'\';', content)
        self.assertIn('awayColorBg.style.cssText = awayBackgroundStyle;', content)
        self.assertIn('awayLogoEl.style.cssText = awayLogoStyle;', content)
        self.assertIn("awayBurstEl.classList.toggle('flex', awayShowWhiteBurst);", content)
        self.assertNotIn("includes('jets')", content)
        self.assertNotIn("Apply Jets logo fix", content)

    def test_tenant_picks_page_uses_season_scoped_team_data_for_modal_brand_payload(self):
        Teams.objects.filter(teamNameSlug="ari", gameseason=2526).update(
            teamLogo="https://example.test/ari-season.png",
            color="ABCDEF",
            alternateColor="123456",
            logo_contrast_preset=Teams.LogoContrastPreset.WHITE_BURST,
        )
        Teams.objects.filter(teamNameSlug="atl", gameseason=2526).update(
            teamLogo="https://example.test/atl-season.png",
            color="654321",
            alternateColor="FEDCBA",
            logo_contrast_preset=Teams.LogoContrastPreset.REVERSE_GRADIENT,
        )
        self._create_pick(
            user=self.member,
            pool=self.smith_pool,
            game=self.game,
            pick=self.game.homeTeamSlug,
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_picks_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-away-logo="https://example.test/ari-season.png"')
        self.assertContains(response, 'data-home-logo="https://example.test/atl-season.png"')
        self.assertContains(response, 'alt="Arizona Cardinals logo"')
        self.assertContains(response, 'alt="Atlanta Falcons logo"')
        self.assertContains(response, 'data-away-background-style="background: linear-gradient(135deg, #12345640 0%, #ABCDEF 50%, #ABCDEF 100%);"')
        self.assertContains(response, 'data-home-background-style="background: linear-gradient(135deg, #65432140 0%, #FEDCBA 50%, #FEDCBA 100%);"')

    def test_multi_family_picks_page_shows_submit_to_all_option(self):
        self._active_membership(self.member, self.jones_family)
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_picks_url())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_submit_to_multiple_families"])
        self.assertContains(response, 'data-testid="apply-to-all-families"')
        self.assertContains(response, 'data-testid="multi-family-target-pool"')
        self.assertContains(response, "Submit to all eligible families")
        self.assertContains(response, "saved to 2 family pools")
        self.assertContains(response, "Smith Family")
        self.assertContains(response, "Jones Family")
        self.assertContains(response, 'data-testid="edit-apply-to-all-families"')
        self.assertContains(response, 'data-testid="edit-multi-family-target-pool"')
        self.assertContains(response, "Apply edits to all eligible families")
        self.assertContains(response, "syncEditFamilyTargets")
        self.assertContains(response, "Choose at least one family")

    def test_tenant_post_creates_server_derived_pick_and_ignores_forged_fields(self):
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(
                id="attacker-controlled-id",
                userEmail=self.other_member.email,
                userID=str(self.other_member.id),
                uid=str(self.other_member.id),
                pool=str(self.jones_pool.id),
                pool_id=str(self.jones_pool.id),
                family=str(self.jones_family.id),
                family_id=str(self.jones_family.id),
                slug=self.other_game.slug,
                competition="nfl-preseason",
                gameWeek=self.other_game.gameWeek,
                gameyear=self.other_game.gameyear,
                gameseason=str(self.other_game.gameseason),
                pick_game_id=str(self.other_game.id),
                pick_correct="True",
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        pick = GamePicks.objects.get(pool=self.smith_pool, userEmail=self.member.email)
        self.assertEqual(pick.id, f"{self.smith_pool.id}-{self.member.id}-{self.game.id}")
        self.assertEqual(pick.userEmail, self.member.email)
        self.assertEqual(pick.userID, str(self.member.id))
        self.assertEqual(pick.uid, self.member.id)
        self.assertEqual(pick.pool, self.smith_pool)
        self.assertEqual(pick.slug, self.game.slug)
        self.assertEqual(pick.competition, self.game.competition)
        self.assertEqual(pick.gameWeek, self.game.gameWeek)
        self.assertEqual(pick.gameyear, self.game.gameyear)
        self.assertEqual(pick.gameseason, self.game.gameseason)
        self.assertEqual(pick.pick_game_id, self.game.id)
        self.assertEqual(pick.pick, self.game.homeTeamSlug)
        self.assertFalse(pick.pick_correct)
        self.assertFalse(GamePicks.objects.filter(pool=self.jones_pool, userEmail=self.other_member.email).exists())

    def test_multi_family_submit_fans_out_to_current_user_active_pools(self):
        self._active_membership(self.member, self.jones_family)
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(apply_to_all_families="1"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved_count"], 2)
        smith_pick = GamePicks.objects.get(pool=self.smith_pool, userID=str(self.member.id))
        jones_pick = GamePicks.objects.get(pool=self.jones_pool, userID=str(self.member.id))
        self.assertEqual(smith_pick.pick, self.game.homeTeamSlug)
        self.assertEqual(jones_pick.pick, self.game.homeTeamSlug)
        self.assertFalse(GamePicks.objects.filter(pool=self.jones_pool, userID=str(self.other_member.id)).exists())

    def test_multi_family_submit_respects_selected_eligible_target_pools(self):
        self._active_membership(self.member, self.jones_family)
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(
                apply_to_all_families="1",
                target_pool_ids=[str(self.smith_pool.id)],
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved_pool_ids"], [self.smith_pool.id])
        self.assertTrue(GamePicks.objects.filter(pool=self.smith_pool, userID=str(self.member.id)).exists())
        self.assertFalse(GamePicks.objects.filter(pool=self.jones_pool, userID=str(self.member.id)).exists())

    def test_multi_family_submit_ignores_forged_target_pool_ids(self):
        outsider_family, outsider_pool = self._family_with_pool("Outsider Family", "outsider-family")
        self._active_membership(self.outsider, outsider_family)
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(
                apply_to_all_families="1",
                target_pool_ids=[str(self.smith_pool.id), str(outsider_pool.id)],
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved_pool_ids"], [self.smith_pool.id])
        self.assertTrue(GamePicks.objects.filter(pool=self.smith_pool, userID=str(self.member.id)).exists())
        self.assertFalse(GamePicks.objects.filter(pool=outsider_pool, userID=str(self.member.id)).exists())

    def test_family_specific_edit_after_fanout_only_updates_current_pool(self):
        self._active_membership(self.member, self.jones_family)
        smith_pick = self._create_pick(user=self.member, pool=self.smith_pool, pick=self.game.homeTeamSlug)
        jones_pick = self._create_pick(user=self.member, pool=self.jones_pool, pick=self.game.homeTeamSlug)
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_edit_url(),
            {
                "pick_id": smith_pick.id,
                "pick": self.game.awayTeamSlug,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        smith_pick.refresh_from_db()
        jones_pick.refresh_from_db()
        self.assertEqual(smith_pick.pick, self.game.awayTeamSlug)
        self.assertEqual(jones_pick.pick, self.game.homeTeamSlug)

    def test_multi_family_edit_fans_out_to_current_user_active_pools_when_requested(self):
        self._active_membership(self.member, self.jones_family)
        smith_pick = self._create_pick(user=self.member, pool=self.smith_pool, pick=self.game.homeTeamSlug)
        jones_pick = self._create_pick(user=self.member, pool=self.jones_pool, pick=self.game.homeTeamSlug)
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_edit_url(),
            {
                "pick_id": smith_pick.id,
                "pick": self.game.awayTeamSlug,
                "apply_to_all_families": "1",
                "target_pool_ids": [str(self.smith_pool.id), str(self.jones_pool.id)],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved_count"], 2)
        smith_pick.refresh_from_db()
        jones_pick.refresh_from_db()
        self.assertEqual(smith_pick.pick, self.game.awayTeamSlug)
        self.assertEqual(jones_pick.pick, self.game.awayTeamSlug)

    def test_multi_family_edit_respects_selected_eligible_target_pools(self):
        self._active_membership(self.member, self.jones_family)
        smith_pick = self._create_pick(user=self.member, pool=self.smith_pool, pick=self.game.homeTeamSlug)
        jones_pick = self._create_pick(user=self.member, pool=self.jones_pool, pick=self.game.homeTeamSlug)
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_edit_url(),
            {
                "pick_id": smith_pick.id,
                "pick": self.game.awayTeamSlug,
                "apply_to_all_families": "1",
                "target_pool_ids": [str(self.smith_pool.id)],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved_pool_ids"], [self.smith_pool.id])
        smith_pick.refresh_from_db()
        jones_pick.refresh_from_db()
        self.assertEqual(smith_pick.pick, self.game.awayTeamSlug)
        self.assertEqual(jones_pick.pick, self.game.homeTeamSlug)

    def test_multi_family_edit_requires_at_least_one_selected_target_pool(self):
        self._active_membership(self.member, self.jones_family)
        smith_pick = self._create_pick(user=self.member, pool=self.smith_pool, pick=self.game.homeTeamSlug)
        jones_pick = self._create_pick(user=self.member, pool=self.jones_pool, pick=self.game.homeTeamSlug)
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_edit_url(),
            {
                "pick_id": smith_pick.id,
                "pick": self.game.awayTeamSlug,
                "apply_to_all_families": "1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("at least one family", response.json()["message"])
        smith_pick.refresh_from_db()
        jones_pick.refresh_from_db()
        self.assertEqual(smith_pick.pick, self.game.homeTeamSlug)
        self.assertEqual(jones_pick.pick, self.game.homeTeamSlug)

    def test_multi_family_edit_ignores_forged_target_pool_ids(self):
        outsider_family, outsider_pool = self._family_with_pool("Outsider Family", "outsider-family")
        self._active_membership(self.outsider, outsider_family)
        smith_pick = self._create_pick(user=self.member, pool=self.smith_pool, pick=self.game.homeTeamSlug)
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_edit_url(),
            {
                "pick_id": smith_pick.id,
                "pick": self.game.awayTeamSlug,
                "apply_to_all_families": "1",
                "target_pool_ids": [str(self.smith_pool.id), str(outsider_pool.id)],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved_pool_ids"], [self.smith_pool.id])
        self.assertFalse(GamePicks.objects.filter(pool=outsider_pool, userID=str(self.member.id)).exists())

    def test_superuser_without_real_membership_cannot_open_or_submit_picks(self):
        site_admin = User.objects.create_user(
            "site-admin-picks",
            email="site-admin-picks@example.com",
            password="pass",
            is_superuser=True,
        )
        self.client.force_login(site_admin)

        page_response = self.client.get(self._tenant_picks_url())
        post_response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(page_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)

    def test_tenant_post_rejects_game_outside_current_week_context(self):
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(game_id=str(self.other_game.id), pick=self.other_game.homeTeamSlug),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(GamePicks.objects.filter(pool=self.smith_pool).exists())

    def test_tenant_ajax_edit_uses_current_pool_and_user_lookup(self):
        pick = self._create_pick(
            user=self.member,
            pool=self.smith_pool,
            pick=self.game.homeTeamSlug,
        )
        jones_pick = self._create_pick(
            user=self.other_member,
            pool=self.jones_pool,
            pick=self.game.awayTeamSlug,
        )
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_edit_url(),
            {
                "pick_id": pick.id,
                "pick": self.game.awayTeamSlug,
                "pool": self.jones_pool.id,
                "userEmail": self.other_member.email,
                "userID": self.other_member.id,
                "uid": self.other_member.id,
                "game_id": self.other_game.id,
                "pick_game_id": self.other_game.id,
                "pick_correct": "True",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        pick.refresh_from_db()
        jones_pick.refresh_from_db()
        self.assertEqual(pick.pick, self.game.awayTeamSlug)
        self.assertEqual(pick.pool, self.smith_pool)
        self.assertEqual(pick.userEmail, self.member.email)
        self.assertEqual(pick.pick_game_id, self.game.id)
        self.assertFalse(pick.pick_correct)
        self.assertEqual(jones_pick.pick, self.game.awayTeamSlug)

    def test_cross_pool_pick_id_edit_is_denied_before_lock_or_team_validation(self):
        jones_pick = self._create_pick(
            user=self.other_member,
            pool=self.jones_pool,
            pick=self.game.awayTeamSlug,
        )
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_edit_url(),
            {"pick_id": jones_pick.id, "pick": self.game.homeTeamSlug},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 404)
        jones_pick.refresh_from_db()
        self.assertEqual(jones_pick.pick, self.game.awayTeamSlug)

    def test_outsider_cannot_get_or_post_tenant_picks_by_url_slug_tampering(self):
        self.client.force_login(self.outsider)

        get_response = self.client.get(self._tenant_picks_url())
        post_response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.assertFalse(GamePicks.objects.exists())

    def test_legacy_signed_in_pick_routes_redirect_without_mutating_global_picks(self):
        self.client.force_login(self.member)

        get_response = self.client.get(reverse("game_picks"))
        post_response = self.client.post(
            reverse("game_picks"),
            self._pick_payload(
                id="legacy-forged-id",
                userEmail=self.other_member.email,
                uid=self.other_member.id,
                userID=self.other_member.id,
                pick_correct="True",
            ),
        )
        edit_response = self.client.post(
            reverse("edit_game_pick"),
            {"pick_id": "legacy-forged-id", "pick": self.game.awayTeamSlug},
        )

        self.assertRedirects(
            get_response,
            self._tenant_picks_url(),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            post_response,
            self._tenant_picks_url(),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            edit_response,
            self._tenant_picks_url(),
            fetch_redirect_response=False,
        )
        self.assertFalse(GamePicks.objects.exists())

    def test_tiebreaker_required_when_pool_allows_tiebreakers(self):
        self.game.tieBreakerGame = True
        self.game.save(update_fields=["tieBreakerGame"])
        self.client.force_login(self.member)

        response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(),  # no tiebreaker values
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Tiebreaker", response.json()["message"])
        self.assertFalse(GamePicks.objects.exists())

    def test_tiebreaker_not_required_when_pool_disables_tiebreakers(self):
        self.game.tieBreakerGame = True
        self.game.save(update_fields=["tieBreakerGame"])
        PoolSettings.objects.create(pool=self.smith_pool, allow_tiebreaker=False)
        self.client.force_login(self.member)

        # The picks page stops rendering (and demanding) the tiebreaker inputs.
        get_response = self.client.get(self._tenant_picks_url())
        self.assertFalse(get_response.context["pool_allow_tiebreaker"])
        self.assertNotContains(get_response, "Tiebreakers Required")
        self.assertNotContains(get_response, f'id="tiebreaker1-{self.game.id}"')
        self.assertNotContains(get_response, f'id="tiebreaker2-{self.game.id}"')

        response = self.client.post(
            self._tenant_picks_url(),
            self._pick_payload(),  # no tiebreaker values
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(
            GamePicks.objects.filter(
                pool=self.smith_pool, userID=str(self.member.id), pick_game_id=self.game.id
            ).exists()
        )


class HasRealFamilyMembershipTests(TestCase):
    """Regression guard for the picks-page 404 (#61 gate + superuser synthetic
    membership): a superuser is handed a synthetic, never-saved owner membership
    (no pk) for god-mode oversight, even in families where they hold a real row.
    has_real_family_membership must still recognise them as a real participant
    there, or submitting picks 404s for a superuser in their own family."""

    def setUp(self):
        self.family = Family.objects.create(name='Daghouse', slug='daghouse')
        self.superuser = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.member = User.objects.create_user(
            username='mem', email='mem@example.com', password='pw',
        )

    def _synthetic(self, user):
        # Mirrors authz._superuser_membership: constructed, never saved -> pk None.
        return FamilyMembership(
            family=self.family, user=user,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.ACTIVE,
        )

    def test_saved_membership_is_real(self):
        from pickem_homepage.views import has_real_family_membership

        membership = FamilyMembership.objects.create(
            family=self.family, user=self.member,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )
        self.assertTrue(has_real_family_membership(membership))

    def test_synthetic_membership_counts_when_a_real_active_row_exists(self):
        from pickem_homepage.views import has_real_family_membership

        FamilyMembership.objects.create(
            family=self.family, user=self.superuser,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.ACTIVE,
        )
        synthetic = self._synthetic(self.superuser)
        self.assertIsNone(synthetic.pk)
        self.assertTrue(has_real_family_membership(synthetic))

    def test_synthetic_membership_is_not_real_without_a_row(self):
        from pickem_homepage.views import has_real_family_membership

        self.assertFalse(has_real_family_membership(self._synthetic(self.superuser)))

    def test_inactive_real_row_does_not_count_for_synthetic(self):
        from pickem_homepage.views import has_real_family_membership

        FamilyMembership.objects.create(
            family=self.family, user=self.superuser,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.INACTIVE,
        )
        self.assertFalse(has_real_family_membership(self._synthetic(self.superuser)))


@override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
class BrandedErrorPageTests(TestCase):
    """With DEBUG off (production), an unknown URL should render the branded 404
    template, not Django's plain 'Not Found' page."""

    def test_unknown_url_renders_branded_404(self):
        # Anonymous users get login-redirected by RequireLoginForInternalPages
        # before a 404 can happen, so exercise the 404 as a signed-in user
        # (the reported scenario).
        user = User.objects.create_user(
            username='visitor', email='visitor@example.com', password='pw',
        )
        self.client.force_login(user)
        response = self.client.get('/definitely-not-a-real-page-xyz/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'that play didn', status_code=404)
        self.assertContains(response, 'Back to Home', status_code=404)
        self.assertTemplateUsed(response, '404.html')


class TenantScoresStandingsRulesIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")
        GameWeeks.objects.create(
            weekNumber=1,
            competition="nfl",
            date=timezone.localdate(),
            season=2526,
        )
        GameWeeks.objects.create(
            weekNumber=2,
            competition="nfl",
            date=timezone.localdate() + timedelta(days=7),
            season=2526,
        )
        cls.week_one_game = GamesAndScores.objects.create(
            id=3001,
            slug="ari-atl-2025-week-1",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() - timedelta(hours=1),
            statusType="inprogress",
            statusTitle="In Progress",
            homeTeamId=1,
            homeTeamSlug="atl",
            homeTeamName="Atlanta Falcons",
            awayTeamId=2,
            awayTeamSlug="ari",
            awayTeamName="Arizona Cardinals",
        )
        cls.week_two_game = GamesAndScores.objects.create(
            id=3002,
            slug="buf-mia-2025-week-2",
            competition="nfl",
            gameWeek="2",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() + timedelta(days=7),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=3,
            homeTeamSlug="mia",
            homeTeamName="Miami Dolphins",
            awayTeamId=4,
            awayTeamSlug="buf",
            awayTeamName="Buffalo Bills",
        )
        for team_id, slug, name in [
            (1, "atl", "Atlanta Falcons"),
            (2, "ari", "Arizona Cardinals"),
            (3, "mia", "Miami Dolphins"),
            (4, "buf", "Buffalo Bills"),
        ]:
            Teams.objects.create(
                id=team_id,
                gameseason=2526,
                teamNameSlug=slug,
                teamNameName=name,
                color="333333",
                alternateColor="666666",
            )

    def setUp(self):
        self.client = Client()
        self.smith_member = User.objects.create_user(
            "smith-score-member", email="smith-score@example.com", password="pass"
        )
        self.smith_player = User.objects.create_user(
            "smith-score-player", email="smith-player@example.com", password="pass"
        )
        self.jones_player = User.objects.create_user(
            "jones-score-player", email="jones-player@example.com", password="pass"
        )
        self.outsider = User.objects.create_user(
            "scores-outsider", email="scores-outsider@example.com", password="pass"
        )
        self.smith_family, self.smith_pool = self._family_with_pool(
            "Smith Family", "smith-family"
        )
        self.jones_family, self.jones_pool = self._family_with_pool(
            "Jones Family", "jones-family"
        )
        self._active_membership(self.smith_member, self.smith_family)
        self._active_membership(self.smith_player, self.smith_family)
        self._active_membership(self.jones_player, self.jones_family)
        PoolSettings.objects.create(
            pool=self.smith_pool,
            picks_lock_mode=PoolSettings.PicksLockMode.SUNDAY_1PM,
            allow_tiebreaker=True,
        )
        PoolSettings.objects.create(
            pool=self.jones_pool,
            picks_lock_mode=PoolSettings.PicksLockMode.KICKOFF,
            allow_tiebreaker=False,
        )

    def _family_with_pool(self, name, slug, *, pool_slug="main"):
        family = Family.objects.create(name=name, slug=slug)
        pool = Pool.objects.create(
            family=family,
            name="Main Pickem",
            slug=pool_slug,
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        return family, pool

    def _active_membership(self, user, family, role=FamilyMembership.Role.MEMBER):
        return FamilyMembership.objects.create(
            family=family,
            user=user,
            role=role,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _tenant_url(self, route_name, family=None, pool=None, **kwargs):
        family = family or self.smith_family
        pool = pool or self.smith_pool
        route_kwargs = {"family_slug": family.slug, "pool_slug": pool.slug}
        route_kwargs.update(kwargs)
        return reverse(route_name, kwargs=route_kwargs)

    def _seed_private_pool_data(self):
        GamePicks.objects.create(
            id=f"{self.smith_pool.id}-{self.smith_player.id}-{self.week_one_game.id}",
            pool=self.smith_pool,
            userEmail=self.smith_player.email,
            uid=self.smith_player.id,
            userID=str(self.smith_player.id),
            slug=self.week_one_game.slug,
            competition=self.week_one_game.competition,
            gameWeek=self.week_one_game.gameWeek,
            gameyear=self.week_one_game.gameyear,
            gameseason=self.week_one_game.gameseason,
            pick_game_id=self.week_one_game.id,
            pick=self.week_one_game.homeTeamSlug,
            pick_correct=True,
        )
        GamePicks.objects.create(
            id=f"{self.jones_pool.id}-{self.jones_player.id}-{self.week_one_game.id}",
            pool=self.jones_pool,
            userEmail=self.jones_player.email,
            uid=self.jones_player.id,
            userID=str(self.jones_player.id),
            slug=self.week_one_game.slug,
            competition=self.week_one_game.competition,
            gameWeek=self.week_one_game.gameWeek,
            gameyear=self.week_one_game.gameyear,
            gameseason=self.week_one_game.gameseason,
            pick_game_id=self.week_one_game.id,
            pick=self.week_one_game.awayTeamSlug,
            pick_correct=True,
        )
        userSeasonPoints.objects.create(
            pool=self.smith_pool,
            userEmail=self.smith_player.email,
            userID=str(self.smith_player.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=1,
            week_1_winner=True,
            total_points=11,
            year_winner=True,
        )
        userSeasonPoints.objects.create(
            pool=self.jones_pool,
            userEmail=self.jones_player.email,
            userID=str(self.jones_player.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=1,
            week_1_winner=True,
            total_points=99,
            year_winner=True,
        )

    def test_tenant_scores_current_week_keeps_global_games_but_scopes_private_overlays(self):
        self._seed_private_pool_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/scores.html")
        self.assertContains(response, "Atlanta Falcons")
        self.assertContains(response, "Arizona Cardinals")
        self.assertContains(response, "smith-score-player")
        self.assertNotContains(response, "jones-score-player")
        self.assertEqual(response.context["picks"].count(), 1)
        self.assertEqual(response.context["picks"].first().pool, self.smith_pool)
        self.assertEqual(list(response.context["week_winner"]), list(userSeasonPoints.objects.filter(pool=self.smith_pool)))

    def test_tenant_scores_page_includes_gsap_polish_hooks(self):
        self._seed_private_pool_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-scores-page")
        self.assertContains(response, "scores-scoreboard-header")
        self.assertContains(response, "scores-filter-bar")
        self.assertContains(response, "scores-compact-week-winner")
        self.assertContains(response, "scores-compact-week-points")
        self.assertContains(response, "scores-kickoff-group")
        self.assertContains(response, "data-scores-filter")
        self.assertContains(response, "scores-filter-sheen")
        self.assertContains(response, "scoresFilterMotion")
        self.assertContains(response, "scoresLivePulse")
        self.assertContains(response, "gsap.min.js")
        self.assertContains(response, "ScrollTrigger.min.js")

    def test_tenant_scores_current_user_stats_use_stable_user_identity(self):
        self.week_one_game.statusType = "finished"
        self.week_one_game.statusTitle = "Final"
        self.week_one_game.save(update_fields=["statusType", "statusTitle"])
        GamePicks.objects.create(
            id=f"{self.smith_pool.id}-{self.smith_member.id}-{self.week_one_game.id}",
            pool=self.smith_pool,
            userEmail="old-email@example.com",
            uid=self.smith_member.id,
            userID=str(self.smith_member.id),
            slug=self.week_one_game.slug,
            competition=self.week_one_game.competition,
            gameWeek=self.week_one_game.gameWeek,
            gameyear=self.week_one_game.gameyear,
            gameseason=self.week_one_game.gameseason,
            pick_game_id=self.week_one_game.id,
            pick=self.week_one_game.homeTeamSlug,
            pick_correct=True,
        )
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user_weekly_stats"]["total_graded_picks"], 1)
        self.assertEqual(response.context["user_weekly_stats"]["correct_picks"], 1)

    def test_scores_missing_picks_excludes_members_who_already_picked(self):
        # smith_member picks; smith_player does not. Regression: the missing
        # list matched picks by a bare "{user}-{game}" id that never lined up
        # with the pool-scoped pick id, so it flagged everyone (incl. pickers).
        GamePicks.objects.create(
            id=f"{self.smith_pool.id}-{self.smith_member.id}-{self.week_two_game.id}",
            pool=self.smith_pool,
            userEmail=self.smith_member.email,
            uid=self.smith_member.id,
            userID=str(self.smith_member.id),
            slug=self.week_two_game.slug,
            competition=self.week_two_game.competition,
            gameWeek=self.week_two_game.gameWeek,
            gameyear=self.week_two_game.gameyear,
            gameseason=self.week_two_game.gameseason,
            pick_game_id=self.week_two_game.id,
            pick=self.week_two_game.awayTeamSlug,
            pick_correct=False,
        )
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url(
                "family_pool_scores_long", competition=1, gameseason=2526, week=2,
            )
        )

        self.assertEqual(response.status_code, 200)
        picked_keys = response.context["picked_keys"]
        # The picker is recorded, the non-picker is not.
        self.assertIn(f"{self.smith_member.id}-{self.week_two_game.id}", picked_keys)
        self.assertNotIn(f"{self.smith_player.id}-{self.week_two_game.id}", picked_keys)
        # The missing-picks list contains the non-picker but not the picker.
        self.assertContains(response, "smith-score-player - No Pick")
        self.assertNotContains(response, "smith-score-member - No Pick")

    def test_tenant_scores_selected_week_uses_global_week_facts_with_pool_only_overlays(self):
        self._seed_private_pool_data()
        GamePicks.objects.create(
            id=f"{self.smith_pool.id}-{self.smith_player.id}-{self.week_two_game.id}",
            pool=self.smith_pool,
            userEmail=self.smith_player.email,
            uid=self.smith_player.id,
            userID=str(self.smith_player.id),
            slug=self.week_two_game.slug,
            competition=self.week_two_game.competition,
            gameWeek=self.week_two_game.gameWeek,
            gameyear=self.week_two_game.gameyear,
            gameseason=self.week_two_game.gameseason,
            pick_game_id=self.week_two_game.id,
            pick=self.week_two_game.homeTeamSlug,
            pick_correct=False,
        )
        GamePicks.objects.create(
            id=f"{self.jones_pool.id}-{self.jones_player.id}-{self.week_two_game.id}",
            pool=self.jones_pool,
            userEmail=self.jones_player.email,
            uid=self.jones_player.id,
            userID=str(self.jones_player.id),
            slug=self.week_two_game.slug,
            competition=self.week_two_game.competition,
            gameWeek=self.week_two_game.gameWeek,
            gameyear=self.week_two_game.gameyear,
            gameseason=self.week_two_game.gameseason,
            pick_game_id=self.week_two_game.id,
            pick=self.week_two_game.awayTeamSlug,
            pick_correct=False,
        )
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url(
                "family_pool_scores_long",
                competition=1,
                gameseason=2526,
                week=2,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Miami Dolphins")
        self.assertContains(response, "Buffalo Bills")
        self.assertContains(response, "smith-score-player")
        self.assertNotContains(response, "jones-score-player")
        self.assertEqual(list(response.context["picks"].values_list("pool_id", flat=True)), [self.smith_pool.id])
        self.assertEqual(list(response.context["players_names"]), [self.smith_player.id])
        self.assertNotIn(self.jones_player.id, list(response.context["players_ids"]))

    def test_tenant_standings_and_weekly_winners_are_current_pool_only(self):
        self._seed_private_pool_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_standings"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/standings.html")
        self.assertContains(response, "smith-score-player")
        self.assertNotContains(response, "jones-score-player")
        self.assertEqual(list(response.context["player_points"]), list(userSeasonPoints.objects.filter(pool=self.smith_pool)))
        self.assertEqual(response.context["weekly_winners"][1][0].pool, self.smith_pool)

    def test_standings_season_switch_reads_the_family_pool_for_that_season(self):
        # Each season is a separate pool; selecting a past season in the
        # dropdown must surface that season's sibling-pool data (the bug was an
        # empty leaderboard because the current pool was filtered by a season it
        # never held).
        self._seed_private_pool_data()  # current pool (season 2526)
        prior_pool = Pool.objects.create(
            family=self.smith_family,
            name="2024 Pickem",
            slug="2425-pickem",
            season=2425,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=False,
        )
        userSeasonPoints.objects.create(
            pool=prior_pool,
            userEmail=self.smith_player.email,
            userID=str(self.smith_player.id),
            gameseason=2425,
            gameyear="2024",
            week_1_points=7,
            week_1_winner=True,
            total_points=42,
            year_winner=True,
        )
        self.client.force_login(self.smith_member)

        # Default view still shows the current season only.
        current = self.client.get(self._tenant_url("family_pool_standings"))
        self.assertEqual(
            list(current.context["player_points"]),
            list(userSeasonPoints.objects.filter(pool=self.smith_pool)),
        )
        # The dropdown offers the prior season the family actually played.
        self.assertIn("2024-2025", [s["display"] for s in current.context["all_seasons"]])

        # Switching to the prior season reads the sibling pool's data.
        prior = self.client.get(
            self._tenant_url("family_pool_standings"), {"season": "2425"}
        )
        self.assertEqual(prior.status_code, 200)
        self.assertEqual(
            list(prior.context["player_points"]),
            list(userSeasonPoints.objects.filter(pool=prior_pool)),
        )
        self.assertEqual(prior.context["season_winner"].pool, prior_pool)
        self.assertEqual(prior.context["weekly_winners"][1][0].pool, prior_pool)
        self.assertContains(prior, "42")

    def test_tenant_standings_page_includes_compact_gsap_polish_hooks(self):
        self._seed_private_pool_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_standings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-standings-page")
        self.assertContains(response, "standings-scoreboard-header")
        self.assertContains(response, "standings-compact-leaderboard")
        self.assertContains(response, "standings-compact-weekly-champions")
        self.assertContains(response, "standings-compact-breakdown")
        self.assertContains(response, "standingsRowMotion")
        self.assertContains(response, "gsap.min.js")
        self.assertContains(response, "ScrollTrigger.min.js")

    def test_standings_hide_numbered_positions_until_a_game_is_scored(self):
        # Everyone starts even, so the full standings page must show a neutral
        # marker for every player until the first game of the season is scored.
        self._seed_private_pool_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_standings"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["season_has_started"])
        self.assertContains(response, "Standings begin after the first game")

        # Score a game and the numbered leaderboard returns.
        self.week_one_game.gameScored = True
        self.week_one_game.save(update_fields=["gameScored"])

        response = self.client.get(self._tenant_url("family_pool_standings"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["season_has_started"])
        self.assertNotContains(response, "Standings begin after the first game")

    def test_tenant_rules_display_current_context_settings_and_no_editing_form(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_rules"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/rules.html")
        self.assertContains(response, "Smith Family")
        self.assertContains(response, "Main Pickem")
        self.assertContains(response, "Locking: Weekly cutoff — Sunday 1PM ET")
        self.assertContains(response, "Tiebreakers: On")
        # No settings-editing form for non-admins. (The base nav includes a
        # logout POST form, so check for editing controls specifically.)
        self.assertNotContains(response, 'name="picks_lock_mode"')
        self.assertNotContains(response, "Save settings")
        self.assertEqual(response.context["pool_settings"], self.smith_pool.settings)

    def test_tenant_rules_page_includes_compact_polish_hooks(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_rules"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-rules-page")
        self.assertContains(response, "rules-scoreboard-header")
        self.assertContains(response, "rules-compact-card")
        self.assertContains(response, "rulesCardMotion")
        self.assertContains(response, "gsap.min.js")

    def test_legacy_signed_in_scores_standings_and_rules_redirect_before_private_rendering(self):
        self.client.force_login(self.smith_member)

        self.assertRedirects(
            self.client.get(reverse("scores")),
            self._tenant_url("family_pool_scores"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(reverse("scores_long", kwargs={"competition": 1, "gameseason": 2526, "week": 2})),
            self._tenant_url(
                "family_pool_scores_long",
                competition=1,
                gameseason=2526,
                week=2,
            ),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(reverse("standings")),
            self._tenant_url("family_pool_standings"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(reverse("rules")),
            self._tenant_url("family_pool_rules"),
            fetch_redirect_response=False,
        )

    def test_outsider_direct_tenant_scores_standings_and_rules_are_denied(self):
        self.client.force_login(self.outsider)

        self.assertEqual(self.client.get(self._tenant_url("family_pool_scores")).status_code, 404)
        self.assertEqual(self.client.get(self._tenant_url("family_pool_standings")).status_code, 404)
        self.assertEqual(self.client.get(self._tenant_url("family_pool_rules")).status_code, 404)

    def test_query_params_do_not_switch_standings_pool_or_rules_context(self):
        self._seed_private_pool_data()
        self.client.force_login(self.smith_member)

        standings_response = self.client.get(
            self._tenant_url("family_pool_standings"),
            {"season": "2526", "pool": self.jones_pool.id, "family": self.jones_family.slug},
        )
        rules_response = self.client.get(
            self._tenant_url("family_pool_rules"),
            {"pool": self.jones_pool.id, "family": self.jones_family.slug},
        )

        self.assertContains(standings_response, "smith-score-player")
        self.assertNotContains(standings_response, "jones-score-player")
        self.assertContains(rules_response, "Locking: Weekly cutoff — Sunday 1PM ET")
        self.assertContains(rules_response, "Tiebreakers: On")
        self.assertNotContains(rules_response, "Locking: Lock each game at kickoff")
        self.assertNotContains(rules_response, "Tiebreakers: Off")

    def test_final_slug_query_and_overlay_tampering_do_not_cross_family_scores_standings_or_rules(self):
        self._seed_private_pool_data()
        self.client.force_login(self.smith_member)

        wrong_slug_response = self.client.get(
            self._tenant_url(
                "family_pool_scores",
                family=self.jones_family,
                pool=self.jones_pool,
            )
        )
        scores_response = self.client.get(
            self._tenant_url("family_pool_scores"),
            {"family_slug": self.jones_family.slug, "pool_slug": self.jones_pool.slug, "pool": self.jones_pool.id},
        )
        standings_response = self.client.get(
            self._tenant_url("family_pool_standings"),
            {"family": self.jones_family.slug, "pool": self.jones_pool.id, "season": "2526"},
        )
        rules_response = self.client.get(
            self._tenant_url("family_pool_rules"),
            {"family": self.jones_family.slug, "pool": self.jones_pool.id},
        )

        self.assertEqual(wrong_slug_response.status_code, 404)
        for response in [scores_response, standings_response]:
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "smith-score-player")
            self.assertNotContains(response, "jones-score-player")
        self.assertContains(rules_response, "Smith Family")
        self.assertContains(rules_response, "Locking: Weekly cutoff — Sunday 1PM ET")
        self.assertNotContains(rules_response, "Jones Family")
        self.assertNotContains(rules_response, "Locking: Lock each game at kickoff")


class Phase4SharedContextScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")
        GameWeeks.objects.create(
            weekNumber=1,
            competition="nfl",
            date=timezone.localdate(),
            season=2526,
        )
        cls.finished_game = GamesAndScores.objects.create(
            id=3501,
            slug="ari-atl-2025-week-1",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() - timedelta(days=1),
            statusType="finished",
            statusTitle="Final",
            homeTeamId=1,
            homeTeamSlug="atl",
            homeTeamName="Atlanta Falcons",
            awayTeamId=2,
            awayTeamSlug="ari",
            awayTeamName="Arizona Cardinals",
            gameWinner="atl",
            # Ranks only display once a game of the season has been scored.
            gameScored=True,
        )
        for team_id, slug, name in [
            (1, "atl", "Atlanta Falcons"),
            (2, "ari", "Arizona Cardinals"),
        ]:
            Teams.objects.create(
                id=team_id,
                gameseason=2526,
                teamNameSlug=slug,
                teamNameName=name,
                color="333333",
                alternateColor="666666",
            )

    def setUp(self):
        self.client = Client()
        self.request_factory = RequestFactory()
        self.member = User.objects.create_user(
            "shared-member", email="shared@example.com", password="pass"
        )
        self.other_member = User.objects.create_user(
            "shared-other", email="shared-other@example.com", password="pass"
        )
        self.smith_family, self.smith_pool = self._family_with_pool(
            "Smith Family", "smith-family"
        )
        self.jones_family, self.jones_pool = self._family_with_pool(
            "Jones Family", "jones-family"
        )
        self._active_membership(self.member, self.smith_family)
        self._active_membership(self.other_member, self.jones_family)

    def _family_with_pool(self, name, slug, *, pool_slug="main"):
        family = Family.objects.create(name=name, slug=slug)
        pool = Pool.objects.create(
            family=family,
            name="Main Pickem",
            slug=pool_slug,
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        return family, pool

    def _active_membership(self, user, family, role=FamilyMembership.Role.MEMBER):
        return FamilyMembership.objects.create(
            family=family,
            user=user,
            role=role,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _tenant_url(self, route_name, family=None, pool=None, **kwargs):
        family = family or self.smith_family
        pool = pool or self.smith_pool
        route_kwargs = {"family_slug": family.slug, "pool_slug": pool.slug}
        route_kwargs.update(kwargs)
        return reverse(route_name, kwargs=route_kwargs)

    def _tenant_prefix(self):
        return f"/families/{self.smith_family.slug}/pools/{self.smith_pool.slug}/"

    def _create_pick(self, *, user, pool, pick_id, pick_correct=True):
        return GamePicks.objects.create(
            id=pick_id,
            pool=pool,
            userEmail=user.email,
            uid=user.id,
            userID=str(user.id),
            slug=self.finished_game.slug,
            competition=self.finished_game.competition,
            gameWeek=self.finished_game.gameWeek,
            gameyear=self.finished_game.gameyear,
            gameseason=self.finished_game.gameseason,
            pick_game_id=self.finished_game.id,
            pick=self.finished_game.homeTeamSlug,
            pick_correct=pick_correct,
        )

    def test_shared_header_links_preserve_current_family_pool_context(self):
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertEqual(response.status_code, 200)
        markup = response.content.decode()
        self.assertIn(f'href="{self._tenant_prefix()}scores/"', markup)
        self.assertIn(f'href="{self._tenant_prefix()}standings/"', markup)
        self.assertIn(f'href="{self._tenant_prefix()}rules/"', markup)
        self.assertIn(f'href="{self._tenant_prefix()}picks/"', markup)
        self.assertIn(f'href="{self._tenant_prefix()}user/{self.member.id}/"', markup)
        self.assertNotIn('href="/picks"', markup)
        self.assertNotIn('href="/scores"', markup)
        self.assertNotIn('href="/standings/"', markup)
        self.assertNotIn('href="/rules/"', markup)
        self.assertNotIn(f'href="/user/{self.member.id}/"', markup)

    def test_tenant_pick_empty_links_and_ajax_urls_preserve_context(self):
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url("family_pool_game_picks"))

        self.assertEqual(response.status_code, 200)
        markup = response.content.decode()
        self.assertIn(f'href="{self._tenant_prefix()}', markup)
        self.assertIn(f'const pickSubmitUrl = "{self._tenant_prefix()}picks/";', markup)
        self.assertIn(f'const pickEditUrl = "{self._tenant_prefix()}picks/edit/";', markup)
        self.assertNotIn('href="/scores/"', markup)
        self.assertNotIn('href="/standings/"', markup)

    def test_tenant_scores_private_links_preserve_context(self):
        self._create_pick(
            user=self.member,
            pool=self.smith_pool,
            pick_id=f"{self.smith_pool.id}-{self.member.id}-{self.finished_game.id}",
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertEqual(response.status_code, 200)
        markup = response.content.decode()
        self.assertIn(f'href="{self._tenant_prefix()}user/{self.member.id}/"', markup)
        self.assertIn(f'href="{self._tenant_prefix()}picks/"', markup)
        self.assertNotIn(f'href="/user/{self.member.id}/"', markup)
        self.assertNotIn('href="/picks/"', markup)

    def test_footer_stats_context_scopes_private_stats_to_current_pool(self):
        userSeasonPoints.objects.create(
            pool=self.smith_pool,
            userEmail=self.member.email,
            userID=str(self.member.id),
            gameseason=2526,
            gameyear="2025",
            total_points=40,
            current_rank=4,
        )
        userSeasonPoints.objects.create(
            pool=self.jones_pool,
            userEmail=self.member.email,
            userID=str(self.member.id),
            gameseason=2526,
            gameyear="2025",
            total_points=90,
            current_rank=1,
        )
        self._create_pick(
            user=self.member,
            pool=self.smith_pool,
            pick_id=f"{self.smith_pool.id}-{self.member.id}-{self.finished_game.id}",
            pick_correct=True,
        )
        self._create_pick(
            user=self.member,
            pool=self.jones_pool,
            pick_id=f"{self.jones_pool.id}-{self.member.id}-{self.finished_game.id}",
            pick_correct=True,
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertEqual(response.context["user_current_rank"], 4)
        self.assertEqual(response.context["user_correct_picks_week"], 1)
        # The rank renders as a chip in the top-right profile button.
        self.assertContains(response, 'data-testid="navbar-rank"')
        self.assertContains(response, "#4")

    def test_footer_stats_context_suppresses_private_stats_without_safe_pool(self):
        userSeasonPoints.objects.create(
            pool=self.jones_pool,
            userEmail=self.member.email,
            userID=str(self.member.id),
            gameseason=2526,
            gameyear="2025",
            total_points=90,
            current_rank=1,
        )
        self._create_pick(
            user=self.member,
            pool=self.jones_pool,
            pick_id=f"{self.jones_pool.id}-{self.member.id}-{self.finished_game.id}",
            pick_correct=True,
        )
        request = self.request_factory.get("/")
        request.user = self.member

        context = footer_stats_context(request)

        self.assertIsNone(context["user_current_rank"])
        self.assertIsNone(context["user_correct_picks_week"])

    def test_site_banner_context_does_not_show_another_family_banner_on_tenant_page(self):
        SiteBanner.objects.create(
            title="Jones private banner",
            family=self.jones_family,
            is_active=True,
            priority=100,
            start_date=timezone.now() - timedelta(hours=1),
        )
        smith_banner = SiteBanner.objects.create(
            title="Smith private banner",
            family=self.smith_family,
            is_active=True,
            priority=10,
            start_date=timezone.now() - timedelta(hours=1),
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertEqual(response.context["active_banner"], smith_banner)
        self.assertNotContains(response, "Jones private banner")

    def test_site_banner_context_allows_site_wide_banner_when_current_family_has_none(self):
        SiteBanner.objects.create(
            title="Jones private banner",
            family=self.jones_family,
            is_active=True,
            priority=100,
            start_date=timezone.now() - timedelta(hours=1),
        )
        site_banner = SiteBanner.objects.create(
            title="Site-wide banner",
            family=None,
            is_active=True,
            priority=1,
            start_date=timezone.now() - timedelta(hours=1),
        )
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertEqual(response.context["active_banner"], site_banner)
        self.assertNotContains(response, "Jones private banner")

    def test_final_standings_rules_profile_footer_and_banner_links_preserve_tenant_context(self):
        userSeasonPoints.objects.create(
            pool=self.smith_pool,
            userEmail=self.member.email,
            userID=str(self.member.id),
            gameseason=2526,
            gameyear="2025",
            total_points=40,
            current_rank=4,
            week_1_winner=True,
            year_winner=True,
        )
        userSeasonPoints.objects.create(
            pool=self.jones_pool,
            userEmail=self.other_member.email,
            userID=str(self.other_member.id),
            gameseason=2526,
            gameyear="2025",
            total_points=90,
            current_rank=1,
            week_1_winner=True,
            year_winner=True,
        )
        SiteBanner.objects.create(
            title="Jones final private banner",
            family=self.jones_family,
            is_active=True,
            priority=100,
            start_date=timezone.now() - timedelta(hours=1),
        )
        smith_banner = SiteBanner.objects.create(
            title="Smith final private banner",
            family=self.smith_family,
            is_active=True,
            priority=10,
            start_date=timezone.now() - timedelta(hours=1),
        )
        self.client.force_login(self.member)

        standings_response = self.client.get(self._tenant_url("family_pool_standings"))
        rules_response = self.client.get(self._tenant_url("family_pool_rules"))
        profile_response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.member.id)
        )

        tenant_profile_href = f'href="{self._tenant_prefix()}user/{self.member.id}/"'
        for response in [standings_response, rules_response, profile_response]:
            self.assertEqual(response.status_code, 200)
            markup = response.content.decode()
            self.assertIn(f'href="{self._tenant_prefix()}scores/"', markup)
            self.assertIn(f'href="{self._tenant_prefix()}standings/"', markup)
            self.assertIn(f'href="{self._tenant_prefix()}rules/"', markup)
            self.assertNotIn('href="/scores"', markup)
            self.assertNotIn('href="/standings/"', markup)
            self.assertNotIn('href="/rules/"', markup)
            self.assertNotIn(f'href="/user/{self.member.id}/"', markup)

        self.assertIn(tenant_profile_href, standings_response.content.decode())
        self.assertEqual(standings_response.context["user_current_rank"], 4)
        self.assertEqual(standings_response.context["active_banner"], smith_banner)
        self.assertNotContains(standings_response, "Jones final private banner")
        self.assertEqual(profile_response.context["stats"]["current_season_points"], 40)
        self.assertNotEqual(profile_response.context["stats"]["current_season_points"], 90)


class TenantProfilesPlayersMessageBoardIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")
        GameWeeks.objects.create(
            weekNumber=1,
            competition="nfl",
            date=timezone.localdate(),
            season=2526,
        )
        cls.game = GamesAndScores.objects.create(
            id=4001,
            slug="ari-atl-2025-week-1",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now() + timedelta(days=1),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=1,
            homeTeamSlug="atl",
            homeTeamName="Atlanta Falcons",
            awayTeamId=2,
            awayTeamSlug="ari",
            awayTeamName="Arizona Cardinals",
        )
        for team_id, slug, name in [
            (1, "atl", "Atlanta Falcons"),
            (2, "ari", "Arizona Cardinals"),
        ]:
            Teams.objects.create(
                id=team_id,
                gameseason=2526,
                teamNameSlug=slug,
                teamNameName=name,
                teamLogo=f"https://example.test/{slug}.png",
                color="333333",
                alternateColor="666666",
            )

    def setUp(self):
        self.client = Client()
        self.smith_member = User.objects.create_user(
            "smith-profile-member", email="smith-member@example.com", password="pass"
        )
        self.smith_player = User.objects.create_user(
            "smith-profile-player", email="smith-player@example.com", password="pass"
        )
        self.smith_private = User.objects.create_user(
            "smith-private-player", email="smith-private@example.com", password="pass"
        )
        self.jones_player = User.objects.create_user(
            "jones-profile-player", email="jones-player@example.com", password="pass"
        )
        self.outsider = User.objects.create_user(
            "profile-outsider", email="profile-outsider@example.com", password="pass"
        )
        self.smith_family, self.smith_pool = self._family_with_pool(
            "Smith Family", "smith-family"
        )
        self.jones_family, self.jones_pool = self._family_with_pool(
            "Jones Family", "jones-family"
        )
        self._active_membership(self.smith_member, self.smith_family)
        self._active_membership(self.smith_player, self.smith_family)
        self._active_membership(self.smith_private, self.smith_family)
        self._active_membership(self.jones_player, self.jones_family)
        UserProfile.objects.create(user=self.smith_private, private_profile=True)

    def _family_with_pool(self, name, slug, *, pool_slug="main"):
        family = Family.objects.create(name=name, slug=slug)
        pool = Pool.objects.create(
            family=family,
            name="Main Pickem",
            slug=pool_slug,
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        return family, pool

    def _active_membership(self, user, family, role=FamilyMembership.Role.MEMBER):
        return FamilyMembership.objects.create(
            family=family,
            user=user,
            role=role,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _tenant_url(self, route_name, family=None, pool=None, **kwargs):
        family = family or self.smith_family
        pool = pool or self.smith_pool
        route_kwargs = {"family_slug": family.slug, "pool_slug": pool.slug}
        route_kwargs.update(kwargs)
        return reverse(route_name, kwargs=route_kwargs)

    def _create_pick(self, *, user, pool, pick_id):
        return GamePicks.objects.create(
            id=pick_id,
            pool=pool,
            userEmail=user.email,
            uid=user.id,
            userID=str(user.id),
            slug=self.game.slug,
            competition=self.game.competition,
            gameWeek=self.game.gameWeek,
            gameyear=self.game.gameyear,
            gameseason=self.game.gameseason,
            pick_game_id=self.game.id,
            pick=self.game.homeTeamSlug,
            pick_correct=True,
        )

    def _seed_profile_data(self):
        # Profile pages only reveal picks for games that have kicked off, so
        # backdate the shared fixture game for the picks seeded here.
        GamesAndScores.objects.filter(id=self.game.id).update(
            startTimestamp=timezone.now() - timedelta(hours=1)
        )
        userSeasonPoints.objects.create(
            pool=self.smith_pool,
            userEmail=self.smith_player.email,
            userID=str(self.smith_player.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=3,
            week_1_winner=True,
            total_points=33,
        )
        userSeasonPoints.objects.create(
            pool=self.jones_pool,
            userEmail=self.jones_player.email,
            userID=str(self.jones_player.id),
            gameseason=2526,
            gameyear="2025",
            week_1_points=9,
            week_1_winner=True,
            total_points=99,
        )
        self._create_pick(
            user=self.smith_player,
            pool=self.smith_pool,
            pick_id=f"{self.smith_pool.id}-{self.smith_player.id}-{self.game.id}",
        )
        self._create_pick(
            user=self.jones_player,
            pool=self.jones_pool,
            pick_id=f"{self.jones_pool.id}-{self.jones_player.id}-{self.game.id}",
        )
        userStats.objects.create(
            pool=self.smith_pool,
            userEmail=self.smith_player.email,
            userID=str(self.smith_player.id),
            pickPercentSeason=67,
            pickPercentTotal=67,
            correctPickTotalSeason=2,
            correctPickTotalTotal=2,
            totalPicksSeason=3,
            totalPicksTotal=3,
            mostPickedSeason=self.game.homeTeamSlug,
            perfectWeeksSeason=1,
        )
        userStats.objects.create(
            pool=self.jones_pool,
            userEmail=self.jones_player.email,
            userID=str(self.jones_player.id),
            pickPercentSeason=99,
            pickPercentTotal=99,
            correctPickTotalSeason=99,
            correctPickTotalTotal=99,
            totalPicksSeason=100,
            totalPicksTotal=100,
            mostPickedSeason=self.game.awayTeamSlug,
            perfectWeeksSeason=9,
        )
        MessageBoardPost.objects.create(
            family=self.smith_family,
            user=self.smith_player,
            title="Smith profile post",
            content="Smith family post",
        )
        MessageBoardPost.objects.create(
            family=self.jones_family,
            user=self.jones_player,
            title="Jones profile post",
            content="Jones family post",
        )

    def _seed_message_board_data(self):
        smith_post = MessageBoardPost.objects.create(
            family=self.smith_family,
            user=self.smith_player,
            title="Smith thread",
            content="Smith family only",
        )
        smith_comment = MessageBoardComment.objects.create(
            family=self.smith_family,
            post=smith_post,
            user=self.smith_member,
            content="Smith comment",
        )
        jones_post = MessageBoardPost.objects.create(
            family=self.jones_family,
            user=self.jones_player,
            title="Jones thread",
            content="Jones family only",
        )
        jones_comment = MessageBoardComment.objects.create(
            family=self.jones_family,
            post=jones_post,
            user=self.jones_player,
            content="Jones comment",
        )
        return smith_post, smith_comment, jones_post, jones_comment

    def _json_post(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_tenant_players_list_contains_only_current_family_active_members(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_players"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/players.html")
        self.assertContains(response, "smith-profile-member")
        self.assertContains(response, "smith-profile-player")
        self.assertNotContains(response, "jones-profile-player")
        self.assertQuerysetEqual(
            response.context["players"].values_list("id", flat=True).order_by("id"),
            sorted([self.smith_member.id, self.smith_player.id, self.smith_private.id]),
        )

    def test_tenant_players_page_includes_compact_polish_hooks(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_players"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-players-page")
        self.assertContains(response, "players-scoreboard-header")
        self.assertContains(response, "players-compact-card")
        self.assertContains(response, "playersCardMotion")
        self.assertContains(response, "gsap.min.js")

    def test_profile_hides_picks_for_games_that_have_not_started(self):
        # A lone pick on a future game (e.g. opening night) must not leak on
        # the profile page before kickoff. The class fixture game starts
        # tomorrow, so this pick stays hidden.
        self._create_pick(
            user=self.smith_player,
            pool=self.smith_pool,
            pick_id=f"{self.smith_pool.id}-{self.smith_player.id}-{self.game.id}-future",
        )
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.smith_player.id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recent_picks"]), 0)
        self.assertEqual(response.context["team_chart_data"], [])

    def test_tenant_profile_scopes_stats_picks_posts_and_links_to_current_pool(self):
        self._seed_profile_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.smith_player.id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/user_profile.html")
        self.assertContains(response, "smith-profile-player")
        self.assertContains(response, "33")
        self.assertContains(response, "Smith Family")
        self.assertNotContains(response, "jones-profile-player")
        self.assertEqual(response.context["family"], self.smith_family)
        self.assertEqual(response.context["pool"], self.smith_pool)
        self.assertEqual(response.context["stats"]["current_season_points"], 33)
        self.assertNotEqual(response.context["stats"]["current_season_points"], 99)
        self.assertEqual(response.context["recent_picks"][0].pool, self.smith_pool)
        self.assertEqual(response.context["posts_count"], 1)

    def test_tenant_profile_requires_target_user_current_family_membership(self):
        self._seed_profile_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.jones_player.id)
        )

        self.assertEqual(response.status_code, 404)

    def test_superuser_can_open_own_profile_in_a_family_with_no_real_membership(self):
        # Regression test: the navbar "My Profile" link builds a tenant-scoped
        # URL from the current family/pool + the logged-in user's id. Under
        # god mode, a superuser can browse into (and thus land on) a family
        # they hold no real FamilyMembership row in, so their own profile
        # link must not 404 there.
        self._seed_profile_data()
        sre = User.objects.create_user(
            "site-sre", email="sre@example.com", password="pass", is_superuser=True
        )
        self.assertFalse(
            FamilyMembership.objects.filter(user=sre, family=self.smith_family).exists()
        )
        self.client.force_login(sre)

        response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=sre.id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/user_profile.html")
        self.assertEqual(response.context["family"], self.smith_family)

        # A superuser can likewise open any real member's profile there...
        member_response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.smith_player.id)
        )
        self.assertEqual(member_response.status_code, 200)

        # ...but a non-superuser is still blocked from cross-family profiles.
        self.client.force_login(self.smith_member)
        outsider_response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=sre.id)
        )
        self.assertEqual(outsider_response.status_code, 404)

    def test_private_profile_message_applies_after_family_membership_is_proven(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.smith_private.id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/user_profile_private.html")
        self.assertContains(response, "This Profile is Private")

    def test_legacy_signed_in_profile_renders_global_profile_without_tenant_redirect(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(reverse("user_profile", kwargs={"user_id": self.smith_player.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/user_profile.html")

    def test_legacy_anonymous_profile_detail_is_not_available(self):
        response = self.client.get(reverse("user_profile", kwargs={"user_id": self.smith_player.id}))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_outsider_direct_tenant_profiles_and_players_are_denied(self):
        self.client.force_login(self.outsider)

        self.assertEqual(
            self.client.get(
                self._tenant_url("family_pool_user_profile", user_id=self.smith_player.id)
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self._tenant_url("family_pool_players")).status_code,
            404,
        )

    def test_profile_ajax_settings_coerce_false_boolean_values(self):
        self.client.force_login(self.smith_member)

        response = self._json_post(
            reverse("profile"),
            {"setting": "private_profile", "value": "false"},
        )

        self.assertEqual(response.status_code, 200)
        self.smith_member.profile.refresh_from_db()
        self.assertFalse(self.smith_member.profile.private_profile)

    def test_profile_page_exposes_live_email_notifications_toggle(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="emailNotifications"')
        self.assertNotContains(
            response,
            'id="emailNotifications" data-setting="email_notifications" disabled',
        )
        self.assertContains(
            response,
            'Receive weekly pick reminders when your account is eligible',
        )

    def test_profile_ajax_settings_reject_invalid_boolean_values_without_raw_errors(self):
        self.client.force_login(self.smith_member)

        response = self._json_post(
            reverse("profile"),
            {"setting": "email_notifications", "value": "definitely"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {"success": False, "error": "invalid_setting_value"},
        )

    def test_profile_ajax_settings_reject_malformed_json(self):
        self.client.force_login(self.smith_member)

        response = self.client.post(
            reverse("profile"),
            data="{not-json",
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {"success": False, "error": "invalid_json"},
        )

    def test_profile_username_update_is_case_insensitive_and_catches_integrity_errors(self):
        User.objects.create_user(
            "TakenName", email="taken@example.com", password="pass", is_active=False
        )
        self.client.force_login(self.smith_member)

        response = self.client.post(
            reverse("profile"),
            {
                "username": "takenname",
                "tagline": "",
                "favorite_team": "",
                "phone_number": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.smith_member.refresh_from_db()
        self.assertEqual(self.smith_member.username, "smith-profile-member")
        self.assertContains(response, "This username is already taken.")

    def test_check_username_requires_csrf_and_returns_generic_result(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.smith_member)

        csrf_response = csrf_client.post(
            reverse("check_username"),
            data=json.dumps({"username": "smith-profile-player"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(csrf_response.status_code, 403)

        self.client.force_login(self.smith_member)
        ok_response = self._json_post(
            reverse("check_username"),
            {"username": "smith-profile-player"},
        )
        self.assertEqual(ok_response.status_code, 200)
        self.assertJSONEqual(
            ok_response.content,
            {"success": True, "message": "Username can be checked on save."},
        )

    def test_toggle_theme_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.smith_member)

        response = csrf_client.post(
            reverse("toggle_theme"),
            data=json.dumps({"theme": "dark"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)

    def test_user_profile_template_pins_chart_assets_with_sri(self):
        self._seed_profile_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.smith_player.id)
        )

        self.assertContains(response, "chart.js@")
        self.assertContains(response, "chartjs-plugin-datalabels@")
        self.assertContains(response, 'integrity="')
        self.assertContains(response, 'crossorigin="anonymous"')

    def test_scores_template_guards_live_update_reentrancy(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_scores"))

        self.assertContains(response, "if (updateInterval)")
        self.assertContains(response, "updateInterval = null;")
        self.assertContains(response, "document.removeEventListener('visibilitychange', window.visibilityHandler);")

    def test_tenant_create_post_assigns_current_family_server_side(self):
        self.client.force_login(self.smith_member)

        response = self.client.post(
            self._tenant_url("family_pool_create_post"),
            {
                "title": "Forged family",
                "content": "Smith server scoped",
                "family": self.jones_family.id,
                "family_id": self.jones_family.id,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        post = MessageBoardPost.objects.get(content="Smith server scoped")
        self.assertEqual(post.family, self.smith_family)
        self.assertEqual(post.user, self.smith_member)

    def test_messages_page_renders_threads_scoped_to_family_with_ajax_and_links(self):
        MessageBoardPost.objects.create(
            family=self.smith_family, user=self.smith_member,
            title="Smith thread", content="Smith board content",
        )
        MessageBoardPost.objects.create(
            family=self.jones_family, user=self.jones_player,
            title="Jones thread", content="Jones board content",
        )
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_messages"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/family_messages.html")
        self.assertContains(response, "Message Board")
        self.assertContains(response, "Smith board content")
        # Cross-family isolation.
        self.assertNotContains(response, "Jones board content")
        # Wires the tenant AJAX endpoints and links the author to their profile.
        self.assertContains(response, self._tenant_url("family_pool_vote_post"))
        self.assertContains(response, self._tenant_url("family_pool_create_comment"))
        self.assertContains(
            response,
            self._tenant_url("family_pool_user_profile", user_id=self.smith_member.id),
        )

    def test_messages_page_renders_comments_modal_and_open_trigger(self):
        # Comments open in an overlay modal on top of the board, so the page
        # must ship the modal container and the per-post trigger.
        MessageBoardPost.objects.create(
            family=self.smith_family, user=self.smith_member,
            title="Smith thread", content="Smith board content",
        )
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_messages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="comments-modal"')
        self.assertContains(response, "open-comments")
        self.assertContains(response, "modal-comment-list")

    def test_comment_payloads_include_display_name_and_avatar(self):
        # The Reddit-style comment list renders avatars and display names, so
        # both the create and fetch JSON payloads must carry those fields.
        post = MessageBoardPost.objects.create(
            family=self.smith_family, user=self.smith_member,
            title="Smith thread", content="Smith board content",
        )
        self.client.force_login(self.smith_member)

        created = self._json_post(
            self._tenant_url("family_pool_create_comment"),
            {"post_id": post.id, "content": "hello there"},
        )
        self.assertEqual(created.status_code, 200)
        comment = created.json()["comment"]
        self.assertIn("user_display", comment)
        # No social account -> empty avatar so the client renders an initials
        # badge (matching the server-rendered post cards) instead of a
        # placeholder image.
        self.assertEqual(comment["avatar"], "")

        fetched = self.client.get(
            self._tenant_url("family_pool_get_post_comments", post_id=post.id),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(fetched.status_code, 200)
        first = fetched.json()["comments"][0]
        self.assertIn("user_display", first)
        self.assertIn("avatar", first)

    def test_messages_page_denies_outsiders(self):
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(self._tenant_url("family_pool_messages")).status_code, 404
        )

    def test_tenant_create_comment_denies_cross_family_post_and_parent_ids_generically(self):
        _smith_post, _smith_comment, jones_post, jones_comment = self._seed_message_board_data()
        self.client.force_login(self.smith_member)

        response = self._json_post(
            self._tenant_url("family_pool_create_comment"),
            {
                "post_id": jones_post.id,
                "parent_id": jones_comment.id,
                "content": "tampered",
            },
        )

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIn("not found", payload["error"].lower())
        self.assertNotIn("Jones", json.dumps(payload))
        self.assertFalse(MessageBoardComment.objects.filter(content="tampered").exists())

    def test_tenant_vote_post_and_comment_deny_cross_family_ids_generically(self):
        _smith_post, _smith_comment, jones_post, jones_comment = self._seed_message_board_data()
        self.client.force_login(self.smith_member)

        post_response = self._json_post(
            self._tenant_url("family_pool_vote_post"),
            {"post_id": jones_post.id, "vote_type": 1},
        )
        comment_response = self._json_post(
            self._tenant_url("family_pool_vote_comment"),
            {"comment_id": jones_comment.id, "vote_type": 1},
        )

        for response in [post_response, comment_response]:
            self.assertEqual(response.status_code, 404)
            payload = response.json()
            self.assertFalse(payload["success"])
            self.assertIn("not found", payload["error"].lower())
            self.assertNotIn("Jones", json.dumps(payload))
        self.assertFalse(MessageBoardVote.objects.filter(family=self.jones_family).exists())

    def test_tenant_get_comments_serializes_only_current_family_post_comments(self):
        smith_post, smith_comment, jones_post, jones_comment = self._seed_message_board_data()
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url("family_pool_get_post_comments", post_id=smith_post.id),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        tamper_response = self.client.get(
            self._tenant_url("family_pool_get_post_comments", post_id=jones_post.id),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["comments"][0]["id"], smith_comment.id)
        self.assertNotIn(jones_comment.id, [comment["id"] for comment in payload["comments"]])
        self.assertEqual(tamper_response.status_code, 404)
        tamper_payload = tamper_response.json()
        self.assertFalse(tamper_payload["success"])
        self.assertNotIn("Jones", json.dumps(tamper_payload))

    def test_tenant_edit_post_updates_content_for_author_only(self):
        smith_post, _smith_comment, _jones_post, _jones_comment = self._seed_message_board_data()

        self.client.force_login(self.smith_member)
        denied = self._json_post(
            self._tenant_url("family_pool_edit_post", post_id=smith_post.id),
            {"title": "hijacked", "content": "hijacked"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(denied.json()["success"])

        self.client.force_login(self.smith_player)
        allowed = self._json_post(
            self._tenant_url("family_pool_edit_post", post_id=smith_post.id),
            {"title": "Updated title", "content": "Updated content"},
        )
        self.assertEqual(allowed.status_code, 200)
        payload = allowed.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["post"]["content"], "Updated content")
        smith_post.refresh_from_db()
        self.assertEqual(smith_post.content, "Updated content")
        self.assertEqual(smith_post.title, "Updated title")

    def test_tenant_edit_post_rejects_overlong_title_and_content(self):
        # The form inputs carry maxlength client-side, but a crafted request
        # bypasses them; the server must reject rather than 500 on DB overflow.
        smith_post, _smith_comment, _jones_post, _jones_comment = self._seed_message_board_data()
        self.client.force_login(self.smith_player)

        for payload in (
            {"title": "x" * 201, "content": "fine"},
            {"title": "fine", "content": "x" * 2001},
        ):
            with self.subTest(payload_keys={k: len(v) for k, v in payload.items()}):
                response = self._json_post(
                    self._tenant_url("family_pool_edit_post", post_id=smith_post.id),
                    payload,
                )
                self.assertEqual(response.status_code, 400)
                smith_post.refresh_from_db()
                self.assertEqual(smith_post.content, "Smith family only")
                self.assertEqual(smith_post.title, "Smith thread")

    def test_tenant_create_post_rejects_overlong_title(self):
        self.client.force_login(self.smith_member)

        response = self.client.post(
            self._tenant_url("family_pool_create_post"),
            {"title": "x" * 201, "content": "fine"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            MessageBoardPost.objects.filter(family=self.smith_family, content="fine").exists()
        )

    def test_tenant_delete_post_allows_author_or_moderator_denies_others(self):
        smith_post, _smith_comment, _jones_post, _jones_comment = self._seed_message_board_data()
        moderator = User.objects.create_user(
            "smith-moderator", email="smith-moderator@example.com", password="pass"
        )
        self._active_membership(moderator, self.smith_family, role=FamilyMembership.Role.OWNER)

        self.client.force_login(self.smith_private)
        denied = self._json_post(
            self._tenant_url("family_pool_delete_post", post_id=smith_post.id), {}
        )
        self.assertEqual(denied.status_code, 403)
        smith_post.refresh_from_db()
        self.assertTrue(smith_post.is_active)

        self.client.force_login(moderator)
        allowed = self._json_post(
            self._tenant_url("family_pool_delete_post", post_id=smith_post.id), {}
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()["success"])
        smith_post.refresh_from_db()
        self.assertFalse(smith_post.is_active)

    def test_tenant_edit_comment_updates_content_for_author_only(self):
        _smith_post, smith_comment, _jones_post, _jones_comment = self._seed_message_board_data()

        self.client.force_login(self.smith_player)
        denied = self._json_post(
            self._tenant_url("family_pool_edit_comment", comment_id=smith_comment.id),
            {"content": "hijacked"},
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.smith_member)
        allowed = self._json_post(
            self._tenant_url("family_pool_edit_comment", comment_id=smith_comment.id),
            {"content": "Updated comment"},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["comment"]["content"], "Updated comment")
        smith_comment.refresh_from_db()
        self.assertEqual(smith_comment.content, "Updated comment")

    def test_tenant_delete_comment_allows_author_or_moderator_denies_others(self):
        _smith_post, smith_comment, _jones_post, _jones_comment = self._seed_message_board_data()
        moderator = User.objects.create_user(
            "smith-comment-moderator", email="smith-comment-moderator@example.com", password="pass"
        )
        self._active_membership(moderator, self.smith_family, role=FamilyMembership.Role.OWNER)

        self.client.force_login(self.smith_player)
        denied = self._json_post(
            self._tenant_url("family_pool_delete_comment", comment_id=smith_comment.id), {}
        )
        self.assertEqual(denied.status_code, 403)
        smith_comment.refresh_from_db()
        self.assertTrue(smith_comment.is_active)

        self.client.force_login(moderator)
        allowed = self._json_post(
            self._tenant_url("family_pool_delete_comment", comment_id=smith_comment.id), {}
        )
        self.assertEqual(allowed.status_code, 200)
        smith_comment.refresh_from_db()
        self.assertFalse(smith_comment.is_active)

    def test_superuser_without_membership_can_moderate_posts(self):
        # Superusers get a synthetic owner membership from the tenant context;
        # moderation must honor it rather than requiring a saved membership row.
        smith_post, _smith_comment, _jones_post, _jones_comment = self._seed_message_board_data()
        sre = User.objects.create_user(
            "board-sre", email="board-sre@example.com", password="pass", is_superuser=True
        )
        self.client.force_login(sre)

        response = self._json_post(
            self._tenant_url("family_pool_delete_post", post_id=smith_post.id), {}
        )

        self.assertEqual(response.status_code, 200)
        smith_post.refresh_from_db()
        self.assertFalse(smith_post.is_active)

    def test_tenant_delete_comment_deactivates_reply_subtree(self):
        smith_post, smith_comment, _jones_post, _jones_comment = self._seed_message_board_data()
        reply = MessageBoardComment.objects.create(
            family=self.smith_family,
            post=smith_post,
            user=self.smith_player,
            parent=smith_comment,
            content="reply level 1",
        )
        nested_reply = MessageBoardComment.objects.create(
            family=self.smith_family,
            post=smith_post,
            user=self.smith_member,
            parent=reply,
            content="reply level 2",
        )
        self.client.force_login(self.smith_member)

        response = self._json_post(
            self._tenant_url("family_pool_delete_comment", comment_id=smith_comment.id), {}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deactivated_count"], 3)
        for obj in (smith_comment, reply, nested_reply):
            obj.refresh_from_db()
            self.assertFalse(obj.is_active)
        self.assertEqual(smith_post.comment_count, 0)

    def test_tenant_edit_delete_post_and_comment_deny_cross_family_ids_generically(self):
        _smith_post, _smith_comment, jones_post, jones_comment = self._seed_message_board_data()
        self.client.force_login(self.smith_member)

        responses = [
            self._json_post(
                self._tenant_url("family_pool_edit_post", post_id=jones_post.id),
                {"content": "tampered"},
            ),
            self._json_post(
                self._tenant_url("family_pool_delete_post", post_id=jones_post.id), {}
            ),
            self._json_post(
                self._tenant_url("family_pool_edit_comment", comment_id=jones_comment.id),
                {"content": "tampered"},
            ),
            self._json_post(
                self._tenant_url("family_pool_delete_comment", comment_id=jones_comment.id), {}
            ),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 404)
            payload = response.json()
            self.assertFalse(payload["success"])
            self.assertNotIn("Jones", json.dumps(payload))
        jones_post.refresh_from_db()
        jones_comment.refresh_from_db()
        self.assertTrue(jones_post.is_active)
        self.assertTrue(jones_comment.is_active)
        self.assertNotEqual(jones_post.content, "tampered")

    def test_lobby_links_to_messages_page_instead_of_inline_board(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_home"))

        self.assertEqual(response.status_code, 200)
        # The lobby now links to the dedicated tenant messages page...
        self.assertContains(response, self._tenant_url("family_pool_messages"))
        # ...and no longer embeds the inline create form or legacy fetch URLs.
        self.assertNotContains(response, 'id="family-message-form"')
        self.assertNotContains(response, "fetch('/message-board/create-post/'")

    def test_final_object_id_body_and_slug_tampering_do_not_cross_family_profiles_players_or_message_board(self):
        self._seed_profile_data()
        smith_post, _smith_comment, jones_post, jones_comment = self._seed_message_board_data()
        self.client.force_login(self.smith_member)

        players_response = self.client.get(
            self._tenant_url(
                "family_pool_players",
                family=self.jones_family,
                pool=self.jones_pool,
            )
        )
        profile_response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.jones_player.id),
            {"family": self.jones_family.slug, "pool": self.jones_pool.id},
        )
        comments_response = self.client.get(
            self._tenant_url("family_pool_get_post_comments", post_id=jones_post.id),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        create_comment_response = self._json_post(
            self._tenant_url("family_pool_create_comment"),
            {
                "post_id": jones_post.id,
                "parent_id": jones_comment.id,
                "content": "cross-family body tamper",
                "family": self.jones_family.id,
                "pool": self.jones_pool.id,
            },
        )
        vote_post_response = self._json_post(
            self._tenant_url("family_pool_vote_post"),
            {"post_id": jones_post.id, "vote_type": 1, "family": self.jones_family.id},
        )
        vote_comment_response = self._json_post(
            self._tenant_url("family_pool_vote_comment"),
            {"comment_id": jones_comment.id, "vote_type": 1, "family": self.jones_family.id},
        )
        create_post_response = self.client.post(
            self._tenant_url("family_pool_create_post"),
            {
                "title": "Forged family target",
                "content": "server-derived family target",
                "family": self.jones_family.id,
                "pool": self.jones_pool.id,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(players_response.status_code, 404)
        self.assertEqual(profile_response.status_code, 404)
        for response in [
            comments_response,
            create_comment_response,
            vote_post_response,
            vote_comment_response,
        ]:
            self.assertEqual(response.status_code, 404)
            self.assertFalse(response.json()["success"])
            self.assertNotIn("Jones", json.dumps(response.json()))

        self.assertEqual(create_post_response.status_code, 200)
        created_post = MessageBoardPost.objects.get(content="server-derived family target")
        self.assertEqual(created_post.family, self.smith_family)
        self.assertEqual(created_post.user, self.smith_member)
        self.assertFalse(
            MessageBoardComment.objects.filter(content="cross-family body tamper").exists()
        )
        self.assertFalse(
            MessageBoardVote.objects.filter(family=self.jones_family, user=self.smith_member).exists()
        )
        self.assertTrue(
            MessageBoardPost.objects.filter(id=smith_post.id, family=self.smith_family).exists()
        )


class FamilySwitcherContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            "switcher-user", email="switcher@example.com", password="pass"
        )
        self.outsider = User.objects.create_user(
            "switcher-outsider", email="switcher-outsider@example.com", password="pass"
        )

    def _family_with_pool(self, name, slug, *, pool_slug="main", status=Family.Status.ACTIVE):
        family = Family.objects.create(name=name, slug=slug, status=status)
        pool = Pool.objects.create(
            family=family,
            name="Main Pickem",
            slug=pool_slug,
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        return family, pool

    def _active_membership(self, user, family, role=FamilyMembership.Role.MEMBER):
        return FamilyMembership.objects.create(
            family=family,
            user=user,
            role=role,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _tenant_url(self, family, pool):
        return reverse(
            "family_pool_home",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def test_one_family_user_sees_current_family_and_pool_in_header_context(self):
        family, pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.user, family)
        self.client.force_login(self.user)

        response = self.client.get(self._tenant_url(family, pool))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_family"], family)
        self.assertEqual(response.context["current_pool"], pool)
        self.assertEqual(len(response.context["family_switcher_choices"]), 1)
        self.assertContains(response, 'data-testid="family-context-switcher"')
        self.assertContains(response, 'data-testid="family-switcher-create"')
        self.assertContains(response, "Create new family")
        self.assertContains(response, "Current family")
        self.assertContains(response, "Smith Family")
        self.assertContains(response, "Main Pickem")

    def test_multi_family_switcher_lists_only_authenticated_active_memberships(self):
        smith, smith_pool = self._family_with_pool("Smith Family", "smith-family")
        jones, jones_pool = self._family_with_pool("Jones Family", "jones-family")
        inactive, _inactive_pool = self._family_with_pool("Inactive Family", "inactive-family")
        outsider_family, _outsider_pool = self._family_with_pool("Outsider Family", "outsider-family")
        self._active_membership(self.user, smith)
        self._active_membership(self.user, jones)
        FamilyMembership.objects.create(
            family=inactive,
            user=self.user,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.INACTIVE,
        )
        self._active_membership(self.outsider, outsider_family)
        self.client.force_login(self.user)

        response = self.client.get(self._tenant_url(smith, smith_pool))

        choice_names = [
            choice["family"].name
            for choice in response.context["family_switcher_choices"]
        ]
        self.assertEqual(choice_names, ["Jones Family", "Smith Family"])
        self.assertContains(response, "Switch family")
        self.assertContains(response, self._tenant_url(smith, smith_pool))
        self.assertContains(response, self._tenant_url(jones, jones_pool))
        self.assertContains(response, "Jones Family")
        self.assertNotContains(response, "Inactive Family")
        self.assertNotContains(response, "Outsider Family")

    def test_no_family_user_sees_onboarding_actions_without_family_leakage(self):
        outsider_family, _pool = self._family_with_pool("Outsider Family", "outsider-family")
        self._active_membership(self.outsider, outsider_family)
        self.client.force_login(self.user)

        response = self.client.get(reverse("onboarding"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["current_family"])
        self.assertIsNone(response.context["current_pool"])
        self.assertEqual(response.context["family_switcher_choices"], [])
        self.assertContains(response, 'data-testid="family-onboarding-actions"')
        self.assertContains(response, reverse("create_family"))
        self.assertContains(response, reverse("join_family"))
        self.assertNotContains(response, "Outsider Family")


class FamilyAdminExperienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            "admin-owner", email="owner@example.com", password="pass"
        )
        self.admin_user = User.objects.create_user(
            "admin-user", email="admin@example.com", password="pass"
        )
        self.member = User.objects.create_user(
            "admin-member", email="member@example.com", password="pass"
        )
        self.inactive_user = User.objects.create_user(
            "admin-inactive", email="inactive@example.com", password="pass"
        )
        self.outsider = User.objects.create_user(
            "admin-outsider", email="outsider@example.com", password="pass"
        )

        self.family, self.pool = self._family_with_pool(
            "Smith Family", "smith-family", pool_slug="smith-main"
        )
        self.other_family, self.other_pool = self._family_with_pool(
            "Jones Family", "jones-family", pool_slug="jones-main"
        )

        self._membership(self.owner, self.family, FamilyMembership.Role.OWNER)
        self._membership(self.admin_user, self.family, FamilyMembership.Role.ADMIN)
        self._membership(self.member, self.family, FamilyMembership.Role.MEMBER)
        self._membership(
            self.inactive_user,
            self.family,
            FamilyMembership.Role.ADMIN,
            status=FamilyMembership.Status.INACTIVE,
        )
        self._membership(self.outsider, self.other_family, FamilyMembership.Role.OWNER)

        self.current_audit = FamilyAuditLog.objects.create(
            family=self.family,
            pool=self.pool,
            actor=self.owner,
            action=FamilyAuditLog.Action.INVITATION_CREATED,
            target_type="FamilyInvitation",
            target_id="smith-invite",
            metadata={"summary": "Smith admin event"},
        )
        FamilyAuditLog.objects.create(
            family=self.other_family,
            pool=self.other_pool,
            actor=self.outsider,
            action=FamilyAuditLog.Action.MEMBERSHIP_UPDATED,
            target_type="FamilyMembership",
            target_id="jones-member",
            metadata={"summary": "Jones private event"},
        )

    def _family_with_pool(self, name, slug, *, pool_slug):
        family = Family.objects.create(name=name, slug=slug)
        pool = Pool.objects.create(
            family=family,
            name="Main Pickem",
            slug=pool_slug,
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        PoolSettings.objects.create(pool=pool)
        return family, pool

    def _membership(
        self,
        user,
        family,
        role=FamilyMembership.Role.MEMBER,
        *,
        status=FamilyMembership.Status.ACTIVE,
    ):
        return FamilyMembership.objects.create(
            family=family,
            user=user,
            role=role,
            status=status,
        )

    def _admin_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def test_superuser_god_mode_accesses_any_family_with_badge(self):
        # A superuser with NO membership anywhere sees any family's pages.
        sre = User.objects.create_user(
            "site-sre", email="sre@example.com", password="pass", is_superuser=True
        )
        self.client.force_login(sre)

        lobby = self.client.get(
            reverse("family_pool_home",
                    kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug})
        )
        self.assertEqual(lobby.status_code, 200)
        # Always-visible superuser indicator in the navbar.
        self.assertContains(lobby, 'data-testid="superuser-badge"')

        # Admin pages too (synthetic owner context), across BOTH families.
        for family, pool in ((self.family, self.pool), (self.other_family, self.other_pool)):
            admin_page = self.client.get(self._admin_url(family=family, pool=pool))
            self.assertEqual(admin_page.status_code, 200)

        # The switcher is reserved for real memberships only.
        self.assertEqual(lobby.context["family_switcher_choices"], [])
        # ...without creating any membership rows (no roster contamination).
        self.assertFalse(FamilyMembership.objects.filter(user=sre).exists())

        # Regular members get neither god mode nor the badge.
        self.client.force_login(self.member)
        other_lobby = self.client.get(
            reverse("family_pool_home",
                    kwargs={"family_slug": self.other_family.slug,
                            "pool_slug": self.other_pool.slug})
        )
        self.assertNotEqual(other_lobby.status_code, 200)
        own_lobby = self.client.get(
            reverse("family_pool_home",
                    kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug})
        )
        self.assertNotContains(own_lobby, 'data-testid="superuser-badge"')

    def test_commissioner_badge_is_scoped_to_the_current_family_owner_membership(self):
        lobby_url = reverse(
            "family_pool_home",
            kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug},
        )

        # Plain member: no badges.
        self.client.force_login(self.member)
        page = self.client.get(lobby_url)
        self.assertNotContains(page, 'data-testid="commissioner-badge"')
        self.assertNotContains(page, 'data-testid="superuser-badge"')

        # The family owner role (rebranded "Commissioner") earns the badge
        # without any profile flag.
        self.client.force_login(self.owner)
        page = self.client.get(lobby_url)
        self.assertContains(page, 'data-testid="commissioner-badge"')
        self.assertNotContains(page, 'data-testid="superuser-badge"')
        self.client.force_login(self.member)

        # A legacy profile flag alone no longer grants the family-scoped badge.
        UserProfile.objects.update_or_create(
            user=self.member, defaults={"is_commissioner": True}
        )
        page = self.client.get(lobby_url)
        self.assertNotContains(page, 'data-testid="commissioner-badge"')
        self.assertNotContains(page, 'data-testid="superuser-badge"')

        # Superuser without the owner membership still only shows the global
        # superuser badge.
        self.member.is_superuser = True
        self.member.save(update_fields=["is_superuser"])
        page = self.client.get(lobby_url)
        self.assertNotContains(page, 'data-testid="commissioner-badge"')
        self.assertContains(page, 'data-testid="superuser-badge"')

    def _settings_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_settings",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _banners_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_banners",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    @staticmethod
    def _default_scoring_fields(**overrides):
        """POST payload for the scoring/rules fields at their model defaults."""
        fields = {
            "win_points": 1,
            "tie_points": 0,
            "weekly_winner_points": 2,
            "primary_tiebreaker": "total_score",
            "secondary_tiebreaker": "combined_yards",
            "perfect_week_bonus_amount": 10,
            "entry_fee_amount": 0,
            "pick_type": "straight_up",
            "missed_pick_policy": "zero_points",
            "late_join_policy": "open",
            "payout_structure": "winner_takes_all",
        }
        fields.update(overrides)
        return fields

    def test_scoring_rules_roundtrip_and_render_on_rules_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self._settings_url(),
            {
                "family_name": self.family.name,
                "pool_name": self.pool.name,
                "picks_lock_mode": PoolSettings.PicksLockMode.KICKOFF,
                "allow_tiebreaker": "on",
                **self._default_scoring_fields(
                    win_points=2,
                    tie_points=1,
                    weekly_winner_points=5,
                    primary_tiebreaker="combined_yards",
                    secondary_tiebreaker="coin_flip",
                    perfect_week_bonus_amount=25,
                    entry_fee_amount=40,
                    missed_pick_policy="auto_home",
                    late_join_policy="lock_after_week_1",
                    payout_structure="ninety_ten",
                ),
                "include_playoffs": "on",
                "perfect_week_bonus_enabled": "on",
                "entry_fee_enabled": "on",
            },
        )
        self.assertRedirects(response, self._settings_url())

        settings = self.pool.settings
        settings.refresh_from_db()
        self.assertEqual(settings.win_points, 2)
        self.assertEqual(settings.tie_points, 1)
        self.assertEqual(settings.weekly_winner_points, 5)
        self.assertEqual(settings.primary_tiebreaker, "combined_yards")
        self.assertEqual(settings.secondary_tiebreaker, "coin_flip")
        self.assertTrue(settings.perfect_week_bonus_enabled)
        self.assertEqual(settings.perfect_week_bonus_amount, 25)
        self.assertTrue(settings.entry_fee_enabled)
        self.assertEqual(settings.entry_fee_amount, 40)
        self.assertEqual(settings.pick_type, "straight_up")
        self.assertEqual(settings.missed_pick_policy, "auto_home")
        # include_playoffs is disabled ("coming soon"): even a POST claiming
        # "on" must not flip the stored value.
        self.assertFalse(settings.include_playoffs)
        self.assertEqual(settings.late_join_policy, "lock_after_week_1")
        self.assertEqual(settings.payout_structure, "ninety_ten")

        # The rules page renders the configured values.
        rules_url = reverse(
            "family_pool_rules",
            kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug},
        )
        rules = self.client.get(rules_url)
        self.assertEqual(rules.status_code, 200)
        self.assertContains(rules, "+2")   # win points
        self.assertContains(rules, "+5")   # weekly winner bonus
        self.assertContains(rules, "$25")  # perfect week bonus (dollars)
        self.assertContains(rules, "$40")  # entry fee
        self.assertContains(rules, "coin flip")
        self.assertContains(rules, "auto-assigned the home team")
        self.assertContains(rules, "regular season only")
        self.assertContains(rules, "lock after Week 1")
        self.assertContains(rules, "1st gets 90%, 2nd gets 10%")

    def test_against_the_spread_pick_type_is_rejected_for_now(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self._settings_url(),
            {
                "family_name": self.family.name,
                "pool_name": self.pool.name,
                "allow_tiebreaker": "on",
                **self._default_scoring_fields(pick_type="against_spread"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "coming soon")
        settings = self.pool.settings
        settings.refresh_from_db()
        self.assertEqual(settings.pick_type, "straight_up")

    def test_lobby_uses_static_default_logo_when_family_has_no_canonical_logo(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "family_pool_home",
                kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "images/logo.png")

    def test_scoring_rules_validation_requires_value_when_bonus_enabled(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self._settings_url(),
            {
                "family_name": self.family.name,
                "pool_name": self.pool.name,
                "allow_tiebreaker": "on",
                **self._default_scoring_fields(perfect_week_bonus_amount=0, entry_fee_amount=0),
                "perfect_week_bonus_enabled": "on",
                "entry_fee_enabled": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set a bonus value")
        self.assertContains(response, "Set an entry fee amount")
        settings = self.pool.settings
        settings.refresh_from_db()
        self.assertFalse(settings.perfect_week_bonus_enabled)
        self.assertFalse(settings.entry_fee_enabled)

    def _members_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_members",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _member_update_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_member_update",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _invites_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_invites",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _invite_revoke_url(self, invitation, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_invite_revoke",
            kwargs={
                "family_slug": family.slug,
                "pool_slug": pool.slug,
                "invitation_id": invitation.id,
            },
        )

    def _invite_replace_url(self, invitation, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_invite_replace",
            kwargs={
                "family_slug": family.slug,
                "pool_slug": pool.slug,
                "invitation_id": invitation.id,
            },
        )

    def _picks_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_picks",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _picks_json_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_pick_user_picks",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _winners_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_winners",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _winner_candidate(self, user=None, *, game=None, pick=None, correct=True):
        user = user or self.member
        game = game or self._admin_game(game_id=9701, week="1")
        return GamePicks.objects.create(
            id=f"{self.pool.id}-{user.id}-{game.id}",
            pool=self.pool,
            userEmail=user.email,
            userID=str(user.id),
            uid=user.id,
            slug=game.slug,
            competition=game.competition,
            gameseason=game.gameseason,
            gameWeek=game.gameWeek,
            gameyear=game.gameyear,
            pick_game_id=game.id,
            pick=pick or game.homeTeamSlug,
            pick_correct=correct,
        )

    def _season_points(self, user=None, *, pool=None, week=1, points=0, bonus=0):
        user = user or self.member
        pool = pool or self.pool
        row = userSeasonPoints.objects.create(
            pool=pool,
            userEmail=user.email,
            userID=str(user.id),
            gameyear=str(pool.season)[:4],
            gameseason=pool.season,
            total_points=points + bonus,
        )
        setattr(row, f"week_{week}_points", points)
        setattr(row, f"week_{week}_bonus", bonus)
        row.save()
        return row

    def _admin_invitation(self, raw_code="ADMIN-CODE", **overrides):
        from pickem_homepage.views import hash_invite_code

        defaults = {
            "family": self.family,
            "pool": self.pool,
            "code_hash": hash_invite_code(raw_code),
            "role": FamilyMembership.Role.MEMBER,
            "expires_at": timezone.now() + timedelta(days=14),
            "max_uses": 1,
            "use_count": 1,
            "created_by": self.owner,
        }
        defaults.update(overrides)
        return FamilyInvitation.objects.create(**defaults)

    def _admin_game(self, *, game_id=9501, week="1", season=2526, competition="nfl", home="atl", away="ari"):
        return GamesAndScores.objects.create(
            id=game_id,
            slug=f"{away}-{home}-{season}-week-{week}",
            competition=competition,
            gameWeek=str(week),
            gameyear=str(season)[:4],
            gameseason=season,
            startTimestamp=timezone.now() + timedelta(days=1),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=game_id + 1,
            homeTeamSlug=home,
            homeTeamName=f"{home.upper()} Home",
            awayTeamId=game_id + 2,
            awayTeamSlug=away,
            awayTeamName=f"{away.upper()} Away",
        )

    def _manual_pick_payload(self, game, user=None, *, pick=None, week=None):
        user = user or self.member
        return {
            "target_user_id": str(user.id),
            "week": str(week or game.gameWeek),
            "game_id": str(game.id),
            "pick": pick or game.homeTeamSlug,
        }

    def test_anonymous_admin_hub_redirects_to_login(self):
        response = self.client.get(self._admin_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn(self._admin_url(), response["Location"])

    def test_outsider_and_inactive_membership_admin_hub_return_404(self):
        self.client.force_login(self.outsider)
        outsider_response = self.client.get(self._admin_url())
        self.assertEqual(outsider_response.status_code, 404)

        self.client.force_login(self.inactive_user)
        inactive_response = self.client.get(self._admin_url())
        self.assertEqual(inactive_response.status_code, 404)

    def test_active_member_admin_hub_returns_403(self):
        self.client.force_login(self.member)

        response = self.client.get(self._admin_url())

        self.assertEqual(response.status_code, 403)

    def test_admin_and_owner_admin_hub_render_only_current_family_audit_rows(self):
        for user in (self.owner, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)

                response = self.client.get(self._admin_url())

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pickem/family_admin.html")
                self.assertContains(response, "Smith Family")
                self.assertContains(response, "Main Pickem")
                self.assertContains(response, "Smith admin event")
                self.assertContains(response, "Invitation created")
                self.assertContains(response, "Settings")
                self.assertContains(response, self._settings_url())
                self.assertContains(response, "Invite Users")
                self.assertContains(response, self._invites_url())
                self.assertContains(response, "Picks")
                self.assertContains(response, self._picks_url())
                self.assertNotContains(response, "Jones Family")
                self.assertNotContains(response, "Jones private event")

    def test_admin_hub_includes_compact_polish_hooks(self):
        self.client.force_login(self.owner)

        response = self.client.get(self._admin_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-admin-page")
        self.assertContains(response, "admin-scoreboard-header")
        self.assertContains(response, "admin-compact-stat")
        self.assertContains(response, "admin-tool-card")
        self.assertContains(response, "adminCardMotion")
        self.assertContains(response, "gsap.min.js")

    def test_forged_family_pool_slug_combination_cannot_render_other_family_hub(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                "family_pool_admin",
                kwargs={
                    "family_slug": self.family.slug,
                    "pool_slug": self.other_pool.slug,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_nav_affordance_visible_only_for_tenant_admin_roles(self):
        for user in (self.owner, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)

                response = self.client.get(
                    reverse(
                        "family_pool_home",
                        kwargs={
                            "family_slug": self.family.slug,
                            "pool_slug": self.pool.slug,
                        },
                    )
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-testid="tenant-admin-nav"')
                self.assertContains(response, self._admin_url())

        self.client.force_login(self.member)
        member_response = self.client.get(
            reverse(
                "family_pool_home",
                kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug},
            )
        )

        self.assertEqual(member_response.status_code, 200)
        self.assertNotContains(member_response, 'data-testid="tenant-admin-nav"')
        self.assertNotContains(member_response, self._admin_url())

    def test_admin_and_owner_settings_page_renders_current_context_without_banner_leakage(self):
        # Banner management (the publish form + "Recent banners" list) moved
        # to its own page (family_pool_admin_banners); the settings page keeps
        # only a link to it. Note: the active banner *content* still shows
        # via the site-wide banner context processor on every page, so this
        # only checks that the management UI itself is gone.
        SiteBanner.objects.create(
            family=self.other_family,
            title="Jones-only draft note",
            description="Jones private banner metadata",
            is_active=True,
        )

        for user in (self.owner, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)

                response = self.client.get(self._settings_url())

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pickem/family_admin_settings.html")
                self.assertContains(response, "Smith Family")
                self.assertContains(response, "Main Pickem")
                self.assertContains(response, "Pick locking")
                self.assertContains(response, "Tiebreakers")
                self.assertContains(response, self._banners_url())
                self.assertNotContains(response, "Recent banners")
                self.assertNotContains(response, "Publish Banner")
                self.assertNotContains(response, "Jones Family")
                self.assertNotContains(response, "Jones-only draft note")
                self.assertNotContains(response, "Jones private banner metadata")

    def test_admin_and_owner_banners_page_renders_and_scopes_to_current_family(self):
        SiteBanner.objects.create(
            family=self.family,
            title="Smith-only draft note",
            description="Smith private banner metadata",
            is_active=True,
        )
        SiteBanner.objects.create(
            family=self.other_family,
            title="Jones-only draft note",
            description="Jones private banner metadata",
            is_active=True,
        )

        for user in (self.owner, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)

                response = self.client.get(self._banners_url())

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pickem/family_admin_banners.html")
                self.assertContains(response, "Smith-only draft note")
                self.assertNotContains(response, "Jones-only draft note")
                self.assertNotContains(response, "Jones private banner metadata")

        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self._banners_url()).status_code, 403)

    def test_banners_page_publish_and_deactivate_scoped_to_current_family(self):
        jones_banner = SiteBanner.objects.create(
            family=self.other_family, title="Jones active banner", is_active=True,
        )
        self.client.force_login(self.admin_user)

        publish = self.client.post(
            self._banners_url(),
            {
                "action": "create_banner",
                "title": "Playoffs are here",
                "description": "Good luck everyone",
                "banner_type": "info",
                "icon": "fas fa-star",
            },
        )
        self.assertRedirects(publish, self._banners_url())
        new_banner = SiteBanner.objects.get(family=self.family, title="Playoffs are here")
        self.assertTrue(new_banner.is_active)

        deactivate = self.client.post(
            self._banners_url(),
            {"action": "deactivate_banner", "banner_id": new_banner.id},
        )
        self.assertRedirects(deactivate, self._banners_url())
        new_banner.refresh_from_db()
        self.assertFalse(new_banner.is_active)

        # Cannot deactivate another family's banner via this endpoint.
        cross_family_attempt = self.client.post(
            self._banners_url(),
            {"action": "deactivate_banner", "banner_id": jones_banner.id},
        )
        self.assertRedirects(cross_family_attempt, self._banners_url())
        jones_banner.refresh_from_db()
        self.assertTrue(jones_banner.is_active)

    def test_settings_post_updates_only_current_tenant_and_audits_safe_metadata(self):
        other_settings = self.other_pool.settings
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self._settings_url(),
            {
                "family_name": "Updated Smith Family",
                "pool_name": "Updated Main Pickem",
                "allow_tiebreaker": "on",
                **self._default_scoring_fields(
                    picks_lock_mode=PoolSettings.PicksLockMode.SUNDAY_1PM,
                ),
                "family_id": self.other_family.id,
                "pool_id": self.other_pool.id,
                "site_banner_id": SiteBanner.objects.create(
                    family=self.other_family,
                    title="Do not touch me",
                    description="Other family banner secret",
                    is_active=True,
                ).id,
                "secret": "csrf-token-or-session-secret",
            },
        )

        self.assertRedirects(response, self._settings_url())

        self.family.refresh_from_db()
        self.pool.refresh_from_db()
        self.pool.settings.refresh_from_db()
        self.other_family.refresh_from_db()
        self.other_pool.refresh_from_db()
        other_settings.refresh_from_db()

        self.assertEqual(self.family.name, "Updated Smith Family")
        self.assertEqual(self.pool.name, "Updated Main Pickem")
        self.assertEqual(
            self.pool.settings.picks_lock_mode, PoolSettings.PicksLockMode.SUNDAY_1PM
        )
        self.assertTrue(self.pool.settings.allow_tiebreaker)
        self.assertEqual(self.other_family.name, "Jones Family")
        self.assertEqual(self.other_pool.name, "Main Pickem")
        self.assertEqual(
            other_settings.picks_lock_mode, PoolSettings.PicksLockMode.KICKOFF
        )
        self.assertTrue(other_settings.allow_tiebreaker)

        audit = FamilyAuditLog.objects.get(
            family=self.family,
            pool=self.pool,
            actor=self.admin_user,
            action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
            target_type="AdminSettings",
        )
        self.assertEqual(audit.target_id, str(self.pool.id))
        self.assertEqual(audit.metadata["target_type"], "family_pool_settings")
        self.assertEqual(audit.metadata["family_id"], self.family.id)
        self.assertEqual(audit.metadata["pool_id"], self.pool.id)
        self.assertIn("family.name", audit.metadata["changed_fields"])
        self.assertIn("pool.name", audit.metadata["changed_fields"])
        self.assertIn("settings.picks_lock_mode", audit.metadata["changed_fields"])
        self.assertNotIn("secret", str(audit.metadata).lower())
        self.assertNotIn("csrf", str(audit.metadata).lower())
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.other_family,
                action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
            ).exists()
        )

    def test_settings_post_denies_member_outsider_inactive_anonymous_without_mutation(self):
        for user, expected_status in (
            (self.member, 403),
            (self.outsider, 404),
            (self.inactive_user, 404),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)

                response = self.client.post(
                    self._settings_url(),
                    {
                        "family_name": "Unauthorized Name",
                        "pool_name": "Unauthorized Pool",
                        "allow_tiebreaker": "on",
                    },
                )

                self.assertEqual(response.status_code, expected_status)
                self.family.refresh_from_db()
                self.pool.refresh_from_db()
                self.assertEqual(self.family.name, "Smith Family")
                self.assertEqual(self.pool.name, "Main Pickem")

        self.client.logout()
        response = self.client.post(
            self._settings_url(),
            {
                "family_name": "Anonymous Name",
                "pool_name": "Anonymous Pool",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.family.refresh_from_db()
        self.pool.refresh_from_db()
        self.assertEqual(self.family.name, "Smith Family")
        self.assertEqual(self.pool.name, "Main Pickem")

    def test_settings_post_requires_csrf_and_does_not_deactivate_banners(self):
        smith_banner = SiteBanner.objects.create(
            family=self.family,
            title="Smith active banner",
            is_active=True,
        )
        jones_banner = SiteBanner.objects.create(
            family=self.other_family,
            title="Jones active banner",
            is_active=True,
        )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)

        response = csrf_client.post(
            self._settings_url(),
            {
                "family_name": "CSRF Name",
                "pool_name": "CSRF Pool",
                "allow_tiebreaker": "on",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.family.refresh_from_db()
        self.pool.refresh_from_db()
        smith_banner.refresh_from_db()
        jones_banner.refresh_from_db()
        self.assertEqual(self.family.name, "Smith Family")
        self.assertEqual(self.pool.name, "Main Pickem")
        self.assertTrue(smith_banner.is_active)
        self.assertTrue(jones_banner.is_active)

    def test_member_list_shows_current_family_members_only_to_admins_and_owners(self):
        inactive_member = self._membership(
            User.objects.create_user(
                "admin-inactive-member",
                email="inactive-member@example.com",
                password="pass",
            ),
            self.family,
            FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.INACTIVE,
        )
        other_member = self._membership(
            User.objects.create_user(
                "jones-member",
                email="jones-member@example.com",
                password="pass",
            ),
            self.other_family,
            FamilyMembership.Role.MEMBER,
        )

        for user in (self.owner, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)

                response = self.client.get(self._members_url())

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pickem/family_admin_members.html")
                self.assertContains(response, "admin-owner")
                self.assertContains(response, "admin-user")
                self.assertContains(response, "admin-member")
                self.assertContains(response, inactive_member.user.username)
                self.assertNotContains(response, other_member.user.username)
                self.assertNotContains(response, "jones-member@example.com")

    def test_member_list_denies_member_outsider_inactive_and_anonymous(self):
        for user, expected_status in (
            (self.member, 403),
            (self.outsider, 404),
            (self.inactive_user, 404),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(self._members_url())
                self.assertEqual(response.status_code, expected_status)

        self.client.logout()
        response = self.client.get(self._members_url())
        self.assertEqual(response.status_code, 302)

    def test_member_list_owner_controls_and_admin_readonly_state_are_visible(self):
        self.client.force_login(self.owner)
        owner_response = self.client.get(self._members_url())

        self.assertEqual(owner_response.status_code, 200)
        self.assertContains(owner_response, 'data-testid="family-admin-members"')
        self.assertContains(owner_response, 'data-testid="membership-update-form"')
        self.assertContains(owner_response, self._member_update_url())
        self.assertContains(owner_response, "Save")

        self.client.force_login(self.admin_user)
        admin_response = self.client.get(self._members_url())

        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, 'data-testid="family-admin-members"')
        self.assertContains(admin_response, 'data-testid="membership-readonly-state"')
        self.assertContains(admin_response, "Commissioner role required")
        self.assertNotContains(admin_response, 'data-testid="membership-update-form"')
        self.assertNotContains(admin_response, self._member_update_url())

    def test_owner_can_update_member_role_status_and_audit_safe_metadata(self):
        self.client.force_login(self.owner)
        member_membership = FamilyMembership.objects.get(
            family=self.family,
            user=self.member,
        )

        response = self.client.post(
            self._member_update_url(),
            {
                "membership_id": member_membership.id,
                "role": FamilyMembership.Role.ADMIN,
                "status": FamilyMembership.Status.INACTIVE,
                "user_id": self.outsider.id,
                "family_id": self.other_family.id,
                "secret": "csrf-or-session-secret",
            },
        )

        self.assertRedirects(response, self._members_url())
        member_membership.refresh_from_db()
        self.assertEqual(member_membership.role, FamilyMembership.Role.ADMIN)
        self.assertEqual(member_membership.status, FamilyMembership.Status.INACTIVE)

        audit = FamilyAuditLog.objects.get(
            family=self.family,
            pool=self.pool,
            actor=self.owner,
            action=FamilyAuditLog.Action.MEMBERSHIP_UPDATED,
            target_type="FamilyMembership",
            target_id=str(member_membership.id),
        )
        self.assertEqual(audit.metadata["target_membership_id"], member_membership.id)
        self.assertEqual(audit.metadata["target_user_id"], self.member.id)
        self.assertEqual(audit.metadata["previous_role"], FamilyMembership.Role.MEMBER)
        self.assertEqual(audit.metadata["new_role"], FamilyMembership.Role.ADMIN)
        self.assertEqual(audit.metadata["previous_status"], FamilyMembership.Status.ACTIVE)
        self.assertEqual(audit.metadata["new_status"], FamilyMembership.Status.INACTIVE)
        self.assertEqual(audit.metadata["actor_id"], self.owner.id)
        self.assertNotIn("secret", str(audit.metadata).lower())
        self.assertNotIn("csrf", str(audit.metadata).lower())

    def test_admin_cannot_perform_owner_sensitive_role_or_status_mutations(self):
        member_membership = FamilyMembership.objects.get(
            family=self.family,
            user=self.member,
        )
        self.client.force_login(self.admin_user)

        for role, status in (
            (FamilyMembership.Role.ADMIN, FamilyMembership.Status.ACTIVE),
            (FamilyMembership.Role.OWNER, FamilyMembership.Status.ACTIVE),
            (FamilyMembership.Role.MEMBER, FamilyMembership.Status.INACTIVE),
        ):
            with self.subTest(role=role, status=status):
                response = self.client.post(
                    self._member_update_url(),
                    {
                        "membership_id": member_membership.id,
                        "role": role,
                        "status": status,
                    },
                )

                self.assertEqual(response.status_code, 403)
                member_membership.refresh_from_db()
                self.assertEqual(member_membership.role, FamilyMembership.Role.MEMBER)
                self.assertEqual(member_membership.status, FamilyMembership.Status.ACTIVE)

        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.family,
                action=FamilyAuditLog.Action.MEMBERSHIP_UPDATED,
                target_id=str(member_membership.id),
            ).exists()
        )

    def test_last_active_owner_cannot_be_demoted_or_deactivated(self):
        owner_membership = FamilyMembership.objects.get(
            family=self.family,
            user=self.owner,
        )
        self.client.force_login(self.owner)

        for role, status in (
            (FamilyMembership.Role.ADMIN, FamilyMembership.Status.ACTIVE),
            (FamilyMembership.Role.OWNER, FamilyMembership.Status.INACTIVE),
        ):
            with self.subTest(role=role, status=status):
                response = self.client.post(
                    self._member_update_url(),
                    {
                        "membership_id": owner_membership.id,
                        "role": role,
                        "status": status,
                    },
                )

                self.assertEqual(response.status_code, 400)
                owner_membership.refresh_from_db()
                self.assertEqual(owner_membership.role, FamilyMembership.Role.OWNER)
                self.assertEqual(owner_membership.status, FamilyMembership.Status.ACTIVE)

    def test_forged_cross_family_membership_id_does_not_leak_or_mutate(self):
        other_member = self._membership(
            User.objects.create_user(
                "jones-target",
                email="jones-target@example.com",
                password="pass",
            ),
            self.other_family,
            FamilyMembership.Role.MEMBER,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            self._member_update_url(),
            {
                "membership_id": other_member.id,
                "role": FamilyMembership.Role.OWNER,
                "status": FamilyMembership.Status.INACTIVE,
                "user_id": other_member.user_id,
            },
        )

        self.assertEqual(response.status_code, 404)
        other_member.refresh_from_db()
        self.assertEqual(other_member.role, FamilyMembership.Role.MEMBER)
        self.assertEqual(other_member.status, FamilyMembership.Status.ACTIVE)
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.other_family,
                action=FamilyAuditLog.Action.MEMBERSHIP_UPDATED,
                target_id=str(other_member.id),
            ).exists()
        )

    def test_membership_update_requires_csrf(self):
        member_membership = FamilyMembership.objects.get(
            family=self.family,
            user=self.member,
        )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)

        response = csrf_client.post(
            self._member_update_url(),
            {
                "membership_id": member_membership.id,
                "role": FamilyMembership.Role.ADMIN,
                "status": FamilyMembership.Status.INACTIVE,
            },
        )

        self.assertEqual(response.status_code, 403)
        member_membership.refresh_from_db()
        self.assertEqual(member_membership.role, FamilyMembership.Role.MEMBER)
        self.assertEqual(member_membership.status, FamilyMembership.Status.ACTIVE)

    def test_admin_invite_page_lists_safe_current_family_metadata_only(self):
        current_invite = self._admin_invitation(
            raw_code="SAFE-LIST-CODE",
            role=FamilyMembership.Role.MEMBER,
            recipient_email="target@example.com",
            use_count=3,
            max_uses=1,
        )
        current_invite.is_revoked = True
        current_invite.save(update_fields=["is_revoked", "updated_at"])
        self._admin_invitation(
            raw_code="OPEN-INVITE-CODE",
            role=FamilyMembership.Role.MEMBER,
            recipient_email="pending@example.com",
            use_count=0,
            max_uses=1,
        )
        self._admin_invitation(
            raw_code="OTHER-FAMILY-CODE",
            family=self.other_family,
            pool=self.other_pool,
            created_by=self.outsider,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(self._invites_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/family_admin_invites.html")
        self.assertContains(response, "Smith Family")
        self.assertContains(response, "Member")
        self.assertContains(response, "Yes")
        self.assertContains(response, "No")
        self.assertContains(response, "target@example.com")
        self.assertContains(response, "admin-owner")
        self.assertContains(response, "Revoked")
        self.assertContains(response, str(current_invite.id))
        self.assertContains(response, "pending@example.com")
        self.assertNotContains(response, "SAFE-LIST-CODE")
        self.assertNotContains(response, current_invite.code_hash)
        self.assertNotContains(response, "OTHER-FAMILY-CODE")
        self.assertNotContains(response, "Jones Family")

    def test_admin_and_owner_can_create_member_invites_with_one_time_link_display(self):
        for user in (self.owner, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                before_count = FamilyInvitation.objects.filter(family=self.family).count()

                response = self.client.post(
                    self._invites_url(),
                    {
                        "role": FamilyMembership.Role.MEMBER,
                        "recipient_email": " TargetUser@Example.com ",
                        "expires_in_days": "21",
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pickem/family_admin_invites.html")
                invitation = FamilyInvitation.objects.filter(
                    family=self.family,
                    created_by=user,
                ).latest("created_at")
                invite_link = response.context["invite_link"]
                self.assertEqual(
                    FamilyInvitation.objects.filter(family=self.family).count(),
                    before_count + 1,
                )
                self.assertEqual(invitation.role, FamilyMembership.Role.MEMBER)
                self.assertEqual(invitation.recipient_email, "targetuser@example.com")
                self.assertEqual(invitation.max_uses, 1)
                self.assertEqual(invitation.use_count, 0)
                self.assertFalse(invitation.is_revoked)
                self.assertTrue(invitation.code_hash.startswith("sha256:"))
                self.assertContains(response, invite_link)
                self.assertIn("/invites/", invite_link)
                audit = FamilyAuditLog.objects.get(
                    family=self.family,
                    actor=user,
                    action=FamilyAuditLog.Action.INVITATION_CREATED,
                    target_id=str(invitation.id),
                )
                self.assertEqual(audit.metadata["recipient_email"], "targetuser@example.com")
                self.assertNotIn(invite_link, str(audit.metadata))

                reload_response = self.client.get(self._invites_url())
                self.assertNotContains(reload_response, invite_link)
                self.assertNotContains(reload_response, invitation.code_hash)

    @patch("pickem_homepage.views.transaction.on_commit", side_effect=lambda callback: callback())
    @patch("pickem_homepage.views.send_family_invitation_email")
    @patch("pickem_homepage.views.resend_invite_email_is_configured", return_value=True)
    def test_targeted_invite_queues_resend_delivery_when_configured(
        self,
        configured_mock,
        send_mock,
        on_commit_mock,
    ):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self._invites_url(),
            {
                "role": FamilyMembership.Role.MEMBER,
                "recipient_email": "target@example.com",
                "expires_in_days": "14",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invite email will be sent to target@example.com.")
        configured_mock.assert_called_once_with()
        on_commit_mock.assert_called_once()
        send_mock.assert_called_once_with(
            invitation=ANY,
            invite_link=ANY,
            invite_code=ANY,
        )

    @patch("pickem_homepage.views.send_family_invitation_email")
    @patch("pickem_homepage.views.resend_invite_email_is_configured", return_value=False)
    def test_targeted_invite_warns_when_resend_not_configured(
        self,
        configured_mock,
        send_mock,
    ):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self._invites_url(),
            {
                "role": FamilyMembership.Role.MEMBER,
                "recipient_email": "target@example.com",
                "expires_in_days": "14",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Invite saved for target@example.com, but Resend is not configured yet so no email was sent. Use the invite link below.",
        )
        configured_mock.assert_called_once_with()
        send_mock.assert_not_called()

    @patch("pickem_homepage.views.transaction.on_commit", side_effect=lambda callback: callback())
    @patch("pickem_homepage.views.send_family_invitation_email")
    @patch("pickem_homepage.views.resend_invite_email_is_configured", return_value=True)
    def test_replacing_targeted_invite_requeues_resend_delivery_when_configured(
        self,
        configured_mock,
        send_mock,
        on_commit_mock,
    ):
        invite = self._admin_invitation(raw_code="REPLACE-TARGET", recipient_email="target@example.com")
        self.client.force_login(self.admin_user)

        response = self.client.post(self._invite_replace_url(invite))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invite replaced. Share the new invite link now.")
        self.assertContains(response, "Invite email will be sent to target@example.com.")
        configured_mock.assert_called_once_with()
        on_commit_mock.assert_called_once()
        send_mock.assert_called_once_with(
            invitation=ANY,
            invite_link=ANY,
            invite_code=ANY,
        )

    @patch("pickem_homepage.views.send_family_invitation_email")
    @patch("pickem_homepage.views.resend_invite_email_is_configured", return_value=False)
    def test_replacing_targeted_invite_warns_when_resend_not_configured(
        self,
        configured_mock,
        send_mock,
    ):
        invite = self._admin_invitation(raw_code="REPLACE-TARGET-WARN", recipient_email="target@example.com")
        self.client.force_login(self.admin_user)

        response = self.client.post(self._invite_replace_url(invite))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Invite saved for target@example.com, but Resend is not configured yet so no email was sent. Use the invite link below.",
        )
        configured_mock.assert_called_once_with()
        send_mock.assert_not_called()

    def test_admin_cannot_create_admin_role_invite_but_owner_can(self):
        self.client.force_login(self.admin_user)

        admin_response = self.client.post(
            self._invites_url(),
            {
                "role": FamilyMembership.Role.ADMIN,
                "expires_in_days": "14",
                "recipient_email": "admin-target@example.com",
            },
        )

        self.assertEqual(admin_response.status_code, 400)
        self.assertFalse(
            FamilyInvitation.objects.filter(
                family=self.family,
                role=FamilyMembership.Role.ADMIN,
            ).exists()
        )

        self.client.force_login(self.owner)
        owner_response = self.client.post(
            self._invites_url(),
            {
                "role": FamilyMembership.Role.ADMIN,
                "expires_in_days": "14",
                "recipient_email": "admin-target@example.com",
            },
        )

        self.assertEqual(owner_response.status_code, 200)
        self.assertTrue(
            FamilyInvitation.objects.filter(
                family=self.family,
                role=FamilyMembership.Role.ADMIN,
                created_by=self.owner,
            ).exists()
        )

    def test_invite_revoke_and_replace_are_current_family_scoped_and_audited(self):
        invite = self._admin_invitation(raw_code="REVOKE-ME")
        self.client.force_login(self.admin_user)

        revoke_response = self.client.post(self._invite_revoke_url(invite))

        self.assertRedirects(revoke_response, self._invites_url())
        invite.refresh_from_db()
        self.assertTrue(invite.is_revoked)
        revoke_audit = FamilyAuditLog.objects.get(
            family=self.family,
            actor=self.admin_user,
            action=FamilyAuditLog.Action.INVITATION_REVOKED,
            target_id=str(invite.id),
        )
        self.assertEqual(revoke_audit.metadata["role"], FamilyMembership.Role.MEMBER)
        self.assertNotIn("REVOKE-ME", str(revoke_audit.metadata))

        replacement_source = self._admin_invitation(raw_code="REPLACE-ME")
        replace_response = self.client.post(self._invite_replace_url(replacement_source))

        self.assertEqual(replace_response.status_code, 200)
        replacement_source.refresh_from_db()
        self.assertTrue(replacement_source.is_revoked)
        replacement = FamilyInvitation.objects.exclude(id__in=[invite.id, replacement_source.id]).get(
            family=self.family,
            created_by=self.admin_user,
        )
        self.assertEqual(replacement.role, replacement_source.role)
        self.assertEqual(replacement.max_uses, 1)
        self.assertContains(replace_response, replace_response.context["invite_link"])
        self.assertNotIn("REPLACE-ME", str(FamilyAuditLog.objects.filter(
            family=self.family,
            target_id=str(replacement.id),
        ).values_list("metadata", flat=True)))

    def test_cross_family_invitation_ids_cannot_be_revoked_or_replaced(self):
        other_invite = self._admin_invitation(
            raw_code="JONES-SECRET",
            family=self.other_family,
            pool=self.other_pool,
            created_by=self.outsider,
        )
        self.client.force_login(self.owner)

        revoke_response = self.client.post(self._invite_revoke_url(other_invite))
        replace_response = self.client.post(self._invite_replace_url(other_invite))

        self.assertEqual(revoke_response.status_code, 404)
        self.assertEqual(replace_response.status_code, 404)
        other_invite.refresh_from_db()
        self.assertFalse(other_invite.is_revoked)
        self.assertEqual(
            FamilyInvitation.objects.filter(family=self.other_family).count(),
            1,
        )
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.other_family,
                action__in=[
                    FamilyAuditLog.Action.INVITATION_REVOKED,
                    FamilyAuditLog.Action.INVITATION_CREATED,
                ],
                target_id=str(other_invite.id),
            ).exists()
        )

    def test_invite_mutations_deny_member_outsider_inactive_anonymous_and_csrf(self):
        invite = self._admin_invitation(raw_code="NO-MUTATE")

        for user, expected_status in (
            (self.member, 403),
            (self.outsider, 404),
            (self.inactive_user, 404),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                create_response = self.client.post(
                    self._invites_url(),
                    {
                        "role": FamilyMembership.Role.MEMBER,
                        "expires_in_days": "14",
                        "recipient_email": "blocked@example.com",
                    },
                )
                revoke_response = self.client.post(self._invite_revoke_url(invite))
                replace_response = self.client.post(self._invite_replace_url(invite))

                self.assertEqual(create_response.status_code, expected_status)
                self.assertEqual(revoke_response.status_code, expected_status)
                self.assertEqual(replace_response.status_code, expected_status)
                invite.refresh_from_db()
                self.assertFalse(invite.is_revoked)

        self.client.logout()
        self.assertEqual(self.client.post(self._invites_url()).status_code, 302)
        self.assertEqual(self.client.post(self._invite_revoke_url(invite)).status_code, 302)
        self.assertEqual(self.client.post(self._invite_replace_url(invite)).status_code, 302)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)
        csrf_create = csrf_client.post(
            self._invites_url(),
            {
                "role": FamilyMembership.Role.MEMBER,
                "expires_in_days": "14",
                "recipient_email": "blocked@example.com",
            },
        )
        csrf_revoke = csrf_client.post(self._invite_revoke_url(invite))
        csrf_replace = csrf_client.post(self._invite_replace_url(invite))

        self.assertEqual(csrf_create.status_code, 403)
        self.assertEqual(csrf_revoke.status_code, 403)
        self.assertEqual(csrf_replace.status_code, 403)
        invite.refresh_from_db()
        self.assertFalse(invite.is_revoked)

    def test_create_invite_rejected_when_entries_locked(self):
        settings = self.pool.settings
        settings.late_join_policy = PoolSettings.LateJoinPolicy.LOCK_AFTER_WEEK_1
        settings.save(update_fields=["late_join_policy"])
        self.client.force_login(self.owner)
        before_count = FamilyInvitation.objects.count()

        with patch("pickem_api.weekly_winners.week_is_complete", return_value=True):
            response = self.client.post(
                self._invites_url(),
                {
                    "role": FamilyMembership.Role.MEMBER,
                    "recipient_email": "blocked@example.com",
                    "expires_in_days": "14",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "pickem/family_admin_invites.html")
        self.assertEqual(FamilyInvitation.objects.count(), before_count)
        self.assertContains(
            response,
            "Entries are locked for this pool, so new invites can&#x27;t be created.",
            status_code=400,
        )

    def test_manual_pick_page_lists_current_family_users_and_current_pool_games(self):
        current_game = self._admin_game(game_id=9601, week="1")
        other_week_game = self._admin_game(game_id=9602, week="2", home="mia", away="buf")
        other_season_game = self._admin_game(game_id=9603, week="1", season=2527, home="dal", away="nyg")
        other_competition_game = self._admin_game(game_id=9604, week="1", competition="college", home="osu", away="um")
        other_member = self._membership(
            User.objects.create_user(
                "jones-admin-picks",
                email="jones-admin-picks@example.com",
                password="pass",
            ),
            self.other_family,
            FamilyMembership.Role.MEMBER,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(self._picks_url(), {"week": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/family_admin_picks.html")
        self.assertContains(response, "Smith Family")
        self.assertContains(response, "Manual Picks")
        self.assertContains(response, self.member.username)
        self.assertContains(response, self.admin_user.username)
        self.assertContains(response, current_game.homeTeamName)
        self.assertContains(response, current_game.awayTeamName)
        self.assertNotContains(response, other_member.user.username)
        self.assertNotContains(response, other_week_game.homeTeamName)
        self.assertNotContains(response, other_season_game.homeTeamName)
        self.assertNotContains(response, other_competition_game.homeTeamName)

    def test_admin_and_owner_can_retrieve_current_pool_picks_for_active_family_users_only(self):
        game = self._admin_game(game_id=9610, week="1")
        other_game = self._admin_game(game_id=9611, week="1", home="mia", away="buf")
        GamePicks.objects.create(
            id=f"{self.pool.id}-{self.member.id}-{game.id}",
            pool=self.pool,
            userEmail=self.member.email,
            userID=str(self.member.id),
            uid=self.member.id,
            slug=game.slug,
            competition=game.competition,
            gameseason=game.gameseason,
            gameWeek=game.gameWeek,
            gameyear=game.gameyear,
            pick_game_id=game.id,
            pick=game.awayTeamSlug,
            pick_correct=True,
        )
        GamePicks.objects.create(
            id=f"{self.other_pool.id}-{self.outsider.id}-{other_game.id}",
            pool=self.other_pool,
            userEmail=self.outsider.email,
            userID=str(self.outsider.id),
            uid=self.outsider.id,
            slug=other_game.slug,
            competition=other_game.competition,
            gameseason=other_game.gameseason,
            gameWeek=other_game.gameWeek,
            gameyear=other_game.gameyear,
            pick_game_id=other_game.id,
            pick=other_game.homeTeamSlug,
        )

        for user in (self.owner, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(
                    self._picks_json_url(),
                    {"target_user_id": self.member.id, "week": "1"},
                    HTTP_ACCEPT="application/json",
                )

                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertTrue(data["success"])
                self.assertEqual(data["target_user"]["id"], self.member.id)
                self.assertEqual(data["picks"][str(game.id)]["pick"], game.awayTeamSlug)
                self.assertEqual(data["picks"][str(game.id)]["pick_id"], f"{self.pool.id}-{self.member.id}-{game.id}")
                self.assertNotIn(str(other_game.id), data["picks"])

        self.client.force_login(self.owner)
        cross_family_response = self.client.get(
            self._picks_json_url(),
            {"target_user_id": self.outsider.id, "week": "1"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(cross_family_response.status_code, 404)
        self.assertNotIn("Jones", cross_family_response.content.decode())
        self.assertNotIn(self.outsider.email, cross_family_response.content.decode())

    def test_manual_pick_submission_server_derives_scope_and_writes_audit(self):
        game = self._admin_game(game_id=9620, week="3")
        other_pool_game = self._admin_game(game_id=9621, week="3", home="mia", away="buf")
        GamePicks.objects.create(
            id=f"{self.other_pool.id}-{self.outsider.id}-{other_pool_game.id}",
            pool=self.other_pool,
            userEmail=self.outsider.email,
            userID=str(self.outsider.id),
            uid=self.outsider.id,
            slug=other_pool_game.slug,
            competition=other_pool_game.competition,
            gameseason=other_pool_game.gameseason,
            gameWeek=other_pool_game.gameWeek,
            gameyear=other_pool_game.gameyear,
            pick_game_id=other_pool_game.id,
            pick=other_pool_game.awayTeamSlug,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self._picks_url(),
            {
                **self._manual_pick_payload(game, pick=game.homeTeamSlug),
                "pool": self.other_pool.id,
                "pool_id": self.other_pool.id,
                "season": 1999,
                "gameseason": 1999,
                "competition": "forged",
                "correctness": "true",
                "pick_correct": "true",
                "pick_id": "forged-pick-id",
                "id": "forged-id",
                "user_id": self.outsider.id,
            },
        )

        self.assertRedirects(response, self._picks_url() + "?week=3")
        pick = GamePicks.objects.get(pool=self.pool, userID=str(self.member.id), pick_game_id=game.id)
        self.assertEqual(pick.id, f"{self.pool.id}-{self.member.id}-{game.id}")
        self.assertEqual(pick.userEmail, self.member.email)
        self.assertEqual(pick.uid, self.member.id)
        self.assertEqual(pick.slug, game.slug)
        self.assertEqual(pick.gameseason, self.pool.season)
        self.assertEqual(pick.competition, self.pool.competition)
        self.assertEqual(pick.gameWeek, "3")
        self.assertEqual(pick.pick, game.homeTeamSlug)
        self.assertFalse(pick.pick_correct)
        self.assertFalse(GamePicks.objects.filter(pool=self.pool, userID=str(self.outsider.id)).exists())

        audit = FamilyAuditLog.objects.get(
            family=self.family,
            pool=self.pool,
            actor=self.admin_user,
            action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED,
            target_type="GamePicks",
            target_id=pick.id,
        )
        self.assertIsNone(audit.metadata["previous_pick"])
        self.assertEqual(audit.metadata["new_pick"], game.homeTeamSlug)
        self.assertEqual(audit.metadata["target_user_id"], self.member.id)
        self.assertEqual(audit.metadata["game_id"], game.id)
        self.assertEqual(audit.metadata["week"], "3")
        self.assertEqual(audit.metadata["actor_id"], self.admin_user.id)
        self.assertNotIn("forged", str(audit.metadata).lower())
        self.assertNotIn("csrf", str(audit.metadata).lower())

    def test_manual_pick_update_records_previous_pick_and_ignores_correctness_forgery(self):
        game = self._admin_game(game_id=9630, week="4")
        existing = GamePicks.objects.create(
            id=f"{self.pool.id}-{self.member.id}-{game.id}",
            pool=self.pool,
            userEmail=self.member.email,
            userID=str(self.member.id),
            uid=self.member.id,
            slug=game.slug,
            competition=game.competition,
            gameseason=game.gameseason,
            gameWeek=game.gameWeek,
            gameyear=game.gameyear,
            pick_game_id=game.id,
            pick=game.homeTeamSlug,
            pick_correct=True,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            self._picks_url(),
            {
                **self._manual_pick_payload(game, pick=game.awayTeamSlug),
                "pick_correct": "true",
            },
        )

        self.assertRedirects(response, self._picks_url() + "?week=4")
        existing.refresh_from_db()
        self.assertEqual(existing.pick, game.awayTeamSlug)
        self.assertFalse(existing.pick_correct)
        audit = FamilyAuditLog.objects.get(
            family=self.family,
            action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED,
            target_id=existing.id,
        )
        self.assertEqual(audit.metadata["previous_pick"], game.homeTeamSlug)
        self.assertEqual(audit.metadata["new_pick"], game.awayTeamSlug)

    def test_manual_pick_submission_rejects_locked_games(self):
        game = self._admin_game(game_id=9635, week="4")
        GamesAndScores.objects.filter(id=game.id).update(
            startTimestamp=timezone.now() - timedelta(minutes=5),
            statusType="inprogress",
            statusTitle="In Progress",
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(self._picks_url(), self._manual_pick_payload(game))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(GamePicks.objects.filter(pool=self.pool, pick_game_id=game.id).exists())
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.family,
                action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED,
            ).exists()
        )

    def test_manual_pick_submission_rejects_invalid_team_cross_family_user_and_wrong_game_scope(self):
        game = self._admin_game(game_id=9640, week="5")
        wrong_week_game = self._admin_game(game_id=9641, week="6", home="mia", away="buf")
        wrong_season_game = self._admin_game(game_id=9642, week="5", season=2527, home="dal", away="nyg")
        wrong_competition_game = self._admin_game(game_id=9643, week="5", competition="college", home="osu", away="um")
        self.client.force_login(self.admin_user)

        cases = [
            ({**self._manual_pick_payload(game, pick="not-a-team")}, 400),
            ({**self._manual_pick_payload(game, user=self.outsider)}, 404),
            ({**self._manual_pick_payload(wrong_week_game, week="5", pick=wrong_week_game.homeTeamSlug)}, 404),
            ({**self._manual_pick_payload(wrong_season_game, pick=wrong_season_game.homeTeamSlug)}, 404),
            ({**self._manual_pick_payload(wrong_competition_game, pick=wrong_competition_game.homeTeamSlug)}, 404),
        ]
        for payload, expected_status in cases:
            with self.subTest(payload=payload):
                response = self.client.post(self._picks_url(), payload)
                self.assertEqual(response.status_code, expected_status)

        self.assertFalse(GamePicks.objects.filter(pool=self.pool).exists())
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.family,
                action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED,
            ).exists()
        )

    def test_manual_pick_access_denies_member_outsider_inactive_anonymous_and_csrf(self):
        game = self._admin_game(game_id=9650, week="7")

        for user, expected_status in (
            (self.member, 403),
            (self.outsider, 404),
            (self.inactive_user, 404),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                page_response = self.client.get(self._picks_url())
                post_response = self.client.post(self._picks_url(), self._manual_pick_payload(game))
                json_response = self.client.get(
                    self._picks_json_url(),
                    {"target_user_id": self.member.id, "week": "7"},
                    HTTP_ACCEPT="application/json",
                )
                self.assertEqual(page_response.status_code, expected_status)
                self.assertEqual(post_response.status_code, expected_status)
                self.assertEqual(json_response.status_code, expected_status)
                if expected_status == 404:
                    self.assertNotIn("Smith", json_response.content.decode())
                    self.assertNotIn("Jones", json_response.content.decode())

        self.client.logout()
        browser_response = self.client.get(self._picks_url())
        json_response = self.client.get(
            self._picks_json_url(),
            {"target_user_id": self.member.id, "week": "7"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(browser_response.status_code, 302)
        self.assertEqual(json_response.status_code, 401)
        self.assertNotIn("/accounts/login", json_response.content.decode())
        self.assertIn("auth", json_response.json()["error"])

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)
        csrf_response = csrf_client.post(self._picks_url(), self._manual_pick_payload(game))
        self.assertEqual(csrf_response.status_code, 403)
        self.assertFalse(GamePicks.objects.filter(pool=self.pool).exists())

    def test_winner_page_lists_current_family_candidates_and_current_pool_rows(self):
        current_game = self._admin_game(game_id=9701, week="2")
        other_pool_game = self._admin_game(game_id=9702, week="2", home="mia", away="buf")
        current_pick = self._winner_candidate(self.member, game=current_game)
        self._season_points(self.member, week=2, points=3)
        GamePicks.objects.create(
            id=f"{self.other_pool.id}-{self.outsider.id}-{other_pool_game.id}",
            pool=self.other_pool,
            userEmail=self.outsider.email,
            userID=str(self.outsider.id),
            uid=self.outsider.id,
            slug=other_pool_game.slug,
            competition=other_pool_game.competition,
            gameseason=other_pool_game.gameseason,
            gameWeek=other_pool_game.gameWeek,
            gameyear=other_pool_game.gameyear,
            pick_game_id=other_pool_game.id,
            pick=other_pool_game.homeTeamSlug,
            pick_correct=True,
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(self._winners_url(), {"week": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/family_admin_winners.html")
        self.assertContains(response, "Edit Winners")
        self.assertContains(response, "Smith Family")
        self.assertContains(response, self.member.username)
        self.assertContains(response, str(current_pick.uid))
        self.assertNotContains(response, self.outsider.username)
        self.assertNotContains(response, other_pool_game.homeTeamName)

    def test_winner_post_sets_current_pool_winner_bonus_total_and_audit(self):
        game = self._admin_game(game_id=9710, week="3")
        self._winner_candidate(self.member, game=game)
        member_points = self._season_points(self.member, week=3, points=4)
        owner_points = self._season_points(self.owner, week=3, points=5, bonus=2)
        setattr(owner_points, "week_3_winner", True)
        owner_points.total_points = 7
        owner_points.save()
        other_points = self._season_points(self.outsider, pool=self.other_pool, week=3, points=8)

        self.client.force_login(self.owner)
        response = self.client.post(
            self._winners_url(),
            {
                "week_number": "3",
                "winner_uid": str(self.member.id),
                "gameseason": "1999",
                "pool_id": str(self.other_pool.id),
                "family_id": str(self.other_family.id),
                "bonus": "99",
            },
        )

        self.assertRedirects(response, self._winners_url() + "?week=3")
        member_points.refresh_from_db()
        owner_points.refresh_from_db()
        other_points.refresh_from_db()
        self.assertTrue(member_points.week_3_winner)
        self.assertEqual(member_points.week_3_bonus, 2)
        self.assertEqual(member_points.total_points, 6)
        self.assertFalse(owner_points.week_3_winner)
        self.assertEqual(owner_points.week_3_bonus, 0)
        self.assertEqual(owner_points.total_points, 5)
        self.assertFalse(other_points.week_3_winner)
        self.assertEqual(other_points.week_3_bonus, 0)
        self.assertEqual(other_points.total_points, 8)

        audit = FamilyAuditLog.objects.get(
            family=self.family,
            pool=self.pool,
            actor=self.owner,
            action=FamilyAuditLog.Action.WEEK_WINNER_UPDATED,
            target_type="userSeasonPoints",
            target_id=str(member_points.id),
        )
        self.assertEqual(audit.metadata["week"], 3)
        self.assertEqual(audit.metadata["previous_winner_user_id"], self.owner.id)
        self.assertEqual(audit.metadata["new_winner_user_id"], self.member.id)
        self.assertEqual(audit.metadata["bonus_points"], 2)
        self.assertEqual(audit.metadata["actor_id"], self.owner.id)
        self.assertNotIn("1999", str(audit.metadata))
        self.assertNotIn("pool_id", audit.metadata)
        self.assertNotIn("family_id", audit.metadata)

    def test_winner_post_rejects_invalid_weeks_before_dynamic_fields(self):
        self._season_points(self.member, week=1, points=1)
        self.client.force_login(self.owner)

        for invalid_week in ("0", "19", "abc", "1; DROP", "", None):
            with self.subTest(invalid_week=invalid_week):
                payload = {"winner_uid": str(self.member.id)}
                if invalid_week is not None:
                    payload["week_number"] = invalid_week
                response = self.client.post(self._winners_url(), payload)
                self.assertEqual(response.status_code, 400)

        row = userSeasonPoints.objects.get(pool=self.pool, userID=str(self.member.id))
        self.assertFalse(row.week_1_winner)
        self.assertEqual(row.week_1_bonus, 0)
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.family,
                action=FamilyAuditLog.Action.WEEK_WINNER_UPDATED,
            ).exists()
        )

    def test_winner_post_rejects_forged_users_and_missing_current_pool_standings(self):
        game = self._admin_game(game_id=9720, week="4")
        self._winner_candidate(self.member, game=game)
        self._season_points(self.outsider, pool=self.other_pool, week=4, points=6)
        no_standing_user = User.objects.create_user(
            "admin-no-standing",
            email="no-standing@example.com",
            password="pass",
        )
        self._membership(no_standing_user, self.family, FamilyMembership.Role.MEMBER)

        self.client.force_login(self.owner)
        cases = [
            self.outsider.id,
            no_standing_user.id,
        ]
        for winner_uid in cases:
            with self.subTest(winner_uid=winner_uid):
                response = self.client.post(
                    self._winners_url(),
                    {"week_number": "4", "winner_uid": str(winner_uid)},
                )
                self.assertEqual(response.status_code, 404)

        self.assertFalse(userSeasonPoints.objects.filter(pool=self.pool, week_4_winner=True).exists())
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.family,
                action=FamilyAuditLog.Action.WEEK_WINNER_UPDATED,
            ).exists()
        )

    def test_winner_access_denies_member_outsider_inactive_anonymous_and_csrf(self):
        self._season_points(self.member, week=5, points=2)

        for user, expected_status in (
            (self.member, 403),
            (self.outsider, 404),
            (self.inactive_user, 404),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                get_response = self.client.get(self._winners_url())
                post_response = self.client.post(
                    self._winners_url(),
                    {"week_number": "5", "winner_uid": str(self.member.id)},
                )
                self.assertEqual(get_response.status_code, expected_status)
                self.assertEqual(post_response.status_code, expected_status)

        self.client.logout()
        response = self.client.get(self._winners_url())
        self.assertEqual(response.status_code, 302)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)
        csrf_response = csrf_client.post(
            self._winners_url(),
            {"week_number": "5", "winner_uid": str(self.member.id)},
        )
        self.assertEqual(csrf_response.status_code, 403)
        self.assertFalse(userSeasonPoints.objects.filter(pool=self.pool, week_5_winner=True).exists())

    def test_winner_post_denies_non_owner_admin_without_mutation(self):
        self._season_points(self.member, week=5, points=2)

        self.client.force_login(self.admin_user)
        get_response = self.client.get(self._winners_url())
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(
            self._winners_url(),
            {"week_number": "5", "winner_uid": str(self.member.id)},
        )
        self.assertEqual(post_response.status_code, 403)
        self.assertFalse(userSeasonPoints.objects.filter(pool=self.pool, week_5_winner=True).exists())
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                family=self.family,
                action=FamilyAuditLog.Action.WEEK_WINNER_UPDATED,
            ).exists()
        )

    def test_winner_override_visible_to_owner_only(self):
        self._season_points(self.member, week=1, points=2)

        self.client.force_login(self.owner)
        owner_response = self.client.get(self._winners_url())
        self.assertEqual(owner_response.status_code, 200)
        self.assertIn(b"Correct this", owner_response.content)

        self.client.force_login(self.admin_user)
        admin_response = self.client.get(self._winners_url())
        self.assertEqual(admin_response.status_code, 200)
        self.assertNotIn(b"Correct this", admin_response.content)

    def test_legacy_commissioner_routes_are_disabled_without_login_html_or_global_mutation(self):
        UserProfile.objects.create(user=self.owner, is_commissioner=True)
        legacy_pick_game = self._admin_game(game_id=9730, week="6")
        legacy_standing = self._season_points(self.owner, week=6, points=4)

        self.client.force_login(self.owner)
        page_response = self.client.get(reverse("commissioners"))
        self.assertEqual(page_response.status_code, 404)
        self.assertNotContains(page_response, "Commissioners Dashboard", status_code=404)

        json_routes = [
            (
                "set_week_winner",
                "post",
                {
                    "week_number": "6",
                    "winner_uid": str(self.owner.id),
                    "gameseason": str(self.pool.season),
                },
            ),
            (
                "submit_manual_pick",
                "post",
                {
                    "user_id": str(self.owner.id),
                    "game_id": str(legacy_pick_game.id),
                    "pick": legacy_pick_game.homeTeamSlug,
                },
            ),
            ("get_user_picks", "get", {"user_id": str(self.owner.id)}),
        ]
        for route_name, method, payload in json_routes:
            with self.subTest(route_name=route_name):
                url = reverse(route_name)
                if method == "post":
                    response = self.client.post(
                        url,
                        data=json.dumps(payload),
                        content_type="application/json",
                        HTTP_ACCEPT="application/json",
                    )
                else:
                    response = self.client.get(url, payload, HTTP_ACCEPT="application/json")
                self.assertIn(response.status_code, (403, 404))
                self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
                body = response.content.decode()
                self.assertNotIn("/accounts/login", body)
                self.assertNotIn("Smith", body)
                self.assertNotIn("Jones", body)

        legacy_standing.refresh_from_db()
        self.assertFalse(legacy_standing.week_6_winner)
        self.assertEqual(legacy_standing.week_6_bonus, 0)
        self.assertFalse(GamePicks.objects.filter(userID=str(self.owner.id), pick_game_id=legacy_pick_game.id).exists())


class BatchInviteTests(TestCase):
    """Task 10: submitting several `recipient_email` values at once creates
    one invite per valid, distinct address instead of a single invite."""

    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            "batch-owner", email="batch-owner@example.com", password="pass"
        )
        self.family = Family.objects.create(name="Batch Family", slug="batch-family")
        self.pool = Pool.objects.create(
            family=self.family,
            name="Main Pickem",
            slug="batch-main",
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        PoolSettings.objects.create(pool=self.pool)
        FamilyMembership.objects.create(
            family=self.family, user=self.owner, role=FamilyMembership.Role.OWNER
        )
        self.client.force_login(self.owner)

    def _invites_url(self):
        return reverse(
            "family_pool_admin_invites",
            kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug},
        )

    def test_multiple_emails_create_multiple_invites(self):
        before_count = FamilyInvitation.objects.filter(family=self.family).count()

        # Batch success uses Post/Redirect/Get; follow to the final page where the
        # summary flash message renders.
        response = self.client.post(
            self._invites_url(),
            {
                "role": FamilyMembership.Role.MEMBER,
                "recipient_email": ["a@x.com", "b@x.com"],
                "expires_in_days": "14",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][1], 302)
        self.assertEqual(
            FamilyInvitation.objects.filter(family=self.family).count(),
            before_count + 2,
        )
        recipient_emails = set(
            FamilyInvitation.objects.filter(family=self.family).values_list(
                "recipient_email", flat=True
            )
        )
        self.assertIn("a@x.com", recipient_emails)
        self.assertIn("b@x.com", recipient_emails)
        self.assertContains(response, "Sent 2 invite(s).")
        # A multi-invite batch does not surface a one-time invite link.
        self.assertIsNone(response.context.get("invite_link"))

    def test_invalid_email_skipped_valid_still_created(self):
        before_count = FamilyInvitation.objects.filter(family=self.family).count()

        # One created + one skipped goes through the batch-summary (redirect) path.
        response = self.client.post(
            self._invites_url(),
            {
                "role": FamilyMembership.Role.MEMBER,
                "recipient_email": ["good@x.com", "not-an-email"],
                "expires_in_days": "14",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][1], 302)
        self.assertEqual(
            FamilyInvitation.objects.filter(family=self.family).count(),
            before_count + 1,
        )
        self.assertTrue(
            FamilyInvitation.objects.filter(
                family=self.family, recipient_email="good@x.com"
            ).exists()
        )
        self.assertContains(response, "Sent 1 invite(s).")
        self.assertContains(response, "Skipped")
        self.assertContains(response, "not-an-email")

    def test_all_blank_emails_creates_no_invite_and_400s(self):
        before_count = FamilyInvitation.objects.filter(family=self.family).count()

        response = self.client.post(
            self._invites_url(),
            {
                "role": FamilyMembership.Role.MEMBER,
                "recipient_email": ["", "   "],
                "expires_in_days": "14",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            FamilyInvitation.objects.filter(family=self.family).count(),
            before_count,
        )
        self.assertContains(
            response,
            "Enter at least one email address to invite.",
            status_code=400,
        )
        # No blank-recipient invite should have been created, so the
        # per-invite email feedback message (which would otherwise render
        # "Invite email will be sent to None.") must never appear.
        self.assertNotContains(response, "sent to None", status_code=400)
        self.assertNotContains(response, "saved for None", status_code=400)


class CreateFamilyFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            "creator", email="creator@example.com", password="pass"
        )
        self.other_user = User.objects.create_user(
            "other", email="other@example.com", password="pass"
        )

    def test_create_family_requires_login(self):
        response = self.client.get(reverse("create_family"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_onboarding_links_to_create_family_route(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("onboarding"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("create_family")}"')
        self.assertContains(response, "Create family")

    def test_create_family_form_renders_validation_errors(self):
        self.client.force_login(self.user)
        family_count = Family.objects.count()

        response = self.client.post(reverse("create_family"), {"name": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/create_family.html")
        self.assertContains(response, "This field is required.")
        self.assertEqual(Family.objects.count(), family_count)

    @staticmethod
    def _payload(**overrides):
        """A complete create-family POST: the flow now requires explicit
        rule choices (prefilled from PoolSettings defaults in the UI)."""
        payload = {
            "name": "Smith Family",
            "picks_lock_mode": PoolSettings.PicksLockMode.KICKOFF,
            "allow_tiebreaker": "on",
            "win_points": 1,
            "tie_points": 0,
            "weekly_winner_points": 2,
            "primary_tiebreaker": PoolSettings.PrimaryTiebreaker.TOTAL_SCORE,
            "secondary_tiebreaker": PoolSettings.SecondaryTiebreaker.COMBINED_YARDS,
            "perfect_week_bonus_amount": 10,
            "entry_fee_amount": 0,
            "pick_type": PoolSettings.PickType.STRAIGHT_UP,
            "missed_pick_policy": PoolSettings.MissedPickPolicy.ZERO_POINTS,
            "late_join_policy": PoolSettings.LateJoinPolicy.OPEN,
            "payout_structure": PoolSettings.PayoutStructure.WINNER_TAKES_ALL,
        }
        payload.update(overrides)
        return payload

    def test_create_family_form_renders_rules_and_invite_rows(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("create_family"))

        self.assertEqual(response.status_code, 200)
        # The full rules form is inline, prefilled with the defaults.
        self.assertContains(response, "Set your league rules")
        self.assertContains(response, "Points per win")
        self.assertContains(response, "Primary tiebreaker")
        # Invites are one-email-per-row with a client-side add button.
        self.assertContains(response, "Invite your members")
        self.assertContains(response, 'name="invite_emails"')
        self.assertContains(response, "Add another email")

    def test_valid_post_creates_family_default_pool_settings_owner_and_audit(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("create_family"),
            self._payload(
                # Non-default rules prove the inline form actually persists.
                win_points=3,
                weekly_winner_points=5,
                missed_pick_policy=PoolSettings.MissedPickPolicy.AUTO_HOME,
                invite_emails=["cousin@example.com", "aunt@example.com"],
            ),
        )

        family = Family.objects.get(name="Smith Family")
        pool = Pool.objects.get(family=family)
        membership = FamilyMembership.objects.get(family=family, user=self.user)

        self.assertRedirects(
            response,
            reverse(
                "family_pool_home",
                kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
            ),
            fetch_redirect_response=False,
        )
        self.assertEqual(family.slug, "smith-family")
        self.assertEqual(family.status, Family.Status.ACTIVE)
        # No season in the default name — headers append display_season
        # themselves, and the old seasoned default rendered it twice.
        self.assertEqual(pool.name, "Pick'em Pool")
        self.assertEqual(pool.slug, "pickem-pool")
        self.assertEqual(pool.season, get_season())
        self.assertEqual(pool.competition, "nfl")
        self.assertEqual(pool.status, Pool.Status.ACTIVE)
        self.assertTrue(pool.is_default)
        self.assertEqual(pool.family, family)
        self.assertTrue(PoolSettings.objects.filter(pool=pool).exists())
        self.assertEqual(membership.role, FamilyMembership.Role.OWNER)
        self.assertEqual(membership.status, FamilyMembership.Status.ACTIVE)
        self.assertEqual(
            FamilyMembership.objects.filter(
                family=family,
                role=FamilyMembership.Role.OWNER,
                status=FamilyMembership.Status.ACTIVE,
            ).count(),
            1,
        )
        self.assertQuerysetEqual(
            FamilyMembership.objects.filter(family=family).values_list(
                "user_id", flat=True
            ),
            [self.user.id],
        )
        self.assertTrue(
            FamilyAuditLog.objects.filter(
                family=family,
                pool=pool,
                actor=self.user,
                action=FamilyAuditLog.Action.MEMBERSHIP_CREATED,
                target_type="FamilyMembership",
                target_id=str(membership.id),
            ).exists()
        )
        self.assertTrue(
            FamilyAuditLog.objects.filter(
                family=family,
                pool=pool,
                actor=self.user,
                action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
                target_type="Pool",
                target_id=str(pool.id),
            ).exists()
        )
        # The inline rules landed on PoolSettings, not silent defaults.
        settings = PoolSettings.objects.get(pool=pool)
        self.assertEqual(settings.win_points, 3)
        self.assertEqual(settings.weekly_winner_points, 5)
        self.assertEqual(
            settings.missed_pick_policy, PoolSettings.MissedPickPolicy.AUTO_HOME
        )
        # Each email row became a targeted single-use invitation.
        recipients = set(
            FamilyInvitation.objects.filter(family=family).values_list(
                "recipient_email", flat=True
            )
        )
        self.assertEqual(recipients, {"cousin@example.com", "aunt@example.com"})

    def test_invalid_invite_email_row_blocks_submission(self):
        self.client.force_login(self.user)
        family_count = Family.objects.count()

        response = self.client.post(
            reverse("create_family"),
            self._payload(invite_emails=["cousin@example.com", "not-an-email"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "don&#x27;t look right")
        # The bad row is preserved for correction, nothing was created.
        self.assertContains(response, 'value="not-an-email"')
        self.assertEqual(Family.objects.count(), family_count)
        self.assertFalse(FamilyInvitation.objects.exists())

    def test_own_and_duplicate_invite_emails_are_skipped(self):
        self.client.force_login(self.user)

        self.client.post(
            reverse("create_family"),
            self._payload(
                invite_emails=[
                    "creator@example.com",   # the creator: never self-invite
                    "cousin@example.com",
                    "COUSIN@example.com",    # case-insensitive duplicate
                ],
            ),
        )

        family = Family.objects.get(name="Smith Family")
        recipients = list(
            FamilyInvitation.objects.filter(family=family).values_list(
                "recipient_email", flat=True
            )
        )
        self.assertEqual(recipients, ["cousin@example.com"])

    def test_locked_pick_type_is_rejected_inline(self):
        self.client.force_login(self.user)
        family_count = Family.objects.count()

        response = self.client.post(
            reverse("create_family"),
            self._payload(pick_type=PoolSettings.PickType.AGAINST_SPREAD),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "coming soon")
        self.assertEqual(Family.objects.count(), family_count)

    def test_slug_collisions_receive_unique_family_slug(self):
        Family.objects.create(name="Smith Family", slug="smith-family")
        self.client.force_login(self.user)

        response = self.client.post(reverse("create_family"), self._payload())

        family = Family.objects.get(slug="smith-family-2")
        pool = Pool.objects.get(family=family)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(pool.slug, "pickem-pool")

    def test_client_supplied_tenant_and_role_fields_are_ignored(self):
        attacker_family = Family.objects.create(
            name="Attacker Family", slug="attacker-family"
        )
        attacker_pool = Pool.objects.create(
            family=attacker_family,
            name="Attacker Pool",
            slug="attacker-pool",
            season=1999,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        self.client.force_login(self.user)

        self.client.post(
            reverse("create_family"),
            self._payload(
                name="Controlled Family",
                owner=self.other_user.id,
                user=self.other_user.id,
                user_id=self.other_user.id,
                role=FamilyMembership.Role.ADMIN,
                status=FamilyMembership.Status.INACTIVE,
                season=1999,
                family=attacker_family.id,
                family_id=attacker_family.id,
                pool=attacker_pool.id,
                pool_id=attacker_pool.id,
                is_default="false",
            ),
        )

        family = Family.objects.get(name="Controlled Family")
        pool = Pool.objects.get(family=family)
        membership = FamilyMembership.objects.get(family=family)

        self.assertNotEqual(family.id, attacker_family.id)
        self.assertNotEqual(pool.id, attacker_pool.id)
        self.assertEqual(pool.season, get_season())
        self.assertTrue(pool.is_default)
        self.assertEqual(membership.user, self.user)
        self.assertEqual(membership.role, FamilyMembership.Role.OWNER)
        self.assertEqual(membership.status, FamilyMembership.Status.ACTIVE)
        self.assertFalse(
            FamilyMembership.objects.filter(
                family=family,
                user=self.other_user,
            ).exists()
        )

    def test_create_family_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(reverse("create_family"), {"name": "Smith Family"})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Family.objects.filter(name="Smith Family").exists())


class FamilyDeactivationTests(TestCase):
    """Commissioner soft-delete: type-the-name confirm, data preserved,
    tenant pages go dark, and only the owner can pull the trigger."""

    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            "deactivate-owner", email="deactivate-owner@example.com", password="pass"
        )
        self.admin_user = User.objects.create_user(
            "deactivate-admin", email="deactivate-admin@example.com", password="pass"
        )
        self.family = Family.objects.create(name="Sunset Family", slug="sunset")
        self.pool = Pool.objects.create(
            family=self.family,
            name="Pick'em Pool",
            slug="pickem-pool",
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        PoolSettings.objects.create(pool=self.pool)
        FamilyMembership.objects.create(
            family=self.family, user=self.owner, role=FamilyMembership.Role.OWNER
        )
        FamilyMembership.objects.create(
            family=self.family, user=self.admin_user, role=FamilyMembership.Role.ADMIN
        )
        self.delete_url = reverse(
            "family_pool_admin_delete_family",
            kwargs={"family_slug": "sunset", "pool_slug": "pickem-pool"},
        )

    def test_owner_deactivates_with_exact_name_and_data_survives(self):
        pick = GamePicks.objects.create(
            id=f"{self.pool.id}-{self.owner.id}-1",
            pool=self.pool,
            userID=str(self.owner.id),
            pick_game_id=1,
            gameseason=2526,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_url, {"confirm_name": "Sunset Family"}
        )

        self.assertRedirects(
            response, reverse("family_picker"), fetch_redirect_response=False
        )
        self.family.refresh_from_db()
        self.assertEqual(self.family.status, Family.Status.INACTIVE)
        self.assertTrue(
            FamilyAuditLog.objects.filter(
                family=self.family,
                actor=self.owner,
                action=FamilyAuditLog.Action.FAMILY_STATUS_UPDATED,
            ).exists()
        )
        # Soft delete: every row survives.
        self.assertTrue(GamePicks.objects.filter(id=pick.id).exists())
        self.assertTrue(
            FamilyMembership.objects.filter(family=self.family).count() == 2
        )
        # The tenant pages are gone for members now.
        lobby = self.client.get(
            reverse(
                "family_pool_home",
                kwargs={"family_slug": "sunset", "pool_slug": "pickem-pool"},
            )
        )
        self.assertEqual(lobby.status_code, 404)

    def test_wrong_confirm_name_deactivates_nothing(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_url, {"confirm_name": "sunset family"}
        )

        self.assertRedirects(
            response,
            reverse(
                "family_pool_admin_settings",
                kwargs={"family_slug": "sunset", "pool_slug": "pickem-pool"},
            ),
            fetch_redirect_response=False,
        )
        self.family.refresh_from_db()
        self.assertEqual(self.family.status, Family.Status.ACTIVE)
        self.assertFalse(
            FamilyAuditLog.objects.filter(
                action=FamilyAuditLog.Action.FAMILY_STATUS_UPDATED
            ).exists()
        )

    def test_admin_cannot_deactivate_family(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self.delete_url, {"confirm_name": "Sunset Family"}
        )

        self.assertEqual(response.status_code, 403)
        self.family.refresh_from_db()
        self.assertEqual(self.family.status, Family.Status.ACTIVE)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.delete_url)

        self.assertEqual(response.status_code, 405)
        self.family.refresh_from_db()
        self.assertEqual(self.family.status, Family.Status.ACTIVE)

    def test_danger_zone_renders_for_owner_only(self):
        settings_url = reverse(
            "family_pool_admin_settings",
            kwargs={"family_slug": "sunset", "pool_slug": "pickem-pool"},
        )

        self.client.force_login(self.owner)
        owner_view = self.client.get(settings_url)
        self.assertContains(owner_view, "Danger Zone")
        self.assertContains(owner_view, "Deactivate family")

        self.client.force_login(self.admin_user)
        admin_view = self.client.get(settings_url)
        self.assertEqual(admin_view.status_code, 200)
        self.assertNotContains(admin_view, "Danger Zone")

    def test_deactivated_family_leaves_picker_and_switcher(self):
        self.client.force_login(self.owner)
        self.client.post(self.delete_url, {"confirm_name": "Sunset Family"})

        # No other family: the picker redirects to onboarding.
        response = self.client.get(reverse("family_picker"))
        self.assertRedirects(
            response, reverse("onboarding"), fetch_redirect_response=False
        )


class InviteFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            "invite-owner", email="owner@example.com", password="pass"
        )
        self.admin_user = User.objects.create_user(
            "invite-admin", email="admin@example.com", password="pass"
        )
        self.member = User.objects.create_user(
            "invite-member", email="member@example.com", password="pass"
        )
        self.outsider = User.objects.create_user(
            "invite-outsider", email="outsider@example.com", password="pass"
        )
        self.joiner = User.objects.create_user(
            "invite-joiner", email="joiner@example.com", password="pass"
        )
        self.family = Family.objects.create(name="Smith Family", slug="smith-family")
        self.pool = Pool.objects.create(
            family=self.family,
            name="Main Pickem",
            slug="main",
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.owner,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.admin_user,
            role=FamilyMembership.Role.ADMIN,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.member,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _create_invite_url(self, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "create_family_invite",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

    def _join_url(self):
        return reverse("join_family")

    def _link_url(self, code):
        return reverse("accept_invite_link", kwargs={"invite_code": code})

    def _hash_code(self, raw_code):
        from pickem_homepage.views import hash_invite_code

        return hash_invite_code(raw_code)

    def _invitation(self, raw_code="VALID-CODE", **overrides):
        defaults = {
            "family": self.family,
            "pool": self.pool,
            "code_hash": self._hash_code(raw_code),
            "role": FamilyMembership.Role.MEMBER,
            "expires_at": timezone.now() + timedelta(days=14),
            "max_uses": 1,
            "created_by": self.owner,
        }
        defaults.update(overrides)
        return FamilyInvitation.objects.create(**defaults)

    def test_owner_can_create_member_invite_hash_only_with_defaults_and_audit(self):
        self.client.force_login(self.owner)
        before = timezone.now()

        response = self.client.post(self._create_invite_url())

        invitation = FamilyInvitation.objects.get(family=self.family)
        invite_link = response.context["invite_link"]

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/family_pool_home.html")
        self.assertEqual(invitation.pool, self.pool)
        self.assertEqual(invitation.role, FamilyMembership.Role.MEMBER)
        self.assertEqual(invitation.max_uses, 1)
        self.assertEqual(invitation.use_count, 0)
        self.assertFalse(invitation.is_revoked)
        self.assertGreaterEqual(invitation.expires_at, before + timedelta(days=13, hours=23))
        self.assertLessEqual(invitation.expires_at, timezone.now() + timedelta(days=14, minutes=1))
        self.assertTrue(invitation.code_hash.startswith("sha256:"))
        self.assertFalse(hasattr(invitation, "code"))
        self.assertFalse(hasattr(invitation, "raw_code"))
        self.assertIn("/invites/", invite_link)
        self.assertContains(response, invite_link)
        self.assertTrue(
            FamilyAuditLog.objects.filter(
                family=self.family,
                pool=self.pool,
                actor=self.owner,
                action=FamilyAuditLog.Action.INVITATION_CREATED,
                target_type="FamilyInvitation",
                target_id=str(invitation.id),
            ).exists()
        )
        audit = FamilyAuditLog.objects.get(
            action=FamilyAuditLog.Action.INVITATION_CREATED,
            target_id=str(invitation.id),
        )
        self.assertNotIn(invite_link, str(audit.metadata))

    def test_non_owners_cannot_create_phase_three_invites(self):
        for user, expected_status in [
            (self.admin_user, 403),
            (self.member, 403),
            (self.outsider, 404),
        ]:
            self.client.force_login(user)

            response = self.client.post(self._create_invite_url())

            self.assertEqual(response.status_code, expected_status)
            self.assertFalse(FamilyInvitation.objects.exists())

    def test_invite_creation_is_post_only_and_csrf_protected(self):
        self.client.force_login(self.owner)

        get_response = self.client.get(self._create_invite_url())

        self.assertEqual(get_response.status_code, 405)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)

        response = csrf_client.post(self._create_invite_url())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(FamilyInvitation.objects.exists())

    def test_manual_code_acceptance_creates_member_and_redirects_to_pool(self):
        invite = self._invitation(raw_code="manual-code")
        self.client.force_login(self.joiner)

        response = self.client.post(self._join_url(), {"code": " manual code "})

        membership = FamilyMembership.objects.get(family=self.family, user=self.joiner)
        invite.refresh_from_db()
        self.assertRedirects(
            response,
            reverse(
                "family_pool_home",
                kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug},
            ),
            fetch_redirect_response=False,
        )
        self.assertEqual(membership.role, FamilyMembership.Role.MEMBER)
        self.assertEqual(membership.status, FamilyMembership.Status.ACTIVE)
        self.assertEqual(invite.use_count, 1)
        self.assertTrue(
            FamilyAuditLog.objects.filter(
                family=self.family,
                pool=self.pool,
                actor=self.joiner,
                action=FamilyAuditLog.Action.MEMBERSHIP_CREATED,
                target_type="FamilyMembership",
                target_id=str(membership.id),
                metadata__source="invite_acceptance",
            ).exists()
        )

    def test_link_acceptance_requires_login_and_accepts_on_get(self):
        self._invitation(raw_code="link-code")

        anonymous = self.client.get(self._link_url("link-code"))

        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/accounts/login/", anonymous["Location"])
        self.client.force_login(self.joiner)

        get_response = self.client.get(self._link_url("link-code"))

        self.assertRedirects(
            get_response,
            reverse(
                "family_pool_home",
                kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug},
            ),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            FamilyMembership.objects.filter(
                family=self.family,
                user=self.joiner,
                status=FamilyMembership.Status.ACTIVE,
            ).exists()
        )

    def test_email_targeted_invite_accepts_case_insensitive_matching_user_email(self):
        invite = self._invitation(
            raw_code="email-code",
            recipient_email="Joiner@Example.com",
            use_count=0,
        )
        self.client.force_login(self.joiner)

        response = self.client.post(self._join_url(), {"code": "email-code"})

        invite.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            FamilyMembership.objects.filter(
                family=self.family,
                user=self.joiner,
                status=FamilyMembership.Status.ACTIVE,
            ).exists()
        )
        self.assertEqual(invite.use_count, 1)

    def test_join_family_accepts_full_invite_link_pasted_into_form(self):
        invite = self._invitation(
            raw_code="paste-link-code",
            recipient_email="joiner@example.com",
            use_count=0,
        )
        self.client.force_login(self.joiner)

        response = self.client.post(
            self._join_url(),
            {"code": "https://family-pickem.com/invites/paste-link-code/"},
        )

        invite.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(invite.use_count, 1)

    def test_email_targeted_invite_rejects_wrong_account_without_mutation(self):
        invite = self._invitation(
            raw_code="wrong-email-code",
            recipient_email="someoneelse@example.com",
            use_count=0,
        )
        self.client.force_login(self.joiner)

        response = self.client.post(self._join_url(), {"code": "wrong-email-code"})

        invite.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "someoneelse@example.com")
        self.assertFalse(
            FamilyMembership.objects.filter(
                family=self.family,
                user=self.joiner,
                status=FamilyMembership.Status.ACTIVE,
            ).exists()
        )
        self.assertEqual(invite.use_count, 0)

    def test_link_click_wrong_account_shows_error_not_500(self):
        # GET the email link while signed in as the wrong account: must render the
        # graceful error page (200), not 500 on an unbound-form add_error().
        self._invitation(raw_code="wrong-link", recipient_email="someoneelse@example.com")
        self.client.force_login(self.joiner)

        response = self.client.get(self._link_url("wrong-link"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "someoneelse@example.com")
        self.assertFalse(
            FamilyMembership.objects.filter(family=self.family, user=self.joiner).exists()
        )

    def test_link_click_reaccept_after_joining_redirects_home(self):
        # Clicking a spent link after you've already joined shouldn't 500 or show
        # "invalid"; send an existing member to their family home.
        self._invitation(raw_code="reuse-link", recipient_email="joiner@example.com")
        self.client.force_login(self.joiner)

        first = self.client.get(self._link_url("reuse-link"))
        self.assertEqual(first.status_code, 302)  # joined

        second = self.client.get(self._link_url("reuse-link"))
        self.assertRedirects(
            second,
            reverse("family_pool_home",
                    kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug}),
            fetch_redirect_response=False,
        )

    def test_valid_invite_reactivates_inactive_same_family_membership(self):
        self._invitation(raw_code="reactivate-code")
        membership = FamilyMembership.objects.create(
            family=self.family,
            user=self.joiner,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.INACTIVE,
        )
        self.client.force_login(self.joiner)

        response = self.client.post(self._join_url(), {"code": "reactivate-code"})

        membership.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(membership.status, FamilyMembership.Status.ACTIVE)
        self.assertEqual(membership.role, FamilyMembership.Role.MEMBER)

    def test_invite_acceptance_post_requires_csrf_token(self):
        self._invitation(raw_code="csrf-code")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.joiner)

        response = csrf_client.post(self._join_url(), {"code": "csrf-code"})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            FamilyMembership.objects.filter(family=self.family, user=self.joiner).exists()
        )

    def test_invalid_invite_failures_are_generic_and_do_not_create_membership(self):
        cases = []
        cases.append(("invalid code", "missing-family"))
        cases.append(("revoked-code", self._invitation("revoked-code", is_revoked=True)))
        cases.append((
            "expired-code",
            self._invitation(
                "expired-code",
                expires_at=timezone.now() - timedelta(minutes=1),
            ),
        ))
        cases.append(("exhausted-code", self._invitation("exhausted-code", max_uses=1, use_count=1)))

        inactive_family = Family.objects.create(
            name="Inactive Family",
            slug="inactive-family",
            status=Family.Status.INACTIVE,
        )
        inactive_pool = Pool.objects.create(
            family=inactive_family,
            name="Inactive Main",
            slug="inactive-main",
            season=2526,
            status=Pool.Status.ACTIVE,
        )
        cases.append((
            "inactive-family-code",
            self._invitation(
                "inactive-family-code",
                family=inactive_family,
                pool=inactive_pool,
            ),
        ))

        inactive_pool_same_family = Pool.objects.create(
            family=self.family,
            name="Inactive Pool",
            slug="inactive-pool",
            season=2526,
            status=Pool.Status.INACTIVE,
        )
        cases.append((
            "inactive-pool-code",
            self._invitation("inactive-pool-code", pool=inactive_pool_same_family),
        ))

        other_family = Family.objects.create(name="Other Family", slug="other-family")
        other_pool = Pool.objects.create(
            family=other_family,
            name="Other Main",
            slug="other-main",
            season=2526,
            status=Pool.Status.ACTIVE,
        )
        cases.append((
            "pool-mismatch-code",
            self._invitation("pool-mismatch-code", pool=other_pool),
        ))

        for raw_code, _case in cases:
            with self.subTest(raw_code=raw_code):
                FamilyMembership.objects.filter(
                    family__in=[self.family, inactive_family, other_family],
                    user=self.joiner,
                ).delete()
                self.client.force_login(self.joiner)

                response = self.client.post(self._join_url(), {"code": raw_code})

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pickem/join_family.html")
                self.assertContains(response, "This invitation is invalid or unavailable.")
                self.assertNotContains(response, "Smith Family")
                self.assertNotContains(response, "Inactive Family")
                self.assertNotContains(response, "Other Family")
                self.assertFalse(
                    FamilyMembership.objects.filter(user=self.joiner).exists()
                )

    def _lock_entries_after_week_1(self):
        PoolSettings.objects.create(
            pool=self.pool,
            late_join_policy=PoolSettings.LateJoinPolicy.LOCK_AFTER_WEEK_1,
        )
        # Week 1 complete: every game finished and scored.
        GamesAndScores.objects.create(
            id=9101, slug="wk1-final", competition="nfl", gameWeek="1",
            gameyear="2025", gameseason=2526, startTimestamp=timezone.now(),
            statusType="finished", statusTitle="Final", gameWinner="eagles",
            gameScored=True,
            homeTeamId=1, homeTeamSlug="eagles", homeTeamName="Eagles",
            awayTeamId=2, awayTeamSlug="chiefs", awayTeamName="Chiefs",
        )

    def test_late_join_policy_blocks_new_members_after_week_1(self):
        from pickem_homepage.views import ENTRIES_LOCKED_MESSAGE

        self._lock_entries_after_week_1()
        invite = self._invitation(raw_code="late-code")
        self.client.force_login(self.joiner)

        response = self.client.post(self._join_url(), {"code": "late-code"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/join_family.html")
        self.assertContains(response, ENTRIES_LOCKED_MESSAGE)
        self.assertFalse(
            FamilyMembership.objects.filter(family=self.family, user=self.joiner).exists()
        )
        invite.refresh_from_db()
        self.assertEqual(invite.use_count, 0)

    def test_late_join_policy_still_admits_existing_active_members(self):
        self._lock_entries_after_week_1()
        self._invitation(raw_code="existing-code")
        self.client.force_login(self.member)  # already an active member

        response = self.client.post(self._join_url(), {"code": "existing-code"})

        self.assertRedirects(
            response,
            reverse(
                "family_pool_home",
                kwargs={"family_slug": self.family.slug, "pool_slug": self.pool.slug},
            ),
            fetch_redirect_response=False,
        )

    def test_open_policy_admits_new_members_after_week_1(self):
        PoolSettings.objects.create(
            pool=self.pool,
            late_join_policy=PoolSettings.LateJoinPolicy.OPEN,
        )
        GamesAndScores.objects.create(
            id=9102, slug="wk1-final-open", competition="nfl", gameWeek="1",
            gameyear="2025", gameseason=2526, startTimestamp=timezone.now(),
            statusType="finished", statusTitle="Final", gameWinner="eagles",
            gameScored=True,
            homeTeamId=1, homeTeamSlug="eagles", homeTeamName="Eagles",
            awayTeamId=2, awayTeamSlug="chiefs", awayTeamName="Chiefs",
        )
        self._invitation(raw_code="open-code")
        self.client.force_login(self.joiner)

        response = self.client.post(self._join_url(), {"code": "open-code"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            FamilyMembership.objects.filter(
                family=self.family, user=self.joiner,
                status=FamilyMembership.Status.ACTIVE,
            ).exists()
        )


class FamilyLogoUploadFoundationTests(FamilyAdminExperienceTests):
    def _default_scoring_fields(self, **overrides):
        overrides.setdefault(
            'picks_lock_mode', PoolSettings.PicksLockMode.KICKOFF,
        )
        return super()._default_scoring_fields(**overrides)

    def setUp(self):
        super().setUp()
        self._logo_storage_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._logo_storage_tmp.cleanup)
        field = Family._meta.get_field('logo')
        self._previous_logo_storage = field.storage
        field.storage = FileSystemStorage(location=self._logo_storage_tmp.name)
        self.addCleanup(setattr, field, 'storage', self._previous_logo_storage)
        # The fixture accessed ``family.logo`` before this override, so its
        # cached FieldFile keeps the original storage instance.
        self.family.logo.storage = field.storage

    def _logo_upload(self):
        data = BytesIO()
        Image.new('RGB', (24, 12), 'red').save(data, format='PNG')
        return SimpleUploadedFile('untrusted-name.png', data.getvalue(), content_type='image/png')

    def test_streaming_handler_marks_and_aborts_only_after_exact_five_mib(self):
        from pickem_homepage.upload_handlers import (
            FamilyLogoUploadSizeLimitHandler,
            MAX_FAMILY_LOGO_UPLOAD_BYTES,
        )

        request = SimpleNamespace()
        handler = FamilyLogoUploadSizeLimitHandler(request)
        handler.new_file('logo', 'untrusted.png', 'image/png', None)
        self.assertEqual(
            handler.receive_data_chunk(b'x' * MAX_FAMILY_LOGO_UPLOAD_BYTES, 0),
            b'x' * MAX_FAMILY_LOGO_UPLOAD_BYTES,
        )
        with self.assertRaises(StopUpload):
            handler.receive_data_chunk(b'x', MAX_FAMILY_LOGO_UPLOAD_BYTES)
        self.assertEqual(request._family_logo_upload_error, 'file_too_large')

    def test_admin_uploads_only_canonical_logo_and_settings_template_is_multipart(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            self._settings_url(),
            {
                'family_name': self.family.name,
                'pool_name': self.pool.name,
                **self._default_scoring_fields(),
                'logo': self._logo_upload(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.family.refresh_from_db()
        self.assertTrue(self.family.logo.name.endswith('.webp'))
        rendered = self.client.get(self._settings_url())
        self.assertContains(rendered, 'enctype="multipart/form-data"')
        self.assertContains(rendered, 'accept="image/jpeg,image/png,image/webp"')
        self.assertContains(rendered, 'Choose a JPEG, PNG, or WebP image up to 5 MB.')
        self.assertNotContains(rendered, 'logo_url')

    def test_settings_logo_editor_keeps_native_form_contract_and_enhancement_hooks(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(self._settings_url())

        self.assertContains(response, 'data-family-logo-form')
        self.assertContains(response, 'id="id_logo"')
        self.assertContains(response, 'data-family-logo-server-preview')
        self.assertContains(response, 'data-family-logo-editor')
        self.assertContains(response, 'data-family-logo-clear')
        self.assertContains(response, 'data-family-logo-save')
        self.assertContains(response, 'data-family-logo-adjust')
        self.assertContains(response, 'data-family-logo-full-image')
        for field_name in ('crop_x', 'crop_y', 'crop_width', 'crop_height', 'remove_logo'):
            self.assertContains(response, 'name="%s"' % field_name)
        self.assertContains(response, 'vendor/cropperjs/cropper.js')
        self.assertContains(response, 'js/family-logo-editor.js')
        self.assertNotContains(response, 'logo_url')

    def test_settings_error_keeps_bound_values_and_old_server_logo(self):
        self.family.logo.save('already.webp', SimpleUploadedFile('already.webp', b'canonical'), save=True)
        self.client.force_login(self.admin_user)
        response = self.client.post(
            self._settings_url(),
            {
                'family_name': 'Edited Family', 'pool_name': self.pool.name,
                **self._default_scoring_fields(),
                'logo': SimpleUploadedFile('bad.png', b'not-an-image', content_type='image/png'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Edited Family"')
        self.assertContains(response, 'data-family-logo-saved-image')
        self.assertContains(response, 'Select the file again before saving settings.')

    def test_settings_only_renders_canonical_or_static_logo_sources(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(self._settings_url())

        self.assertContains(response, 'images/logo.png')
        self.assertNotContains(response, 'blob:')
        self.assertNotContains(response, 'logo_url')

    def test_invalid_logo_preserves_existing_reference(self):
        self.family.logo.save('already.webp', SimpleUploadedFile('already.webp', b'canonical'), save=True)
        original = self.family.logo.name
        self.client.force_login(self.admin_user)
        response = self.client.post(
            self._settings_url(),
            {'family_name': self.family.name, 'pool_name': self.pool.name, **self._default_scoring_fields(),
             'logo': SimpleUploadedFile('bad.png', b'not-an-image', content_type='image/png')},
        )
        self.assertEqual(response.status_code, 200)
        self.family.refresh_from_db()
        self.assertEqual(self.family.logo.name, original)
        self.assertContains(response, "safely read")

    def test_crop_coordinates_are_forwarded_only_with_source_file(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(self._settings_url(), {
            'family_name': self.family.name, 'pool_name': self.pool.name,
            **self._default_scoring_fields(), 'logo': self._logo_upload(),
            'crop_x': '0', 'crop_y': '0', 'crop_width': '12', 'crop_height': '12',
        })
        self.assertEqual(response.status_code, 302)
        self.family.refresh_from_db()
        self.assertTrue(self.family.logo.name.endswith('.webp'))

    def test_invalid_crop_and_replacement_removal_tampering_preserve_logo(self):
        self.family.logo.save('already.webp', SimpleUploadedFile('already.webp', b'canonical'), save=True)
        original = self.family.logo.name
        self.client.force_login(self.admin_user)
        for payload in (
            {'crop_x': '0', 'crop_y': '0', 'crop_width': '12'},
            {'crop_x': '0', 'crop_y': '0', 'crop_width': '12', 'crop_height': '11'},
            {'remove_logo': 'true', 'logo': self._logo_upload()},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(self._settings_url(), {
                    'family_name': self.family.name, 'pool_name': self.pool.name,
                    **self._default_scoring_fields(), **payload,
                })
                self.assertEqual(response.status_code, 200)
                self.family.refresh_from_db()
                self.assertEqual(self.family.logo.name, original)

    def test_remove_logo_clears_reference_and_audits_presence_only(self):
        self.family.logo.save('already.webp', SimpleUploadedFile('already.webp', b'canonical'), save=True)
        self.client.force_login(self.admin_user)
        response = self.client.post(self._settings_url(), {
            'family_name': self.family.name, 'pool_name': self.pool.name,
            **self._default_scoring_fields(), 'remove_logo': 'true',
        })
        self.assertEqual(response.status_code, 302)
        self.family.refresh_from_db()
        self.assertFalse(self.family.logo.name)
        audit = FamilyAuditLog.objects.filter(family=self.family).latest('created_at')
        self.assertEqual(audit.metadata['logo'], {'before_present': True, 'after_present': False})

    def test_replacement_deletes_only_the_previous_logo_after_commit(self):
        self.family.logo.save('previous.webp', SimpleUploadedFile('previous.webp', b'canonical'), save=True)
        old_name = self.family.logo.name
        self.client.force_login(self.admin_user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self._settings_url(), {
                'family_name': self.family.name,
                'pool_name': self.pool.name,
                **self._default_scoring_fields(),
                'logo': self._logo_upload(),
            })

        self.assertEqual(response.status_code, 302)
        self.family.refresh_from_db()
        self.assertNotEqual(self.family.logo.name, old_name)
        self.assertFalse(self.family.logo.storage.exists(old_name))
        self.assertTrue(self.family.logo.storage.exists(self.family.logo.name))

    def test_removal_deletes_only_the_previous_logo_after_commit(self):
        self.family.logo.save('previous.webp', SimpleUploadedFile('previous.webp', b'canonical'), save=True)
        old_name = self.family.logo.name
        self.client.force_login(self.admin_user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self._settings_url(), {
                'family_name': self.family.name,
                'pool_name': self.pool.name,
                **self._default_scoring_fields(),
                'remove_logo': 'true',
            })

        self.assertEqual(response.status_code, 302)
        self.family.refresh_from_db()
        self.assertFalse(self.family.logo.name)
        self.assertFalse(Family._meta.get_field('logo').storage.exists(old_name))

    def test_first_upload_has_no_obsolete_logo_cleanup(self):
        storage = Family._meta.get_field('logo').storage
        self.client.force_login(self.admin_user)

        with patch.object(storage, 'delete', wraps=storage.delete) as delete, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self._settings_url(), {
                'family_name': self.family.name,
                'pool_name': self.pool.name,
                **self._default_scoring_fields(),
                'logo': self._logo_upload(),
            })

        self.assertEqual(response.status_code, 302)
        delete.assert_not_called()

    def test_audit_failure_compensates_only_new_logo_and_retains_old_reference(self):
        self.family.logo.save('previous.webp', SimpleUploadedFile('previous.webp', b'canonical'), save=True)
        old_name = self.family.logo.name
        storage = Family._meta.get_field('logo').storage
        self.client.force_login(self.admin_user)

        with patch.object(FamilyAuditLog.objects, 'create', side_effect=RuntimeError('audit failed')), \
             patch.object(storage, 'delete', wraps=storage.delete) as delete:
            with self.assertRaises(RuntimeError):
                self.client.post(self._settings_url(), {
                    'family_name': self.family.name,
                    'pool_name': self.pool.name,
                    **self._default_scoring_fields(),
                    'logo': self._logo_upload(),
                })

        self.family.refresh_from_db()
        self.assertEqual(self.family.logo.name, old_name)
        self.assertTrue(storage.exists(old_name))
        self.assertEqual(delete.call_count, 1)
        self.assertNotEqual(delete.call_args.args[0], old_name)

    def test_hostile_logo_posts_have_no_storage_or_audit_side_effects(self):
        self.family.logo.save('previous.webp', SimpleUploadedFile('previous.webp', b'canonical'), save=True)
        old_name = self.family.logo.name
        storage = Family._meta.get_field('logo').storage
        audit_count = FamilyAuditLog.objects.filter(family=self.family).count()
        cases = (
            (Client(), self._settings_url(), 302),
            (self.client, self._settings_url(), 403, self.member),
            (self.client, self._settings_url(), 404, self.outsider),
            (self.client, self._settings_url(pool=self.other_pool), 404, self.admin_user),
        )

        with patch.object(storage, 'save', wraps=storage.save) as save:
            for client, url, expected_status, *user in cases:
                with self.subTest(url=url, expected_status=expected_status):
                    if user:
                        client.force_login(user[0])
                    response = client.post(url, {
                        'family_name': self.family.name,
                        'pool_name': self.pool.name,
                        **self._default_scoring_fields(),
                        'logo': self._logo_upload(),
                        'family_id': self.other_family.id,
                        'pool_id': self.other_pool.id,
                        'logo_key': 'family-logos/other-family/forged.webp',
                    })
                    self.assertEqual(response.status_code, expected_status)
            save.assert_not_called()

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)
        with patch.object(storage, 'save', wraps=storage.save) as save:
            csrf_response = csrf_client.post(self._settings_url(), {
                'family_name': self.family.name,
                'pool_name': self.pool.name,
                **self._default_scoring_fields(),
                'logo': self._logo_upload(),
            })
            self.assertEqual(csrf_response.status_code, 403)
            save.assert_not_called()

        self.family.refresh_from_db()
        self.assertEqual(self.family.logo.name, old_name)
        self.assertTrue(storage.exists(old_name))
        self.assertEqual(FamilyAuditLog.objects.filter(family=self.family).count(), audit_count)

    def test_member_picker_renders_only_canonical_logo_in_decorative_compact_mark(self):
        self.family.logo.save(
            'canonical.webp', SimpleUploadedFile('canonical.webp', b'canonical'), save=True
        )
        canonical_url = self.family.logo.url
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('family_picker'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, canonical_url)
        self.assertContains(response, 'h-10 w-10 shrink-0 object-contain')
        self.assertContains(response, 'alt="" aria-hidden="true"')
        self.assertNotContains(response, 'alt="%s logo"' % self.family.name)
        self.assertNotContains(response, 'logo_url')
        self.assertNotContains(response, 'blob:')

    def test_picker_default_and_superadmin_variants_use_same_static_mark_contract(self):
        superuser = User.objects.create_user(
            'logo-superuser', email='logosre@example.com', password='pass', is_superuser=True,
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse('family_picker'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Families you can oversee as Superuser')
        self.assertContains(response, 'images/logo.png')
        self.assertContains(response, 'alt="" aria-hidden="true"')
        self.assertNotContains(response, 'logo_url')
        self.assertNotContains(response, 'blob:')

    def test_family_home_uses_canonical_or_default_decorative_compact_mark(self):
        self.client.force_login(self.admin_user)
        lobby_url = reverse(
            'family_pool_home',
            kwargs={'family_slug': self.family.slug, 'pool_slug': self.pool.slug},
        )

        default_response = self.client.get(lobby_url)
        self.assertEqual(default_response.status_code, 200)
        self.assertContains(default_response, 'images/logo.png')
        self.assertContains(default_response, 'alt="" aria-hidden="true"')
        self.assertContains(default_response, 'h-16 w-16 shrink-0 object-contain sm:h-20 sm:w-20')
        self.assertNotContains(default_response, 'logo_url')

        self.family.logo.save(
            'canonical.webp', SimpleUploadedFile('canonical.webp', b'canonical'), save=True
        )
        canonical_url = self.family.logo.url
        saved_response = self.client.get(lobby_url)
        self.assertContains(saved_response, canonical_url)
        self.assertNotContains(saved_response, 'blob:')

    def test_uploaded_and_removed_logo_render_only_persisted_canonical_or_default_sources(self):
        self.client.force_login(self.admin_user)
        settings_url = self._settings_url()
        picker_url = reverse('family_picker')
        lobby_url = reverse(
            'family_pool_home',
            kwargs={'family_slug': self.family.slug, 'pool_slug': self.pool.slug},
        )
        upload_response = self.client.post(settings_url, {
            'family_name': self.family.name,
            'pool_name': self.pool.name,
            **self._default_scoring_fields(),
            'logo': self._logo_upload(),
        })
        self.assertEqual(upload_response.status_code, 302)
        self.family.refresh_from_db()
        canonical_url = self.family.logo.url
        self.assertTrue(self.family.logo.name.endswith('.webp'))

        for url in (settings_url, picker_url, lobby_url):
            with self.subTest(saved_surface=url):
                response = self.client.get(url)
                self.assertContains(response, canonical_url)
                self.assertNotContains(response, 'blob:')
                self.assertNotContains(response, 'logo_url')
                self.assertNotContains(response, 'untrusted-name.png')

        remove_response = self.client.post(settings_url, {
            'family_name': self.family.name,
            'pool_name': self.pool.name,
            **self._default_scoring_fields(),
            'remove_logo': 'true',
        })
        self.assertEqual(remove_response.status_code, 302)
        self.family.refresh_from_db()
        self.assertFalse(self.family.logo.name)

        for url in (settings_url, picker_url, lobby_url):
            with self.subTest(default_surface=url):
                response = self.client.get(url)
                self.assertContains(response, 'images/logo.png')
                self.assertNotContains(response, canonical_url)
                self.assertNotContains(response, 'blob:')
                self.assertNotContains(response, 'logo_url')
class StaleInviteRedemptionTests(TestCase):
    """A previously-issued invite link is otherwise perfectly valid (unexpired,
    unused, correct family/pool) but must still be rejected when redeemed by a
    brand-new (non-member) user after the pool has locked entries following
    Week 1. Exercises accept_invitation_for_user() directly rather than via
    the join_family/accept_invite_link views."""

    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.owner = User.objects.create_user(
            "stale-invite-owner", email="stale-owner@example.com", password="pass"
        )
        self.new_user = User.objects.create_user(
            "stale-invite-newuser", email="stale-newuser@example.com", password="pass"
        )
        self.family = Family.objects.create(name="Stale Family", slug="stale-family")
        self.pool = Pool.objects.create(
            family=self.family,
            name="Main Pickem",
            slug="main",
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.owner,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.ACTIVE,
        )
        PoolSettings.objects.create(
            pool=self.pool,
            late_join_policy=PoolSettings.LateJoinPolicy.LOCK_AFTER_WEEK_1,
        )

    def test_prior_link_rejected_for_new_user_when_locked(self):
        from pickem_homepage.views import (
            accept_invitation_for_user,
            create_admin_invitation,
            ENTRIES_LOCKED_MESSAGE,
        )

        factory = RequestFactory()

        # Invite issued earlier, while the pool was still open to new joiners.
        creation_request = factory.post("/family/stale-family/main/invites/")
        creation_request.user = self.owner
        invitation, raw_code = create_admin_invitation(
            family=self.family,
            pool=self.pool,
            actor=self.owner,
            role=FamilyMembership.Role.MEMBER,
            recipient_email='',
            expires_in_days=14,
            request=creation_request,
        )

        # Week 1 has since completed, locking the pool to new entries. A new
        # (never-a-member) user now tries to redeem that still-valid link.
        with patch("pickem_api.weekly_winners.week_is_complete", return_value=True):
            redemption_request = factory.post("/invites/{}/".format(raw_code))
            redemption_request.user = self.new_user
            result_invitation, result_pool, membership, error = accept_invitation_for_user(
                redemption_request, raw_code,
            )

        self.assertIsNone(result_invitation)
        self.assertIsNone(result_pool)
        self.assertIsNone(membership)
        self.assertEqual(error, ENTRIES_LOCKED_MESSAGE)
        self.assertFalse(
            FamilyMembership.objects.filter(
                family=self.family, user=self.new_user,
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.use_count, 0)


class FamilyAdminSettingsFormTests(TestCase):
    """Server-side protections on the pool-admin settings form."""

    def _payload(self, **overrides):
        payload = {
            'family_name': 'Smith Family',
            'pool_name': 'Main Pickem',
            'picks_lock_mode': PoolSettings.PicksLockMode.KICKOFF,
            'win_points': '1',
            'tie_points': '0',
            'weekly_winner_points': '2',
            'primary_tiebreaker': PoolSettings.PrimaryTiebreaker.TOTAL_SCORE,
            'secondary_tiebreaker': PoolSettings.SecondaryTiebreaker.COMBINED_YARDS,
            'perfect_week_bonus_amount': '10',
            'entry_fee_amount': '0',
            'pick_type': PoolSettings.PickType.STRAIGHT_UP,
            'missed_pick_policy': PoolSettings.MissedPickPolicy.ZERO_POINTS,
            'late_join_policy': PoolSettings.LateJoinPolicy.OPEN,
            'payout_structure': PoolSettings.PayoutStructure.WINNER_TAKES_ALL,
        }
        payload.update(overrides)
        return payload

    def _form(self, **overrides):
        from pickem_homepage.forms import FamilyAdminSettingsForm

        return FamilyAdminSettingsForm(
            self._payload(**overrides),
            initial={'include_playoffs': False},
        )

    def test_baseline_payload_is_valid(self):
        form = self._form()
        self.assertTrue(form.is_valid(), form.errors)

    def test_crop_fields_are_all_or_nothing_strict_square_integers(self):
        valid = self._form(crop_x='0', crop_y='1', crop_width='12', crop_height='12')
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.cleaned_data['crop_data'], {'x': 0, 'y': 1, 'width': 12, 'height': 12})
        for invalid in (
            {'crop_x': '0'},
            {'crop_x': '0', 'crop_y': '0', 'crop_width': '12', 'crop_height': '12.0'},
            {'crop_x': '-1', 'crop_y': '0', 'crop_width': '12', 'crop_height': '12'},
            {'crop_x': '0', 'crop_y': '0', 'crop_width': '12', 'crop_height': '11'},
        ):
            with self.subTest(invalid=invalid):
                form = self._form(**invalid)
                self.assertFalse(form.is_valid())
                self.assertIn('logo', form.errors)

    def test_zero_win_points_rejected(self):
        form = self._form(win_points='0')
        self.assertFalse(form.is_valid())
        self.assertIn('win_points', form.errors)

    def test_secondary_tiebreaker_may_not_repeat_primary_metric(self):
        cases = [
            (PoolSettings.PrimaryTiebreaker.COMBINED_YARDS,
             PoolSettings.SecondaryTiebreaker.COMBINED_YARDS),
            (PoolSettings.PrimaryTiebreaker.TOTAL_SCORE,
             PoolSettings.SecondaryTiebreaker.TOTAL_SCORE),
            (PoolSettings.PrimaryTiebreaker.TOTAL_SCORE_NO_OVER,
             PoolSettings.SecondaryTiebreaker.TOTAL_SCORE),
        ]
        for primary, secondary in cases:
            with self.subTest(primary=primary, secondary=secondary):
                form = self._form(
                    primary_tiebreaker=primary, secondary_tiebreaker=secondary
                )
                self.assertFalse(form.is_valid())
                self.assertIn('secondary_tiebreaker', form.errors)

    def test_terminal_secondary_choices_always_allowed(self):
        for secondary in (
            PoolSettings.SecondaryTiebreaker.SPLIT_POINTS,
            PoolSettings.SecondaryTiebreaker.COIN_FLIP,
        ):
            form = self._form(secondary_tiebreaker=secondary)
            self.assertTrue(form.is_valid(), form.errors)

    def test_include_playoffs_is_disabled_and_ignores_tampering(self):
        # Even a hand-crafted POST claiming include_playoffs=on keeps the
        # stored (initial) value, because the field is disabled.
        form = self._form(include_playoffs='on')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data['include_playoffs'])

    def test_against_spread_pick_type_rejected(self):
        form = self._form(pick_type=PoolSettings.PickType.AGAINST_SPREAD)
        self.assertFalse(form.is_valid())
        self.assertIn('pick_type', form.errors)


class IsCommissionerTests(TestCase):
    """Unit tests for the is_commissioner() helper."""

    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def test_anonymous_user_returns_false(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(is_commissioner(AnonymousUser()))

    def test_authenticated_user_no_profile_returns_false(self):
        user = User.objects.create_user("noprofile", password="pass")
        # Delete profile if auto-created by a signal
        UserProfile.objects.filter(user=user).delete()
        self.assertFalse(is_commissioner(user))

    def test_authenticated_user_with_profile_not_commissioner(self):
        user = User.objects.create_user("regular", password="pass")
        UserProfile.objects.update_or_create(
            user=user, defaults={"is_commissioner": False}
        )
        self.assertFalse(is_commissioner(user))

    def test_user_with_commissioner_profile_returns_true(self):
        user = User.objects.create_user("commish", password="pass")
        UserProfile.objects.update_or_create(
            user=user, defaults={"is_commissioner": True}
        )
        self.assertTrue(is_commissioner(user))

    def test_superuser_returns_true(self):
        user = User.objects.create_superuser(
            "admin", "admin@example.com", "pass"
        )
        self.assertTrue(is_commissioner(user))


class TenantAuthorizationDecoratorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.family = Family.objects.create(name="Smith Family", slug="smith-family")
        self.pool = Pool.objects.create(
            family=self.family,
            name="Main Pickem",
            slug="main",
            season=2526,
        )
        self.member = User.objects.create_user("member", password="pass")
        self.admin_user = User.objects.create_user("admin-member", password="pass")
        self.owner = User.objects.create_user("owner-member", password="pass")
        self.outsider = User.objects.create_user("outsider", password="pass")

        FamilyMembership.objects.create(
            family=self.family,
            user=self.member,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.admin_user,
            role=FamilyMembership.Role.ADMIN,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.owner,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _request(self, user):
        request = self.factory.get("/families/smith-family/pools/main/proof/")
        request.user = user
        return request

    def _view(self, minimum_role=FamilyMembership.Role.MEMBER):
        @family_member_required(minimum_role=minimum_role)
        def guarded_view(request, family_slug, pool_slug):
            return HttpResponse(request.tenant_context.membership.role)

        return guarded_view

    def test_anonymous_browser_request_redirects_to_login(self):
        response = self._view()(self._request(AnonymousUser()), "smith-family", "main")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_non_member_browser_request_raises_404(self):
        with self.assertRaises(Http404):
            self._view()(self._request(self.outsider), "smith-family", "main")

    def test_member_browser_request_is_allowed_for_member_route(self):
        response = self._view()(self._request(self.member), "smith-family", "main")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, FamilyMembership.Role.MEMBER.encode())

    def test_member_browser_request_gets_403_for_admin_route(self):
        response = self._view(FamilyMembership.Role.ADMIN)(
            self._request(self.member), "smith-family", "main"
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_and_owner_browser_requests_are_allowed_for_admin_route(self):
        for user in [self.admin_user, self.owner]:
            response = self._view(FamilyMembership.Role.ADMIN)(
                self._request(user), "smith-family", "main"
            )

            self.assertEqual(response.status_code, 200)


class GetSeasonTests(TestCase):
    """Unit tests for pickem.utils.get_season()."""

    def test_returns_season_int_when_record_exists(self):
        currentSeason.objects.create(season=2526, display_name="2025-2026")
        result = get_season()
        self.assertEqual(result, 2526)
        self.assertIsInstance(result, int)

    def test_returns_display_name_when_requested(self):
        currentSeason.objects.create(season=2526, display_name="2025-2026")
        result = get_season(display_name=True)
        self.assertEqual(result, "2025-2026")

    def test_returns_default_int_when_no_record(self):
        currentSeason.objects.all().delete()
        result = get_season()
        self.assertEqual(result, 2024)

    def test_returns_default_display_when_no_record(self):
        currentSeason.objects.all().delete()
        result = get_season(display_name=True)
        self.assertEqual(result, "2024-2025")


class MessageBoardPostModelTests(TestCase):
    """Unit tests for the MessageBoardPost model."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("poster", password="pass")

    def test_str(self):
        post = MessageBoardPost.objects.create(
            user=self.user, title="Hello World", content="body"
        )
        self.assertEqual(str(post), "Hello World by poster")

    def test_score_property(self):
        post = MessageBoardPost.objects.create(
            user=self.user, title="Score Test", content="body",
            upvotes=10, downvotes=3,
        )
        self.assertEqual(post.score, 7)

    def test_comment_count_property(self):
        post = MessageBoardPost.objects.create(
            user=self.user, title="Comments", content="body"
        )
        MessageBoardComment.objects.create(
            post=post, user=self.user, content="c1"
        )
        MessageBoardComment.objects.create(
            post=post, user=self.user, content="c2"
        )
        # Inactive comment should not be counted
        MessageBoardComment.objects.create(
            post=post, user=self.user, content="hidden", is_active=False
        )
        self.assertEqual(post.comment_count, 2)


class MessageBoardCommentModelTests(TestCase):
    """Unit tests for the MessageBoardComment model."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("commenter", password="pass")
        cls.post = MessageBoardPost.objects.create(
            user=cls.user, title="Post", content="body"
        )

    def test_str(self):
        comment = MessageBoardComment.objects.create(
            post=self.post, user=self.user, content="Nice"
        )
        self.assertEqual(str(comment), "Comment by commenter on Post")

    def test_depth_top_level_is_zero(self):
        comment = MessageBoardComment.objects.create(
            post=self.post, user=self.user, content="Top"
        )
        self.assertEqual(comment.depth, 0)

    def test_depth_reply_is_one(self):
        parent = MessageBoardComment.objects.create(
            post=self.post, user=self.user, content="Parent"
        )
        reply = MessageBoardComment.objects.create(
            post=self.post, user=self.user, content="Reply", parent=parent
        )
        self.assertEqual(reply.depth, 1)


class SiteBannerModelTests(TestCase):
    """Unit tests for the SiteBanner model."""

    def test_str_active(self):
        banner = SiteBanner.objects.create(
            title="Season Starts",
            is_active=True,
            start_date=timezone.now() - timezone.timedelta(hours=1),
        )
        self.assertIn("Active", str(banner))

    def test_str_inactive(self):
        banner = SiteBanner.objects.create(
            title="Old News",
            is_active=False,
        )
        self.assertIn("Inactive", str(banner))

    def test_is_currently_active_true(self):
        banner = SiteBanner.objects.create(
            title="Now",
            is_active=True,
            start_date=timezone.now() - timezone.timedelta(hours=1),
            end_date=timezone.now() + timezone.timedelta(hours=1),
        )
        self.assertTrue(banner.is_currently_active())

    def test_is_currently_active_false_when_disabled(self):
        banner = SiteBanner.objects.create(
            title="Off",
            is_active=False,
            start_date=timezone.now() - timezone.timedelta(hours=1),
        )
        self.assertFalse(banner.is_currently_active())

    def test_is_currently_active_false_before_start(self):
        banner = SiteBanner.objects.create(
            title="Future",
            is_active=True,
            start_date=timezone.now() + timezone.timedelta(hours=1),
        )
        self.assertFalse(banner.is_currently_active())

    def test_is_currently_active_false_after_end(self):
        banner = SiteBanner.objects.create(
            title="Expired",
            is_active=True,
            start_date=timezone.now() - timezone.timedelta(hours=2),
            end_date=timezone.now() - timezone.timedelta(hours=1),
        )
        self.assertFalse(banner.is_currently_active())

    def test_site_wide_banner_can_remain_family_null_and_active(self):
        banner = SiteBanner.objects.create(
            title="Site-wide",
            is_active=True,
            start_date=timezone.now() - timezone.timedelta(hours=1),
            family=None,
        )

        self.assertIsNone(banner.family)
        self.assertEqual(SiteBanner.get_active_banner(), banner)


class HomepageFamilyScopeModelTests(TestCase):
    """Model tests for nullable family scope on homepage-owned data."""

    @classmethod
    def setUpTestData(cls):
        cls.family = Family.objects.create(name="Tenant Family", slug="tenant-family")
        cls.user = User.objects.create_user("family_user", password="pass")

    def test_message_board_rows_can_reference_family(self):
        post = MessageBoardPost.objects.create(
            family=self.family,
            user=self.user,
            title="Scoped post",
            content="body",
        )
        comment = MessageBoardComment.objects.create(
            family=self.family,
            post=post,
            user=self.user,
            content="reply",
        )
        post_vote = MessageBoardVote.objects.create(
            family=self.family,
            user=self.user,
            post=post,
            vote_type=1,
        )
        comment_vote = MessageBoardVote.objects.create(
            family=self.family,
            user=self.user,
            comment=comment,
            vote_type=-1,
        )

        self.assertEqual(post.family, self.family)
        self.assertEqual(comment.family, self.family)
        self.assertEqual(post_vote.family, self.family)
        self.assertEqual(comment_vote.family, self.family)

    def test_family_fields_are_nullable_first(self):
        post = MessageBoardPost.objects.create(
            family=None,
            user=self.user,
            title="Legacy post",
            content="body",
        )
        comment = MessageBoardComment.objects.create(
            family=None,
            post=post,
            user=self.user,
            content="reply",
        )
        vote = MessageBoardVote.objects.create(
            family=None,
            user=self.user,
            post=post,
            vote_type=1,
        )

        self.assertIsNone(post.family)
        self.assertIsNone(comment.family)
        self.assertIsNone(vote.family)


class HomepageFamilyBackfillMigrationTests(TestCase):
    """Direct tests for homepage family backfill helpers."""

    migration = import_module(
        "pickem_homepage.migrations.0005_add_family_scope"
    )

    def setUp(self):
        legacy_family = Family.objects.filter(
            slug=self.migration.LEGACY_FAMILY_SLUG
        ).first()
        if legacy_family:
            FamilyMembership.objects.filter(family=legacy_family).delete()

    def test_backfill_assigns_message_board_rows_to_legacy_family_and_leaves_banners_site_wide(self):
        user = User.objects.create_user("poster", password="pass")
        post = MessageBoardPost.objects.create(user=user, title="Post", content="body")
        comment = MessageBoardComment.objects.create(
            post=post, user=user, content="comment"
        )
        post_vote = MessageBoardVote.objects.create(
            user=user, post=post, vote_type=1
        )
        comment_vote = MessageBoardVote.objects.create(
            user=user, comment=comment, vote_type=-1
        )
        banner = SiteBanner.objects.create(title="Global", is_active=True)

        self.migration.backfill_homepage_family_scope(
            apps=MigrationExecutor(connection).loader.project_state().apps,
            schema_editor=None,
        )

        legacy_family = Family.objects.get(slug=self.migration.LEGACY_FAMILY_SLUG)
        post.refresh_from_db()
        comment.refresh_from_db()
        post_vote.refresh_from_db()
        comment_vote.refresh_from_db()
        banner.refresh_from_db()
        self.assertEqual(post.family, legacy_family)
        self.assertEqual(comment.family, legacy_family)
        self.assertEqual(post_vote.family, legacy_family)
        self.assertEqual(comment_vote.family, legacy_family)
        self.assertIsNone(banner.family)

    def test_backfill_creates_member_memberships_for_message_board_only_active_users(self):
        post_user = User.objects.create_user("post_only", password="pass")
        comment_user = User.objects.create_user("comment_only", password="pass")
        vote_user = User.objects.create_user("vote_only", password="pass")
        post = MessageBoardPost.objects.create(
            user=post_user, title="Post", content="body"
        )
        comment = MessageBoardComment.objects.create(
            post=post, user=comment_user, content="comment"
        )
        MessageBoardVote.objects.create(user=vote_user, comment=comment, vote_type=1)

        self.migration.backfill_homepage_family_scope(
            apps=MigrationExecutor(connection).loader.project_state().apps,
            schema_editor=None,
        )

        legacy_family = Family.objects.get(slug=self.migration.LEGACY_FAMILY_SLUG)
        memberships = FamilyMembership.objects.filter(
            family=legacy_family,
            user__in=[post_user, comment_user, vote_user],
            status=FamilyMembership.Status.ACTIVE,
            role=FamilyMembership.Role.MEMBER,
        )
        self.assertEqual(memberships.count(), 3)

    def test_backfill_preserves_existing_elevated_roles_and_skips_inactive_users(self):
        admin_user = User.objects.create_user("admin_member", password="pass")
        inactive_user = User.objects.create_user(
            "inactive_member", password="pass", is_active=False
        )
        legacy_family, _ = Family.objects.get_or_create(
            slug=self.migration.LEGACY_FAMILY_SLUG,
            defaults={"name": self.migration.LEGACY_FAMILY_NAME},
        )
        FamilyMembership.objects.create(
            family=legacy_family,
            user=admin_user,
            role=FamilyMembership.Role.ADMIN,
            status=FamilyMembership.Status.ACTIVE,
        )
        MessageBoardPost.objects.create(
            user=admin_user, title="Admin post", content="body"
        )
        MessageBoardPost.objects.create(
            user=inactive_user, title="Inactive post", content="body"
        )

        self.migration.backfill_homepage_family_scope(
            apps=MigrationExecutor(connection).loader.project_state().apps,
            schema_editor=None,
        )

        admin_membership = FamilyMembership.objects.get(
            family=legacy_family, user=admin_user
        )
        self.assertEqual(admin_membership.role, FamilyMembership.Role.ADMIN)
        self.assertFalse(
            FamilyMembership.objects.filter(
                family=legacy_family, user=inactive_user
            ).exists()
        )

    def test_comment_and_vote_family_backfill_derive_from_targets(self):
        legacy_family, _ = Family.objects.get_or_create(
            slug=self.migration.LEGACY_FAMILY_SLUG,
            defaults={"name": self.migration.LEGACY_FAMILY_NAME},
        )
        user = User.objects.create_user("target_user", password="pass")
        post = MessageBoardPost.objects.create(
            family=legacy_family, user=user, title="Scoped", content="body"
        )
        comment = MessageBoardComment.objects.create(
            family=None, post=post, user=user, content="comment"
        )
        post_vote = MessageBoardVote.objects.create(
            family=None, user=user, post=post, vote_type=1
        )
        comment_vote = MessageBoardVote.objects.create(
            family=None, user=user, comment=comment, vote_type=-1
        )

        self.migration.backfill_homepage_family_scope(
            apps=MigrationExecutor(connection).loader.project_state().apps,
            schema_editor=None,
        )

        comment.refresh_from_db()
        post_vote.refresh_from_db()
        comment_vote.refresh_from_db()
        self.assertEqual(comment.family, legacy_family)
        self.assertEqual(post_vote.family, legacy_family)
        self.assertEqual(comment_vote.family, legacy_family)


class HomepageFamilyScopeAdminTests(TestCase):
    """Admin registration tests for homepage family scope fields."""

    def test_admin_classes_expose_family_for_homepage_scope(self):
        expected_models = [
            SiteBanner,
            MessageBoardPost,
            MessageBoardComment,
            MessageBoardVote,
        ]

        for model in expected_models:
            model_admin = admin.site._registry[model]
            self.assertIn("family", model_admin.list_filter)
            self.assertIn("family", model_admin.get_list_display(None))


class DjangoSystemCheckTests(TestCase):
    """Verify that Django system checks pass."""

    def test_django_system_check(self):
        out = StringIO()
        call_command("check", stdout=out, stderr=StringIO())
        # If check passes, no exception is raised


class PoolLockTemplateTagTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Smith Family", slug="smith-family")
        self.pool = Pool.objects.create(
            family=self.family,
            name="Main Pickem",
            slug="main",
            season=2526,
            competition="nfl",
        )
        self.game = GamesAndScores.objects.create(
            id=100,
            slug="home-away",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now(),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=1,
            homeTeamSlug="home",
            homeTeamName="Home",
            awayTeamId=2,
            awayTeamSlug="away",
            awayTeamName="Away",
        )

    def test_pool_lock_helpers_do_not_swallow_unexpected_query_errors(self):
        from pickem_homepage.templatetags.pickem_homepage_extras import (
            game_lock_reason_for_pool,
            is_game_locked_for_pool,
        )

        with patch(
            "pickem_homepage.templatetags.pickem_homepage_extras.GamesAndScores.objects.filter",
            side_effect=RuntimeError("db broke"),
        ):
            with self.assertRaisesMessage(RuntimeError, "db broke"):
                is_game_locked_for_pool(self.game, self.pool)
            with self.assertRaisesMessage(RuntimeError, "db broke"):
                game_lock_reason_for_pool(self.game, self.pool)


class HomepageFormSecurityTests(TestCase):
    def test_game_picks_form_exposes_only_bindable_pick_fields(self):
        from pickem_homepage.forms import GamePicksForm

        self.assertEqual(
            tuple(GamePicksForm.Meta.fields),
            ("pick", "tieBreakerScore", "tieBreakerYards"),
        )


class GlobalLeaderboardTests(TestCase):
    """The public site-wide leaderboard blends every pool for the season."""

    def setUp(self):
        self.client = Client()
        self.season = 2526
        site, _ = Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        social_app, _ = SocialApp.objects.get_or_create(
            provider="google",
            defaults={
                "name": "Google",
                "client_id": "test-client-id",
                "secret": "test-secret",
            },
        )
        social_app.sites.add(site)
        currentSeason.objects.create(season=self.season, display_name="2025-2026")
        self.smith_family = Family.objects.create(name="Smith", slug="smith-gl")
        self.jones_family = Family.objects.create(name="Jones", slug="jones-gl")
        self.smith_pool = Pool.objects.create(
            family=self.smith_family, name="Smith Pool", slug="smith-pool-gl",
            season=self.season, competition="nfl", status=Pool.Status.ACTIVE,
            is_default=True,
        )
        self.jones_pool = Pool.objects.create(
            family=self.jones_family, name="Jones Pool", slug="jones-pool-gl",
            season=self.season, competition="nfl", status=Pool.Status.ACTIVE,
            is_default=True,
        )
        self.alice = User.objects.create_user("alice-gl", email="alice-gl@example.com", password="x")
        self.bob = User.objects.create_user("bob-gl", email="bob-gl@example.com", password="x")
        self.admin = User.objects.create_user(
            "admin-gl", email="admin-gl@example.com", password="x", is_superuser=True
        )
        self._link_google(self.alice, given_name="Alice")
        self._link_google(self.bob, given_name="Bob")
        FamilyMembership.objects.create(
            family=self.smith_family,
            user=self.alice,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.smith_family,
            user=self.bob,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.smith_family,
            user=self.admin,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _link_google(self, user, *, given_name=None):
        return SocialAccount.objects.create(
            user=user,
            provider="google",
            uid=f"google-{user.id}",
            extra_data={"given_name": given_name or user.username},
        )

    def _points(self, pool, user, total):
        return userSeasonPoints.objects.create(
            pool=pool, userEmail=user.email, userID=str(user.id),
            gameseason=self.season, gameyear="2025", total_points=total,
        )

    def test_leaderboard_is_public_and_blends_points_across_pools(self):
        # Alice plays in BOTH pools; her site-wide total is the sum.
        self._points(self.smith_pool, self.alice, 10)
        self._points(self.jones_pool, self.alice, 7)
        # Bob only plays one pool.
        self._points(self.smith_pool, self.bob, 12)

        response = self.client.get(reverse("global_leaderboard"))  # no login
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/global_leaderboard.html")

        entries = {e["userID"]: e for e in response.context["entries"]}
        self.assertEqual(entries[str(self.alice.id)]["points"], 17)  # 10 + 7 blended
        self.assertEqual(entries[str(self.alice.id)]["leagues"], 2)
        self.assertEqual(entries[str(self.bob.id)]["points"], 12)
        # Alice (17) outranks Bob (12) even though Bob's single-pool score is higher.
        self.assertEqual(entries[str(self.alice.id)]["rank"], 1)
        self.assertEqual(entries[str(self.bob.id)]["rank"], 2)

    def test_leaderboard_excludes_superusers_and_blends_accuracy(self):
        self._points(self.smith_pool, self.alice, 10)
        self._points(self.smith_pool, self.admin, 999)  # admin must not appear
        local_adminjim = User.objects.create_user(
            "ADMINJIM", email="adminjim@example.com", password="x"
        )
        FamilyMembership.objects.create(
            family=self.smith_family,
            user=local_adminjim,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )
        self._points(self.smith_pool, local_adminjim, 250)
        # The global leaderboard blends accuracy from the pool-null (global)
        # userStats row — the one update_stats writes per user in its default,
        # season-wide run. A per-pool row (pool=<pool>) is a different record and
        # must not feed the global figure.
        userStats.objects.create(
            pool=None, userEmail=self.alice.email, userID=str(self.alice.id),
            correctPickTotalSeason=8, totalPicksSeason=10, weeksWonSeason=1,
        )
        # A per-pool row for the same user with different numbers must be ignored
        # by the global leaderboard (regression guard for pool-scoped rows).
        userStats.objects.create(
            pool=self.smith_pool, userEmail=self.alice.email, userID=str(self.alice.id),
            correctPickTotalSeason=1, totalPicksSeason=10, weeksWonSeason=0,
        )

        response = self.client.get(reverse("global_leaderboard"))
        self.assertEqual(response.status_code, 200)
        ids = [e["userID"] for e in response.context["entries"]]
        self.assertIn(str(self.alice.id), ids)
        self.assertNotIn(str(self.admin.id), ids)
        self.assertNotIn(str(local_adminjim.id), ids)
        alice = next(e for e in response.context["entries"] if e["userID"] == str(self.alice.id))
        self.assertEqual(alice["accuracy"], 80)  # 8/10 from the global row, not 9/20

    def test_leaderboard_includes_active_member_with_no_points_row(self):
        FamilyMembership.objects.create(
            family=self.jones_family,
            user=self.bob,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )

        response = self.client.get(reverse("global_leaderboard"))

        entries = {e["userID"]: e for e in response.context["entries"]}
        self.assertIn(str(self.bob.id), entries)
        self.assertEqual(entries[str(self.bob.id)]["points"], 0)
        self.assertEqual(entries[str(self.bob.id)]["leagues"], 0)

    def test_players_tied_at_zero_share_rank_one_and_podium_is_hidden(self):
        # Season just started: everyone has a standings row but no points, so
        # all players must be tied at rank 1 (not 1,2,3) and the podium hidden.
        self._points(self.smith_pool, self.alice, 0)
        self._points(self.smith_pool, self.bob, 0)

        response = self.client.get(reverse("global_leaderboard"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_scores"])
        ranks = {e["userID"]: e["rank"] for e in response.context["entries"]}
        self.assertEqual(ranks[str(self.alice.id)], 1)
        self.assertEqual(ranks[str(self.bob.id)], 1)

    def test_competition_ranking_skips_after_a_tie(self):
        # Two tied leaders, then a third player: ranks are 1, 1, 3.
        self._points(self.smith_pool, self.alice, 10)
        self._points(self.smith_pool, self.bob, 10)
        carol = User.objects.create_user("carol-gl", email="carol-gl@example.com", password="x")
        self._link_google(carol, given_name="Carol")
        FamilyMembership.objects.create(
            family=self.smith_family,
            user=carol,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )
        self._points(self.smith_pool, carol, 5)

        response = self.client.get(reverse("global_leaderboard"))

        self.assertTrue(response.context["has_scores"])
        ranks = {e["userID"]: e["rank"] for e in response.context["entries"]}
        self.assertEqual(ranks[str(self.alice.id)], 1)
        self.assertEqual(ranks[str(self.bob.id)], 1)
        self.assertEqual(ranks[str(carol.id)], 3)


class TeamBrandPresentationFilterTests(TestCase):
    def test_dict_input_normalizes_hash_prefixed_and_shorthand_colors(self):
        from pickem_homepage.templatetags.pickem_homepage_extras import (
            team_brand_presentation,
        )

        presentation = team_brand_presentation(
            {
                "color": "#123",
                "alternateColor": "#003594",
                "logo_contrast_preset": Teams.LogoContrastPreset.REVERSE_GRADIENT,
            }
        )

        self.assertEqual(
            presentation["background_style"],
            "background: linear-gradient(135deg, #11223340 0%, #003594 50%, #003594 100%);",
        )
        self.assertEqual(
            presentation["preset"],
            Teams.LogoContrastPreset.REVERSE_GRADIENT,
        )

    def test_blank_and_invalid_colors_fall_back_to_safe_defaults(self):
        from pickem_homepage.templatetags.pickem_homepage_extras import (
            team_brand_presentation,
        )

        team = Teams(
            color="",
            alternateColor="not-a-color",
            logo_contrast_preset=Teams.LogoContrastPreset.WHITE_BURST,
        )

        presentation = team_brand_presentation(team)

        self.assertEqual(
            presentation["background_style"],
            "background: linear-gradient(135deg, #66666640 0%, #333333 50%, #333333 100%);",
        )
        self.assertTrue(presentation["show_white_burst"])

    def test_default_preset_uses_existing_gradient_and_no_glow(self):
        from pickem_homepage.templatetags.pickem_homepage_extras import (
            team_brand_presentation,
        )

        team = Teams(color="003594", alternateColor="869397", logo_contrast_preset="")

        presentation = team_brand_presentation(team)

        self.assertEqual(
            presentation["preset"],
            Teams.LogoContrastPreset.DEFAULT,
        )
        self.assertEqual(
            presentation["background_style"],
            "background: linear-gradient(135deg, #86939740 0%, #003594 50%, #003594 100%);",
        )
        self.assertFalse(presentation["show_white_burst"])
        self.assertEqual(presentation["logo_style"], "")

    def test_reverse_gradient_swaps_primary_and_alternate_colors(self):
        from pickem_homepage.templatetags.pickem_homepage_extras import (
            team_brand_presentation,
        )

        team = Teams(
            color="112233",
            alternateColor="AABBCC",
            logo_contrast_preset=Teams.LogoContrastPreset.REVERSE_GRADIENT,
        )

        presentation = team_brand_presentation(team)

        self.assertEqual(
            presentation["preset"],
            Teams.LogoContrastPreset.REVERSE_GRADIENT,
        )
        self.assertEqual(
            presentation["background_style"],
            "background: linear-gradient(135deg, #11223340 0%, #AABBCC 50%, #AABBCC 100%);",
        )
        self.assertFalse(presentation["show_white_burst"])
        self.assertEqual(presentation["logo_style"], "")

    def test_white_burst_keeps_default_gradient_and_adds_logo_glow(self):
        from pickem_homepage.templatetags.pickem_homepage_extras import (
            team_brand_presentation,
        )

        team = Teams(
            color="224466",
            alternateColor="88AACC",
            logo_contrast_preset=Teams.LogoContrastPreset.WHITE_BURST,
        )

        presentation = team_brand_presentation(team)

        self.assertEqual(
            presentation["preset"],
            Teams.LogoContrastPreset.WHITE_BURST,
        )
        self.assertEqual(
            presentation["background_style"],
            "background: linear-gradient(135deg, #88AACC40 0%, #224466 50%, #224466 100%);",
        )
        self.assertTrue(presentation["show_white_burst"])
        self.assertIn("drop-shadow", presentation["logo_style"])
        self.assertIn("rgba(255, 255, 255", presentation["logo_style"])


class PicksLockForPoolModeTests(TestCase):
    def _future_game(self):
        return GamesAndScores.objects.create(
            id=990001,
            slug="aaa-bbb-2425-week-1",
            gameseason=2425,
            gameWeek='1',
            gameyear="2024",
            competition='nfl',
            statusType='notstarted',
            statusTitle='Scheduled',
            startTimestamp=timezone.now() + timedelta(days=2),
            awayTeamSlug='aaa',
            awayTeamId=1,
            awayTeamName='Aaa Team',
            homeTeamSlug='bbb',
            homeTeamId=2,
            homeTeamName='Bbb Team',
        )

    def test_sunday_1pm_mode_uses_week_rule(self):
        from pickem.utils import is_pick_locked_for_pool
        fam = Family.objects.create(name="M", slug="m")
        pool = Pool.objects.create(family=fam, name="p", slug="p", season=2425)
        PoolSettings.objects.create(pool=pool, picks_lock_mode=PoolSettings.PicksLockMode.SUNDAY_1PM)
        game = self._future_game()
        locked, _reason = is_pick_locked_for_pool(game, pool)
        self.assertFalse(locked)  # future game, before any cutoff

    def test_kickoff_mode_future_game_unlocked(self):
        from pickem.utils import is_pick_locked_for_pool
        fam = Family.objects.create(name="K", slug="k")
        pool = Pool.objects.create(family=fam, name="p", slug="p", season=2425)
        PoolSettings.objects.create(pool=pool, picks_lock_mode=PoolSettings.PicksLockMode.KICKOFF)
        game = self._future_game()
        locked, _reason = is_pick_locked_for_pool(game, pool)
        self.assertFalse(locked)

    def test_sunday_1pm_mode_locks_late_game_before_its_own_kickoff(self):
        """Discriminates the two modes: a "late" game (after the week's Sunday
        1PM ET cutoff) that hasn't kicked off yet must be locked under
        SUNDAY_1PM but would NOT be locked under KICKOFF (see test below).
        """
        from pickem.utils import is_pick_locked_for_pool
        fam = Family.objects.create(name="S1", slug="s1")
        pool = Pool.objects.create(family=fam, name="p", slug="p", season=2425)
        PoolSettings.objects.create(pool=pool, picks_lock_mode=PoolSettings.PicksLockMode.SUNDAY_1PM)

        # Anchor game fixes the week's Sunday 1PM ET cutoff safely in the past
        # (2020-01-05 is a Sunday) so "now" is always past it.
        anchor = GamesAndScores.objects.create(
            id=990002,
            slug="anchor-990002",
            gameseason=2425,
            gameWeek='1',
            gameyear="2024",
            competition='nfl',
            statusType='finished',
            statusTitle='Final',
            startTimestamp=timezone.make_aware(timezone.datetime(2020, 1, 5, 12, 0)),
            awayTeamSlug='ccc',
            awayTeamId=3,
            awayTeamName='Ccc Team',
            homeTeamSlug='ddd',
            homeTeamId=4,
            homeTeamName='Ddd Team',
        )
        # Target "late" game: kickoff hasn't happened yet, but the week's
        # Sunday 1PM ET cutoff (anchored above) has already passed.
        late_game = GamesAndScores.objects.create(
            id=990003,
            slug="late-990003",
            gameseason=2425,
            gameWeek='1',
            gameyear="2024",
            competition='nfl',
            statusType='notstarted',
            statusTitle='Scheduled',
            startTimestamp=timezone.now() + timedelta(hours=2),
            awayTeamSlug='eee',
            awayTeamId=5,
            awayTeamName='Eee Team',
            homeTeamSlug='fff',
            homeTeamId=6,
            homeTeamName='Fff Team',
        )

        locked, reason = is_pick_locked_for_pool(late_game, pool, week_games=[anchor, late_game])
        self.assertTrue(locked)
        self.assertIn("Sunday 1PM", reason)

    def test_kickoff_mode_does_not_lock_late_game_before_its_own_kickoff(self):
        """Same 'late game' shape as above, but under KICKOFF mode the game
        must stay unlocked until its own kickoff, regardless of any weekly
        cutoff — proving the branch genuinely reads picks_lock_mode."""
        from pickem.utils import is_pick_locked_for_pool
        fam = Family.objects.create(name="K1", slug="k1")
        pool = Pool.objects.create(family=fam, name="p", slug="p", season=2425)
        PoolSettings.objects.create(pool=pool, picks_lock_mode=PoolSettings.PicksLockMode.KICKOFF)

        anchor = GamesAndScores.objects.create(
            id=990004,
            slug="anchor-990004",
            gameseason=2425,
            gameWeek='1',
            gameyear="2024",
            competition='nfl',
            statusType='finished',
            statusTitle='Final',
            startTimestamp=timezone.make_aware(timezone.datetime(2020, 1, 5, 12, 0)),
            awayTeamSlug='ggg',
            awayTeamId=7,
            awayTeamName='Ggg Team',
            homeTeamSlug='hhh',
            homeTeamId=8,
            homeTeamName='Hhh Team',
        )
        late_game = GamesAndScores.objects.create(
            id=990005,
            slug="late-990005",
            gameseason=2425,
            gameWeek='1',
            gameyear="2024",
            competition='nfl',
            statusType='notstarted',
            statusTitle='Scheduled',
            startTimestamp=timezone.now() + timedelta(hours=2),
            awayTeamSlug='iii',
            awayTeamId=9,
            awayTeamName='Iii Team',
            homeTeamSlug='jjj',
            homeTeamId=10,
            homeTeamName='Jjj Team',
        )

        locked, reason = is_pick_locked_for_pool(late_game, pool, week_games=[anchor, late_game])
        self.assertFalse(locked)
        self.assertEqual(reason, "Game not started yet")


class PicksLockFormFieldTests(TestCase):
    def test_form_has_lock_mode_choice(self):
        from pickem_homepage.forms import PoolRulesForm
        form = PoolRulesForm()
        self.assertIn('picks_lock_mode', form.fields)
        self.assertNotIn('picks_lock_at_kickoff', form.fields)

    def test_admin_settings_fields_list_updated(self):
        from pickem_homepage.views import ADMIN_POOL_SETTINGS_FIELDS
        self.assertIn('picks_lock_mode', ADMIN_POOL_SETTINGS_FIELDS)
        self.assertNotIn('picks_lock_at_kickoff', ADMIN_POOL_SETTINGS_FIELDS)


class PicksPageLockFilterTests(TestCase):
    def test_template_uses_pool_aware_filter(self):
        # Guard against regressing to statusType-only gating.
        import pathlib
        tpl = pathlib.Path('pickem_homepage/templates/pickem/picks.html').read_text()
        # The interactive pick options must gate on the pool-aware filter.
        self.assertIn('is_game_locked_for_pool:pool', tpl)
        # The old kickoff-only gate must be gone from the team-option cards.
        self.assertNotIn("game.statusType != 'notstarted' or auth_required", tpl)


class PayoutGroupingTests(TestCase):
    def test_payout_not_in_generic_choice_loop(self):
        import pathlib
        tpl = pathlib.Path('pickem_homepage/templates/pickem/family_admin_settings.html').read_text()
        # payout_structure must render inside the entry-fee card, keyed by name.
        self.assertIn('form.payout_structure', tpl)
        # And the entry-fee card must contain the payout wrapper marker.
        self.assertIn('data-payout-group', tpl)

        from pickem_homepage import views
        # The generic rule_choice_fields loop (rendered for family_admin_settings.html)
        # must no longer include payout_structure — it's grouped under Entry Fee instead.
        source = pathlib.Path(views.__file__).read_text()
        settings_view_block = source.split("def family_pool_admin_settings(")[1]
        rule_choice_fields_snippet = settings_view_block.split("'rule_choice_fields':")[1][:200]
        self.assertNotIn("payout_structure", rule_choice_fields_snippet)


class BannerIconChoicesTests(TestCase):
    def test_both_forms_use_select(self):
        from django import forms as djf
        from pickem_homepage.forms import SiteBannerForm, FamilyBannerForm, BANNER_ICON_CHOICES
        self.assertTrue(len(BANNER_ICON_CHOICES) >= 10)
        for FormClass in (SiteBannerForm, FamilyBannerForm):
            widget = FormClass().fields['icon'].widget
            self.assertIsInstance(widget, djf.Select)

    def test_unknown_existing_icon_stays_selectable(self):
        from pickem_homepage.forms import FamilyBannerForm
        from pickem_homepage.models import SiteBanner
        b = SiteBanner(icon='fas fa-custom-thing', title='t', description='d')
        form = FamilyBannerForm(instance=b)
        rendered = str(form['icon'])
        self.assertIn('fas fa-custom-thing', rendered)


class CreateFamilyRenderTests(TestCase):
    """Regression guard for the create-family page: it must render every
    CreateFamilyForm field it's supposed to, including picks_lock_mode.

    NOTE: the CreateFamilyForm field for the family's display name is
    ``name`` (rendered as ``name="name"``) — there is no ``family_name`` or
    ``pool_name`` field on this form (those belong to FamilyAdminSettingsForm
    on the separate family-admin-settings page; the pool name here is
    auto-generated in the view). This test checks the fields that actually
    exist on CreateFamilyForm.
    """

    def test_form_fields_still_present(self):
        u = User.objects.create_user('cf', 'cf@x.com', 'pw')
        c = Client()
        c.force_login(u)
        html = c.get('/families/create/').content.decode()
        for needed in ('name="name"', 'picks_lock_mode', 'name="entry_fee_amount"'):
            self.assertIn(needed, html)
