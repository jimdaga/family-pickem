from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from pickem_api.models import Family, FamilyAuditLog, Pool
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.models import SuperAdminAuditLog


class DiffFieldsTests(TestCase):
    def test_returns_only_changed_fields_as_before_after_pairs(self):
        before = {'win_points': 1, 'tie_points': 1}
        after = {'win_points': 2, 'tie_points': 1}
        self.assertEqual(diff_fields(before, after), {'win_points': [1, 2]})

    def test_returns_empty_dict_when_nothing_changed(self):
        self.assertEqual(diff_fields({'a': 1}, {'a': 1}), {})


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
