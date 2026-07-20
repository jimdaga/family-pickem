"""Repair and moderation actions.

Plain functions, no HTTP awareness beyond taking `request` for the audit trail.
That keeps them unit-testable and usable from a shell.
"""
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from pickem_api.management.commands.update_games import STATUS_MAP
from pickem_api.models import (
    FamilyAuditLog,
    GamePicks,
    GamesAndScores,
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
    previous_reason = profile.blocked_reason
    profile.blocked_at = timezone.now()
    profile.blocked_by = request.user
    profile.blocked_reason = reason.strip()
    profile.save(update_fields=['blocked_at', 'blocked_by', 'blocked_reason'])

    flush_user_sessions(user)

    changes = {
        'is_active': [was_active, False],
        # Capture the prior reason (Django admin can edit it directly), not a
        # hardcoded '', so the audit trail reflects the real before-state.
        'blocked_reason': [previous_reason, reason.strip()],
    }
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

    Two resets are required for this to actually recompute:
      1. Clear pick_correct on the week's picks — update_picks only ever
         sets picks True, never back to False, so a formerly-correct-now-wrong
         pick would otherwise stay True.
      2. Reset gameScored=False on the games those picks reference — update_picks
         only revisits games where gameScored is False, so without this the
         common case (games already scored) recomputes nothing and the cleared
         picks stay False.

    Games are SHARED across pools, so a result correction invalidates every
    pool's grading on the affected games, not just the target pool's. The
    clear therefore covers all picks on those games, and standings are
    recomputed for every affected pool (reported in the result/audit).
    """
    week_picks = GamePicks.objects.filter(
        pool=pool, gameseason=pool.season, gameWeek=str(week),
    )
    game_ids = list(week_picks.values_list('pick_game_id', flat=True).distinct())

    affected_picks = GamePicks.objects.filter(pick_game_id__in=game_ids)
    affected_pool_ids = sorted(
        set(
            affected_picks.exclude(pool=None)
            .order_by()
            .values_list('pool_id', flat=True)
            .distinct()
        )
        | {pool.id}
    )

    affected_picks.update(pick_correct=False)
    GamesAndScores.objects.filter(id__in=game_ids).update(gameScored=False)
    call_command('update_picks', season=pool.season)
    for affected_pool_id in affected_pool_ids:
        call_command('update_standings', season=pool.season, pool=affected_pool_id)

    sibling_pool_ids = [p for p in affected_pool_ids if p != pool.id]
    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Re-scored week {week} for {pool.family.slug}/{pool.slug}',
        changes={
            'rescore_week': [None, week],
            'sibling_pools_recomputed': [None, sibling_pool_ids],
        },
        family=pool.family,
        pool=pool,
        family_action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED,
    )
    return {'pool': pool.id, 'week': week, 'affected_pools': affected_pool_ids}


@transaction.atomic
def fix_stuck_game(request, game, status, home_score, away_score):
    """Unwedge a game ESPN left in progress forever. Destructive: it overwrites
    what the feed reported, so record both sides. Global action (games aren't
    owned by a pool), so no FamilyAuditLog dual-write.

    `status` is expected to be the NORMALIZED statusType value the rest of the
    app stores (e.g. 'finished', 'inprogress') — the same vocabulary
    update_games.py writes and update_picks.py reads (statusType="finished").
    As a defensive fallback, a raw ESPN STATUS_* code is mapped through the
    same STATUS_MAP update_games.py uses, so a caller that passes one by
    mistake doesn't silently wedge the game further.

    Just writing the status string is not enough to unstick anything:
    update_picks only scores games with statusType="finished" AND a populated
    gameWinner, and only re-scores games with gameScored=False. So this also
    derives gameWinner from the corrected scores (higher score's team slug;
    empty for a real tie) when the status is 'finished', and resets
    gameScored=False so the next update_picks run actually picks this game up.
    """
    normalized_status = STATUS_MAP.get(status, status)

    before = {
        'statusType': game.statusType,
        'homeTeamScore': game.homeTeamScore,
        'awayTeamScore': game.awayTeamScore,
        'gameWinner': game.gameWinner,
        'gameScored': game.gameScored,
    }

    game.statusType = normalized_status
    game.homeTeamScore = home_score
    game.awayTeamScore = away_score

    if normalized_status == 'finished' and home_score is not None and away_score is not None:
        if home_score > away_score:
            game.gameWinner = game.homeTeamSlug
        elif away_score > home_score:
            game.gameWinner = game.awayTeamSlug
        else:
            # A real tie: no winner, update_picks marks it scored with zero
            # correct picks once it sees the equal, populated scores.
            game.gameWinner = ''
    # Non-finished status: leave gameWinner untouched — there's nothing to
    # derive a winner from yet.

    game.gameScored = False
    game.save(
        update_fields=[
            'statusType', 'homeTeamScore', 'awayTeamScore', 'gameWinner', 'gameScored',
        ]
    )

    after = {
        'statusType': game.statusType,
        'homeTeamScore': game.homeTeamScore,
        'awayTeamScore': game.awayTeamScore,
        'gameWinner': game.gameWinner,
        'gameScored': game.gameScored,
    }
    changes = diff_fields(before, after)

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=game,
        summary=f'Fixed stuck game {game.slug} -> {normalized_status}',
        changes=changes,
    )
    return changes


@transaction.atomic
def force_delete_family(request, family):
    """Hard-delete a family and every pool/family-scoped row beneath it.

    Family/Pool FKs are mostly PROTECT (Pool.family, FamilyMembership.family,
    FamilyInvitation.family, FamilyAuditLog.family, PoolSettings.pool), so a
    raw `family.delete()` raises ProtectedError until every child row is gone.
    Deletion runs child-first in one transaction so a failure partway through
    rolls back cleanly rather than leaving the family half-deleted.

    NEVER deletes User or UserProfile rows: memberships, picks, and season
    stats disappear, but the accounts underneath them survive untouched.

    log_action() derives target_type/target_id from a live target object, but
    the target here (the family) no longer exists once we're done. So the
    audit write happens *before* `family.delete()`, while `family` still has
    a real pk — the resulting SuperAdminAuditLog row is a plain DB row with
    those values already baked in, so it survives the family's deletion
    intact, still inside the same atomic block.
    """
    from pickem_api.models import (
        Family, Pool, PoolSettings, FamilyMembership, FamilyInvitation, FamilyAuditLog,
        GamePicks, userPoints, userSeasonPoints, userStats,
    )
    from pickem_homepage.models import (
        MessageBoardPost, MessageBoardComment, MessageBoardVote, SiteBanner,
    )

    # Re-fetch under a row lock so two concurrent force-deletes can't both act on
    # the same stale instance (double audit, or a success reported after another
    # request already deleted it). If it vanished while we waited, there's nothing
    # to do.
    try:
        family = Family.objects.select_for_update().get(pk=family.pk)
    except Family.DoesNotExist:
        return None

    pool_ids = list(Pool.objects.filter(family=family).values_list('id', flat=True))

    # Capture the before-state (pre-deletion counts) BEFORE mutating anything, per
    # the destructive-action audit convention. These are the same numbers the
    # deletes would report, snapshotted while the rows still exist.
    counts = {
        'picks': GamePicks.objects.filter(pool_id__in=pool_ids).count(),
        'user_points': userPoints.objects.filter(pool_id__in=pool_ids).count(),
        'season_points': userSeasonPoints.objects.filter(pool_id__in=pool_ids).count(),
        'user_stats': userStats.objects.filter(pool_id__in=pool_ids).count(),
        'votes': MessageBoardVote.objects.filter(family=family).count(),
        'comments': MessageBoardComment.objects.filter(family=family).count(),
        'posts': MessageBoardPost.objects.filter(family=family).count(),
        'family_audit': FamilyAuditLog.objects.filter(family=family).count(),
        'invitations': FamilyInvitation.objects.filter(family=family).count(),
        'pool_settings': PoolSettings.objects.filter(pool_id__in=pool_ids).count(),
        'memberships': FamilyMembership.objects.filter(family=family).count(),
        'banners': SiteBanner.objects.filter(family=family).count(),
        'pools': Pool.objects.filter(family=family).count(),
    }
    before = {'slug': family.slug, 'name': family.name, 'deleted_counts': counts}

    # Audit the before-state before we mutate. `family` still has a live pk here so
    # log_action can derive target_type/target_id; no `family=` kwarg is passed, so
    # it writes only a SuperAdminAuditLog row (no FamilyAuditLog dual-write that
    # would PROTECT-block the delete). That row survives the family's deletion
    # below, inside the same atomic block.
    log_action(
        request,
        action=SuperAdminAuditLog.Action.FAMILY_FORCE_DELETED,
        target=family,
        summary=f"Force-deleted family {before['slug']}",
        changes={'before': before, 'after': None},
    )

    # Delete child-first (FKs are mostly PROTECT), then the family itself.
    GamePicks.objects.filter(pool_id__in=pool_ids).delete()
    userPoints.objects.filter(pool_id__in=pool_ids).delete()
    userSeasonPoints.objects.filter(pool_id__in=pool_ids).delete()
    userStats.objects.filter(pool_id__in=pool_ids).delete()
    MessageBoardVote.objects.filter(family=family).delete()
    MessageBoardComment.objects.filter(family=family).delete()
    MessageBoardPost.objects.filter(family=family).delete()
    FamilyAuditLog.objects.filter(family=family).delete()
    FamilyInvitation.objects.filter(family=family).delete()
    PoolSettings.objects.filter(pool_id__in=pool_ids).delete()
    FamilyMembership.objects.filter(family=family).delete()
    SiteBanner.objects.filter(family=family).delete()
    Pool.objects.filter(family=family).delete()
    family.delete()
    return counts
