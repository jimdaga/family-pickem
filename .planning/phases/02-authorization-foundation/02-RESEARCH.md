# Phase 02: authorization-foundation - Research

**Researched:** 2026-06-28  
**Domain:** Django tenant authorization helpers and scoped query foundations  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Guard behavior

- **D-01:** Tenant guard helpers should return or raise `404` for authenticated users who are not active members of the requested family/pool. This reduces family/pool existence leakage.
- **D-02:** Tenant guard helpers should return or raise `403` for active family members who lack the required role for an action.
- **D-03:** Anonymous browser/page requests should redirect to login.
- **D-04:** Anonymous API/helper denials should return an authentication error, not a redirect and not a fake object result. Planners may choose the exact DRF/Django exception type that best fits existing tests and call sites.

### Family and pool resolution

- **D-05:** Phase 2 helpers should prefer explicit tenant context: `family_slug`, `pool_slug`, family/pool model instances, or equivalent explicit arguments.
- **D-06:** Legacy default family/pool fallback is allowed only as a temporary bridge for existing global routes during the transition. New tenant-aware code must pass explicit family/pool context.
- **D-07:** If both family and pool are supplied, helpers must verify that the pool belongs to the supplied family.
- **D-08:** Pool access requires active membership in the pool's family. Mismatched family/pool pairs must be rejected even if the user belongs to one side.
- **D-09:** Do not introduce `PoolMembership` in Phase 2. Phase 1 intentionally uses family-level membership for v1 access.

### Role boundaries

- **D-10:** Tenant helpers should not grant a global bypass to `User.is_superuser`.
- **D-11:** Tenant helpers should not grant a global bypass to legacy `UserProfile.is_commissioner`.
- **D-12:** Even superusers and commissioners must have explicit active `FamilyMembership` for tenant-scoped family/pool helpers. Django admin may keep its separate global staff/superuser behavior; this decision applies to family/pool guard helpers.
- **D-13:** The role ladder is:
  - `member`: read/play access within the family/pool.
  - `admin`: non-destructive family operations such as invites, settings, and member management where ownership is not affected.
  - `owner`: destructive or ownership-sensitive operations such as ownership transfer, owner/admin removal, family/pool archive/delete, and equivalent high-risk actions.
- **D-14:** Phase 2 should expose role-check helpers for these boundaries, but detailed admin UI/action wiring belongs mostly to Phase 5.

### Runtime wiring scope

- **D-15:** Phase 2 should primarily build reusable helpers and tests.
- **D-16:** Broad migration of existing pages and APIs stays in Phase 4 and Phase 5.
- **D-17:** A minimal proof endpoint or proof integration is acceptable only if the planner finds a tiny, low-risk path. The default should be helper-level tests without user-facing route changes.
- **D-18:** Do not wrap high-risk existing picks, standings, commissioner, or message-board flows broadly in Phase 2 unless it is strictly necessary to prove helper behavior.

### the agent's Discretion

- Exact module placement for helper code, but prefer a small centralized module over adding more logic to the already-large `pickem_homepage.views`.
- Exact exception classes and decorator/function APIs, provided they preserve the locked 404/403/login/API split and are easy to test.
- Whether to include a tiny proof route or keep Phase 2 entirely helper/test focused.
- Exact names for helper functions and test classes, provided they are clear and reusable by later route migration phases.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- Tenant-aware URL migration for all pages and APIs belongs to Phase 4 and Phase 5.
- Onboarding, create/join family, invite acceptance, and family switching belong to Phase 3 and Phase 5.
- CSRF/rate-limit/settings hardening remains Phase 6 unless the planner identifies tiny helper-adjacent tests that do not expand scope.
- Cron/scoring pool-awareness remains Phase 6.
- `PoolMembership` remains deferred unless future requirements require family members who are not pool participants.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTHZ-01 | Every family/pool read path checks authenticated membership server-side. | Add central family/pool resolvers backed by active `FamilyMembership`. [VERIFIED: .planning/REQUIREMENTS.md; VERIFIED: pickem/pickem_api/models.py] |
| AUTHZ-02 | Every family/pool write path checks authenticated membership server-side. | Add write/action helpers now; defer broad route wiring. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md] |
| AUTHZ-03 | Owner/admin actions require least-privilege role checks. | Implement member/admin/owner role ladder from `FamilyMembership.role`. [VERIFIED: pickem/pickem_api/models.py] |
| AUTHZ-04 | Users outside a family cannot view or infer private tenant data. | Non-members and mismatched family/pool pairs should fail as 404/NotFound. [VERIFIED: SECURITY_THREAT_MODEL.md; VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md] |
| AUTHZ-05 | Client-provided identifiers are validated against server-resolved membership and allowed objects. | Query helpers must scope private rows by resolved `family`/`pool`. [VERIFIED: DISCOVERY.md; VERIFIED: codebase grep] |
| SEC-03 | Cross-family isolation has automated negative tests. | Add helper-level negative tests before Phase 4/5 route migration. [VERIFIED: TEST_PLAN.md] |
</phase_requirements>

## Summary

Phase 2 should be additive, helper-first, and test-heavy: create a centralized `pickem_api.authz` module for tenant context resolution, role guards, and scoped query helpers, then prove the locked denial behavior with focused tests. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md] Phase 1 already added `Family`, `Pool`, `FamilyMembership`, nullable `pool` fields on competition tables, and nullable `family` fields on homepage community rows, so no Phase 2 schema migration is expected. [VERIFIED: .planning/STATE.md; VERIFIED: pickem/pickem_api/models.py; VERIFIED: pickem/pickem_homepage/models.py]

Existing runtime paths remain global: homepage views query `GamePicks`, `userSeasonPoints`, profiles, banners, and message-board rows without tenant filters; API views expose global picks and standings-style data through broad querysets; commissioner checks use `User.is_superuser` or `UserProfile.is_commissioner`. [VERIFIED: pickem/pickem_homepage/views.py; VERIFIED: pickem/pickem_api/views.py] The safest Phase 2 plan is therefore helper-level tests plus optional test-only decorator/DRF adapter coverage, not production wiring into picks, standings, message-board, or commissioner flows. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]

**Primary recommendation:** Use `pickem_api.authz` as the shared backend-owned authorization surface; expose optional thin browser/DRF adapters, but keep existing product routes untouched unless a tiny no-data proof path is absolutely necessary. [VERIFIED: pickem/pickem_api/models.py; VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]

## Project Constraints (from AGENTS.md)

- The local server is assumed to run at `http://localhost:8000`; do not start it for this phase. [VERIFIED: AGENTS.md]
- Use `curl http://localhost:8000` for browser-output validation when page changes occur. [VERIFIED: AGENTS.md]
- Run Django commands from `pickem` with the virtualenv, e.g. `../venv/bin/python manage.py test`. [VERIFIED: AGENTS.md]
- Use Django ORM, not raw SQL, for application code. [VERIFIED: AGENTS.md]
- Current season should use `pickem.utils.get_season()` or configured model/API logic, not hardcoded values. [VERIFIED: AGENTS.md]
- Tailwind migration is active, but Phase 2 should not need CSS/template edits. [VERIFIED: AGENTS.md; VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Tenant resolution | API / Backend | Database / Storage | Resolution requires server-side `Family`, `Pool`, and active `FamilyMembership` lookups. [VERIFIED: pickem/pickem_api/models.py] |
| Role checks | API / Backend | Database / Storage | Roles are stored in `FamilyMembership.role`, and UI hiding is insufficient. [VERIFIED: pickem/pickem_api/models.py; VERIFIED: SECURITY_THREAT_MODEL.md] |
| Browser anonymous handling | Frontend Server / Django Views | API / Backend | Page requests should redirect anonymous users via Django auth behavior. [CITED: https://docs.djangoproject.com/en/4.0/topics/auth/default/] |
| API anonymous handling | API / Backend | — | API helpers should raise DRF authentication exceptions, not redirects. [CITED: https://www.django-rest-framework.org/api-guide/exceptions/] |
| Scoped query helpers | API / Backend | Database / Storage | Current views contain many direct ORM filters; helpers reduce missed tenant filters later. [VERIFIED: codebase grep] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 4.0.2 | Browser exceptions, login behavior, ORM, `TestCase`. | Project-pinned framework and native primitives match page 404/403/login requirements. [VERIFIED: local pip show; CITED: https://docs.djangoproject.com/en/4.0/topics/auth/default/] |
| Django REST Framework | 3.13.1 | API permissions and API exceptions. | Project-pinned API framework already used by `pickem_api.views`. [VERIFIED: local pip show; VERIFIED: pickem/pickem_api/views.py] |
| Django ORM | Django 4.0.2 built-in | Tenant lookups and queryset scoping. | Existing code uses ORM directly; no new repository layer is needed. [VERIFIED: codebase grep] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `login_required` | Django 4.0.2 | Redirect anonymous browser users. | Compose into browser tenant decorators. [CITED: https://docs.djangoproject.com/en/4.0/topics/auth/default/] |
| `Http404` / `get_object_or_404` | Django 4.0.2 | Hide inaccessible families/pools from authenticated non-members. | Use for page/helper 404 behavior. [CITED: https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/] |
| `PermissionDenied` | Django 4.0.2 / DRF 3.13.1 | Return 403 for active members with insufficient role. | Use only after active membership is known. [CITED: https://docs.djangoproject.com/en/4.0/ref/exceptions/; CITED: https://www.django-rest-framework.org/api-guide/exceptions/] |
| `NotAuthenticated`, `NotFound` | DRF 3.13.1 | API-specific anonymous/non-member errors. | Use in DRF adapter helpers. [CITED: https://www.django-rest-framework.org/api-guide/exceptions/] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pickem_api.authz` | `pickem_homepage/authz.py` | Homepage wrappers are useful later, but core tenant models live in `pickem_api`; shared code should not depend on the large homepage views module. [VERIFIED: pickem/pickem_api/models.py; VERIFIED: pickem/pickem_homepage/views.py] |
| Helper-only tests | Production proof endpoint | A proof endpoint may demonstrate integration, but likely touches deferred route migration; helper and decorator tests are lower risk. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md] |
| DRF permission class only | Resolver functions plus queryset helpers | Permission classes do not scope list querysets by themselves; list views need explicit filters. [CITED: https://www.django-rest-framework.org/api-guide/permissions/] |

**Installation:**

```bash
# No package installation recommended for Phase 2.
```

**Version verification:** `cd pickem && ../venv/bin/python -m pip show Django djangorestframework` verified Django 4.0.2 and DRF 3.13.1. [VERIFIED: local pip show]

## Package Legitimacy Audit

No external package installs are recommended. [VERIFIED: local pip show]

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| N/A | N/A | N/A | N/A | N/A | N/A | No install |

**Packages removed due to [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
Browser URL or API request
  -> authenticate request
     -> anonymous page: login redirect
     -> anonymous API: DRF NotAuthenticated
  -> resolve explicit family
     -> no active membership: 404 / DRF NotFound
  -> resolve pool inside family when needed
     -> mismatched pool/family: 404 / DRF NotFound
  -> enforce role ladder
     -> active member wrong role: 403 / DRF PermissionDenied
  -> return TenantContext
  -> apply family/pool scoped queryset helper
  -> view/API returns authorized tenant data only
```

### Recommended Project Structure

```text
pickem/
├── pickem_api/
│   ├── authz.py          # new shared tenant context, resolvers, role guards, query helpers
│   ├── permissions.py    # optional DRF adapters; keep existing IsAdminOrReadOnly
│   └── tests.py          # core helper and API exception tests
└── pickem_homepage/
    └── tests.py          # browser decorator tests only if a page wrapper is added
```

### Pattern 1: Explicit Tenant Context

**What:** Return a small context object containing `family`, optional `pool`, and `membership`. [VERIFIED: pickem/pickem_api/models.py]  
**When to use:** New tenant-aware routes and future Phase 4/5 migrations. [VERIFIED: FAMILY_MULTI_TENANCY_PLAN.md]

```python
# Source: Phase 02 context + existing Django models.
context = resolve_pool_context(
    user=request.user,
    family_slug=family_slug,
    pool_slug=pool_slug,
)
picks = for_pool(GamePicks.objects.filter(gameseason=season), context.pool)
```

### Pattern 2: Role Ladder Groups

**What:** Define role groups where `member` allows member/admin/owner, `admin` allows admin/owner, and `owner` allows owner only. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]

```python
# Source: Phase 02 D-13 role ladder.
ROLE_GROUPS = {
    "member": {"member", "admin", "owner"},
    "admin": {"admin", "owner"},
    "owner": {"owner"},
}
```

### Pattern 3: Separate Browser and API Adapters

**What:** Keep core lookup logic shared, but map failures to Django page exceptions or DRF API exceptions at the boundary. [CITED: https://docs.djangoproject.com/en/4.0/ref/exceptions/; CITED: https://www.django-rest-framework.org/api-guide/exceptions/]

```python
# Source: Django/DRF official exception patterns.
family = resolve_family_for_page(request.user, family_slug)
api_family = resolve_family_for_api(request, family_slug)
```

### Anti-Patterns to Avoid

- Reusing `commissioner_required` for tenant admin: it allows global superuser/commissioner bypass. [VERIFIED: pickem/pickem_homepage/views.py]
- Looking up `Pool` by slug without `family`: `Pool.slug` is unique only within a family. [VERIFIED: pickem/pickem_api/models.py]
- Treating inactive membership as access: `FamilyMembership.status` exists and must be filtered to active. [VERIFIED: pickem/pickem_api/models.py]
- Returning empty fake results for denied API access: Phase 2 requires explicit auth/permission errors. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]
- Wiring high-risk existing picks, standings, message-board, or commissioner routes in Phase 2. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Browser anonymous redirect | Repeated custom redirects | `login_required` or a wrapper preserving the same behavior | Native Django behavior is already standard. [CITED: https://docs.djangoproject.com/en/4.0/topics/auth/default/] |
| Page 404/403 | Custom response objects | `Http404` and `PermissionDenied` | Native exceptions preserve standard page semantics. [CITED: https://docs.djangoproject.com/en/4.0/ref/exceptions/] |
| API errors | Ad hoc JSON errors | DRF `NotAuthenticated`, `NotFound`, `PermissionDenied` | DRF normalizes API exception responses. [CITED: https://www.django-rest-framework.org/api-guide/exceptions/] |
| Tenant filtering | Inline filters in every view | `for_family()` and `for_pool()` helpers | Current direct filters are the main future leak risk. [VERIFIED: codebase grep] |

**Key insight:** Phase 2 should make the secure path reusable before Phase 4/5 route migration begins. [VERIFIED: .planning/ROADMAP.md]

## Runtime State Inventory

Phase 2 is not a rename/refactor/migration phase, but runtime auth behavior depends on Phase 1 data. [VERIFIED: .planning/STATE.md]

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Legacy family/pool/membership backfill exists from Phase 1. [VERIFIED: .planning/STATE.md] | No data migration; tests should create explicit fixtures. |
| Live service config | No helper behavior depends on external UI/service config. [VERIFIED: DISCOVERY.md] | None. |
| OS-registered state | Cron jobs exist, but cron/scoring hardening is deferred. [VERIFIED: AGENTS.md; VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md] | None. |
| Secrets/env vars | Test settings provide local secret/database behavior. [VERIFIED: pickem/pickem/test_settings.py] | None. |
| Build artifacts | No package/build artifact change required. [VERIFIED: local pip show] | None. |

## Common Pitfalls

### Pitfall 1: Global Commissioner Bypass
**What goes wrong:** A superuser or legacy commissioner accesses tenant operations without family membership. [VERIFIED: pickem/pickem_homepage/views.py]  
**How to avoid:** Tenant helpers must ignore `is_superuser` and `UserProfile.is_commissioner` and require active `FamilyMembership`. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]

### Pitfall 2: Pool/Family Mismatch
**What goes wrong:** A user supplies a valid family slug and a pool slug from another family. [VERIFIED: pickem/pickem_api/models.py]  
**How to avoid:** Resolve `Pool` with both `family` and `slug`; test mismatch denial. [VERIFIED: pickem/pickem_api/models.py]

### Pitfall 3: Permission Before Membership
**What goes wrong:** Non-members can infer existence if role checks return 403 before membership is resolved. [ASSUMED]  
**How to avoid:** Resolve active membership first; only active members can receive wrong-role 403. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]

### Pitfall 4: DRF Permissions Without Scoped Querysets
**What goes wrong:** A list endpoint can pass a permission check and still serialize rows from other families. [CITED: https://www.django-rest-framework.org/api-guide/permissions/]  
**How to avoid:** Pair API helpers with `for_family()` / `for_pool()` queryset helpers. [VERIFIED: codebase grep]

## Code Examples

### Core Resolver

```python
# Source: Phase 02 locked decisions and FamilyMembership model.
def resolve_family_context(user, *, family_slug, minimum_role="member"):
    if not user.is_authenticated:
        raise TenantAuthenticationRequired()
    family = get_object_or_404(Family, slug=family_slug, status=Family.Status.ACTIVE)
    membership = FamilyMembership.objects.filter(
        family=family,
        user=user,
        status=FamilyMembership.Status.ACTIVE,
    ).first()
    if membership is None:
        raise TenantNotFound()
    require_family_role(membership, minimum_role)
    return TenantContext(family=family, membership=membership)
```

### Pool Resolver

```python
# Source: Pool has family-scoped slug uniqueness.
def resolve_pool_context(user, *, family_slug, pool_slug, minimum_role="member"):
    context = resolve_family_context(
        user=user,
        family_slug=family_slug,
        minimum_role=minimum_role,
    )
    pool = get_object_or_404(
        Pool,
        family=context.family,
        slug=pool_slug,
        status=Pool.Status.ACTIVE,
    )
    return TenantContext(family=context.family, pool=pool, membership=context.membership)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global season/week/user filters. | Resolve family/pool before private filters. | Phase 2 foundation after Phase 1 schema. | Enables safe route-by-route migration. [VERIFIED: .planning/STATE.md] |
| Global `commissioner_required`. | Family role ladder from active `FamilyMembership`. | Locked in Phase 02 context. | Prevents tenant bypass. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md] |
| Read-open `IsAdminOrReadOnly` for many APIs. | Tenant-aware API helpers plus scoped querysets for private endpoints. | Phase 2/4. | Reduces BOLA risk. [VERIFIED: pickem/pickem_api/permissions.py; VERIFIED: SECURITY_THREAT_MODEL.md] |

**Deprecated/outdated:**
- `commissioner_required` is legacy-global authorization, not tenant authorization. [VERIFIED: pickem/pickem_homepage/views.py]
- `IsAdminOrReadOnly` is not tenant-safe for private family/pool data. [VERIFIED: pickem/pickem_api/permissions.py]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Running role checks before membership checks is a common source of existence leakage. | Common Pitfalls | Low; locked decisions define the required 404/403 split regardless. |

## Open Questions

1. **Proof route or helper-only tests?**  
   What we know: Phase 02 defaults to helper-level tests and permits a proof only if tiny and low-risk. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]  
   Recommendation: Helper-only plus optional test-only URLConf; avoid production proof routes.

2. **Legacy fallback now or later?**  
   What we know: Fallback is bridge-only and explicit context is preferred. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md]  
   Recommendation: Implement fallback only behind an explicit `allow_legacy_default=True` argument.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Django tests | ✓ | 3.10.6 | None. [VERIFIED: local command] |
| Django | Helpers/tests | ✓ | 4.0.2 | None. [VERIFIED: local pip show] |
| DRF | API adapters/tests | ✓ | 3.13.1 | None. [VERIFIED: local pip show] |
| Django test runner | Validation | ✓ | Django 4.0.2 | None. [VERIFIED: local command] |

**Missing dependencies with no fallback:** none  
**Missing dependencies with fallback:** Context7 CLI was absent; official docs and local package checks were used. [VERIFIED: local command; CITED: https://docs.djangoproject.com/en/4.0/; CITED: https://www.django-rest-framework.org/]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Django `TestCase` via Django 4.0.2 test runner. [VERIFIED: local command] |
| Config file | `pickem/pickem/test_settings.py`. [VERIFIED: pickem/pickem/test_settings.py] |
| Quick run command | `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings --verbosity=2` |
| Full suite command | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| AUTHZ-01 | Active member resolves own family/pool; non-member cannot. | unit | `cd pickem && ../venv/bin/python manage.py test pickem_api.tests.TenantAuthorizationHelperTests --settings=pickem.test_settings -v 2` | ❌ Wave 0 |
| AUTHZ-02 | Write/action helpers require active membership. | unit | same as above | ❌ Wave 0 |
| AUTHZ-03 | Member denied admin; admin denied owner; no global bypass. | unit | `cd pickem && ../venv/bin/python manage.py test pickem_api.tests.TenantRoleGuardTests --settings=pickem.test_settings -v 2` | ❌ Wave 0 |
| AUTHZ-04 | Non-member and mismatched family/pool receive 404/NotFound. | unit | same as above | ❌ Wave 0 |
| AUTHZ-05 | Query helpers filter by resolved family/pool. | unit | `cd pickem && ../venv/bin/python manage.py test pickem_api.tests.TenantScopedQueryHelperTests --settings=pickem.test_settings -v 2` | ❌ Wave 0 |
| SEC-03 | Negative isolation matrix covers non-member, inactive member, wrong role, mismatch. | unit | focused authz tests | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings --verbosity=2`
- **Per wave merge:** `cd pickem && ../venv/bin/python manage.py test pickem_api pickem_homepage --settings=pickem.test_settings --verbosity=2`
- **Phase gate:** `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`, `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings`, and full suite. [VERIFIED: .planning/STATE.md]

### Wave 0 Gaps

- [ ] `pickem/pickem_api/authz.py` - core helper module.
- [ ] `TenantAuthorizationHelperTests` - active/non-member/inactive/mismatch behavior.
- [ ] `TenantRoleGuardTests` - role ladder and no bypass behavior.
- [ ] `TenantScopedQueryHelperTests` - query helper filtering.
- [ ] Optional browser adapter tests only if a homepage wrapper is added.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Django sessions and DRF session/token authentication are configured. [VERIFIED: pickem/pickem/settings.py] |
| V3 Session Management | yes | Use Django auth for anonymous browser requests; do not rely solely on session-selected tenant. [CITED: https://docs.djangoproject.com/en/4.0/topics/auth/default/; VERIFIED: FAMILY_MULTI_TENANCY_PLAN.md] |
| V4 Access Control | yes | Active `FamilyMembership` plus role ladder. [VERIFIED: pickem/pickem_api/models.py] |
| V5 Input Validation | yes | Validate slugs/IDs against server-resolved tenant context. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| V6 Cryptography | no direct change | Invite-code hashing already exists; Phase 2 adds no cryptography. [VERIFIED: .planning/STATE.md] |

### Known Threat Patterns for Django Tenant Authorization

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Broken object-level authorization | Elevation of Privilege / Information Disclosure | Resolve objects through active membership and scoped queryset. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Existence leak | Information Disclosure | 404/NotFound for non-members and mismatches. [VERIFIED: .planning/phases/02-authorization-foundation/02-CONTEXT.md] |
| Global staff/commissioner bypass | Elevation of Privilege | Require explicit active `FamilyMembership`. [VERIFIED: pickem/pickem_homepage/views.py] |
| Inactive membership reuse | Elevation of Privilege | Filter `FamilyMembership.status='active'`. [VERIFIED: pickem/pickem_api/models.py] |
| List endpoint leakage | Information Disclosure | Scope list querysets by `family`/`pool`. [CITED: https://www.django-rest-framework.org/api-guide/permissions/] |

## Recommended Plan Slices

| Slice | Scope | Files | Verification |
|-------|-------|-------|--------------|
| 1. RED helper tests | Add negative and positive helper tests. | `pickem/pickem_api/tests.py` | Focused tests fail before implementation. |
| 2. Core authz module | Add context, resolvers, role guards, exceptions, scoped query helpers. | `pickem/pickem_api/authz.py` | `pickem_api` tests pass. |
| 3. Optional adapters | Add DRF/browser adapter tests only if needed. | `pickem_api/permissions.py`, `pickem_homepage/tests.py` | Focused adapter tests pass. |
| 4. Final validation | Run check, migration check, focused apps, full suite. | planning summary only | Full validation green. |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/02-authorization-foundation/02-CONTEXT.md` - locked Phase 2 guard behavior and scope.
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` - project scope, requirements, roadmap, and Phase 1 state.
- Phase 1 summaries `01-01` through `01-04` - schema/backfill/test outcomes.
- `SECURITY_THREAT_MODEL.md`, `FAMILY_MULTI_TENANCY_PLAN.md`, `TEST_PLAN.md`, `DISCOVERY.md`, `MIGRATION_PLAN.md` - threat, product, test, discovery, and migration constraints.
- `pickem/pickem_api/models.py`, `pickem/pickem_homepage/models.py`, `pickem/pickem_homepage/views.py`, `pickem/pickem_api/views.py`, `pickem/pickem_api/permissions.py`, existing tests and settings.

### Secondary (MEDIUM confidence)

- https://docs.djangoproject.com/en/4.0/topics/auth/default/ - Django auth decorators.
- https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/ - `get_object_or_404`.
- https://docs.djangoproject.com/en/4.0/ref/exceptions/ - Django exceptions.
- https://www.django-rest-framework.org/api-guide/permissions/ - DRF permissions.
- https://www.django-rest-framework.org/api-guide/exceptions/ - DRF exceptions.

### Tertiary (LOW confidence)

- A1 only: role-before-membership ordering as a general existence-leak explanation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - installed versions verified locally and no new packages are needed.
- Architecture: HIGH - recommendation follows locked decisions and verified code ownership.
- Pitfalls: HIGH - visible in code/discovery docs except one marked assumption.

**Research date:** 2026-06-28  
**Valid until:** 2026-07-28 or until Django/DRF versions or Phase 02 context changes.
