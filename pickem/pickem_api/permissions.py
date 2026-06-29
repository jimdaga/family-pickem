from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework import status

from pickem_api.authz import (
    AuthenticationRequired,
    PermissionDeniedForTenant,
    TenantNotFound,
)


class IsAdminOrReadOnly(BasePermission):
    """GET/HEAD/OPTIONS open to anyone; POST/PUT/PATCH/DELETE require is_staff."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


def tenant_authz_error_response(error):
    if isinstance(error, AuthenticationRequired):
        return Response(
            {'detail': 'Authentication required.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if isinstance(error, PermissionDeniedForTenant):
        return Response(
            {'detail': 'Permission denied.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(error, TenantNotFound):
        return Response(
            {'detail': 'Not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    raise error
