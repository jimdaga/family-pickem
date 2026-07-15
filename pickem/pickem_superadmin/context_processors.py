"""Context available to every superadmin console page.

Scoped by path so the scheduler-health query (one indexed row lookup) only
runs for `/superadmin/` requests, not site-wide. The health readout is the
console's signature element — a live instrument reading present in the chrome
on every page, since a dead pipeline is otherwise invisible until scores go
stale.
"""


def _environment_label():
    """A short badge for the chrome so an operator can't mistake prod for dev on
    a console that performs destructive, audited writes. Prefer an explicit
    APP_ENVIRONMENT if set; otherwise derive from DEBUG."""
    import os

    from django.conf import settings

    explicit = os.environ.get('APP_ENVIRONMENT', '').strip()
    if explicit:
        return explicit
    return 'dev' if settings.DEBUG else 'prod'


def chrome(request):
    if not request.path.startswith('/superadmin/'):
        return {}

    # Imported lazily so this processor stays cheap for non-superadmin requests
    # and avoids import cost at startup.
    from pickem_superadmin import jobs

    try:
        health = jobs.scheduler_health()
    except Exception:
        # The chrome must never take down a page it decorates. A health probe
        # that errors reads as "unknown", not a 500.
        health = {'alive': False, 'last_run': None, 'last_status': None, 'stale': True}

    return {'sa_health': health, 'sa_environment': _environment_label()}
