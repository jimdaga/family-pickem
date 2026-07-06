---
phase: 05-family-admin-experience
plan: 01
subsystem: tenant-admin
tags: [django, tenant-authz, audit-log, tailwind, tdd]

requires:
  - phase: 02-authorization-foundation
    provides: [family_member_required, request.tenant_context, 403/404/login denial split]
  - phase: 04-family-scoped-app-pages
    provides: [explicit family/pool URLs, current tenant navigation context]
provides:
  - Tenant admin hub route at /families/<family_slug>/pools/<pool_slug>/admin/.
  - Owner/admin-only family admin shell with scoped recent audit log display.
  - Tenant-role-gated shared navigation affordance for current family owners/admins.
  - Negative authorization tests for anonymous, outsider, inactive, member, and forged slug access.
affects: [phase-05-family-admin-experience, tenant-admin-navigation, family-audit-log]

tech-stack:
  added: []
  patterns: [Django tenant route guard, request.tenant_context scoped admin query, selective patch staging in dirty worktree]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/family_admin.html
    - .planning/phases/05-family-admin-experience/05-01-SUMMARY.md
  modified:
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/templates/pickem/base.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "The admin hub uses family_member_required(minimum_role=ADMIN); global commissioner/superuser status does not grant tenant access."
  - "Recent audit activity is queried by request.tenant_context.family only, so other-family audit rows never render."
  - "The shared nav admin affordance is shown only when current family/pool context exists and current_membership.role is owner/admin."

patterns-established:
  - "Tenant admin pages should derive family, pool, and membership from request.tenant_context before any private query."
  - "Admin hub sections can expose available admin links while labeling later Phase 5 surfaces by plan number."

requirements-completed: [AUTHZ-03, AUTHZ-05, SEC-01]

coverage:
  - id: D1
    description: "Tenant admin hub route exists under explicit family/pool URL and enforces anonymous/login, non-member/inactive 404, and member 403 behavior."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Owner/admin hub renders current family/pool context and only current-family recent audit rows."
    requirement: SEC-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_admin_and_owner_admin_hub_render_only_current_family_audit_rows"
        status: pass
    human_judgment: false
  - id: D3
    description: "Shared navigation exposes the tenant admin link only for current-family owners/admins."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_nav_affordance_visible_only_for_tenant_admin_roles"
        status: pass
    human_judgment: false

duration: 36min
completed: 2026-07-01
status: complete
---

# Phase 05 Plan 01: Tenant Admin Hub Summary

Owner/admin tenant admin hub with scoped audit display and role-gated navigation.

## Performance

- **Duration:** 36min
- **Started:** 2026-07-01T02:30:00Z
- **Completed:** 2026-07-01T03:06:11Z
- **Tasks:** 3
- **Files modified:** 5 plan-relevant code files

## Accomplishments

- Added `family_pool_admin` at `/families/<family_slug>/pools/<pool_slug>/admin/`.
- Added `family_admin.html` with practical Tailwind admin shell, section cards, scoped counts, and recent audit table.
- Added focused RED/GREEN `FamilyAdminExperienceTests` for tenant authorization, audit isolation, forged slug denial, and nav visibility.
- Replaced the shared nav commissioner affordance with a current tenant owner/admin admin link.

## Task Commits

1. **Task 1: Add failing admin hub authorization coverage** - `c8e511c` (test)
2. **Tasks 2-3: Implement tenant admin hub and tenant-role navigation** - `e48eb55` (feat)

**Plan metadata:** captured in the final docs commit after STATE/ROADMAP updates.

## Files Created/Modified

- `pickem/pickem_homepage/tests.py` - Added `FamilyAdminExperienceTests`.
- `pickem/pickem_homepage/urls.py` - Added the tenant admin hub route.
- `pickem/pickem_homepage/views.py` - Added admin section metadata and `family_pool_admin`.
- `pickem/pickem_homepage/templates/pickem/family_admin.html` - Added the admin hub UI and scoped audit table.
- `pickem/pickem_homepage/templates/pickem/base.html` - Replaced commissioner nav affordance with tenant owner/admin link.

## Decisions Made

- Used the existing tenant authorization helper instead of global commissioner checks.
- Kept later admin tools visible as plan-numbered sections without adding mutation routes ahead of their plans.
- Filtered audit logs by `family=tenant_context.family`; pool is displayed when present but not used to broaden visibility.

## Deviations from Plan

### Process Deviations

**1. Coupled Task 2 and Task 3 implementation commit**
- **Found during:** Task 2 and Task 3
- **Issue:** The TDD RED class intentionally included both hub behavior and nav behavior, so Task 2's verification command stayed red until Task 3's nav change existed.
- **Fix:** Implemented the route/template/audit query and the navigation affordance before committing the green implementation.
- **Files modified:** `pickem/pickem_homepage/urls.py`, `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/templates/pickem/family_admin.html`, `pickem/pickem_homepage/templates/pickem/base.html`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `e48eb55`

**2. Dirty worktree required selective staging**
- **Found during:** Task 3 commit
- **Issue:** `base.html` already had unrelated user/frontend-refactor changes.
- **Fix:** Used patch staging for only the tenant-admin nav hunks. Unrelated avatar/logo/header changes remained unstaged.
- **Files modified:** `pickem/pickem_homepage/templates/pickem/base.html`
- **Verification:** `git diff --cached` showed only the tenant-admin base-template hunks before commit.
- **Committed in:** `e48eb55`

**Total deviations:** 2 process deviations  
**Impact on plan:** No scope expansion. The deviations preserved a green implementation commit and protected unrelated dirty work.

## Issues Encountered

- None in the product implementation.
- Stub scan found a pre-existing unrelated TODO in `pickem/pickem_homepage/views.py`; it was not introduced or touched by this plan.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None for this plan. Admin section statuses point to planned Phase 5 follow-up plans and do not block the hub, authorization baseline, or audit display delivered here.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: tenant-admin-route | `pickem/pickem_homepage/views.py` | New browser admin route crosses untrusted slugs into tenant context resolution; mitigated with `family_member_required(minimum_role=ADMIN)` and negative tests. |
| threat_flag: audit-display | `pickem/pickem_homepage/views.py` | Private audit rows render to browser users; mitigated with current-family-only query and cross-family audit test. |

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2` - 6 tests.
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - no issues.
- PASS: `git diff --check` - no whitespace errors.
- PASS: `curl -s --max-time 5 http://localhost:8000 | head -40` - returned public homepage HTML including `<title>Family Pick'em</title>`.

## Next Phase Readiness

Phase 05 now has the dedicated tenant admin entry point and authorization baseline. Plan 05-02 can add settings edits into this hub, and later Phase 5 plans can fill the member, invite, manual-pick, and winner tools without relying on global commissioner navigation.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/05-family-admin-experience/05-01-SUMMARY.md`.
- Created/modified plan files exist.
- Task commits exist: `c8e511c` and `e48eb55`.
- No tracked files were deleted by task commits.

---
*Phase: 05-family-admin-experience*
*Completed: 2026-07-01*
