from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from datetime import timedelta

from pickem_api.models import (
    Family, FamilyMembership, GamePicks, GamesAndScores, GameWeeks, Pool,
    currentSeason,
)
from pickem_homepage.forms import BANNER_ICON_CHOICES
from pickem_homepage.models import SiteBanner
from pickem_superadmin import jobs, services
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminAuditLog

# A game still statusType='inprogress' this long after kickoff is stuck —
# ESPN sometimes never posts a final status. statusType is the NORMALIZED
# value update_games.py writes (see STATUS_MAP), not a raw ESPN code, and the
# kickoff time lives in startTimestamp (there is no gameTime/gameStatus field).
STUCK_GAME_AFTER = timezone.timedelta(hours=6)


def _anomalies(season):
    """Cheap checks that each point at something actionable. If a check cannot be
    made cheap, it does not belong on the landing page."""
    pools_without_settings = list(Pool.objects.filter(settings__isnull=True))

    stuck_games = list(
        GamesAndScores.objects.filter(
            statusType='inprogress',
            startTimestamp__lt=timezone.now() - STUCK_GAME_AFTER,
        )[:20]
    )

    families_without_members = list(
        Family.objects.annotate(
            active_members=Count('memberships', filter=Q(memberships__status='active')),
        ).filter(active_members=0)
    )

    # "Stale current pools": a family whose most-recent pool never rolled forward
    # to the current season. Historical pools are expected and never flagged —
    # only the newest pool per family, and only if it is behind the current season.
    families_off_season = []
    if season:
        latest_by_family = {}
        for pool in Pool.objects.select_related('family').order_by('family_id', '-season', '-id'):
            latest_by_family.setdefault(pool.family_id, pool)
        for pool in latest_by_family.values():
            if pool.season != season:
                families_off_season.append({'family': pool.family, 'latest_pool': pool})

    return {
        'pools_without_settings': pools_without_settings,
        'stuck_games': stuck_games,
        'families_without_members': families_without_members,
        'families_off_season': families_off_season,
    }


#: A pool younger than this has simply not started yet, not been abandoned.
#: Grounded in live data: at 14 days this flags the three genuinely dead pools
#: and none of the several created within the last week.
ABANDONED_AFTER_DAYS = 14

#: Window for the "new pools" feed.
NEW_POOL_WINDOW_DAYS = 30


def _pool_health(season):
    """Abandoned pools, pools that went quiet, and recent signups.

    Two tiers rather than one, because a single recency threshold cannot tell
    them apart. Players PRE-PICK: pools have submitted a whole week days in
    advance and then legitimately gone silent, so "no picks in N days" flags
    healthy pools. Instead:

    * abandoned - never received a single pick, and old enough that this is not
      just a pool that has yet to get going;
    * went quiet - has picks in its history, but nothing for the CURRENT week
      once that week has actually kicked off.
    """
    now = timezone.now()
    cutoff = now - timedelta(days=ABANDONED_AFTER_DAYS)

    pools = (
        Pool.objects.filter(status=Pool.Status.ACTIVE)
        .select_related('family')
        .annotate(pick_count=Count('game_picks', distinct=True))
    )

    abandoned = [
        {
            'pool': pool,
            'age_days': (now - pool.created_at).days,
            'members': FamilyMembership.objects.filter(
                family=pool.family, status=FamilyMembership.Status.ACTIVE
            ).count(),
        }
        for pool in pools
        if pool.pick_count == 0 and pool.created_at <= cutoff
    ]
    abandoned.sort(key=lambda row: row['age_days'], reverse=True)

    # "Went quiet" needs a week that has actually started; before kickoff a
    # pool with no picks for it is early, not quiet.
    quiet = []
    current_week = None
    if season:
        today = timezone.localdate()
        week_row = (
            GameWeeks.objects.filter(season=season, date__lte=today)
            .order_by('-date').first()
        )
        current_week = str(week_row.weekNumber) if week_row else None
    if current_week:
        week_started = GamesAndScores.objects.filter(
            gameseason=season,
            gameWeek=current_week,
            startTimestamp__lte=now,
        ).exists()
        if week_started:
            for pool in pools.filter(season=season):
                if not pool.pick_count:
                    continue  # already counted as abandoned, or simply new
                has_current = GamePicks.objects.filter(
                    pool=pool, gameseason=season, gameWeek=current_week
                ).exists()
                if not has_current:
                    quiet.append({'pool': pool, 'picks': pool.pick_count})

    new_cutoff = now - timedelta(days=NEW_POOL_WINDOW_DAYS)
    new_pools = [
        {
            'pool': pool,
            'age_days': (now - pool.created_at).days,
            'members': FamilyMembership.objects.filter(
                family=pool.family, status=FamilyMembership.Status.ACTIVE
            ).count(),
            'picks': pool.pick_count,
        }
        for pool in pools.filter(created_at__gte=new_cutoff).order_by('-created_at')
    ]

    return {
        'abandoned': abandoned,
        'quiet': quiet,
        'new_pools': new_pools,
        'abandoned_after_days': ABANDONED_AFTER_DAYS,
        'new_window_days': NEW_POOL_WINDOW_DAYS,
        'current_week': current_week,
    }


@superadmin_required
def overview(request):
    current = currentSeason.objects.first()
    season = current.season if current else None

    counts = {
        'families': Family.objects.count(),
        'families_inactive': Family.objects.filter(status=Family.Status.INACTIVE).count(),
        'pools': Pool.objects.count(),
        'users': User.objects.count(),
        'users_blocked': User.objects.filter(is_active=False).count(),
        'picks_this_season': (
            GamePicks.objects.filter(gameseason=season).count() if season else 0
        ),
    }

    return render(request, 'superadmin/overview.html', {
        'counts': counts,
        'health': jobs.scheduler_health(),
        'anomalies': _anomalies(season),
        'pool_health': _pool_health(season),
        'current_season': current,
        'site_banners': SiteBanner.objects.filter(family__isnull=True, is_active=True),
        'banner_icon_choices': BANNER_ICON_CHOICES,
    })


@superadmin_required
@require_POST
def pool_settings_backfill(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    services.backfill_pool_settings(request, pool)
    messages.success(request, f'Backfilled settings for {pool.family.slug}/{pool.slug}.')
    return redirect('superadmin:overview')


@superadmin_required
@require_POST
def season_update(request):
    """get_season() reads this and it drives the whole app — picks, standings,
    scores, stats. Highest blast radius in the console, so it takes a typed
    confirmation."""
    # Read-only lookup for validation/`before` capture — do NOT create a row
    # here. A rejected request (bad int, or wrong confirm) must write nothing,
    # same as every other action in this console.
    existing = currentSeason.objects.first()

    try:
        new_season = int(request.POST.get('season', ''))
    except ValueError:
        messages.error(request, 'Season must be an integer in YYZZ format (e.g. 2627).')
        return redirect('superadmin:overview')

    if request.POST.get('confirm', '').strip() != str(new_season):
        messages.error(
            request,
            f'Confirmation did not match. Type "{new_season}" exactly to change the season.',
        )
        return redirect('superadmin:overview')

    before = {
        'season': existing.season if existing else None,
        'display_name': existing.display_name if existing else None,
    }

    display_name = request.POST.get('display_name', '').strip()
    after = {'season': new_season, 'display_name': display_name}

    changes = diff_fields(before, after)
    if not changes:
        messages.success(request, 'No changes.')
        return redirect('superadmin:overview')

    # currentSeason is a singleton but has no DB-level uniqueness constraint, so
    # do the create/update under a row lock and collapse any stray duplicates in
    # the same transaction. That serializes concurrent updates and keeps
    # get_season()'s `.first()` reads deterministic.
    with transaction.atomic():
        current = currentSeason.objects.select_for_update().order_by('id').first()
        if current is None:
            current = currentSeason.objects.create()
        current.season = new_season
        current.display_name = display_name
        current.save()
        currentSeason.objects.exclude(pk=current.pk).delete()
    log_action(
        request,
        action=SuperAdminAuditLog.Action.SEASON_UPDATED,
        target=current,
        summary=f'Current season set to {new_season}',
        changes=changes,
    )
    messages.success(request, f'Current season is now {new_season}.')
    return redirect('superadmin:overview')


@superadmin_required
@require_POST
def banner_publish(request):
    """Publish a site-wide banner. SiteBanner.family is nullable, and null is
    precisely what makes it site-wide rather than one family's."""
    title = request.POST.get('title', '').strip()
    if not title:
        messages.error(request, 'A banner needs a title.')
        return redirect('superadmin:overview')

    valid_icons = {value for value, _label in BANNER_ICON_CHOICES}
    icon = request.POST.get('icon', '').strip()
    if icon not in valid_icons:
        icon = 'fas fa-bullhorn'

    valid_banner_types = {value for value, _label in SiteBanner.BANNER_TYPES}
    banner_type = request.POST.get('banner_type', 'info').strip()
    if banner_type not in valid_banner_types:
        banner_type = 'info'

    banner = SiteBanner.objects.create(
        title=title,
        description=request.POST.get('description', '').strip(),
        banner_type=banner_type,
        icon=icon,
        family=None,
        is_active=True,
    )
    log_action(
        request,
        action=SuperAdminAuditLog.Action.BANNER_PUBLISHED,
        target=banner,
        summary=f'Published site-wide banner: {title}',
        changes={'title': [None, title], 'is_active': [None, True]},
    )
    messages.success(request, 'Banner published site-wide.')
    return redirect('superadmin:overview')


@superadmin_required
@require_POST
def banner_deactivate(request, banner_id):
    banner = get_object_or_404(SiteBanner, pk=banner_id)
    banner.is_active = False
    banner.save(update_fields=['is_active', 'updated_at'])

    log_action(
        request,
        action=SuperAdminAuditLog.Action.BANNER_DEACTIVATED,
        target=banner,
        summary=f'Deactivated banner: {banner.title}',
        changes={'is_active': [True, False]},
    )
    messages.success(request, 'Banner deactivated.')
    return redirect('superadmin:overview')
