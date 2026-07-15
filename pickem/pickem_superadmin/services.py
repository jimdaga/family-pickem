"""Repair and moderation actions.

Plain functions, no HTTP awareness beyond taking `request` for the audit trail.
That keeps them unit-testable and usable from a shell.
"""
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from pickem_api.models import (
    FamilyAuditLog,
    GamePicks,
    PoolSettings,
    UserProfile,
)
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.models import SuperAdminAuditLog


def flush_user_sessions(user):
    """Kill this user's active sessions so a block takes effect now, not at next
    login. Django stores the user id inside the encoded session payload, so we
    decode rather than query — the table has no user column."""
    killed = 0
    for session in Session.objects.iterator():
        data = session.get_decoded()
        if str(data.get('_auth_user_id')) == str(user.pk):
            session.delete()
            killed += 1
    return killed


@transaction.atomic
def block_user(request, user, reason):
    if user.is_superuser:
        raise ValidationError('Superusers cannot be blocked.')
    if user.pk == request.user.pk:
        raise ValidationError('You cannot block yourself.')
    if not reason or not reason.strip():
        raise ValidationError('A reason is required to block a user.')

    was_active = user.is_active
    user.is_active = False
    user.save(update_fields=['is_active'])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.blocked_at = timezone.now()
    profile.blocked_by = request.user
    profile.blocked_reason = reason.strip()
    profile.save(update_fields=['blocked_at', 'blocked_by', 'blocked_reason'])

    flush_user_sessions(user)

    changes = {'is_active': [was_active, False], 'blocked_reason': ['', reason.strip()]}
    log_action(
        request,
        action=SuperAdminAuditLog.Action.USER_BLOCKED,
        target=user,
        summary=f'Blocked user {user.username}: {reason.strip()}',
        changes=changes,
    )
    return changes


@transaction.atomic
def unblock_user(request, user):
    was_active = user.is_active
    user.is_active = True
    user.save(update_fields=['is_active'])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    previous_reason = profile.blocked_reason
    profile.blocked_at = None
    profile.blocked_by = None
    profile.blocked_reason = ''
    profile.save(update_fields=['blocked_at', 'blocked_by', 'blocked_reason'])

    changes = {'is_active': [was_active, True], 'blocked_reason': [previous_reason, '']}
    log_action(
        request,
        action=SuperAdminAuditLog.Action.USER_UNBLOCKED,
        target=user,
        summary=f'Unblocked user {user.username}',
        changes=changes,
    )
    return changes


@transaction.atomic
def backfill_pool_settings(request, pool):
    """Create the default PoolSettings row for a pool that has none. Idempotent."""
    settings_obj, created = PoolSettings.objects.get_or_create(pool=pool)
    if created:
        log_action(
            request,
            action=SuperAdminAuditLog.Action.DATA_REPAIR,
            target=pool,
            summary=f'Backfilled PoolSettings for {pool.family.slug}/{pool.slug}',
            changes={'pool_settings': [None, 'created with defaults']},
            family=pool.family,
            pool=pool,
            family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
        )
    return settings_obj


def recompute_pool(request, pool):
    """Re-run standings + stats scoped to one pool. Idempotent — safe to spam.

    Not wrapped in transaction.atomic: the commands manage their own writes and
    can be long-running, so holding one transaction open across both would pin a
    connection for no benefit. Re-running on failure is safe precisely because
    this is idempotent.
    """
    call_command('update_standings', season=pool.season, pool=pool.id)
    call_command('update_stats', season=pool.season, pool=pool.id)

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Recomputed standings + stats for {pool.family.slug}/{pool.slug}',
        changes={'recompute': [None, f'season {pool.season}']},
        family=pool.family,
        pool=pool,
        family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
    )
    return {'pool': pool.id, 'season': pool.season}


@transaction.atomic
def delete_pick(request, pick):
    """Destructive and NOT reversible. The audit row is the only record of what the
    pick was, so capture it before deleting."""
    before = {
        'pick': [pick.pick, None],
        'pick_game_id': [pick.pick_game_id, None],
        'userID': [pick.userID, None],
        'id': [pick.id, None],
    }
    pool = pick.pool
    pick.delete()

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Deleted pick {before["id"][0]}',
        changes=before,
        family=pool.family if pool else None,
        pool=pool,
        family_action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED if pool else None,
    )
    return before


@transaction.atomic
def reset_season_row(request, season_points):
    """Destructive: delete a drifted userSeasonPoints row so a recompute rebuilds it
    from scratch. Capture the totals first — this is not reversible."""
    pool = season_points.pool
    before = {
        'userID': [season_points.userID, None],
        'total_points': [season_points.total_points, None],
    }
    season_points.delete()

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Reset season row for {before["userID"][0]}',
        changes=before,
        family=pool.family if pool else None,
        pool=pool,
        family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED if pool else None,
    )
    return before


def rescore_week(request, pool, week):
    """Re-score one week after a game result is corrected.

    Clearing first is the whole point: update_picks only scores *unscored* picks,
    so recomputing without clearing would leave an already-scored (and now wrong)
    pick exactly as wrong as it was. Idempotent.
    """
    GamePicks.objects.filter(
        pool=pool, gameseason=pool.season, gameWeek=str(week),
    ).update(pick_correct=False)
    call_command('update_picks', season=pool.season)
    call_command('update_standings', season=pool.season, pool=pool.id)

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Re-scored week {week} for {pool.family.slug}/{pool.slug}',
        changes={'rescore_week': [None, week]},
        family=pool.family,
        pool=pool,
        family_action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED,
    )
    return {'pool': pool.id, 'week': week}


@transaction.atomic
def fix_stuck_game(request, game, status, home_score, away_score):
    """Unwedge a game ESPN left in progress forever. Destructive: it overwrites
    what the feed reported, so record both sides. Global action (games aren't
    owned by a pool), so no FamilyAuditLog dual-write."""
    before = {
        'statusType': game.statusType,
        'homeTeamScore': game.homeTeamScore,
        'awayTeamScore': game.awayTeamScore,
    }

    game.statusType = status
    game.homeTeamScore = home_score
    game.awayTeamScore = away_score
    game.save(update_fields=['statusType', 'homeTeamScore', 'awayTeamScore'])

    after = {
        'statusType': game.statusType,
        'homeTeamScore': game.homeTeamScore,
        'awayTeamScore': game.awayTeamScore,
    }
    changes = diff_fields(before, after)

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=game,
        summary=f'Fixed stuck game {game.slug} -> {status}',
        changes=changes,
    )
    return changes
