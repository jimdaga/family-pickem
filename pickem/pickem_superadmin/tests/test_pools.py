from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Family, FamilyAuditLog, Pool, PoolSettings
from pickem_superadmin.models import SuperAdminAuditLog


class PoolsMatrixTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        self.settings = PoolSettings.objects.create(pool=self.pool)
        self.client.force_login(self.root)

    def _row(self, **overrides):
        """A full matrix row post payload for self.pool.

        Values match PoolSettings' actual field defaults (tie_points=0,
        perfect_week_bonus_amount=10, picks_lock_mode=kickoff,
        allow_tiebreaker checked) so that posting this payload unmodified is a
        true no-op diff — required for the "unchanged row" and "only the
        touched field is in the audit diff" tests below to mean what they say.
        """
        payload = {
            f'{self.pool.id}-win_points': '1',
            f'{self.pool.id}-tie_points': '0',
            f'{self.pool.id}-weekly_winner_points': '2',
            f'{self.pool.id}-picks_lock_mode': PoolSettings.PicksLockMode.KICKOFF,
            f'{self.pool.id}-allow_tiebreaker': 'on',
            f'{self.pool.id}-primary_tiebreaker': PoolSettings.PrimaryTiebreaker.TOTAL_SCORE,
            f'{self.pool.id}-secondary_tiebreaker': PoolSettings.SecondaryTiebreaker.COMBINED_YARDS,
            f'{self.pool.id}-perfect_week_bonus_amount': '10',
            f'{self.pool.id}-entry_fee_amount': '0',
            f'{self.pool.id}-missed_pick_policy': PoolSettings.MissedPickPolicy.ZERO_POINTS,
            f'{self.pool.id}-late_join_policy': PoolSettings.LateJoinPolicy.OPEN,
            f'{self.pool.id}-payout_structure': PoolSettings.PayoutStructure.WINNER_TAKES_ALL,
            f'{self.pool.id}-updated_at': self.settings.updated_at.isoformat(),
        }
        payload.update({f'{self.pool.id}-{k}': v for k, v in overrides.items()})
        return payload

    def test_page_lists_every_pool_across_families(self):
        response = self.client.get(reverse('superadmin:pools'))
        self.assertContains(response, 'dagostino')
        self.assertContains(response, 'pickem-pool')

    def test_save_writes_only_changed_fields(self):
        self.client.post(reverse('superadmin:pools_save'), self._row(win_points='3'))
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.win_points, 3)

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.POOL_SETTINGS_UPDATED)
        self.assertEqual(entry.changes, {'win_points': [1, 3]})

    def test_save_dual_writes_to_the_family_audit_log(self):
        self.client.post(reverse('superadmin:pools_save'), self._row(win_points='3'))
        family_entry = FamilyAuditLog.objects.get()
        self.assertEqual(family_entry.family, self.family)
        self.assertEqual(family_entry.metadata['source'], 'superadmin')

    def test_unchanged_row_writes_no_audit_entry(self):
        self.client.post(reverse('superadmin:pools_save'), self._row())
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_against_spread_is_rejected_server_side(self):
        """The widget is disabled, but never trust the widget. Enabling this would
        silently corrupt scoring — the backend does not implement it."""
        self.client.post(
            reverse('superadmin:pools_save'),
            self._row(pick_type=PoolSettings.PickType.AGAINST_SPREAD),
        )
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.pick_type, PoolSettings.PickType.STRAIGHT_UP)

    def test_include_playoffs_is_rejected_server_side(self):
        self.client.post(reverse('superadmin:pools_save'), self._row(include_playoffs='on'))
        self.settings.refresh_from_db()
        self.assertFalse(self.settings.include_playoffs)

    def test_stale_row_is_rejected_instead_of_clobbering(self):
        """Two operators with the page open must not silently overwrite each other."""
        stale = self.settings.updated_at.isoformat()
        self.client.post(reverse('superadmin:pools_save'), self._row(win_points='3'))

        response = self.client.post(
            reverse('superadmin:pools_save'),
            self._row(win_points='9', updated_at=stale),
            follow=True,
        )
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.win_points, 3)
        self.assertContains(response, 'changed since you loaded it')

    def test_pools_row_form_has_lock_mode(self):
        from pickem_superadmin.forms import PoolSettingsRowForm

        form = PoolSettingsRowForm()
        self.assertIn('picks_lock_mode', form.fields)
        self.assertNotIn('picks_lock_at_kickoff', form.fields)

    def test_invalid_cell_does_not_discard_the_valid_edits(self):
        other_pool = Pool.objects.create(
            family=self.family, name='Second', slug='second', season=2627,
        )
        other_settings = PoolSettings.objects.create(pool=other_pool)

        payload = self._row(win_points='not-a-number')
        payload.update({
            f'{other_pool.id}-win_points': '5',
            f'{other_pool.id}-tie_points': '0',
            f'{other_pool.id}-weekly_winner_points': '2',
            f'{other_pool.id}-picks_lock_mode': PoolSettings.PicksLockMode.KICKOFF,
            f'{other_pool.id}-allow_tiebreaker': 'on',
            f'{other_pool.id}-primary_tiebreaker': PoolSettings.PrimaryTiebreaker.TOTAL_SCORE,
            f'{other_pool.id}-secondary_tiebreaker': PoolSettings.SecondaryTiebreaker.COMBINED_YARDS,
            f'{other_pool.id}-perfect_week_bonus_amount': '10',
            f'{other_pool.id}-entry_fee_amount': '0',
            f'{other_pool.id}-missed_pick_policy': PoolSettings.MissedPickPolicy.ZERO_POINTS,
            f'{other_pool.id}-late_join_policy': PoolSettings.LateJoinPolicy.OPEN,
            f'{other_pool.id}-payout_structure': PoolSettings.PayoutStructure.WINNER_TAKES_ALL,
            f'{other_pool.id}-updated_at': other_settings.updated_at.isoformat(),
        })

        response = self.client.post(reverse('superadmin:pools_save'), payload, follow=True)

        other_settings.refresh_from_db()
        self.settings.refresh_from_db()
        self.assertEqual(other_settings.win_points, 5)   # good edit landed
        self.assertEqual(self.settings.win_points, 1)    # bad edit did not
        self.assertContains(response, 'could not be saved')
