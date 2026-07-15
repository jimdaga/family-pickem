from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import Family, FamilyAuditLog, Pool
from pickem_superadmin.audit import log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import PoolSettingsRowForm
from pickem_superadmin.matrix import save_matrix
from pickem_superadmin.models import SuperAdminAuditLog

TRACKED_FIELDS = tuple(PoolSettingsRowForm.Meta.fields)

# The matrix save only writes rows present in the POST, so paginating the
# display is safe: saving on page 2 touches only page-2 rows.
POOLS_PER_PAGE = 40


def _pool_queryset(request):
    pools = (
        Pool.objects.select_related('family', 'settings').order_by('family__name', 'name')
    )
    family_slug = request.GET.get('family', '').strip()
    season = request.GET.get('season', '').strip()
    if family_slug:
        pools = pools.filter(family__slug=family_slug)
    if season:
        pools = pools.filter(season=season)
    return pools


@superadmin_required
def pools(request):
    page_obj = Paginator(_pool_queryset(request), POOLS_PER_PAGE).get_page(
        request.GET.get('page')
    )

    rows = []
    for pool in page_obj:
        settings_obj = getattr(pool, 'settings', None)
        rows.append({
            'pool': pool,
            'settings': settings_obj,
            # A pool with no settings row cannot be edited here; Overview links to
            # the backfill repair action instead of silently rendering blanks.
            # Prefixed by the *settings* pk (not the pool pk) — that's the model
            # save_matrix actually binds the form to, and pools_save keys its
            # rows the same way, so the two must agree.
            'form': (
                PoolSettingsRowForm(instance=settings_obj, prefix=str(settings_obj.pk))
                if settings_obj else None
            ),
        })

    return render(request, 'superadmin/pools.html', {
        'rows': rows,
        'page_obj': page_obj,
        'families': Family.objects.order_by('name').values_list('slug', 'name'),
        'seasons': Pool.objects.order_by('-season').values_list('season', flat=True).distinct(),
        'family_filter': request.GET.get('family', ''),
        'season_filter': request.GET.get('season', ''),
    })


@superadmin_required
@require_POST
def pools_save(request):
    pool_qs = Pool.objects.select_related('family', 'settings')
    settings_objects = [
        pool.settings for pool in pool_qs if getattr(pool, 'settings', None) is not None
    ]

    def on_save(settings_obj, changes):
        pool = settings_obj.pool
        log_action(
            request,
            action=SuperAdminAuditLog.Action.POOL_SETTINGS_UPDATED,
            target=pool,
            summary=f'Updated settings for {pool.family.slug}/{pool.slug}',
            changes=changes,
            family=pool.family,
            pool=pool,
            family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
        )

    saved, failed, stale = save_matrix(
        request,
        objects=settings_objects,
        form_class=PoolSettingsRowForm,
        tracked_fields=TRACKED_FIELDS,
        key_field='win_points',
        on_save=on_save,
    )

    if saved:
        messages.success(request, f'Saved {saved} pool(s).')
    if stale:
        labels = [f'{s.pool.family.slug}/{s.pool.slug}' for s in stale]
        messages.error(
            request,
            f'Not saved — changed since you loaded it: {", ".join(labels)}. Reload and retry.',
        )
    if failed:
        labels = [f'{f.pool.family.slug}/{f.pool.slug}' for f in failed]
        messages.error(request, f'Invalid values could not be saved: {", ".join(labels)}.')
    if not saved and not stale and not failed:
        messages.success(request, 'No changes.')

    return redirect('superadmin:pools')
