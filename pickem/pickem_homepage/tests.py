from io import StringIO
from importlib import import_module

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404, HttpResponse
from django.test import TestCase, Client, RequestFactory
from django.utils import timezone

from pickem.utils import get_season
from pickem_api.models import currentSeason, Family, FamilyMembership, Pool, UserProfile
from pickem_homepage.authz import family_member_required
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
