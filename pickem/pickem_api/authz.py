from dataclasses import dataclass
from typing import Optional, Union

from django.contrib.auth.models import AnonymousUser

from pickem_api.models import Family, FamilyMembership, Pool


LEGACY_FAMILY_SLUG = 'legacy-family-league'

ROLE_ORDER = {
    FamilyMembership.Role.MEMBER: 10,
    FamilyMembership.Role.ADMIN: 20,
    FamilyMembership.Role.OWNER: 30,
}


class TenantAuthorizationError(Exception):
    """Base class for tenant authorization denials."""


class AuthenticationRequired(TenantAuthorizationError):
    """The caller must authenticate before tenant access can be evaluated."""


class TenantNotFound(TenantAuthorizationError):
    """The requested tenant object should be treated as not found."""


class PermissionDeniedForTenant(TenantAuthorizationError):
    """The user belongs to the tenant but lacks the required role."""


@dataclass(frozen=True)
class TenantContext:
    family: Family
    pool: Optional[Pool]
    membership: FamilyMembership


FamilyRef = Union[Family, int, str]
PoolRef = Union[Pool, int, str]


def role_allows(actual_role, minimum_role):
    try:
        return ROLE_ORDER[actual_role] >= ROLE_ORDER[minimum_role]
    except KeyError:
        return False


def _require_authenticated(user):
    if (
        user is None
        or isinstance(user, AnonymousUser)
        or not getattr(user, 'is_authenticated', False)
    ):
        raise AuthenticationRequired()


def resolve_family(family: FamilyRef) -> Family:
    if isinstance(family, Family):
        return family

    queryset = Family.objects.filter(status=Family.Status.ACTIVE)
    if isinstance(family, int):
        resolved = queryset.filter(pk=family).first()
    else:
        resolved = queryset.filter(slug=family).first()

    if not resolved:
        raise TenantNotFound()
    return resolved


def resolve_pool_context(
    *,
    pool: Optional[PoolRef],
    family: Optional[FamilyRef],
    allow_legacy_default=False,
) -> Pool:
    if pool is None:
        if allow_legacy_default:
            return get_legacy_default_pool()
        raise TenantNotFound()

    resolved_family = resolve_family(family) if family is not None else None

    if isinstance(pool, Pool):
        resolved_pool = pool
    else:
        queryset = Pool.objects.filter(status=Pool.Status.ACTIVE)
        if resolved_family is not None:
            queryset = queryset.filter(family=resolved_family)

        if isinstance(pool, int):
            resolved_pool = queryset.filter(pk=pool).first()
        else:
            # Pool.slug is only unique within a family, so a slug lookup without
            # a family scope could resolve an arbitrary pool from another tenant.
            if resolved_family is None:
                raise TenantNotFound()
            resolved_pool = queryset.filter(slug=pool).first()

    if not resolved_pool or resolved_pool.status != Pool.Status.ACTIVE:
        raise TenantNotFound()

    if resolved_family is not None and resolved_pool.family_id != resolved_family.id:
        raise TenantNotFound()

    return resolved_pool


def get_legacy_default_pool() -> Pool:
    family = Family.objects.filter(
        slug=LEGACY_FAMILY_SLUG,
        status=Family.Status.ACTIVE,
    ).first()
    if not family:
        raise TenantNotFound()

    pool = (
        Pool.objects.filter(family=family, status=Pool.Status.ACTIVE, is_default=True)
        .order_by('-season', 'slug')
        .first()
    )
    if pool:
        return pool

    pool = (
        Pool.objects.filter(family=family, status=Pool.Status.ACTIVE)
        .order_by('-season', 'slug')
        .first()
    )
    if not pool:
        raise TenantNotFound()
    return pool


def require_family_membership(
    user,
    family: FamilyRef,
    *,
    minimum_role=FamilyMembership.Role.MEMBER,
) -> FamilyMembership:
    _require_authenticated(user)
    resolved_family = resolve_family(family)
    membership = FamilyMembership.objects.filter(
        family=resolved_family,
        user=user,
        status=FamilyMembership.Status.ACTIVE,
    ).first()
    if not membership:
        raise TenantNotFound()
    if not role_allows(membership.role, minimum_role):
        raise PermissionDeniedForTenant()
    return membership


def require_pool_membership(
    user,
    *,
    pool: PoolRef,
    family: Optional[FamilyRef] = None,
    minimum_role=FamilyMembership.Role.MEMBER,
) -> FamilyMembership:
    resolved_pool = resolve_pool_context(
        pool=pool,
        family=family,
        allow_legacy_default=False,
    )
    return require_family_membership(
        user,
        resolved_pool.family,
        minimum_role=minimum_role,
    )


def require_tenant_context(
    user,
    *,
    family: FamilyRef,
    pool: Optional[PoolRef] = None,
    minimum_role=FamilyMembership.Role.MEMBER,
) -> TenantContext:
    resolved_family = resolve_family(family)
    resolved_pool = None
    if pool is not None:
        resolved_pool = resolve_pool_context(pool=pool, family=resolved_family)
    membership = require_family_membership(
        user,
        resolved_family,
        minimum_role=minimum_role,
    )
    return TenantContext(
        family=resolved_family,
        pool=resolved_pool,
        membership=membership,
    )


def get_user_family_memberships(user):
    _require_authenticated(user)
    return FamilyMembership.objects.filter(
        user=user,
        status=FamilyMembership.Status.ACTIVE,
        family__status=Family.Status.ACTIVE,
    ).select_related('family').order_by('family__name', 'family__slug')
