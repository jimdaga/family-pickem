from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import Family, FamilyMembership
from pickem_superadmin import services
from pickem_superadmin.audit import log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import FamilyRowForm
from pickem_superadmin.matrix import save_matrix
from pickem_superadmin.models import SuperAdminAuditLog

TRACKED_FIELDS = tuple(FamilyRowForm.Meta.fields)


@superadmin_required
def families(request):
    family_qs = Family.objects.annotate(
        member_count=Count(
            'memberships',
            filter=Q(memberships__status=FamilyMembership.Status.ACTIVE),
            distinct=True,
        ),
        pool_count=Count('pools', distinct=True),
    ).order_by('name')

    rows = [
        {'family': family, 'form': FamilyRowForm(instance=family, prefix=str(family.id))}
        for family in family_qs
    ]
    return render(request, 'superadmin/families.html', {'rows': rows})


@superadmin_required
@require_POST
def families_save(request):
    # Family edits are a global superadmin action — no per-family FamilyAuditLog
    # dual-write here (unlike pools_save). A family editing its own name via this
    # console is the superadmin acting on it, not the family acting on itself, and
    # there's no FamilyAuditLog.Action for "our own record was edited" to dual-write.
    def on_save(family, changes):
        log_action(
            request,
            action=SuperAdminAuditLog.Action.FAMILY_UPDATED,
            target=family,
            summary=f'Updated family {family.slug}',
            changes=changes,
        )

    saved, failed, stale = save_matrix(
        request,
        objects=Family.objects.all(),
        form_class=FamilyRowForm,
        tracked_fields=TRACKED_FIELDS,
        key_field='slug',
        on_save=on_save,
    )

    if saved:
        messages.success(request, f'Saved {saved} family(ies).')
    if stale:
        labels = [f.slug for f in stale]
        messages.error(
            request,
            f'Not saved — changed since you loaded it: {", ".join(labels)}. Reload and retry.',
        )
    if failed:
        labels = [f.slug for f in failed]
        messages.error(request, f'Invalid values could not be saved: {", ".join(labels)}.')
    if not saved and not stale and not failed:
        messages.success(request, 'No changes.')

    return redirect('superadmin:families')


@superadmin_required
@require_POST
def family_force_delete(request, family_id):
    family = get_object_or_404(Family, id=family_id)
    confirm = (request.POST.get('confirm_slug') or '').strip()
    if confirm != family.slug:
        messages.error(request, f'Confirmation did not match. Type "{family.slug}" exactly to delete.')
        return redirect('superadmin:families')
    services.force_delete_family(request, family)
    messages.success(request, f'Family "{family.slug}" and all related data were deleted.')
    return redirect('superadmin:families')
