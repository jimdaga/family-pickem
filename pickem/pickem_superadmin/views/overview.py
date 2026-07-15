from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from pickem_api.models import (
    Family, GamePicks, GamesAndScores, Pool, currentSeason,
)
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

    pools_off_season = list(Pool.objects.exclude(season=season)) if season else []

    return {
        'pools_without_settings': pools_without_settings,
        'stuck_games': stuck_games,
        'families_without_members': families_without_members,
        'pools_off_season': pools_off_season,
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
        'current_season': current,
        'site_banners': SiteBanner.objects.filter(family__isnull=True, is_active=True),
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
    current = currentSeason.objects.first()
    if current is None:
        current = currentSeason.objects.create()

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

    before = {'season': current.season, 'display_name': current.display_name}
    current.season = new_season
    current.display_name = request.POST.get('display_name', '').strip()
    after = {'season': current.season, 'display_name': current.display_name}

    changes = diff_fields(before, after)
    if not changes:
        messages.success(request, 'No changes.')
        return redirect('superadmin:overview')

    current.save()
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

    banner = SiteBanner.objects.create(
        title=title,
        description=request.POST.get('description', '').strip(),
        banner_type=request.POST.get('banner_type', 'info'),
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
        action=SuperAdminAuditLog.Action.BANNER_PUBLISHED,
        target=banner,
        summary=f'Deactivated banner: {banner.title}',
        changes={'is_active': [True, False]},
    )
    messages.success(request, 'Banner deactivated.')
    return redirect('superadmin:overview')
