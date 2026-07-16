"""The gate. If this file goes green while a view is undecorated, the console is a hole."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Family, FamilyMembership, Pool


# Every superadmin GET URL. Add a row here when you add a view — test_all_urls_are_covered
# asserts this list (plus SUPERADMIN_POST_URLS) matches the registered URLconf, so you
# cannot forget.
SUPERADMIN_URLS = [
    'superadmin:overview',
    'superadmin:users',
    'superadmin:pools',
    'superadmin:families',
    'superadmin:teams',
    'superadmin:jobs',
    'superadmin:audit',
]

# POST-only endpoints. The gate test hits them with POST and asserts the same
# 404-for-non-superusers rule; they are excluded from the GET-200 test.
SUPERADMIN_POST_URLS = [
    ('superadmin:user_block', [1]),
    ('superadmin:user_unblock', [1]),
    ('superadmin:user_update', [1]),
    ('superadmin:pools_save', []),
    ('superadmin:families_save', []),
    ('superadmin:teams_save', []),
    ('superadmin:jobs_queue', []),
    ('superadmin:jobs_schedule_save', []),
    ('superadmin:season_update', []),
    ('superadmin:pool_settings_backfill', [1]),
    ('superadmin:banner_publish', []),
    ('superadmin:banner_deactivate', [1]),
    ('superadmin:pool_recompute', [1]),
    ('superadmin:pool_rescore_week', [1]),
    ('superadmin:pick_delete', ['x']),
    ('superadmin:season_row_reset', [1]),
    ('superadmin:game_fix', [1]),
]

# GET endpoints that take a required arg, so they cannot be reversed with no
# args like SUPERADMIN_URLS. Covered by their own gate test class below.
SUPERADMIN_GET_ARG_URLS = [
    ('superadmin:pool_detail', [1]),
]


class SuperadminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        cls.member = User.objects.create_user(
            username='member', email='member@example.com', password='pw',
        )
        cls.commissioner = User.objects.create_user(
            username='commish', email='commish@example.com', password='pw',
        )
        family = Family.objects.create(name='Dagostino', slug='dagostino')
        Pool.objects.create(
            family=family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        FamilyMembership.objects.create(
            family=family, user=cls.member, role=FamilyMembership.Role.MEMBER,
        )
        FamilyMembership.objects.create(
            family=family, user=cls.commissioner, role=FamilyMembership.Role.OWNER,
        )

    def test_anonymous_is_redirected_to_login(self):
        # RequireLoginForInternalPagesMiddleware intercepts before the view runs.
        for name in SUPERADMIN_URLS:
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn('/accounts/', response['Location'])

    def test_ordinary_member_gets_404(self):
        self.client.force_login(self.member)
        for name in SUPERADMIN_URLS:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 404)

    def test_family_commissioner_gets_404(self):
        # A commissioner governs one family. This console is global.
        self.client.force_login(self.commissioner)
        for name in SUPERADMIN_URLS:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 404)

    def test_superuser_gets_200(self):
        self.client.force_login(self.superuser)
        for name in SUPERADMIN_URLS:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_post_endpoints_reject_non_superusers(self):
        self.client.force_login(self.member)
        for name, args in SUPERADMIN_POST_URLS:
            with self.subTest(url=name):
                response = self.client.post(reverse(name, args=args))
                self.assertEqual(response.status_code, 404)

    def test_all_urls_are_covered(self):
        """A new view with no entry in these lists fails here — so it can never
        silently skip the gate tests above."""
        from pickem_superadmin import urls as superadmin_urls

        registered = {
            f'superadmin:{p.name}'
            for p in superadmin_urls.urlpatterns
            if p.name is not None
        }
        covered = (
            set(SUPERADMIN_URLS)
            | {name for name, _ in SUPERADMIN_POST_URLS}
            | {name for name, _ in SUPERADMIN_GET_ARG_URLS}
        )
        self.assertEqual(registered, covered)


class PoolDetailGateTests(TestCase):
    """pool_detail is a GET view that requires an arg, so it can't live in
    SUPERADMIN_URLS (which reverses with none). Same gate rule, own fixtures."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='root2', email='root2@example.com', password='pw',
        )
        cls.member = User.objects.create_user(
            username='member2', email='member2@example.com', password='pw',
        )
        family = Family.objects.create(name='Smiths', slug='smiths')
        cls.pool = Pool.objects.create(
            family=family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )

    def test_ordinary_member_gets_404(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('superadmin:pool_detail', args=[self.pool.id]))
        self.assertEqual(response.status_code, 404)

    def test_superuser_gets_200(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('superadmin:pool_detail', args=[self.pool.id]))
        self.assertEqual(response.status_code, 200)
