from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Family, Pool, FamilyInvitation, FamilyMembership
from pickem_homepage.emailing import (
    resend_invite_email_is_configured,
    send_family_invitation_email,
    send_test_email,
)
from pickem_homepage.views import hash_invite_code
from pickem_superadmin.models import EmailProviderSettings, SuperAdminAuditLog


class EmailProviderSettingsModelTests(TestCase):
    def test_api_key_is_encrypted_at_rest(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.set_api_key('re_test_secret_123456')
        settings_obj.save()

        settings_obj.refresh_from_db()
        self.assertNotEqual(settings_obj.api_key_ciphertext, 're_test_secret_123456')
        self.assertEqual(settings_obj.get_api_key(), 're_test_secret_123456')
        self.assertTrue(settings_obj.has_api_key)

    def test_corrupt_ciphertext_fails_closed(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.api_key_ciphertext = 'definitely-not-valid-fernet'
        settings_obj.save(update_fields=['api_key_ciphertext', 'updated_at'])

        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.get_api_key(), '')
        self.assertFalse(settings_obj.has_api_key)
        self.assertEqual(settings_obj.masked_api_key, '')


class EmailSettingsViewTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.client.force_login(self.root)

    def test_page_renders(self):
        response = self.client.get(reverse('superadmin:email_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Save email settings')
        self.assertContains(response, 'Enable invite emails')

    def test_post_saves_encrypted_settings_and_audits_without_plaintext_key(self):
        response = self.client.post(
            reverse('superadmin:email_settings'),
            {
                'provider': EmailProviderSettings.Provider.RESEND,
                'invites_enabled': 'on',
                'from_email': 'Family Pickem <invite@family-pickem.com>',
                'reply_to_email': 'support@family-pickem.com',
                'api_key': 're_super_secret_123456',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        settings_obj = EmailProviderSettings.load()
        self.assertTrue(settings_obj.invites_enabled)
        self.assertEqual(settings_obj.from_email, 'Family Pickem <invite@family-pickem.com>')
        self.assertEqual(settings_obj.reply_to_email, 'support@family-pickem.com')
        self.assertNotEqual(settings_obj.api_key_ciphertext, 're_super_secret_123456')
        self.assertEqual(settings_obj.get_api_key(), 're_super_secret_123456')

        audit = SuperAdminAuditLog.objects.get(action=SuperAdminAuditLog.Action.EMAIL_SETTINGS_UPDATED)
        self.assertNotIn('re_super_secret_123456', str(audit.changes))
        self.assertEqual(audit.changes['has_api_key'], [False, True])
        self.assertEqual(audit.changes['api_key_rotated'], [False, True])

    def test_enabled_invites_require_from_email_and_api_key(self):
        response = self.client.post(
            reverse('superadmin:email_settings'),
            {
                'provider': EmailProviderSettings.Provider.RESEND,
                'invites_enabled': 'on',
                'from_email': '',
                'reply_to_email': '',
                'api_key': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'From email is required when invites are enabled.')
        self.assertContains(response, 'API key is required when invites are enabled.')
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_page_renders_send_test_email_section(self):
        response = self.client.get(reverse('superadmin:email_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Send test email')
        self.assertContains(response, 'Recipient email')

    def test_send_test_email_reports_not_configured(self):
        response = self.client.post(
            reverse('superadmin:email_settings'),
            {
                'action': 'send_test_email',
                'to_email': 'check@example.com',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email provider is not fully configured yet.')
        self.assertFalse(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.EMAIL_TEST_SENT
            ).exists()
        )

    def test_page_renders_even_when_stored_api_key_is_corrupt(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.api_key_ciphertext = 'definitely-not-valid-fernet'
        settings_obj.save(update_fields=['api_key_ciphertext', 'updated_at'])

        response = self.client.get(reverse('superadmin:email_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'unset')

    def test_send_test_email_audits_success(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.invites_enabled = True
        settings_obj.from_email = 'Family Pickem <invite@family-pickem.com>'
        settings_obj.set_api_key('re_configured_secret')
        settings_obj.save()

        with patch('pickem_superadmin.views.email.send_test_email', return_value={'status': 'sent', 'response': {'id': 'email_1'}}) as send_mock:
            response = self.client.post(
                reverse('superadmin:email_settings'),
                {
                    'action': 'send_test_email',
                    'to_email': 'check@example.com',
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test email sent to check@example.com.')
        send_mock.assert_called_once_with(to_email='check@example.com')
        audit = SuperAdminAuditLog.objects.get(action=SuperAdminAuditLog.Action.EMAIL_TEST_SENT)
        self.assertEqual(audit.summary, 'Sent test email to check@example.com')


class InviteEmailSendingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner', email='owner@example.com', password='pw',
        )
        family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        FamilyMembership.objects.create(
            family=family, user=self.owner, role=FamilyMembership.Role.OWNER,
        )
        self.invitation = FamilyInvitation.objects.create(
            family=family,
            pool=self.pool,
            code_hash=hash_invite_code('abc123'),
            recipient_email='target@example.com',
            role=FamilyMembership.Role.MEMBER,
            created_by=self.owner,
        )

    def test_resend_config_detection_reads_database_settings(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.invites_enabled = True
        settings_obj.from_email = 'Family Pickem <invite@family-pickem.com>'
        settings_obj.set_api_key('re_configured_secret')
        settings_obj.save()

        with patch('pickem_homepage.emailing.resend', new=Mock()):
            self.assertTrue(resend_invite_email_is_configured())

    def test_send_family_invitation_email_uses_database_backed_settings(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.invites_enabled = True
        settings_obj.from_email = 'Family Pickem <invite@family-pickem.com>'
        settings_obj.reply_to_email = 'reply@family-pickem.com'
        settings_obj.set_api_key('re_configured_secret')
        settings_obj.save()

        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'email_123'}
        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = send_family_invitation_email(
                invitation=self.invitation,
                invite_link='https://family-pickem.com/invite/abc123',
                invite_code='abc123',
            )

        self.assertEqual(result['status'], 'sent')
        resend_mock.Emails.send.assert_called_once()
        params = resend_mock.Emails.send.call_args.args[0]
        self.assertEqual(params['from'], 'Family Pickem <invite@family-pickem.com>')
        self.assertEqual(params['reply_to'], 'reply@family-pickem.com')
        self.assertEqual(params['to'], ['target@example.com'])
        self.assertIn('https://family-pickem.com/invite/abc123', params['html'])
        self.assertNotIn('Fallback invite code', params['html'])
        self.assertNotIn('Fallback invite code', params['text'])

    def test_invite_email_is_branded_and_escapes_html(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.invites_enabled = True
        settings_obj.from_email = "Family Pick'em <invite@family-pickem.com>"
        settings_obj.set_api_key('re_configured_secret')
        settings_obj.save()

        # A family name carrying HTML must never render unescaped into the email.
        evil_family = Family.objects.create(name='<script>x</script>Crew', slug='evil')
        evil_pool = Pool.objects.create(
            family=evil_family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        invitation = FamilyInvitation.objects.create(
            family=evil_family, pool=evil_pool,
            code_hash=hash_invite_code('xyz789'),
            recipient_email='target@example.com',
            role=FamilyMembership.Role.MEMBER, created_by=self.owner,
        )

        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'email_456'}
        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            send_family_invitation_email(
                invitation=invitation,
                invite_link='https://family-pickem.com/invite/xyz789',
                invite_code='xyz789',
            )
        params = resend_mock.Emails.send.call_args.args[0]

        # Escaping: the raw tag is gone, the escaped form is present.
        self.assertNotIn('<script>x</script>', params['html'])
        self.assertIn('&lt;script&gt;', params['html'])
        # Branding: styled CTA, brand colour, and the wordmark are present.
        self.assertIn('Accept your invite', params['html'])
        self.assertIn('#0B3D91', params['html'])
        self.assertIn("Family Pick'em", params['html'])
        # Plain-text alternative carries the raw (unescaped) name and the link.
        self.assertIn('<script>x</script>Crew', params['text'])
        self.assertIn('https://family-pickem.com/invite/xyz789', params['text'])

    def test_send_family_invitation_email_skips_when_not_configured(self):
        result = send_family_invitation_email(
            invitation=self.invitation,
            invite_link='https://family-pickem.com/invite/abc123',
            invite_code='abc123',
        )

        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'not_configured')

    def test_send_test_email_skips_when_not_configured(self):
        result = send_test_email(to_email='check@example.com')

        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'not_configured')

    def test_send_test_email_uses_database_backed_settings(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.invites_enabled = True
        settings_obj.from_email = 'Family Pickem <invite@family-pickem.com>'
        settings_obj.reply_to_email = 'reply@family-pickem.com'
        settings_obj.set_api_key('re_configured_secret')
        settings_obj.save()

        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'email_test_123'}
        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = send_test_email(to_email='check@example.com')

        self.assertEqual(result['status'], 'sent')
        resend_mock.Emails.send.assert_called_once()
        params = resend_mock.Emails.send.call_args.args[0]
        self.assertEqual(params['from'], 'Family Pickem <invite@family-pickem.com>')
        self.assertEqual(params['reply_to'], 'reply@family-pickem.com')
        self.assertEqual(params['to'], ['check@example.com'])
        self.assertIn("Family Pick'em email configuration test", params['subject'])

    @patch.dict(
        'os.environ',
        {
            'RESEND_API_KEY': 're_env_secret',
            'RESEND_FROM_EMAIL': 'Env Sender <env@example.com>',
        },
        clear=False,
    )
    @patch('pickem_homepage.emailing.settings.RESEND_API_KEY', 're_env_secret')
    @patch('pickem_homepage.emailing.settings.RESEND_FROM_EMAIL', 'Env Sender <env@example.com>')
    @patch('pickem_homepage.emailing.resend', new=Mock())
    def test_database_row_disables_environment_fallback(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.invites_enabled = False
        settings_obj.from_email = ''
        settings_obj.api_key_ciphertext = ''
        settings_obj.save()

        self.assertFalse(resend_invite_email_is_configured())
