"""Direct unit coverage for save_matrix() itself.

pools_save (test_pools.py) exercises this through the pools matrix, but
save_matrix is meant to be reused by the families and teams matrices too, so
it needs coverage that isn't tangled up in any one caller's URL/view/audit
wiring.
"""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from pickem_api.models import Family, Pool, PoolSettings
from pickem_superadmin.forms import PoolSettingsRowForm
from pickem_superadmin.matrix import save_matrix

TRACKED_FIELDS = tuple(PoolSettingsRowForm.Meta.fields)


class SaveMatrixTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        self.settings = PoolSettings.objects.create(pool=self.pool)

    def _request(self, data):
        request = self.factory.post('/superadmin/pools/save/', data)
        request.user = self.user
        return request

    def _payload(self, pk=None, **overrides):
        pk = pk if pk is not None else self.settings.pk
        obj = PoolSettings.objects.get(pk=pk)
        payload = {
            f'{pk}-win_points': str(obj.win_points),
            f'{pk}-tie_points': str(obj.tie_points),
            f'{pk}-weekly_winner_points': str(obj.weekly_winner_points),
            f'{pk}-picks_lock_mode': obj.picks_lock_mode,
            f'{pk}-primary_tiebreaker': obj.primary_tiebreaker,
            f'{pk}-secondary_tiebreaker': obj.secondary_tiebreaker,
            f'{pk}-perfect_week_bonus_amount': str(obj.perfect_week_bonus_amount),
            f'{pk}-entry_fee_amount': str(obj.entry_fee_amount),
            f'{pk}-missed_pick_policy': obj.missed_pick_policy,
            f'{pk}-late_join_policy': obj.late_join_policy,
            f'{pk}-payout_structure': obj.payout_structure,
            f'{pk}-updated_at': obj.updated_at.isoformat(),
        }
        if obj.allow_tiebreaker:
            payload[f'{pk}-allow_tiebreaker'] = 'on'
        if obj.perfect_week_bonus_enabled:
            payload[f'{pk}-perfect_week_bonus_enabled'] = 'on'
        if obj.entry_fee_enabled:
            payload[f'{pk}-entry_fee_enabled'] = 'on'
        payload.update({f'{pk}-{k}': v for k, v in overrides.items()})
        return payload

    def test_stale_row_is_rejected_and_not_saved(self):
        """A row carrying an updated_at that no longer matches the DB is
        rejected outright — never partially applied, never saved."""
        stale_stamp = self.settings.updated_at.isoformat()
        # Simulate a concurrent save that moved updated_at forward.
        self.settings.win_points = 5
        self.settings.save()

        calls = []
        saved, failed, stale = save_matrix(
            self._request(self._payload(win_points='9', updated_at=stale_stamp)),
            objects=[self.settings],
            form_class=PoolSettingsRowForm,
            tracked_fields=TRACKED_FIELDS,
            key_field='win_points',
            on_save=lambda obj, changes: calls.append((obj, changes)),
        )

        self.settings.refresh_from_db()
        self.assertEqual(saved, 0)
        self.assertEqual(failed, [])
        self.assertEqual(stale, [self.settings])
        self.assertEqual(self.settings.win_points, 5)
        self.assertEqual(calls, [])

    def test_concurrent_save_does_not_clobber_a_prior_save_lost_update(self):
        """Two requests can load the same row with the same updated_at. The
        first save must not be silently overwritten by the second just
        because the second's in-memory `obj.updated_at` (captured before
        either request started) still matches what it submits — the check
        has to be re-verified against a fresh DB read at save time, not
        trusted from the possibly-stale in-memory object."""
        stale_copy = PoolSettings.objects.get(pk=self.settings.pk)
        stale_stamp = stale_copy.updated_at.isoformat()

        # First "request" saves successfully, advancing updated_at in the DB.
        first_saved, _failed, _stale = save_matrix(
            self._request(self._payload(win_points='5', updated_at=stale_stamp)),
            objects=[self.settings],
            form_class=PoolSettingsRowForm,
            tracked_fields=TRACKED_FIELDS,
            key_field='win_points',
            on_save=lambda obj, changes: None,
        )
        self.assertEqual(first_saved, 1)

        # Second "request" holds a stale in-memory copy from before the first
        # request's save (same updated_at as what it submits) — a real lost
        # update. It must be rejected, not silently applied.
        calls = []
        saved, failed, stale = save_matrix(
            self._request(self._payload(win_points='9', updated_at=stale_stamp)),
            objects=[stale_copy],
            form_class=PoolSettingsRowForm,
            tracked_fields=TRACKED_FIELDS,
            key_field='win_points',
            on_save=lambda obj, changes: calls.append((obj, changes)),
        )

        self.settings.refresh_from_db()
        self.assertEqual(saved, 0)
        self.assertEqual(stale, [stale_copy])
        self.assertEqual(
            self.settings.win_points, 5,
            'first save must not be clobbered by the second',
        )
        self.assertEqual(calls, [])

    def test_stale_check_false_skips_the_concurrency_check(self):
        """stale_check=False (Teams, which has no updated_at column) must save
        even though the submitted stamp no longer matches the DB row."""
        stale_stamp = self.settings.updated_at.isoformat()
        self.settings.win_points = 5
        self.settings.save()

        saved, failed, stale = save_matrix(
            self._request(self._payload(win_points='9', updated_at=stale_stamp)),
            objects=[self.settings],
            form_class=PoolSettingsRowForm,
            tracked_fields=TRACKED_FIELDS,
            key_field='win_points',
            on_save=lambda obj, changes: None,
            stale_check=False,
        )

        self.settings.refresh_from_db()
        self.assertEqual(saved, 1)
        self.assertEqual(stale, [])
        self.assertEqual(failed, [])
        self.assertEqual(self.settings.win_points, 9)

    def test_unchanged_row_is_not_counted_as_saved(self):
        calls = []
        saved, failed, stale = save_matrix(
            self._request(self._payload()),
            objects=[self.settings],
            form_class=PoolSettingsRowForm,
            tracked_fields=TRACKED_FIELDS,
            key_field='win_points',
            on_save=lambda obj, changes: calls.append((obj, changes)),
        )

        self.assertEqual(saved, 0)
        self.assertEqual(failed, [])
        self.assertEqual(stale, [])
        self.assertEqual(calls, [])

    def test_on_save_fires_only_for_changed_rows(self):
        other_pool = Pool.objects.create(
            family=self.family, name='Second', slug='second', season=2627,
        )
        other_settings = PoolSettings.objects.create(pool=other_pool)

        payload = self._payload()  # unchanged for self.settings
        payload.update(self._payload(pk=other_settings.pk, win_points='5'))

        calls = []
        saved, failed, stale = save_matrix(
            self._request(payload),
            objects=[self.settings, other_settings],
            form_class=PoolSettingsRowForm,
            tracked_fields=TRACKED_FIELDS,
            key_field='win_points',
            on_save=lambda obj, changes: calls.append((obj.pk, changes)),
        )

        other_settings.refresh_from_db()
        self.settings.refresh_from_db()
        self.assertEqual(saved, 1)
        self.assertEqual(failed, [])
        self.assertEqual(stale, [])
        self.assertEqual(calls, [(other_settings.pk, {'win_points': [1, 5]})])
        self.assertEqual(other_settings.win_points, 5)
        self.assertEqual(self.settings.win_points, 1)

    def test_rows_absent_from_post_are_skipped_entirely(self):
        """key_field presence gates whether a row is even considered — a row
        for an object that simply wasn't on the submitted page must not show
        up in saved/failed/stale."""
        other_pool = Pool.objects.create(
            family=self.family, name='Second', slug='second', season=2627,
        )
        other_settings = PoolSettings.objects.create(pool=other_pool)

        # Payload only carries self.settings' row; other_settings is absent.
        saved, failed, stale = save_matrix(
            self._request(self._payload(win_points='3')),
            objects=[self.settings, other_settings],
            form_class=PoolSettingsRowForm,
            tracked_fields=TRACKED_FIELDS,
            key_field='win_points',
            on_save=lambda obj, changes: None,
        )

        self.assertEqual(saved, 1)
        self.assertEqual(failed, [])
        self.assertEqual(stale, [])

    def test_invalid_row_is_reported_and_not_saved(self):
        saved, failed, stale = save_matrix(
            self._request(self._payload(win_points='not-a-number')),
            objects=[self.settings],
            form_class=PoolSettingsRowForm,
            tracked_fields=TRACKED_FIELDS,
            key_field='win_points',
            on_save=lambda obj, changes: None,
        )

        self.settings.refresh_from_db()
        self.assertEqual(saved, 0)
        self.assertEqual(failed, [self.settings])
        self.assertEqual(stale, [])
        self.assertEqual(self.settings.win_points, 1)
