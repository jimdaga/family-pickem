from io import StringIO

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import TestCase, Client
from django.utils import timezone

from pickem.utils import get_season
from pickem_api.models import currentSeason, UserProfile
from pickem_homepage.models import (
    MessageBoardPost,
    MessageBoardComment,
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


class DjangoSystemCheckTests(TestCase):
    """Verify that Django system checks pass."""

    def test_django_system_check(self):
        out = StringIO()
        call_command("check", stdout=out, stderr=StringIO())
        # If check passes, no exception is raised
