from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from pickem_api.models import Family, FamilyAuditLog, Pool
from pickem_superadmin.audit import _client_ip, diff_fields, log_action
from pickem_superadmin.models import SuperAdminAuditLog


class DiffFieldsTests(TestCase):
    def test_returns_only_changed_fields_as_before_after_pairs(self):
        before = {'win_points': 1, 'tie_points': 1}
        after = {'win_points': 2, 'tie_points': 1}
        self.assertEqual(diff_fields(before, after), {'win_points': [1, 2]})

    def test_returns_empty_dict_when_nothing_changed(self):
        self.assertEqual(diff_fields({'a': 1}, {'a': 1}), {})

    def test_key_present_in_before_but_absent_from_after_is_recorded(self):
        """A delete-style diff (e.g. diff_fields(snapshot, {})) must not lose
        the pre-deletion snapshot just because `after` has no key for it."""
        before = {'win_points': 1}
        after = {}
        self.assertEqual(diff_fields(before, after), {'win_points': [1, None]})

    def test_key_present_in_after_but_absent_from_before_is_recorded(self):
        before = {}
        after = {'win_points': 1}
        self.assertEqual(diff_fields(before, after), {'win_points': [None, 1]})


class ClientIpTests(TestCase):
    def _request(self, **meta):
        request = RequestFactory().post('/superadmin/')
        request.META.update(meta)
        return request

    def test_returns_none_for_malformed_x_forwarded_for(self):
        request = self._request(
            HTTP_X_FORWARDED_FOR='unknown', REMOTE_ADDR='unknown',
        )
        self.assertIsNone(_client_ip(request))

    def test_falls_back_to_valid_remote_addr_when_forwarded_is_malformed(self):
        request = self._request(
            HTTP_X_FORWARDED_FOR='unknown', REMOTE_ADDR='10.0.0.5',
        )
        self.assertEqual(_client_ip(request), '10.0.0.5')

    def test_returns_leftmost_hop_when_forwarded_is_a_valid_chain(self):
        request = self._request(
            HTTP_X_FORWARDED_FOR='203.0.113.5, 10.0.0.1',
            REMOTE_ADDR='10.0.0.1',
        )
        self.assertEqual(_client_ip(request), '203.0.113.5')


class LogActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        cls.family = Family.objects.create(name='Dagostino', slug='dagostino')
        cls.pool = Pool.objects.create(
            family=cls.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )

    def _request(self):
        request = RequestFactory().post('/superadmin/')
        request.user = self.root
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        request.META['HTTP_USER_AGENT'] = 'pytest-agent'
        return request

    def test_writes_a_superadmin_row_with_actor_and_request_metadata(self):
        log_action(
            self._request(),
            action=SuperAdminAuditLog.Action.USER_BLOCKED,
            target=self.root,
            summary='Blocked user spammer',
            changes={'is_active': [True, False]},
        )
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.actor, self.root)
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.USER_BLOCKED)
        self.assertEqual(entry.target_type, 'User')
        self.assertEqual(entry.target_id, str(self.root.id))
        self.assertEqual(entry.changes, {'is_active': [True, False]})
        self.assertEqual(entry.ip_address, '10.0.0.5')
        self.assertEqual(entry.user_agent, 'pytest-agent')

    def test_family_scoped_action_dual_writes_to_the_family_audit_log(self):
        """A superadmin editing a pool must not leave a gap in that family's own
        history — the commissioner sees it too."""
        log_action(
            self._request(),
            action=SuperAdminAuditLog.Action.POOL_SETTINGS_UPDATED,
            target=self.pool,
            summary='Updated settings for dagostino/pickem-pool',
            changes={'win_points': [1, 2]},
            family=self.family,
            pool=self.pool,
            family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
        )
        self.assertEqual(SuperAdminAuditLog.objects.count(), 1)
        family_entry = FamilyAuditLog.objects.get()
        self.assertEqual(family_entry.family, self.family)
        self.assertEqual(family_entry.pool, self.pool)
        self.assertEqual(family_entry.actor, self.root)
        self.assertEqual(family_entry.metadata['changes'], {'win_points': [1, 2]})
        self.assertEqual(family_entry.metadata['source'], 'superadmin')

    def test_global_action_does_not_write_a_family_row(self):
        log_action(
            self._request(),
            action=SuperAdminAuditLog.Action.TEAM_UPDATED,
            target=None,
            summary='Updated team colors',
        )
        self.assertEqual(FamilyAuditLog.objects.count(), 0)

    def test_family_without_family_action_raises(self):
        """The pairing guard: passing `family` without `family_action` must
        raise rather than silently skip the family's own audit row."""
        with self.assertRaises(ValueError):
            log_action(
                self._request(),
                action=SuperAdminAuditLog.Action.POOL_SETTINGS_UPDATED,
                target=self.pool,
                summary='Updated settings for dagostino/pickem-pool',
                family=self.family,
                pool=self.pool,
            )

    def test_survives_unparseable_forwarded_for_header(self):
        """The write path must not 500 just because a proxy sent a
        placeholder like 'unknown' in X-Forwarded-For. This is the
        regression test for the production DataError: on SQLite (used in
        CI) an invalid value would previously have been stored verbatim
        instead of raising, masking the bug that crashes on Postgres inet."""
        request = self._request()
        request.META['HTTP_X_FORWARDED_FOR'] = 'unknown'
        request.META['REMOTE_ADDR'] = 'also-not-an-ip'
        entry = log_action(
            request,
            action=SuperAdminAuditLog.Action.TEAM_UPDATED,
            target=None,
            summary='Updated team colors',
        )
        self.assertIsNone(entry.ip_address)


from django.urls import reverse


class AuditPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.client.force_login(self.root)

    def test_page_lists_superadmin_entries_with_before_after(self):
        SuperAdminAuditLog.objects.create(
            actor=self.root,
            action=SuperAdminAuditLog.Action.USER_BLOCKED,
            target_type='User', target_id='7',
            summary='Blocked user spammer',
            changes={'is_active': [True, False]},
        )
        response = self.client.get(reverse('superadmin:audit'))
        self.assertContains(response, 'Blocked user spammer')
        self.assertContains(response, 'is_active')

    def test_filtering_by_action_narrows_the_list(self):
        SuperAdminAuditLog.objects.create(
            actor=self.root, action=SuperAdminAuditLog.Action.USER_BLOCKED,
            summary='blocked someone',
        )
        SuperAdminAuditLog.objects.create(
            actor=self.root, action=SuperAdminAuditLog.Action.TEAM_UPDATED,
            summary='touched a team',
        )
        response = self.client.get(
            reverse('superadmin:audit'), {'action': SuperAdminAuditLog.Action.USER_BLOCKED},
        )
        self.assertContains(response, 'blocked someone')
        self.assertNotContains(response, 'touched a team')
