"""The only write path for superadmin audit rows.

Views never touch SuperAdminAuditLog.objects.create() directly. Routing every
write through log_action() is what makes "no unaudited write" enforceable rather
than aspirational.
"""
import ipaddress

from pickem_api.models import FamilyAuditLog
from pickem_superadmin.models import SuperAdminAuditLog


def diff_fields(before, after):
    """{field: [before, after]} for changed fields only.

    Iterates the union of both dicts' keys so a key missing from either side
    (e.g. a delete-style call like diff_fields(snapshot, {})) is still
    recorded as [value, None] / [None, value] instead of silently dropped.
    """
    changed = {}
    for key in before.keys() | after.keys():
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            changed[key] = [before_value, after_value]
    return changed


def _valid_ip(value):
    if not value:
        return None
    try:
        ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    return value.strip()


def _client_ip(request):
    """Best-effort client IP for the audit row.

    NOTE: this value is ADVISORY, not evidence. X-Forwarded-For is entirely
    client-controlled and this app has no trusted-proxy configuration, so a
    caller can put anything in that header. The authoritative record of "who
    did this" is the `actor` FK (an authenticated superuser), not the IP.
    This is a deliberate, accepted limitation — do not build trusted-proxy
    handling to "fix" it.

    Both candidates are validated with `ipaddress.ip_address` before use
    because `GenericIPAddressField` is backed by Postgres `inet` in
    production, and `.objects.create()` does not run field validators —
    a malformed value (e.g. a proxy sending "unknown") would otherwise raise
    django.db.utils.DataError and 500 the only audit write path.
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        leftmost = forwarded.split(',')[0].strip()
        valid = _valid_ip(leftmost)
        if valid is not None:
            return valid
    return _valid_ip(request.META.get('REMOTE_ADDR'))


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
