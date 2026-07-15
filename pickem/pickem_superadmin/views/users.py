from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import UserProfile
from pickem_superadmin import services
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminAuditLog

# Profile fields this console may edit. is_superuser is deliberately absent:
# granting superuser from a web form is a privilege-escalation surface.
EDITABLE_PROFILE_FIELDS = (
    'is_commissioner', 'favorite_team', 'tagline',
    'private_profile', 'email_notifications',
)
BOOLEAN_PROFILE_FIELDS = ('is_commissioner', 'private_profile', 'email_notifications')


@superadmin_required
def users(request):
    user_qs = (
        User.objects.select_related('profile')
        .annotate(family_count=Count('family_memberships', distinct=True))
        .order_by('username')
    )
    query = request.GET.get('q', '').strip()
    if query:
        user_qs = user_qs.filter(username__icontains=query)

    return render(request, 'superadmin/users.html', {
        'users': user_qs,
        'query': query,
    })


@superadmin_required
@require_POST
def user_block(request, user_id):
    target = get_object_or_404(User, pk=user_id)

    # Typed confirmation: the operator must type the username. Arming a
    # destructive action should take deliberate effort, not one stray click.
    if request.POST.get('confirm', '').strip() != target.username:
        messages.error(
            request,
            f'Confirmation did not match. Type "{target.username}" exactly to block.',
        )
        return redirect('superadmin:users')

    try:
        services.block_user(request, target, reason=request.POST.get('reason', ''))
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('superadmin:users')

    messages.success(request, f'Blocked {target.username}.')
    return redirect('superadmin:users')


@superadmin_required
@require_POST
def user_unblock(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    services.unblock_user(request, target)
    messages.success(request, f'Unblocked {target.username}.')
    return redirect('superadmin:users')


@superadmin_required
@require_POST
def user_update(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target)

    before = {field: getattr(profile, field) for field in EDITABLE_PROFILE_FIELDS}
    for field in EDITABLE_PROFILE_FIELDS:
        if field in BOOLEAN_PROFILE_FIELDS:
            setattr(profile, field, request.POST.get(field) == 'on')
        else:
            setattr(profile, field, request.POST.get(field, '').strip())
    after = {field: getattr(profile, field) for field in EDITABLE_PROFILE_FIELDS}

    changes = diff_fields(before, after)
    if not changes:
        messages.success(request, f'No changes for {target.username}.')
        return redirect('superadmin:users')

    profile.save(update_fields=[*EDITABLE_PROFILE_FIELDS, 'updated_at'])
    log_action(
        request,
        action=SuperAdminAuditLog.Action.USER_PROFILE_UPDATED,
        target=target,
        summary=f'Updated profile for {target.username}',
        changes=changes,
    )
    messages.success(request, f'Updated {target.username}.')
    return redirect('superadmin:users')
