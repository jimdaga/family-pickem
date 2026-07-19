from datetime import datetime
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pickem_api.models import (
    Family, FamilyInvitation, FamilyMembership, GameWeeks, GamesAndScores, Pool, Teams, UserProfile,
)
from pickem_homepage.emailing import (
    resend_invite_email_is_configured,
    send_due_email_campaigns,
    send_family_invitation_email,
    send_test_email,
)
from pickem_homepage.views import hash_invite_code
from pickem_superadmin.models import (
    EmailNotificationCampaign, EmailProviderSettings, SuperAdminAuditLog,
)


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
        self.assertContains(response, 'Weekly picks campaign')

    def test_provider_card_hidden_via_attribute_not_class(self):
        """Tailwind's `space-y-4` uses the `:not([hidden])` selector, which only
        keys off the HTML `hidden` attribute. Hiding the card with the `.hidden`
        class instead leaves it counted as a space-y sibling, adding a phantom
        margin that misaligns the left column against the right sidebar.
        With no form errors the card must carry the `hidden` attribute (not
        just the `.hidden` class) so it's correctly skipped for spacing."""
        response = self.client.get(reverse('superadmin:email_settings'))
        html = response.content.decode()

        card_start = html.index('id="provider-settings-card"')
        tag_start = html.rindex('<div', 0, card_start)
        tag_end = html.index('>', card_start)
        opening_tag = html[tag_start:tag_end + 1]

        self.assertIn('hidden', opening_tag)
        self.assertNotRegex(opening_tag, r'class="[^"]*\bhidden\b')

    def test_current_status_has_edit_button_and_never_exposes_key(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.set_api_key('re_super_secret_ABC123')
        settings_obj.save()

        response = self.client.get(reverse('superadmin:email_settings'))

        self.assertContains(response, 'Edit provider settings')
        # Status shows a masked key; the plaintext key is never rendered anywhere.
        self.assertContains(response, settings_obj.masked_api_key)
        self.assertNotContains(response, 're_super_secret_ABC123')

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

    def test_weekly_campaign_save_audits(self):
        campaign = EmailNotificationCampaign.load_weekly_picks()

        response = self.client.post(
            reverse('superadmin:email_settings'),
            {
                'action': 'save_weekly_campaign',
                'campaign-enabled': 'on',
                'campaign-weekday': '2',
                'campaign-hour': '9',
                'campaign-minute': '15',
                'campaign-timezone_name': 'America/New_York',
                'campaign-rollout_mode': EmailNotificationCampaign.RolloutMode.ALLOWLIST,
                'campaign-allowlist_emails': 'jdagostino2@gmail.com, other@example.com',
                'campaign-family_link_strategy': EmailNotificationCampaign.FamilyLinkStrategy.EARLIEST_MEMBERSHIP,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        campaign.refresh_from_db()
        self.assertTrue(campaign.enabled)
        self.assertEqual(campaign.minute, 15)
        self.assertEqual(campaign.allowlist_emails, 'jdagostino2@gmail.com, other@example.com')
        audit = SuperAdminAuditLog.objects.get(action=SuperAdminAuditLog.Action.EMAIL_CAMPAIGN_UPDATED)
        self.assertEqual(audit.summary, 'Updated weekly picks email campaign')

    def test_running_weekly_campaign_now_outside_active_week_errors(self):
        response = self.client.post(
            reverse('superadmin:email_settings'),
            {'action': 'send_weekly_now'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not in an active NFL week window')


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
        self.assertIn('Join the league', params['html'])
        self.assertIn('#0B3D91', params['html'])
        self.assertIn('Family Pick', params['html'])  # wordmark (curly apostrophe)
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


@override_settings(
    SITE_BASE_URL='https://family-pickem.test',
    EMAIL_NOTIFICATION_SAFE_ALLOWLIST_ONLY=True,
    EMAIL_NOTIFICATION_SAFE_ALLOWLIST=['jdagostino2@gmail.com'],
    WEEKLY_PICKS_EMAIL_LOGO_URL='https://cdn.example.test/fp-logo.png',
)
class WeeklyPicksCampaignTests(TestCase):
    def setUp(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.invites_enabled = True
        settings_obj.from_email = 'Family Pickem <invite@family-pickem.com>'
        settings_obj.reply_to_email = 'reply@family-pickem.com'
        settings_obj.set_api_key('re_configured_secret')
        settings_obj.save()

        self.campaign = EmailNotificationCampaign.load_weekly_picks()
        self.campaign.enabled = True
        self.campaign.weekday = 2
        self.campaign.hour = 9
        self.campaign.minute = 0
        self.campaign.timezone_name = 'America/New_York'
        self.campaign.rollout_mode = EmailNotificationCampaign.RolloutMode.ALL_ENABLED_USERS
        self.campaign.allowlist_emails = 'jdagostino2@gmail.com'
        self.campaign.save()

        family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=family,
            name='Main Pool',
            slug='main-pool',
            season=2627,
            is_default=True,
        )
        self.allowed_user = User.objects.create_user(
            username='jdag',
            email='jdagostino2@gmail.com',
            password='pw',
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='pw',
        )
        UserProfile.objects.create(user=self.allowed_user, email_notifications=True)
        UserProfile.objects.create(user=self.other_user, email_notifications=True)
        FamilyMembership.objects.create(
            family=family,
            user=self.allowed_user,
            role=FamilyMembership.Role.MEMBER,
        )
        FamilyMembership.objects.create(
            family=family,
            user=self.other_user,
            role=FamilyMembership.Role.MEMBER,
        )
        Teams.objects.create(
            id=1,
            gameseason=2627,
            teamNameSlug='bears',
            teamNameName='Chicago Bears',
            teamLogo='https://cdn.example.test/bears.png',
            color='0B162A',
            alternateColor='C83803',
        )
        Teams.objects.create(
            id=2,
            gameseason=2627,
            teamNameSlug='packers',
            teamNameName='Green Bay Packers',
            teamLogo='https://cdn.example.test/packers.png',
            color='203731',
            alternateColor='FFB612',
        )

    def _seed_week_one(self):
        GameWeeks.objects.create(
            weekNumber=1,
            competition='nfl',
            date=datetime(2026, 9, 10).date(),
            season=2627,
        )
        GamesAndScores.objects.create(
            id=1,
            slug='bears-packers',
            competition='nfl',
            gameWeek='1',
            gameyear='2026',
            gameseason=2627,
            startTimestamp=timezone.make_aware(datetime(2026, 9, 10, 20, 20)),
            statusType='STATUS_SCHEDULED',
            statusTitle='Scheduled',
            homeTeamId=1,
            homeTeamSlug='packers',
            homeTeamName='Green Bay Packers',
            awayTeamId=2,
            awayTeamSlug='bears',
            awayTeamName='Chicago Bears',
            broadcast='NBC',
            spread=-2.5,
            overUnder=46.5,
            weatherCondition='Clear',
            temperature=71,
        )

    def test_campaign_does_not_send_before_active_week_window(self):
        self._seed_week_one()
        july_17_2026 = timezone.make_aware(datetime(2026, 7, 17, 12, 0))

        result = send_due_email_campaigns(now=july_17_2026)

        self.assertEqual(result['campaigns'], [])

    def test_campaign_sends_only_to_safety_allowlist_during_active_week(self):
        self._seed_week_one()
        september_9_2026 = timezone.make_aware(datetime(2026, 9, 9, 13, 5))
        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'weekly_email_1'}

        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = send_due_email_campaigns(now=september_9_2026)

        self.assertEqual(len(result['campaigns']), 1)
        self.assertEqual(result['campaigns'][0]['sent_count'], 1)
        resend_mock.Emails.send.assert_called_once()
        params = resend_mock.Emails.send.call_args.args[0]
        self.assertEqual(params['to'], ['jdagostino2@gmail.com'])
        self.assertIn('Picks for Week 1 are available', params['subject'])
        self.assertIn('https://cdn.example.test/bears.png', params['html'])
        self.assertIn('https://cdn.example.test/packers.png', params['html'])
        self.assertIn('https://cdn.example.test/fp-logo.png', params['html'])
        self.assertIn(
            'https://family-pickem.test/families/dagostino/pools/main-pool/picks/',
            params['html'],
        )
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.last_sent_season, 2627)
        self.assertEqual(self.campaign.last_sent_week, 1)
        self.assertEqual(self.campaign.last_sent_count, 1)

    def test_campaign_prefers_non_legacy_commissioner_family_for_multi_family_user(self):
        legacy_family, _ = Family.objects.get_or_create(
            slug='legacy-family-league',
            defaults={'name': 'Legacy'},
        )
        Pool.objects.create(
            family=legacy_family,
            name='Legacy Pool',
            slug='legacy-pool',
            season=2627,
            competition='nfl',
            is_default=True,
        )
        FamilyMembership.objects.create(
            family=legacy_family,
            user=self.allowed_user,
            role=FamilyMembership.Role.MEMBER,
        )
        test_family = Family.objects.create(name='Test Family', slug='test')
        Pool.objects.create(
            family=test_family,
            name='Test Pool',
            slug='pickem-pool',
            season=2627,
            competition='nfl',
            is_default=True,
        )
        FamilyMembership.objects.create(
            family=test_family,
            user=self.allowed_user,
            role=FamilyMembership.Role.OWNER,
        )
        self._seed_week_one()
        september_9_2026 = timezone.make_aware(datetime(2026, 9, 9, 13, 5))
        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'weekly_email_2'}

        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            send_due_email_campaigns(now=september_9_2026)

        params = resend_mock.Emails.send.call_args.args[0]
        self.assertIn(
            'https://family-pickem.test/families/test/pools/pickem-pool/picks/',
            params['html'],
        )


class EmailEnvironmentFallbackTests(TestCase):
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
