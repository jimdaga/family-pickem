from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import UserProfile
from pickem_superadmin.models import SuperAdminAuditLog


class UsersPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.spammer = User.objects.create_user(
            username='spammer', email='spam@example.com', password='pw',
        )
        UserProfile.objects.get_or_create(user=self.spammer)
        self.client.force_login(self.root)

    def test_page_lists_users(self):
        response = self.client.get(reverse('superadmin:users'))
        self.assertContains(response, 'spammer')

    def test_block_requires_typed_confirmation_matching_the_username(self):
        """A checkbox is too easy to click by accident. You type the username."""
        response = self.client.post(
            reverse('superadmin:user_block', args=[self.spammer.id]),
            {'confirm': 'wrong-name', 'reason': 'Spamming'},
        )
        self.spammer.refresh_from_db()
        self.assertTrue(self.spammer.is_active)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)
        self.assertEqual(response.status_code, 302)

    def test_block_requires_a_reason(self):
        self.client.post(
            reverse('superadmin:user_block', args=[self.spammer.id]),
            {'confirm': 'spammer', 'reason': ''},
        )
        self.spammer.refresh_from_db()
        self.assertTrue(self.spammer.is_active)

    def test_block_with_correct_confirmation_blocks_the_user(self):
        self.client.post(
            reverse('superadmin:user_block', args=[self.spammer.id]),
            {'confirm': 'spammer', 'reason': 'Spamming the board'},
        )
        self.spammer.refresh_from_db()
        self.assertFalse(self.spammer.is_active)
        self.assertEqual(
            UserProfile.objects.get(user=self.spammer).blocked_reason,
            'Spamming the board',
        )

    def test_unblock_restores_the_user(self):
        self.client.post(
            reverse('superadmin:user_block', args=[self.spammer.id]),
            {'confirm': 'spammer', 'reason': 'Spamming'},
        )
        self.client.post(reverse('superadmin:user_unblock', args=[self.spammer.id]))
        self.spammer.refresh_from_db()
        self.assertTrue(self.spammer.is_active)

    def test_get_request_never_mutates(self):
        self.client.get(reverse('superadmin:user_block', args=[self.spammer.id]))
        self.spammer.refresh_from_db()
        self.assertTrue(self.spammer.is_active)

    def test_update_toggles_commissioner_and_profile_fields(self):
        self.client.post(
            reverse('superadmin:user_update', args=[self.spammer.id]),
            {
                'is_commissioner': 'on',
                'favorite_team': 'ne',
                'tagline': 'go pats',
                'private_profile': '',
                'email_notifications': 'on',
            },
        )
        profile = UserProfile.objects.get(user=self.spammer)
        self.assertTrue(profile.is_commissioner)
        self.assertEqual(profile.favorite_team, 'ne')
        self.assertEqual(profile.tagline, 'go pats')
        self.assertFalse(profile.private_profile)
        self.assertTrue(profile.email_notifications)

    def test_update_cannot_grant_superuser(self):
        """is_superuser is not in the form. A hand-crafted POST must not escalate."""
        self.client.post(
            reverse('superadmin:user_update', args=[self.spammer.id]),
            {'is_superuser': 'on', 'favorite_team': 'ne'},
        )
        self.spammer.refresh_from_db()
        self.assertFalse(self.spammer.is_superuser)
