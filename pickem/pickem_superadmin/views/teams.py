from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import Teams
from pickem_superadmin.audit import log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import TeamRowForm
from pickem_superadmin.matrix import save_matrix
from pickem_superadmin.models import SuperAdminAuditLog

TRACKED_FIELDS = tuple(TeamRowForm.Meta.fields)


@superadmin_required
def teams(request):
    rows = [
        {'team': team, 'form': TeamRowForm(instance=team, prefix=str(team.id))}
        for team in Teams.objects.all().order_by('id')
    ]
    return render(request, 'superadmin/teams.html', {'rows': rows})


@superadmin_required
@require_POST
def teams_save(request):
    # Team edits are a global superadmin action — no FamilyAuditLog dual-write
    # here (teams aren't scoped to a family).
    def on_save(team, changes):
        log_action(
            request,
            action=SuperAdminAuditLog.Action.TEAM_UPDATED,
            target=team,
            summary=f'Updated team {team.id}',
            changes=changes,
        )

    # Teams has no updated_at column, so optimistic-concurrency staleness
    # checking is impossible and must be disabled here.
    saved, failed, _ = save_matrix(
        request,
        objects=Teams.objects.all().order_by('id'),
        form_class=TeamRowForm,
        tracked_fields=TRACKED_FIELDS,
        key_field='logo_contrast_preset',
        on_save=on_save,
        stale_check=False,
    )

    if saved:
        messages.success(request, f'Saved {saved} team(s).')
    if failed:
        labels = [str(t.id) for t in failed]
        messages.error(request, f'Invalid values could not be saved: {", ".join(labels)}.')
    if not saved and not failed:
        messages.success(request, 'No changes.')

    return redirect('superadmin:teams')
