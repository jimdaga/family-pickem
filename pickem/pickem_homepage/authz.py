from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponseForbidden

from pickem_api.authz import (
    AuthenticationRequired,
    PermissionDeniedForTenant,
    TenantNotFound,
    require_tenant_context,
)
from pickem_api.models import FamilyMembership


def family_member_required(view_func=None, *, minimum_role=FamilyMembership.Role.MEMBER):
    def decorator(func):
        @wraps(func)
        def wrapped(request, family_slug, pool_slug=None, *args, **kwargs):
            try:
                request.tenant_context = require_tenant_context(
                    request.user,
                    family=family_slug,
                    pool=pool_slug,
                    minimum_role=minimum_role,
                )
            except AuthenticationRequired:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
            except TenantNotFound:
                raise Http404()
            except PermissionDeniedForTenant:
                return HttpResponseForbidden('Permission denied.')

            return func(request, family_slug, pool_slug, *args, **kwargs)

        return wrapped

    if view_func is not None:
        return decorator(view_func)
    return decorator
