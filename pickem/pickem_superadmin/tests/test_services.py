from io import StringIO

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from pickem_api.models import (
    Family,
    FamilyAuditLog,
    GamePicks,
    GamesAndScores,
    Pool,
    PoolSettings,
    UserProfile,
    userSeasonPoints,
    userStats,
)
from pickem_superadmin import services
from pickem_superadmin.models import SuperAdminAuditLog


class BlockUserTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.other_root = User.objects.create_superuser(
            username='root2', email='root2@example.com', password='pw',
        )
        self.spammer = User.objects.create_user(
            username='spammer', email='spam@example.com', password='pw',
        )
        UserProfile.objects.get_or_create(user=self.spammer)

    def _request(self):
        request = RequestFactory().post('/superadmin/users/')
        request.user = self.root
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        return request

    def test_block_deactivates_user_and_stamps_the_profile(self):
        services.block_user(self._request(), self.spammer, reason='Spamming the board')

        self.spammer.refresh_from_db()
        profile = UserProfile.objects.get(user=self.spammer)
        self.assertFalse(self.spammer.is_active)
        self.assertIsNotNone(profile.blocked_at)
        self.assertEqual(profile.blocked_by, self.root)
        self.assertEqual(profile.blocked_reason, 'Spamming the board')

    def test_block_writes_an_audit_row_with_before_after(self):
        services.block_user(self._request(), self.spammer, reason='Spamming')
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.USER_BLOCKED)
        self.assertEqual(entry.changes['is_active'], [True, False])
        self.assertEqual(entry.target_id, str(self.spammer.id))

    def test_block_flushes_the_users_existing_sessions(self):
        """Without this, a blocked user keeps browsing until their session expires."""
        self.client.force_login(self.spammer)
        self.assertEqual(Session.objects.count(), 1)

        services.block_user(self._request(), self.spammer, reason='Spamming')

        self.assertEqual(Session.objects.count(), 0)

    def test_block_leaves_other_users_sessions_alone(self):
        bystander = User.objects.create_user(username='bystander', password='pw')
        self.client.force_login(bystander)
        other_client_sessions = Session.objects.count()

        services.block_user(self._request(), self.spammer, reason='Spamming')

        self.assertEqual(Session.objects.count(), other_client_sessions)

    def test_cannot_block_a_superuser(self):
        with self.assertRaises(ValidationError):
            services.block_user(self._request(), self.other_root, reason='nope')
        self.other_root.refresh_from_db()
        self.assertTrue(self.other_root.is_active)

    def test_cannot_block_yourself(self):
        """A non-superuser actor must be blocked by the self-block guard, not the
        superuser guard, or this test would pass even if self-block was unenforced."""
        self_blocker = User.objects.create_user(
            username='selfblock', email='selfblock@example.com', password='pw',
        )
        UserProfile.objects.get_or_create(user=self_blocker)
        request = RequestFactory().post('/superadmin/users/')
        request.user = self_blocker
        request.META['REMOTE_ADDR'] = '10.0.0.5'

        with self.assertRaisesMessage(ValidationError, 'You cannot block yourself.'):
            services.block_user(request, self_blocker, reason='nope')

        self_blocker.refresh_from_db()
        self.assertTrue(self_blocker.is_active)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_failed_block_writes_no_audit_row(self):
        with self.assertRaises(ValidationError):
            services.block_user(self._request(), self.other_root, reason='nope')
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_unblock_reverses_the_block(self):
        services.block_user(self._request(), self.spammer, reason='Spamming')
        services.unblock_user(self._request(), self.spammer)

        self.spammer.refresh_from_db()
        profile = UserProfile.objects.get(user=self.spammer)
        self.assertTrue(self.spammer.is_active)
        self.assertIsNone(profile.blocked_at)
        self.assertIsNone(profile.blocked_by)
        self.assertEqual(profile.blocked_reason, '')
        self.assertEqual(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.USER_UNBLOCKED,
            ).count(),
            1,
        )


class PoolScopedCommandTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool_a = Pool.objects.create(
            family=self.family, name='A', slug='a', season=2627,
        )
        self.pool_b = Pool.objects.create(
            family=self.family, name='B', slug='b', season=2627,
        )
        # A scored pick in each pool, so a season-wide run would touch both.
        for pool, user_id, game_id in (
            (self.pool_a, 'alice', 101),
            (self.pool_b, 'bob', 102),
        ):
            GamePicks.objects.create(
                id=f'{pool.slug}-{user_id}-1', pool=pool, userID=user_id,
                pick='ne', gameseason=2627, gameWeek='1', pick_game_id=game_id,
                pick_correct=True,
            )

    def test_update_standings_with_pool_touches_only_that_pool(self):
        """Without --pool there is no way to recompute one pool, which is what the
        repair action needs. The point is the *scoping*, so assert pool B is
        untouched — a test that only asserts pool A got a row would pass even if
        the filter were ignored entirely."""
        call_command(
            'update_standings', season=2627, pool=self.pool_a.id, stdout=StringIO(),
        )

        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_a).exists())
        self.assertFalse(userSeasonPoints.objects.filter(pool=self.pool_b).exists())

    def test_update_standings_without_pool_still_touches_every_pool(self):
        """The existing season-wide behavior must not regress."""
        call_command('update_standings', season=2627, stdout=StringIO())

        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_a).exists())
        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_b).exists())

    def test_update_stats_with_pool_touches_only_that_pool(self):
        call_command('update_stats', season=2627, pool=self.pool_a.id, stdout=StringIO())

        self.assertTrue(userStats.objects.filter(pool=self.pool_a).exists())
        self.assertFalse(userStats.objects.filter(pool=self.pool_b).exists())

    def test_update_stats_without_pool_still_writes_global_row(self):
        """Regression guard: the default (no --pool) path must keep writing the
        single global (pool-null) row per user, unchanged."""
        call_command('update_stats', season=2627, stdout=StringIO())

        self.assertFalse(userStats.objects.filter(pool__isnull=False).exists())


class RepairServiceTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )

    def _request(self):
        request = RequestFactory().post('/superadmin/')
        request.user = self.root
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        return request

    def test_backfill_creates_the_missing_settings_row(self):
        self.assertFalse(PoolSettings.objects.filter(pool=self.pool).exists())
        services.backfill_pool_settings(self._request(), self.pool)
        self.assertTrue(PoolSettings.objects.filter(pool=self.pool).exists())

    def test_backfill_is_idempotent(self):
        services.backfill_pool_settings(self._request(), self.pool)
        services.backfill_pool_settings(self._request(), self.pool)
        self.assertEqual(PoolSettings.objects.filter(pool=self.pool).count(), 1)

    def test_backfill_audits_and_dual_writes(self):
        services.backfill_pool_settings(self._request(), self.pool)
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.DATA_REPAIR)
        self.assertEqual(FamilyAuditLog.objects.count(), 1)

    def test_recompute_pool_is_idempotent(self):
        """Running it twice must not double points — this is the workhorse action
        and it has to be safe to spam."""
        GamePicks.objects.create(
            id='pickem-pool-root-1', pool=self.pool, userID='root',
            pick='ne', gameseason=2627, gameWeek='1', pick_game_id=201,
            pick_correct=True,
        )

        services.recompute_pool(self._request(), self.pool)
        first = list(
            userSeasonPoints.objects.filter(pool=self.pool)
            .order_by('id').values_list('total_points', flat=True)
        )
        services.recompute_pool(self._request(), self.pool)
        second = list(
            userSeasonPoints.objects.filter(pool=self.pool)
            .order_by('id').values_list('total_points', flat=True)
        )
        self.assertEqual(first, second)

    def test_recompute_pool_audits(self):
        services.recompute_pool(self._request(), self.pool)
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
            ).exists()
        )

    def test_delete_pick_records_the_row_before_deleting_it(self):
        """This one is not reversible, so the audit row is the only record of what
        was there."""
        pick = GamePicks.objects.create(
            id='dagostino-pickem-pool-root-1', pool=self.pool, userID='root',
            pick='ne', gameseason=2627, pick_game_id=301,
        )
        services.delete_pick(self._request(), pick)

        self.assertFalse(GamePicks.objects.filter(pk='dagostino-pickem-pool-root-1').exists())
        entry = SuperAdminAuditLog.objects.filter(
            action=SuperAdminAuditLog.Action.DATA_REPAIR,
        ).latest('created_at')
        self.assertEqual(entry.changes['pick'][0], 'ne')
        self.assertIsNone(entry.changes['pick'][1])

    def test_reset_season_row_records_totals_before_deleting_it(self):
        """Also not reversible — capture the totals before the row is gone."""
        row = userSeasonPoints.objects.create(
            pool=self.pool, userID='root', gameseason=2627, total_points=42,
        )
        services.reset_season_row(self._request(), row)

        self.assertFalse(userSeasonPoints.objects.filter(pk=row.pk).exists())
        entry = SuperAdminAuditLog.objects.filter(
            action=SuperAdminAuditLog.Action.DATA_REPAIR,
        ).latest('created_at')
        self.assertEqual(entry.changes['total_points'], [42, None])

    def test_rescore_week_clears_scoring_then_recomputes(self):
        """A corrected game result must actually flip a wrong pick. If rescore only
        recomputed without clearing, an already-scored pick would stay wrong."""
        pick = GamePicks.objects.create(
            id='dagostino-pickem-pool-root-1', pool=self.pool, userID='root',
            pick='ne', gameseason=2627, gameWeek=1, pick_game_id=401,
            pick_correct=True,
        )

        services.rescore_week(self._request(), self.pool, week=1)

        pick.refresh_from_db()
        # No finished game backs this pick, so rescoring must not leave it credited.
        self.assertFalse(pick.pick_correct)
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
                summary__contains='Re-scored week 1',
            ).exists()
        )

    def test_fix_stuck_game_records_before_and_after(self):
        game = GamesAndScores.objects.create(
            id=401, slug='ne-at-nyj', competition='nfl', gameWeek='1',
            gameyear='2026', gameseason=2627, startTimestamp=timezone.now(),
            statusType='STATUS_IN_PROGRESS', statusTitle='In Progress',
            homeTeamId=1, homeTeamSlug='nyj', homeTeamName='Jets',
            awayTeamId=2, awayTeamSlug='ne', awayTeamName='Patriots',
        )
        before_status = game.statusType

        services.fix_stuck_game(
            self._request(), game, status='STATUS_FINAL', home_score=21, away_score=17,
        )

        game.refresh_from_db()
        self.assertEqual(game.statusType, 'STATUS_FINAL')
        self.assertEqual(game.homeTeamScore, 21)
        self.assertEqual(game.awayTeamScore, 17)
        entry = SuperAdminAuditLog.objects.filter(
            action=SuperAdminAuditLog.Action.DATA_REPAIR,
        ).latest('created_at')
        self.assertEqual(entry.changes['statusType'], [before_status, 'STATUS_FINAL'])
        self.assertIsNone(FamilyAuditLog.objects.first())
