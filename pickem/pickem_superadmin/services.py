"""Repair and moderation actions.

Plain functions, no HTTP awareness beyond taking `request` for the audit trail.
That keeps them unit-testable and usable from a shell.
"""
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from pickem_api.models import UserProfile
from pickem_superadmin.audit import log_action
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
