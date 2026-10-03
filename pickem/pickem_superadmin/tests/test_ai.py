from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_superadmin.models import AIProviderSettings, SuperAdminAuditLog


class AIProviderSettingsModelTests(TestCase):
    def test_api_key_is_encrypted_and_write_only(self):
        settings_obj = AIProviderSettings.load()
        settings_obj.set_api_key('sk-test-super-secret-123456')
        settings_obj.save()
        settings_obj.refresh_from_db()

        self.assertNotEqual(settings_obj.api_key_ciphertext, 'sk-test-super-secret-123456')
        self.assertEqual(settings_obj.get_api_key(), 'sk-test-super-secret-123456')
        self.assertNotIn('sk-test-super-secret-123456', str(settings_obj))


class AISettingsViewTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser('root', 'root@example.com', 'pw')
        self.client.force_login(self.root)

    def test_page_never_renders_plaintext_key(self):
        settings_obj = AIProviderSettings.load()
        settings_obj.set_api_key('sk-test-never-render-this')
        settings_obj.save()

        response = self.client.get(reverse('superadmin:ai_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'stored')
        self.assertNotContains(response, 'sk-test-never-render-this')

    @patch('pickem_api.ai_weekly_summaries.validate_openai_configuration', return_value=None)
    def test_post_encrypts_key_and_audits_only_rotation_event(self, validate):
        response = self.client.post(reverse('superadmin:ai_settings'), {
            'provider': AIProviderSettings.Provider.OPENAI,
            'enabled': 'on',
            'model': 'gpt-4o-mini',
            'timeout_seconds': 30,
            'retries': 2,
            'max_runs_per_pool_week': 3, 'reasoning_effort': 'high', 'review_reasoning_effort': 'high',
            'api_key': 'sk-test-do-not-audit',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        settings_obj = AIProviderSettings.load()
        self.assertTrue(settings_obj.enabled)
        self.assertNotEqual(settings_obj.api_key_ciphertext, 'sk-test-do-not-audit')
        self.assertEqual(settings_obj.get_api_key(), 'sk-test-do-not-audit')
        audit = SuperAdminAuditLog.objects.get(action=SuperAdminAuditLog.Action.AI_SETTINGS_UPDATED)
        self.assertNotIn('sk-test-do-not-audit', str(audit.changes))
        self.assertEqual(audit.changes['api_key_rotated'], [False, True])
        validate.assert_called_once()

    @patch('pickem_api.ai_weekly_summaries.validate_openai_configuration', return_value='invalid_api_key')
    def test_invalid_key_is_not_saved(self, validate):
        response = self.client.post(reverse('superadmin:ai_settings'), {
            'provider': AIProviderSettings.Provider.OPENAI,
            'enabled': 'on', 'model': 'gpt-4o-mini', 'timeout_seconds': 30,
            'retries': 2, 'max_runs_per_pool_week': 3, 'reasoning_effort': 'high', 'review_reasoning_effort': 'high', 'api_key': 'sk-test-invalid',
        })

        self.assertContains(response, 'OpenAI rejected this API key. Nothing was saved.')
        self.assertFalse(AIProviderSettings.current())

    @patch('pickem_api.ai_weekly_summaries.validate_openai_configuration', return_value=None)
    def test_saved_key_can_be_validated_without_rendering_or_reentering_it(self, validate):
        settings_obj = AIProviderSettings.load()
        settings_obj.set_api_key('sk-test-validate-saved')
        settings_obj.save()

        response = self.client.post(reverse('superadmin:ai_settings'), {
            'action': 'validate_settings',
        }, follow=True)

        self.assertContains(response, 'OpenAI accepted the saved API key and model.')
        self.assertNotContains(response, 'sk-test-validate-saved')
        validate.assert_called_once()

    def test_enabled_recaps_require_key(self):
        response = self.client.post(reverse('superadmin:ai_settings'), {
            'provider': AIProviderSettings.Provider.OPENAI,
            'enabled': 'on',
            'model': 'gpt-4o-mini',
            'timeout_seconds': 30,
            'retries': 2,
            'max_runs_per_pool_week': 3, 'reasoning_effort': 'high', 'review_reasoning_effort': 'high',
            'api_key': '',
        })

        self.assertContains(response, 'An API key is required when AI recaps are enabled.')
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)


class AIReasoningAndReviewSettingsTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser('root', 'root@example.com', 'pw')
        self.client.force_login(self.root)
        settings_obj = AIProviderSettings.load()
        settings_obj.set_api_key('sk-test-stored')
        settings_obj.save()

    def test_reasoning_and_review_settings_save_audit_and_reach_the_generator(self):
        from pickem_api.ai_weekly_summaries import SummarySettings

        response = self.client.post(reverse('superadmin:ai_settings'), {
            'provider': AIProviderSettings.Provider.OPENAI, 'enabled': 'on', 'model': 'gpt-6-luna',
            'timeout_seconds': 120, 'retries': 2, 'max_runs_per_pool_week': 3,
            'reasoning_effort': 'xhigh', 'review_reasoning_effort': 'medium',
            # review_enabled checkbox left unticked -> reviewer off
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        settings_obj = AIProviderSettings.load()
        self.assertEqual(
            (settings_obj.reasoning_effort, settings_obj.review_enabled, settings_obj.review_reasoning_effort),
            ('xhigh', False, 'medium'),
        )
        audit = SuperAdminAuditLog.objects.get(action=SuperAdminAuditLog.Action.AI_SETTINGS_UPDATED)
        self.assertEqual(audit.changes['reasoning_effort'], ['high', 'xhigh'])
        self.assertEqual(audit.changes['review_enabled'], [True, False])

        config = SummarySettings.from_django()
        self.assertEqual(
            (config.model, config.timeout, config.reasoning_effort, config.review_enabled, config.review_reasoning_effort),
            ('gpt-6-luna', 120, 'xhigh', False, 'medium'),
        )

    def test_page_renders_the_new_controls(self):
        response = self.client.get(reverse('superadmin:ai_settings'))

        self.assertContains(response, 'Writer reasoning effort')
        self.assertContains(response, 'name="review_enabled"')
        self.assertContains(response, 'name="review_reasoning_effort"')
