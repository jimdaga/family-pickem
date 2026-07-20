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
    FamilyMembership,
    GamePicks,
    GamesAndScores,
    Pool,
    PoolSettings,
    UserProfile,
    userSeasonPoints,
    userStats,
)
from pickem_homepage.models import MessageBoardPost
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

    def test_block_audit_captures_the_real_prior_blocked_reason(self):
        """A stale reason (Django admin can set one on an active user) must be
        recorded as the before-state, not a hardcoded ''."""
        profile = UserProfile.objects.get(user=self.spammer)
        profile.blocked_reason = 'left over from a previous block'
        profile.save(update_fields=['blocked_reason'])

        services.block_user(self._request(), self.spammer, reason='Spamming')

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(
            entry.changes['blocked_reason'],
            ['left over from a previous block', 'Spamming'],
        )

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

        # An active family member with no pick at all, so the "every active
        # member gets a zero-points row" path in update_standings actually
        # runs (member_combos isn't empty). Both pools share self.family, so
        # this member is eligible for a zero-row in EITHER pool depending on
        # whether the --pool filter on the member/pool queryset is honored.
        self.member = User.objects.create_user(username='carol', password='pw')
        FamilyMembership.objects.create(
            family=self.family, user=self.member,
            role=FamilyMembership.Role.MEMBER, status=FamilyMembership.Status.ACTIVE,
        )

    def test_update_standings_with_pool_touches_only_that_pool(self):
        """Without --pool there is no way to recompute one pool, which is what the
        repair action needs. The point is the *scoping*, so assert pool B is
        untouched — a test that only asserts pool A got a row would pass even if
        the filter were ignored entirely.

        The zero-points member path is what actually exercises the pool filter
        on the member/pool queryset: with no FamilyMembership fixture at all,
        member_combos is empty regardless of the filter and this test would
        pass even with the filter removed."""
        call_command(
            'update_standings', season=2627, pool=self.pool_a.id, stdout=StringIO(),
        )

        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_a).exists())
        self.assertFalse(userSeasonPoints.objects.filter(pool=self.pool_b).exists())
        self.assertTrue(
            userSeasonPoints.objects.filter(
                pool=self.pool_a, userID=str(self.member.id),
            ).exists()
        )
        self.assertFalse(
            userSeasonPoints.objects.filter(
                pool=self.pool_b, userID=str(self.member.id),
            ).exists()
        )

    def test_update_standings_without_pool_still_touches_every_pool(self):
        """The existing season-wide behavior must not regress."""
        call_command('update_standings', season=2627, stdout=StringIO())

        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_a).exists())
        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_b).exists())

    def test_update_stats_with_pool_touches_only_that_pool(self):
        """Assert on CONTENT, not just presence: `_upsert` always writes under
        the constant --pool id passed in, so an unfiltered `identities` query
        would silently mix pool B's user ('bob') into pool A's rows without
        ever tripping a presence-only assertion on userStats.filter(pool=pool_b)."""
        call_command('update_stats', season=2627, pool=self.pool_a.id, stdout=StringIO())

        pool_a_user_ids = set(
            userStats.objects.filter(pool=self.pool_a).values_list('userID', flat=True)
        )
        self.assertEqual(pool_a_user_ids, {'alice'})
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

    def test_rescore_week_restores_correctness_on_already_scored_games(self):
        """The common case: the week's games are already scored (gameScored=True).
        update_picks skips scored games, so unless rescore resets them to
        unscored, a formerly-correct pick cleared to False stays False and the
        repair silently lowers points. Drives the real pipeline, so a fix that
        only clears pick_correct (without resetting gameScored) fails here."""
        GamesAndScores.objects.create(
            id=410, slug='ne-at-nyj-w1', competition='nfl', gameWeek='1',
            gameyear='2026', gameseason=2627, startTimestamp=timezone.now(),
            statusType='finished', statusTitle='Final',
            homeTeamId=1, homeTeamSlug='nyj', homeTeamName='Jets',
            awayTeamId=2, awayTeamSlug='ne', awayTeamName='Patriots',
            homeTeamScore=21, awayTeamScore=17, gameWinner='nyj', gameScored=True,
        )
        pick = GamePicks.objects.create(
            id='dagostino-pickem-pool-root-w1', pool=self.pool, userID='root',
            pick='nyj', gameseason=2627, gameWeek=1, pick_game_id=410,
            pick_correct=False,
        )

        services.rescore_week(self._request(), self.pool, week=1)

        pick.refresh_from_db()
        self.assertTrue(pick.pick_correct)

    def test_rescore_week_regrades_sibling_pools_on_shared_games(self):
        """Games are shared across pools. After a result correction, every
        pool that picked the game must be re-graded — not just the target
        pool, or siblings silently keep stale pick_correct and standings."""
        other_family = Family.objects.create(name='Smith', slug='smith')
        other_pool = Pool.objects.create(
            family=other_family, name='Smith Pool', slug='smith-pool', season=2627,
        )
        # The game's result was corrected: nyj now the winner, already scored.
        GamesAndScores.objects.create(
            id=420, slug='ne-at-nyj-w2', competition='nfl', gameWeek='1',
            gameyear='2026', gameseason=2627, startTimestamp=timezone.now(),
            statusType='finished', statusTitle='Final',
            homeTeamId=1, homeTeamSlug='nyj', homeTeamName='Jets',
            awayTeamId=2, awayTeamSlug='ne', awayTeamName='Patriots',
            homeTeamScore=21, awayTeamScore=17, gameWinner='nyj', gameScored=True,
        )
        # Target pool's pick: graded correct under the OLD (wrong) result.
        target_pick = GamePicks.objects.create(
            id='dagostino-pickem-pool-root-420', pool=self.pool, userID='root',
            pick='ne', gameseason=2627, gameWeek=1, pick_game_id=420,
            pick_correct=True,
        )
        # Sibling pool's pick on the same game, same stale grading.
        sibling_pick = GamePicks.objects.create(
            id=f'{other_pool.id}-bob-420', pool=other_pool, userID='bob',
            pick='ne', gameseason=2627, gameWeek=1, pick_game_id=420,
            pick_correct=True,
        )

        result = services.rescore_week(self._request(), self.pool, week=1)

        target_pick.refresh_from_db()
        sibling_pick.refresh_from_db()
        self.assertFalse(target_pick.pick_correct)
        self.assertFalse(
            sibling_pick.pick_correct,
            'sibling pool pick on the corrected game must be re-graded too',
        )
        self.assertIn(other_pool.id, result.get('affected_pools', []))

    def test_fix_stuck_game_records_before_and_after(self):
        game = GamesAndScores.objects.create(
            id=401, slug='ne-at-nyj', competition='nfl', gameWeek='1',
            gameyear='2026', gameseason=2627, startTimestamp=timezone.now(),
            statusType='inprogress', statusTitle='In Progress',
            homeTeamId=1, homeTeamSlug='nyj', homeTeamName='Jets',
            awayTeamId=2, awayTeamSlug='ne', awayTeamName='Patriots',
        )
        before_status = game.statusType

        services.fix_stuck_game(
            self._request(), game, status='finished', home_score=21, away_score=17,
        )

        game.refresh_from_db()
        self.assertEqual(game.statusType, 'finished')
        self.assertEqual(game.homeTeamScore, 21)
        self.assertEqual(game.awayTeamScore, 17)
        # 21-17: home team (nyj) wins.
        self.assertEqual(game.gameWinner, 'nyj')
        self.assertFalse(game.gameScored)
        entry = SuperAdminAuditLog.objects.filter(
            action=SuperAdminAuditLog.Action.DATA_REPAIR,
        ).latest('created_at')
        self.assertEqual(entry.changes['statusType'], [before_status, 'finished'])
        self.assertEqual(entry.changes['gameWinner'], [None, 'nyj'])
        self.assertIsNone(FamilyAuditLog.objects.first())

    def test_fix_stuck_game_actually_unsticks_scoring_end_to_end(self):
        """The point of the repair action is to make a stuck game scoreable
        again. Writing statusType alone is not enough: update_picks only scores
        games with statusType="finished" AND a populated gameWinner, and only
        picks up games with gameScored=False. This test drives the real
        update_picks command so a no-op fix (raw status string, no winner, no
        gameScored reset) fails here even though it would pass a test that only
        checks the raw field got written."""
        game = GamesAndScores.objects.create(
            id=402, slug='ne-at-nyj-2', competition='nfl', gameWeek='2',
            gameyear='2026', gameseason=2627, startTimestamp=timezone.now(),
            statusType='inprogress', statusTitle='In Progress', gameScored=False,
            homeTeamId=1, homeTeamSlug='nyj', homeTeamName='Jets',
            awayTeamId=2, awayTeamSlug='ne', awayTeamName='Patriots',
        )
        pick = GamePicks.objects.create(
            id='stuck-game-pick-1', pool=self.pool, userID='root',
            pick='nyj', gameseason=2627, gameWeek='2', pick_game_id=game.id,
            pick_correct=False,
        )

        services.fix_stuck_game(
            self._request(), game, status='finished', home_score=24, away_score=10,
        )
        call_command('update_picks', season=2627, stdout=StringIO())

        pick.refresh_from_db()
        game.refresh_from_db()
        self.assertEqual(game.gameWinner, 'nyj')
        self.assertTrue(game.gameScored)
        self.assertTrue(pick.pick_correct)


class ForceDeleteFamilyTests(TestCase):
    """Family/Pool FKs are mostly PROTECT, so a raw family.delete() would raise
    ProtectedError. The service must delete every pool/family-scoped child row
    first (in dependency order) and must never touch User/UserProfile rows —
    membership disappears, but the account underneath it must survive."""

    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.member = User.objects.create_user(username='delfam-member', password='pw')
        self.family = Family.objects.create(name='ToDelete', slug='to-delete')
        self.pool = Pool.objects.create(
            family=self.family, name='Pool', slug='pool', season=2627,
        )
        self.pool_settings = PoolSettings.objects.create(pool=self.pool)
        self.membership = FamilyMembership.objects.create(
            family=self.family, user=self.member,
            role=FamilyMembership.Role.MEMBER, status=FamilyMembership.Status.ACTIVE,
        )
        self.pick = GamePicks.objects.create(
            id='to-delete-pool-member-1', pool=self.pool, userID=str(self.member.id),
            pick='ne', gameseason=2627, gameWeek='1', pick_game_id=101,
        )
        self.season_row = userSeasonPoints.objects.create(
            pool=self.pool, userID=str(self.member.id), gameseason=2627, total_points=10,
        )
        self.post = MessageBoardPost.objects.create(
            family=self.family, user=self.member, title='Hi', content='Hello there',
        )

    def _request(self):
        request = RequestFactory().post('/superadmin/families/')
        request.user = self.root
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        return request

    def test_cascade_deletes_related_but_keeps_users(self):
        family_pk = self.family.pk

        services.force_delete_family(self._request(), self.family)

        self.assertFalse(Family.objects.filter(pk=family_pk).exists())
        self.assertFalse(Pool.objects.filter(pk=self.pool.pk).exists())
        self.assertFalse(PoolSettings.objects.filter(pk=self.pool_settings.pk).exists())
        self.assertFalse(FamilyMembership.objects.filter(pk=self.membership.pk).exists())
        self.assertFalse(GamePicks.objects.filter(pk=self.pick.pk).exists())
        self.assertFalse(userSeasonPoints.objects.filter(pk=self.season_row.pk).exists())
        self.assertFalse(MessageBoardPost.objects.filter(pk=self.post.pk).exists())

        # Never delete accounts.
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.root.pk).exists())

    def test_writes_an_audit_row_with_captured_before_state(self):
        family_pk = self.family.pk

        services.force_delete_family(self._request(), self.family)

        entry = SuperAdminAuditLog.objects.get(
            action=SuperAdminAuditLog.Action.FAMILY_FORCE_DELETED,
        )
        self.assertEqual(entry.target_id, str(family_pk))
        self.assertEqual(entry.changes['before']['slug'], 'to-delete')
        self.assertEqual(entry.changes['before']['name'], 'ToDelete')
        self.assertEqual(entry.changes['before']['deleted_counts']['pools'], 1)
        self.assertEqual(entry.changes['before']['deleted_counts']['picks'], 1)
        self.assertIsNone(entry.changes['after'])
