from datetime import timedelta
from io import StringIO
from importlib import import_module
import json

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404, HttpResponse
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

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

    def test_scores_returns_200(self):
        resp = self.client.get("/scores/")
        self.assertEqual(resp.status_code, 200)

    def test_standings_returns_200(self):
        resp = self.client.get("/standings/")
        self.assertEqual(resp.status_code, 200)

    def test_rules_returns_200(self):
        resp = self.client.get("/rules/")
        self.assertEqual(resp.status_code, 200)

    def test_picks_returns_200_for_anon(self):
        resp = self.client.get("/picks/")
        self.assertEqual(resp.status_code, 200)

    # -- auth-required pages (302) --

    def test_profile_redirects_anon(self):
        resp = self.client.get("/profile/")
        self.assertEqual(resp.status_code, 302)

    # -- commissioner pages redirect for anon --

    def test_commissioners_redirects_anon(self):
        resp = self.client.get("/commissioners/")
        self.assertEqual(resp.status_code, 302)

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
        self.assertContains(response, "Family Pickem")
        self.assertTemplateUsed(response, "pickem/home.html")

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
            userEmail=self.member.email,
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
        self.assertContains(response, "Family Pickem")

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
        self.assertContains(response, "smith-player")
        self.assertContains(response, "Smith family update")
        self.assertContains(response, "1 of 1")
        self.assertNotContains(response, "Jones Family")
        self.assertNotContains(response, "jones-player")
        self.assertNotContains(response, "Jones family secret")
        self.assertNotContains(response, "2 of 1")

    def test_dashboard_empty_states_do_not_link_to_global_gameplay_pages(self):
        family, pool = self._family_with_pool("Smith Family", "smith-family")
        self._active_membership(self.member, family)
        self.client.force_login(self.member)

        response = self.client.get(self._tenant_url(family, pool))

        self.assertEqual(response.status_code, 200)
        dashboard_markup = response.content.decode().split("<main", 1)[1].split("</main>", 1)[0]
        self.assertIn(f'href="{self._tenant_url(family, pool)}"', dashboard_markup)
        self.assertEqual(dashboard_markup.count('aria-disabled="true"'), 3)
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
        self.assertNotContains(response, self.other_member.email)

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
            picks_lock_at_kickoff=False,
            allow_tiebreaker=True,
        )
        PoolSettings.objects.create(
            pool=self.jones_pool,
            picks_lock_at_kickoff=True,
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

    def test_tenant_rules_display_current_context_settings_and_no_editing_form(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_rules"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/rules.html")
        self.assertContains(response, "Smith Family")
        self.assertContains(response, "Main Pickem")
        self.assertContains(response, "Game locking: Off")
        self.assertContains(response, "Tiebreakers: On")
        self.assertNotContains(response, "<form")
        self.assertNotContains(response, "Save settings")
        self.assertEqual(response.context["pool_settings"], self.smith_pool.settings)

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
        self.assertContains(rules_response, "Game locking: Off")
        self.assertContains(rules_response, "Tiebreakers: On")
        self.assertNotContains(rules_response, "Game locking: On")
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
        self.assertContains(rules_response, "Game locking: Off")
        self.assertNotContains(rules_response, "Jones Family")
        self.assertNotContains(rules_response, "Game locking: On")


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

    def test_private_profile_message_applies_after_family_membership_is_proven(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(
            self._tenant_url("family_pool_user_profile", user_id=self.smith_private.id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/user_profile_private.html")
        self.assertContains(response, "This Profile is Private")

    def test_legacy_signed_in_profile_redirects_to_default_tenant_profile(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(reverse("user_profile", kwargs={"user_id": self.smith_player.id}))

        self.assertRedirects(
            response,
            self._tenant_url("family_pool_user_profile", user_id=self.smith_player.id),
            fetch_redirect_response=False,
        )

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

    def test_tenant_homepage_message_board_uses_tenant_ajax_urls_only(self):
        self.client.force_login(self.smith_member)

        response = self.client.get(self._tenant_url("family_pool_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self._tenant_url("family_pool_create_post"))
        self.assertContains(response, self._tenant_url("family_pool_create_comment"))
        self.assertContains(response, self._tenant_url("family_pool_vote_post"))
        self.assertContains(response, self._tenant_url("family_pool_vote_comment"))
        self.assertNotContains(response, "fetch('/message-board/create-post/'")
        self.assertNotContains(response, "fetch('/message-board/create-comment/'")
        self.assertNotContains(response, "fetch('/message-board/vote-post/'")
        self.assertNotContains(response, "fetch('/message-board/vote-comment/'")

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

    def _settings_url(self, *, family=None, pool=None):
        family = family or self.family
        pool = pool or self.pool
        return reverse(
            "family_pool_admin_settings",
            kwargs={"family_slug": family.slug, "pool_slug": pool.slug},
        )

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
                self.assertNotContains(response, "Jones Family")
                self.assertNotContains(response, "Jones private event")

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

                response = self.client.get(self._settings_url())

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "pickem/family_admin_settings.html")
                self.assertContains(response, "Smith Family")
                self.assertContains(response, "Main Pickem")
                self.assertContains(response, "Pick Locking")
                self.assertContains(response, "Tiebreakers")
                self.assertContains(response, "Smith-only draft note")
                self.assertNotContains(response, "Jones Family")
                self.assertNotContains(response, "Jones-only draft note")
                self.assertNotContains(response, "Jones private banner metadata")

    def test_settings_post_updates_only_current_tenant_and_audits_safe_metadata(self):
        other_settings = self.other_pool.settings
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self._settings_url(),
            {
                "family_name": "Updated Smith Family",
                "pool_name": "Updated Main Pickem",
                "picks_lock_at_kickoff": "",
                "allow_tiebreaker": "on",
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
        self.assertFalse(self.pool.settings.picks_lock_at_kickoff)
        self.assertTrue(self.pool.settings.allow_tiebreaker)
        self.assertEqual(self.other_family.name, "Jones Family")
        self.assertEqual(self.other_pool.name, "Main Pickem")
        self.assertTrue(other_settings.picks_lock_at_kickoff)
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
        self.assertIn("settings.picks_lock_at_kickoff", audit.metadata["changed_fields"])
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

    def test_valid_post_creates_family_default_pool_settings_owner_and_audit(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("create_family"), {"name": "Smith Family"})

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
        self.assertEqual(pool.name, "Main Pickem")
        self.assertEqual(pool.slug, "main-pickem")
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

    def test_slug_collisions_receive_unique_family_slug(self):
        Family.objects.create(name="Smith Family", slug="smith-family")
        self.client.force_login(self.user)

        response = self.client.post(reverse("create_family"), {"name": "Smith Family"})

        family = Family.objects.get(slug="smith-family-2")
        pool = Pool.objects.get(family=family)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(pool.slug, "main-pickem")

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
            {
                "name": "Controlled Family",
                "owner": self.other_user.id,
                "user": self.other_user.id,
                "user_id": self.other_user.id,
                "role": FamilyMembership.Role.ADMIN,
                "status": FamilyMembership.Status.INACTIVE,
                "season": 1999,
                "family": attacker_family.id,
                "family_id": attacker_family.id,
                "pool": attacker_pool.id,
                "pool_id": attacker_pool.id,
                "is_default": "false",
            },
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
            "max_uses": 20,
            "created_by": self.owner,
        }
        defaults.update(overrides)
        return FamilyInvitation.objects.create(**defaults)

    def test_owner_can_create_member_invite_hash_only_with_defaults_and_audit(self):
        self.client.force_login(self.owner)
        before = timezone.now()

        response = self.client.post(self._create_invite_url())

        invitation = FamilyInvitation.objects.get(family=self.family)
        raw_code = response.context["invite_code"]

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pickem/family_pool_home.html")
        self.assertEqual(invitation.pool, self.pool)
        self.assertEqual(invitation.role, FamilyMembership.Role.MEMBER)
        self.assertEqual(invitation.max_uses, 20)
        self.assertEqual(invitation.use_count, 0)
        self.assertFalse(invitation.is_revoked)
        self.assertGreaterEqual(invitation.expires_at, before + timedelta(days=13, hours=23))
        self.assertLessEqual(invitation.expires_at, timezone.now() + timedelta(days=14, minutes=1))
        self.assertTrue(invitation.code_hash.startswith("sha256:"))
        self.assertNotEqual(invitation.code_hash, raw_code)
        self.assertFalse(
            FamilyInvitation.objects.filter(code_hash__icontains=raw_code).exists()
        )
        self.assertFalse(hasattr(invitation, "code"))
        self.assertFalse(hasattr(invitation, "raw_code"))
        self.assertGreaterEqual(len(raw_code), 32)
        self.assertContains(response, raw_code)
        self.assertContains(response, self._link_url(raw_code))
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
        self.assertNotIn(raw_code, str(audit.metadata))

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

    def test_link_acceptance_requires_login_and_accepts_by_post(self):
        self._invitation(raw_code="link-code")

        anonymous = self.client.get(self._link_url("link-code"))

        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/accounts/login/", anonymous["Location"])
        self.client.force_login(self.joiner)

        get_response = self.client.get(self._link_url("link-code"))
        post_response = self.client.post(self._link_url("link-code"))

        self.assertEqual(get_response.status_code, 200)
        self.assertTemplateUsed(get_response, "pickem/join_family.html")
        self.assertRedirects(
            post_response,
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
                self.assertContains(response, "Invite code is invalid or unavailable.")
                self.assertNotContains(response, "Smith Family")
                self.assertNotContains(response, "Inactive Family")
                self.assertNotContains(response, "Other Family")
                self.assertFalse(
                    FamilyMembership.objects.filter(user=self.joiner).exists()
                )


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

    @classmethod
    def setUpTestData(cls):
        cls.migration = import_module(
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
