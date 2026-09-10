from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import (
    Family, FamilyAuditLog, Pool, PoolSettings, currentSeason,
)
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


class PoolsMatrixLayoutTests(TestCase):
    """Header and body column counts must agree.

    The matrix is a wide horizontally-scrolled table; a miscounted colspan
    shifts every cell after it under the wrong header, which is invisible in a
    diff and easy to miss by eye.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            'pm-admin', email='pm@example.com', password='x',
            is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.admin)
        currentSeason.objects.get_or_create(
            season=2627, defaults={'display_name': '2026-2027'}
        )

    def _pool(self, slug, *, with_settings=True):
        family = Family.objects.create(name=slug, slug=slug)
        pool = Pool.objects.create(
            family=family, name='Main', slug=f'{slug}-pool', season=2627,
            competition='nfl', status=Pool.Status.ACTIVE, is_default=True,
        )
        if with_settings:
            PoolSettings.objects.create(pool=pool)
        return pool

    def _counts(self, html):
        import re
        thead = html.split('<thead>', 1)[1].split('</thead>', 1)[0]
        headers = len(re.findall(r'<th[^>]*>', thead))
        body = html.split('<tbody', 1)[1]
        rows = []
        for chunk in body.split('<tr')[1:]:
            row = chunk.split('</tr>', 1)[0]
            width = 0
            for cell in re.findall(r'<td[^>]*>', row):
                m = re.search(r'colspan="(\d+)"', cell)
                width += int(m.group(1)) if m else 1
            if width:
                rows.append(width)
        return headers, rows

    def test_editable_rows_match_the_header_width(self):
        self._pool('withsettings')

        headers, rows = self._counts(
            self.client.get(reverse('superadmin:pools')).content.decode()
        )

        self.assertTrue(rows, 'no body rows rendered')
        for width in rows:
            self.assertEqual(width, headers)

    def test_rows_without_settings_match_the_header_width(self):
        """The no-settings branch uses a colspan, which drifts silently."""
        self._pool('nosettings', with_settings=False)

        headers, rows = self._counts(
            self.client.get(reverse('superadmin:pools')).content.decode()
        )

        self.assertTrue(rows, 'no body rows rendered')
        for width in rows:
            self.assertEqual(width, headers)

    def test_sideline_toggle_is_near_the_front_of_the_table(self):
        """It sits in a horizontally scrolled table; buried at column 17 it was
        off-screen and effectively invisible."""
        import re

        self._pool('placement')
        html = self.client.get(reverse('superadmin:pools')).content.decode()
        thead = html.split('<thead>', 1)[1].split('</thead>', 1)[0]
        headers = [
            re.sub(r'<[^>]+>|\s+', ' ', h).strip()
            for h in re.findall(r'<th[^>]*>(.*?)</th>', thead, re.S)
        ]

        self.assertIn('sideline', headers)
        self.assertLessEqual(headers.index('sideline'), 3)

