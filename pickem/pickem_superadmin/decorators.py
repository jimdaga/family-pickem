"""The single access gate for the superadmin console.

Every view in this app carries @superadmin_required. There is no ungated view.

Non-superusers get 404 rather than 403 so the console does not confirm its own
existence to a probing account. Anonymous users never reach here at all —
RequireLoginForInternalPagesMiddleware redirects them to login first, which is
what every other internal path does, so it discloses nothing.
"""
from functools import wraps

from django.http import Http404


def superadmin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            raise Http404
        return view_func(request, *args, **kwargs)

    return _wrapped
