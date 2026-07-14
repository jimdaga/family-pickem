"""The only write path for superadmin audit rows.

Views never touch SuperAdminAuditLog.objects.create() directly. Routing every
write through log_action() is what makes "no unaudited write" enforceable rather
than aspirational.
"""
from pickem_api.models import FamilyAuditLog
from pickem_superadmin.models import SuperAdminAuditLog


def diff_fields(before, after):
    """{field: [before, after]} for changed fields only."""
    return {
        key: [before[key], after[key]]
        for key in after
        if before.get(key) != after[key]
    }


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def log_action(
    request, *, action, target, summary, changes=None,
    family=None, pool=None, family_action=None,
):
    """Record a superadmin action.

    When `family` is given, also write a FamilyAuditLog row so the family's own
    history has no gap where a superadmin acted on it. `family_action` must then
    be a FamilyAuditLog.Action value.
    """
    changes = changes or {}
    actor = request.user if request.user.is_authenticated else None

    entry = SuperAdminAuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target.__class__.__name__ if target is not None else '',
        target_id=str(target.pk) if target is not None else '',
        summary=summary,
        changes=changes,
        ip_address=_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )

    if family is not None:
        if family_action is None:
            raise ValueError('family_action is required when family is given')
        FamilyAuditLog.objects.create(
            family=family,
            pool=pool,
            actor=actor,
            action=family_action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            metadata={'source': 'superadmin', 'summary': summary, 'changes': changes},
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
        )

    return entry
