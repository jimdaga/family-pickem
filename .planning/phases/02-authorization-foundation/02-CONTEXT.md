# Phase 2: Authorization Foundation - Context

**Gathered:** 2026-06-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 centralizes server-side family/pool authorization before broad route migration. It should add reusable tenant resolution helpers, role guards, query scoping helpers, and negative tests proving cross-family denial. It may include the smallest proof wiring only if research/planning finds a low-risk path; broad page/API migration, onboarding, family switching, admin UX, cron hardening, and non-null tenant enforcement belong to later phases.

</domain>

<decisions>
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning

- `.planning/PROJECT.md` — project value, constraints, and active multi-tenancy requirements.
- `.planning/REQUIREMENTS.md` — v1 authorization requirements `AUTHZ-01` through `AUTHZ-05`, `SEC-03`, and related traceability.
- `.planning/ROADMAP.md` — Phase 2 scope and definition of done.
- `.planning/STATE.md` — Phase 1 completion state and current project position.

### Phase 1 artifacts

- `.planning/phases/01-domain-schema-foundation/01-CONTEXT.md` — locked tenant schema decisions carried into authorization work.
- `.planning/phases/01-domain-schema-foundation/01-01-SUMMARY.md` — core tenant domain model implementation summary.
- `.planning/phases/01-domain-schema-foundation/01-02-SUMMARY.md` — nullable pool scope and legacy competition backfill summary.
- `.planning/phases/01-domain-schema-foundation/01-03-SUMMARY.md` — homepage family scope and message-board-only membership summary.
- `.planning/phases/01-domain-schema-foundation/01-04-SUMMARY.md` — final Phase 1 verification evidence.

### Security and migration docs

- `SECURITY_THREAT_MODEL.md` — tenant isolation risks, required mitigations, and negative security test matrix.
- `FAMILY_MULTI_TENANCY_PLAN.md` — recommended authorization model and URL model.
- `DISCOVERY.md` — current route/API inventory and security findings.
- `TEST_PLAN.md` — authorization negative test expectations.
- `MIGRATION_PLAN.md` — legacy family/pool continuity constraints.

### Current code

- `pickem/pickem_api/models.py` — `Family`, `Pool`, `FamilyMembership`, `PoolSettings`, `FamilyInvitation`, `FamilyAuditLog`, and pool-scoped competition models.
- `pickem/pickem_homepage/models.py` — family-scoped message board and banner models.
- `pickem/pickem_homepage/views.py` — existing `is_commissioner`, `commissioner_required`, global page views, AJAX endpoints, and current inline authorization patterns.
- `pickem/pickem_api/permissions.py` — current DRF `IsAdminOrReadOnly` permission pattern.
- `pickem/pickem_api/views.py` — current API permission decorators and read/write endpoint patterns.
- `pickem/pickem_homepage/urls.py` — existing global browser routes that later phases will migrate or bridge.
- `pickem/pickem_api/urls.py` — existing API routes that later phases will scope or bridge.
- `pickem/pickem_api/tests.py` — existing model/helper test style and Phase 1 tenant tests.
- `pickem/pickem_homepage/tests.py` — existing view/model test style.
- `pickem/pickem/test_settings.py` — isolated test settings.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `pickem_api.models.FamilyMembership` — authoritative family role/status table for helper checks.
- `pickem_api.models.Pool` — pool-to-family relationship that helpers must validate.
- `pickem_homepage.views.commissioner_required` — existing decorator pattern to replace or supplement with family-role decorators.
- `pickem_api.permissions.IsAdminOrReadOnly` — existing DRF permission style that can inform API permission helpers, though it is global/staff-oriented and not tenant-safe for private data.
- Existing Django test files — Phase 2 should add focused helper/decorator/permission tests in the current test style.

### Established Patterns

- Browser views are mostly function-based views with decorators.
- API views use DRF function decorators plus custom permission classes.
- The codebase currently has no service layer; Phase 2 can introduce a small centralized authz helper module without broad refactoring.
- Existing global routes remain in place, so legacy fallback must be explicit and temporary.
- Current commissioner logic is global and should not be treated as tenant authorization.

### Integration Points

- Future page migration can call helper functions/decorators from `pickem_homepage.views`.
- Future API migration can use tenant-aware DRF permission/resolution helpers from `pickem_api.views`.
- Future onboarding and switcher work can rely on helper behavior for active membership and default pool resolution.
- Future admin experience can rely on owner/admin/member role helpers but should wire detailed audit/admin actions in Phase 5.

</code_context>

<specifics>
## Specific Ideas

- Prefer helper APIs that make unsafe use obvious. New tenant-aware routes should not be able to accidentally omit membership checks.
- Make negative tests first-class: non-member cannot resolve family/pool, member of family A cannot resolve pool in family B, member cannot pass admin guard, admin cannot pass owner guard.
- Keep denial behavior stable and testable so future page/API phases inherit the same security model.

</specifics>

<deferred>
## Deferred Ideas

- Tenant-aware URL migration for all pages and APIs belongs to Phase 4 and Phase 5.
- Onboarding, create/join family, invite acceptance, and family switching belong to Phase 3 and Phase 5.
- CSRF/rate-limit/settings hardening remains Phase 6 unless the planner identifies tiny helper-adjacent tests that do not expand scope.
- Cron/scoring pool-awareness remains Phase 6.
- `PoolMembership` remains deferred unless future requirements require family members who are not pool participants.

</deferred>

---
*Phase: 02-authorization-foundation*
*Context gathered: 2026-06-28*
