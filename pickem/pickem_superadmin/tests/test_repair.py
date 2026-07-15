from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pickem_api.models import Family, GamePicks, GamesAndScores, Pool, userSeasonPoints
from pickem_superadmin.models import SuperAdminAuditLog


class RepairViewsTestCase(TestCase):
    """Shared fixtures for the repair-UI views. Field lists match the ones
    already exercised in tests/test_services.py — those are the actual
    required-field set for these models, not the CLAUDE.md summary."""

    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        self.client.force_login(self.root)

    def _make_pick(self, **overrides):
        defaults = dict(
            id='dagostino-pickem-pool-alice-1', pool=self.pool, userID='alice',
            pick='ne', gameseason=2627, gameWeek='1', pick_game_id=101,
            pick_correct=False,
        )
        defaults.update(overrides)
        return GamePicks.objects.create(**defaults)

    def _make_season_row(self, **overrides):
        defaults = dict(
            pool=self.pool, userID='alice', gameseason=2627, total_points=17,
        )
        defaults.update(overrides)
        return userSeasonPoints.objects.create(**defaults)

    def _make_game(self, **overrides):
        defaults = dict(
            id=501, slug='ne-at-nyj', competition='nfl', gameWeek='1',
            gameyear='2026', gameseason=2627, startTimestamp=timezone.now(),
            statusType='inprogress', statusTitle='In Progress',
            homeTeamId=1, homeTeamSlug='nyj', homeTeamName='Jets',
            awayTeamId=2, awayTeamSlug='ne', awayTeamName='Patriots',
        )
        defaults.update(overrides)
        return GamesAndScores.objects.create(**defaults)


class PoolDetailPageTests(RepairViewsTestCase):
    def test_renders_and_lists_season_points_and_picks(self):
        self._make_season_row()
        self._make_pick()

        response = self.client.get(reverse('superadmin:pool_detail', args=[self.pool.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alice')
        self.assertContains(response, 'dagostino')

    def test_404_for_missing_pool(self):
        response = self.client.get(reverse('superadmin:pool_detail', args=[99999]))
        self.assertEqual(response.status_code, 404)


class PoolRecomputeTests(RepairViewsTestCase):
    def test_calls_the_service_and_audits(self):
        response = self.client.post(reverse('superadmin:pool_recompute', args=[self.pool.id]))

        self.assertRedirects(
            response, reverse('superadmin:pool_detail', args=[self.pool.id]),
        )
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
            ).exists()
        )

    def test_get_is_rejected(self):
        response = self.client.get(reverse('superadmin:pool_recompute', args=[self.pool.id]))
        self.assertEqual(response.status_code, 405)


class PoolRescoreWeekTests(RepairViewsTestCase):
    def test_valid_week_rescoreds_and_redirects(self):
        pick = self._make_pick(gameWeek='1', pick_correct=True)

        response = self.client.post(
            reverse('superadmin:pool_rescore_week', args=[self.pool.id]), {'week': '1'},
        )

        self.assertRedirects(
            response, reverse('superadmin:pool_detail', args=[self.pool.id]),
        )
        pick.refresh_from_db()
        self.assertFalse(pick.pick_correct)
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
                summary__contains='Re-scored week 1',
            ).exists()
        )

    def test_bad_week_is_rejected_without_calling_the_service(self):
        response = self.client.post(
            reverse('superadmin:pool_rescore_week', args=[self.pool.id]), {'week': 'not-a-number'},
        )

        self.assertRedirects(
            response, reverse('superadmin:pool_detail', args=[self.pool.id]),
        )
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_get_is_rejected(self):
        response = self.client.get(reverse('superadmin:pool_rescore_week', args=[self.pool.id]))
        self.assertEqual(response.status_code, 405)


class PickDeleteTests(RepairViewsTestCase):
    def test_wrong_confirm_does_not_delete_and_writes_no_audit_row(self):
        pick = self._make_pick()

        response = self.client.post(
            reverse('superadmin:pick_delete', args=[pick.id]), {'confirm': 'wrong-user'},
        )

        self.assertRedirects(
            response, reverse('superadmin:pool_detail', args=[self.pool.id]),
        )
        self.assertTrue(GamePicks.objects.filter(pk=pick.id).exists())
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_correct_confirm_deletes_and_audits(self):
        pick = self._make_pick()

        response = self.client.post(
            reverse('superadmin:pick_delete', args=[pick.id]), {'confirm': 'alice'},
        )

        self.assertRedirects(
            response, reverse('superadmin:pool_detail', args=[self.pool.id]),
        )
        self.assertFalse(GamePicks.objects.filter(pk=pick.id).exists())
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
            ).exists()
        )

    def test_get_is_rejected(self):
        pick = self._make_pick()
        response = self.client.get(reverse('superadmin:pick_delete', args=[pick.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(GamePicks.objects.filter(pk=pick.id).exists())


class SeasonRowResetTests(RepairViewsTestCase):
    def test_wrong_confirm_does_not_reset_and_writes_no_audit_row(self):
        row = self._make_season_row()

        response = self.client.post(
            reverse('superadmin:season_row_reset', args=[row.id]), {'confirm': 'wrong-user'},
        )

        self.assertRedirects(
            response, reverse('superadmin:pool_detail', args=[self.pool.id]),
        )
        self.assertTrue(userSeasonPoints.objects.filter(pk=row.id).exists())
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_correct_confirm_deletes_and_audits(self):
        row = self._make_season_row()

        response = self.client.post(
            reverse('superadmin:season_row_reset', args=[row.id]), {'confirm': 'alice'},
        )

        self.assertRedirects(
            response, reverse('superadmin:pool_detail', args=[self.pool.id]),
        )
        self.assertFalse(userSeasonPoints.objects.filter(pk=row.id).exists())
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
            ).exists()
        )

    def test_get_is_rejected(self):
        row = self._make_season_row()
        response = self.client.get(reverse('superadmin:season_row_reset', args=[row.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(userSeasonPoints.objects.filter(pk=row.id).exists())


class GameFixTests(RepairViewsTestCase):
    def test_valid_finished_status_fixes_the_game(self):
        game = self._make_game()

        response = self.client.post(
            reverse('superadmin:game_fix', args=[game.id]),
            {'status': 'finished', 'home_score': '21', 'away_score': '17'},
        )

        self.assertRedirects(response, reverse('superadmin:overview'))
        game.refresh_from_db()
        self.assertEqual(game.statusType, 'finished')
        self.assertFalse(game.gameScored)
        # 21-17: home team (nyj) wins.
        self.assertEqual(game.gameWinner, 'nyj')
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
            ).exists()
        )

    def test_invalid_status_is_rejected_and_game_unchanged(self):
        game = self._make_game()

        response = self.client.post(
            reverse('superadmin:game_fix', args=[game.id]),
            {'status': 'bogus', 'home_score': '21', 'away_score': '17'},
        )

        self.assertRedirects(response, reverse('superadmin:overview'))
        game.refresh_from_db()
        self.assertEqual(game.statusType, 'inprogress')
        self.assertIsNone(game.homeTeamScore)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_non_integer_scores_are_rejected(self):
        game = self._make_game()

        response = self.client.post(
            reverse('superadmin:game_fix', args=[game.id]),
            {'status': 'finished', 'home_score': 'not-a-number', 'away_score': '17'},
        )

        self.assertRedirects(response, reverse('superadmin:overview'))
        game.refresh_from_db()
        self.assertEqual(game.statusType, 'inprogress')
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_get_is_rejected(self):
        game = self._make_game()
        response = self.client.get(reverse('superadmin:game_fix', args=[game.id]))
        self.assertEqual(response.status_code, 405)
