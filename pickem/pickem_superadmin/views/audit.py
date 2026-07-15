from django.core.paginator import Paginator
from django.shortcuts import render

from pickem_api.models import FamilyAuditLog
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminAuditLog


@superadmin_required
def audit(request):
    entries = SuperAdminAuditLog.objects.select_related('actor')

    action = request.GET.get('action', '').strip()
    actor = request.GET.get('actor', '').strip()
    if action:
        entries = entries.filter(action=action)
    if actor:
        entries = entries.filter(actor__username__icontains=actor)

    # Every family's own audit log in one stream — today this is readable only
    # one family at a time.
    family_entries = Paginator(
        FamilyAuditLog.objects.select_related('family', 'pool', 'actor')
        .order_by('-created_at'),
        25,
    ).get_page(request.GET.get('family_page'))

    return render(request, 'superadmin/audit.html', {
        'entries': Paginator(entries, 50).get_page(request.GET.get('page')),
        'family_entries': family_entries,
        'actions': SuperAdminAuditLog.Action.choices,
        'action_filter': action,
        'actor_filter': actor,
    })
