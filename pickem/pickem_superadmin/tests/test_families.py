from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Family, FamilyMembership, Pool
from pickem_superadmin.models import SuperAdminAuditLog


class FamiliesPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.member = User.objects.create_user(username='member', password='pw')
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        FamilyMembership.objects.create(
            family=self.family, user=self.member, role=FamilyMembership.Role.MEMBER,
        )
        self.client.force_login(self.root)

    def _row(self, **overrides):
        payload = {
            f'{self.family.id}-name': 'Dagostino',
            f'{self.family.id}-slug': 'dagostino',
            f'{self.family.id}-status': Family.Status.ACTIVE,
            f'{self.family.id}-updated_at': self.family.updated_at.isoformat(),
        }
        payload.update({f'{self.family.id}-{k}': v for k, v in overrides.items()})
        return payload

    def test_page_lists_families_with_member_and_pool_counts(self):
        response = self.client.get(reverse('superadmin:families'))
        self.assertContains(response, 'dagostino')
        self.assertContains(response, 'default')
        self.assertNotContains(response, 'logo url')

    def test_deactivating_a_family_saves_and_audits(self):
        self.client.post(
            reverse('superadmin:families_save'),
            self._row(status=Family.Status.INACTIVE),
        )
        self.family.refresh_from_db()
        self.assertEqual(self.family.status, Family.Status.INACTIVE)

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.FAMILY_UPDATED)
        self.assertEqual(entry.changes['status'], ['active', 'inactive'])

    def test_unchanged_row_writes_no_audit_entry(self):
        self.client.post(reverse('superadmin:families_save'), self._row())
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_stale_row_is_rejected(self):
        stale = self.family.updated_at.isoformat()
        self.client.post(reverse('superadmin:families_save'), self._row(name='First'))
        response = self.client.post(
            reverse('superadmin:families_save'),
            self._row(name='Second', updated_at=stale),
            follow=True,
        )
        self.family.refresh_from_db()
        self.assertEqual(self.family.name, 'First')
        self.assertContains(response, 'changed since you loaded it')
