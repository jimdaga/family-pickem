from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from pickem_api.models import UserProfile
from pickem_superadmin import services
from pickem_superadmin.models import SuperAdminAuditLog


class BlockUserTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.other_root = User.objects.create_superuser(
            username='root2', email='root2@example.com', password='pw',
        )
        self.spammer = User.objects.create_user(
            username='spammer', email='spam@example.com', password='pw',
        )
        UserProfile.objects.get_or_create(user=self.spammer)

    def _request(self):
        request = RequestFactory().post('/superadmin/users/')
        request.user = self.root
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        return request

    def test_block_deactivates_user_and_stamps_the_profile(self):
        services.block_user(self._request(), self.spammer, reason='Spamming the board')

        self.spammer.refresh_from_db()
        profile = UserProfile.objects.get(user=self.spammer)
        self.assertFalse(self.spammer.is_active)
        self.assertIsNotNone(profile.blocked_at)
        self.assertEqual(profile.blocked_by, self.root)
        self.assertEqual(profile.blocked_reason, 'Spamming the board')

    def test_block_writes_an_audit_row_with_before_after(self):
        services.block_user(self._request(), self.spammer, reason='Spamming')
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.USER_BLOCKED)
        self.assertEqual(entry.changes['is_active'], [True, False])
        self.assertEqual(entry.target_id, str(self.spammer.id))

    def test_block_flushes_the_users_existing_sessions(self):
        """Without this, a blocked user keeps browsing until their session expires."""
        self.client.force_login(self.spammer)
        self.assertEqual(Session.objects.count(), 1)

        services.block_user(self._request(), self.spammer, reason='Spamming')

        self.assertEqual(Session.objects.count(), 0)

    def test_block_leaves_other_users_sessions_alone(self):
        bystander = User.objects.create_user(username='bystander', password='pw')
        self.client.force_login(bystander)
        other_client_sessions = Session.objects.count()

        services.block_user(self._request(), self.spammer, reason='Spamming')

        self.assertEqual(Session.objects.count(), other_client_sessions)

    def test_cannot_block_a_superuser(self):
        with self.assertRaises(ValidationError):
            services.block_user(self._request(), self.other_root, reason='nope')
        self.other_root.refresh_from_db()
        self.assertTrue(self.other_root.is_active)

    def test_cannot_block_yourself(self):
        with self.assertRaises(ValidationError):
            services.block_user(self._request(), self.root, reason='nope')

    def test_failed_block_writes_no_audit_row(self):
        with self.assertRaises(ValidationError):
            services.block_user(self._request(), self.other_root, reason='nope')
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_unblock_reverses_the_block(self):
        services.block_user(self._request(), self.spammer, reason='Spamming')
        services.unblock_user(self._request(), self.spammer)

        self.spammer.refresh_from_db()
        profile = UserProfile.objects.get(user=self.spammer)
        self.assertTrue(self.spammer.is_active)
        self.assertIsNone(profile.blocked_at)
        self.assertIsNone(profile.blocked_by)
        self.assertEqual(profile.blocked_reason, '')
        self.assertEqual(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.USER_UNBLOCKED,
            ).count(),
            1,
        )
