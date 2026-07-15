from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Teams
from pickem_superadmin.models import SuperAdminAuditLog


class TeamsPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.team = Teams.objects.create(
            id=1, teamNameSlug='team-one', teamNameName='Team One', color='002244',
        )
        self.client.force_login(self.root)

    def _row(self, **overrides):
        payload = {
            f'{self.team.id}-color': '002244',
            f'{self.team.id}-logo_contrast_preset': 'default',
        }
        payload.update({f'{self.team.id}-{k}': v for k, v in overrides.items()})
        return payload

    def test_page_lists_teams(self):
        response = self.client.get(reverse('superadmin:teams'))
        self.assertEqual(response.status_code, 200)

    def test_saving_a_contrast_preset_persists_and_audits(self):
        self.client.post(
            reverse('superadmin:teams_save'),
            self._row(logo_contrast_preset='white-burst'),
        )
        self.team.refresh_from_db()
        self.assertEqual(self.team.logo_contrast_preset, 'white-burst')

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.TEAM_UPDATED)
        self.assertEqual(
            entry.changes['logo_contrast_preset'], ['default', 'white-burst'],
        )

    def test_unchanged_row_writes_no_audit_entry(self):
        self.client.post(reverse('superadmin:teams_save'), self._row())
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)
