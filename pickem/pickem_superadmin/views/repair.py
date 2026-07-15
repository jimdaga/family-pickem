"""Data-repair actions: recompute/rescore a pool, delete a pick, reset a season
row, unstick a game. The heavy lifting lives in services.py (already tested);
these views only gate access, validate input, and translate outcomes into
messages + redirects. They must never call log_action() themselves — the
services do that internally.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import GamePicks, GamesAndScores, Pool, userSeasonPoints
from pickem_superadmin import services
from pickem_superadmin.decorators import superadmin_required

# Weeks selectable in the rescore-week dropdown. 18 covers the current NFL
# regular-season length; there is nothing in GamePicks.gameWeek itself to
# derive this from (it's a free-text CharField), so it's a constant.
WEEK_CHOICES = range(1, 19)

# Only these NORMALIZED statusType values make sense to force a game into.
# Anything else (a raw ESPN STATUS_* code, a typo) is rejected here rather
# than trusted through to the service.
VALID_GAME_STATUSES = ('finished', 'inprogress')


def _redirect_to_pool(pool):
    """Redirect back to a pool's detail page, or the overview if the pool is
    somehow gone (GamePicks.pool and userSeasonPoints.pool are both nullable
    FKs with on_delete=SET_NULL, so this can happen for orphaned rows)."""
    if pool is None:
        return redirect('superadmin:overview')
    return redirect('superadmin:pool_detail', pool_id=pool.id)


@superadmin_required
def pool_detail(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    season_points = userSeasonPoints.objects.filter(pool=pool).order_by('-total_points')
    picks = GamePicks.objects.filter(pool=pool).order_by('-pickUpdated')[:50]

    return render(request, 'superadmin/pool_detail.html', {
        'pool': pool,
        'season_points': season_points,
        'picks': picks,
        'week_choices': WEEK_CHOICES,
    })


@superadmin_required
@require_POST
def pool_recompute(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    services.recompute_pool(request, pool)
    messages.success(request, f'Recomputed {pool.family.slug}/{pool.slug}.')
    return redirect('superadmin:pool_detail', pool_id=pool.id)


@superadmin_required
@require_POST
def pool_rescore_week(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    try:
        week = int(request.POST.get('week'))
    except (TypeError, ValueError):
        messages.error(request, 'Week must be an integer.')
        return redirect('superadmin:pool_detail', pool_id=pool.id)

    services.rescore_week(request, pool, week)
    messages.success(request, f'Re-scored week {week} for {pool.family.slug}/{pool.slug}.')
    return redirect('superadmin:pool_detail', pool_id=pool.id)


@superadmin_required
@require_POST
def pick_delete(request, pick_id):
    pick = get_object_or_404(GamePicks, pk=pick_id)
    # Captured before delete(): once the service deletes the row, pick.pool
    # would still be readable off the cached instance, but read it up front
    # anyway so the redirect target never depends on delete() internals.
    pool = pick.pool

    if request.POST.get('confirm', '').strip() != str(pick.userID):
        messages.error(
            request,
            f'Confirmation did not match. Type "{pick.userID}" exactly to delete.',
        )
        return _redirect_to_pool(pool)

    services.delete_pick(request, pick)
    messages.success(request, f'Deleted pick for {pick.userID}.')
    return _redirect_to_pool(pool)


@superadmin_required
@require_POST
def season_row_reset(request, row_id):
    row = get_object_or_404(userSeasonPoints, pk=row_id)
    pool = row.pool

    if request.POST.get('confirm', '').strip() != str(row.userID):
        messages.error(
            request,
            f'Confirmation did not match. Type "{row.userID}" exactly to reset.',
        )
        return _redirect_to_pool(pool)

    services.reset_season_row(request, row)
    messages.success(request, f'Reset season row for {row.userID}.')
    return _redirect_to_pool(pool)


@superadmin_required
@require_POST
def game_fix(request, game_id):
    game = get_object_or_404(GamesAndScores, pk=game_id)

    status = request.POST.get('status', '').strip()
    if status not in VALID_GAME_STATUSES:
        messages.error(
            request,
            f'Status must be one of: {", ".join(VALID_GAME_STATUSES)}.',
        )
        return redirect('superadmin:overview')

    try:
        home_score = int(request.POST.get('home_score'))
        away_score = int(request.POST.get('away_score'))
    except (TypeError, ValueError):
        messages.error(request, 'Home and away scores must be integers.')
        return redirect('superadmin:overview')

    services.fix_stuck_game(request, game, status, home_score, away_score)
    messages.success(request, f'Fixed game {game.slug}.')
    return redirect('superadmin:overview')
