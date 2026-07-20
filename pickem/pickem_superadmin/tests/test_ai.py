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

    def test_post_encrypts_key_and_audits_only_rotation_event(self):
        response = self.client.post(reverse('superadmin:ai_settings'), {
            'provider': AIProviderSettings.Provider.OPENAI,
            'enabled': 'on',
            'model': 'gpt-4o-mini',
            'timeout_seconds': 30,
            'retries': 2,
            'max_runs_per_pool_week': 3,
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

    def test_enabled_recaps_require_key(self):
        response = self.client.post(reverse('superadmin:ai_settings'), {
            'provider': AIProviderSettings.Provider.OPENAI,
            'enabled': 'on',
            'model': 'gpt-4o-mini',
            'timeout_seconds': 30,
            'retries': 2,
            'max_runs_per_pool_week': 3,
            'api_key': '',
        })

        self.assertContains(response, 'An API key is required when AI recaps are enabled.')
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)
