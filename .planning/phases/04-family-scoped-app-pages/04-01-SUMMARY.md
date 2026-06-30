---
phase: 04-family-scoped-app-pages
plan: 01
subsystem: tenant-dashboard
tags: [django, tenant-authz, dashboard, tests]

requires:
  - phase: 02-authorization-foundation
    provides: [family_member_required, tenant context resolution]
  - phase: 03-onboarding-and-family-selection
    provides: [authenticated root routing, family picker, tenant pool route, header context]
provides:
  - Signed-in root routing into tenant dashboards before legacy global dashboard queries run.
  - Family/pool-scoped dashboard standings, weekly winners, pick status, messages, and active members.
  - Cross-family negative tests for dashboard standings, picks, posts, and member data.
  - Disabled current-context dashboard empty states for unbuilt gameplay destinations.
affects: [phase-04-family-scoped-app-pages, tenant-dashboard, dashboard-links]

tech-stack:
  added: []
  patterns: [Django tenant dashboard query scoping, response-content negative tests, disabled current-context empty states]

key-files:
  created:
    - .planning/phases/04-family-scoped-app-pages/04-01-SUMMARY.md
  modified:
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/templates/pickem/family_pool_home.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Dashboard private widgets read from request.tenant_context.pool or request.tenant_context.family; global NFL week/game facts remain global reference data."
  - "Unbuilt tenant gameplay destinations stay disabled in the dashboard instead of linking users to legacy global gameplay pages."
  - "Shared base navigation global-link cleanup remains deferred to the planned Phase 4 shared navigation cleanup."

patterns-established:
  - "Tenant dashboard data starts from family_member_required and request.tenant_context before private queries run."
  - "Cross-family dashboard tests seed two families/pools and assert other-family standings, pick counts, and posts are absent from response content."
  - "Dashboard empty states use disabled cards until concrete tenant routes exist."

requirements-completed: [AUTHZ-04, POOL-03, SEC-04]

coverage:
  - id: D1
    description: "Signed-in root requests redirect into onboarding, picker, or a tenant dashboard before legacy private dashboard queries run."
    requirement: AUTHZ-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.TenantDashboardIsolationTests.test_signed_in_root_redirects_to_default_tenant_dashboard"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.TenantDashboardIsolationTests.test_signed_in_root_with_multiple_families_routes_to_picker"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tenant dashboard private widgets are scoped to the current family and pool and exclude another family's standings, picks, members, and posts."
    requirement: AUTHZ-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.TenantDashboardIsolationTests.test_dashboard_scopes_private_widgets_to_current_family_and_pool"
        status: pass
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2"
        status: pass
    human_judgment: false
  - id: D3
    description: "Anonymous public home behavior remains available through home.html."
    requirement: AUTHZ-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.TenantDashboardIsolationTests.test_anonymous_root_keeps_public_home_behavior"
        status: pass
    human_judgment: false
  - id: D4
    description: "Dashboard empty states do not link to legacy global gameplay pages before tenant gameplay routes are built."
    requirement: SEC-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.TenantDashboardIsolationTests.test_dashboard_empty_states_do_not_link_to_global_gameplay_pages"
        status: pass
    human_judgment: false

duration: 4min 24s
completed: 2026-06-30
status: complete
---

# Phase 04 Plan 01: Family/Pool Dashboard Summary

Signed-in users now land on a protected family/pool dashboard whose private widgets are scoped to the current tenant instead of the legacy global league.

## Performance

- **Duration:** 4min 24s
- **Started:** 2026-06-30T00:03:09Z
- **Completed:** 2026-06-30T00:07:33Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added dashboard isolation tests covering anonymous public home, signed-in root redirects, direct tenant access, outsider denial, and cross-family negative data assertions.
- Replaced the lightweight tenant pool shell with scoped dashboard queries for current pool standings, recent weekly winners, current-week pick status, family messages, and active family members.
- Updated dashboard markup so unbuilt tenant gameplay destinations are disabled current-context empty states instead of global `/picks/`, `/scores/`, `/standings/`, or `/rules/` links.

## Task Commits

1. **Task 1: Add dashboard tenant isolation tests** - `f676390` (test)
2. **Task 2: Scope tenant dashboard queries** - `ca4cfda` (feat)
3. **Task 3: Render tenant dashboard links and empty states** - `a350a93` (feat)

**Plan metadata:** recorded in the final `docs(04-01)` commit.

## Files Created/Modified

- `pickem/pickem_homepage/tests.py` - Added `TenantDashboardIsolationTests` for routing, membership denial, cross-family dashboard data exclusion, and dashboard link safety.
- `pickem/pickem_homepage/views.py` - Added current-week helper and implemented `family_pool_home()` with tenant-context scoped dashboard querysets.
- `pickem/pickem_homepage/templates/pickem/family_pool_home.html` - Rendered scoped dashboard widgets and disabled unbuilt tenant gameplay empty states.
- `.planning/phases/04-family-scoped-app-pages/04-01-SUMMARY.md` - Captures plan outcome and verification evidence.

## Decisions Made

- Used `request.tenant_context.pool` for standings, winners, and pick status; used `request.tenant_context.family` for messages and member activity.
- Kept `GamesAndScores` and `GameWeeks` as global NFL facts while scoping private overlays by pool/family.
- Left shared base navigation global-link cleanup for the later Phase 4 shared-navigation plan; this plan prevents global gameplay links inside the tenant dashboard content.

## Deviations from Plan

### Auto-fixed Issues

None.

### Process Deviations

**1. Test-first task produced an expected red state before dashboard implementation**
- **Found during:** Task 1
- **Issue:** The new isolation test expected scoped dashboard content that the pre-existing lightweight tenant shell did not render yet.
- **Fix:** Confirmed the failure was the missing scoped dashboard behavior, committed the test coverage, then implemented the view/template changes in later task commits.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** `pickem_homepage.tests.TenantDashboardIsolationTests` and full `pickem_homepage` suite passed after implementation.
- **Committed in:** `f676390`

**2. Scoped dashboard rendering required a template update during Task 2**
- **Found during:** Task 2
- **Issue:** Query scoping in `family_pool_home()` could not satisfy response-content isolation tests until the tenant dashboard template rendered the scoped widgets.
- **Fix:** Updated `family_pool_home.html` in the same commit as the scoped view, then used Task 3 for link/empty-state cleanup and regression coverage.
- **Files modified:** `pickem/pickem_homepage/templates/pickem/family_pool_home.html`
- **Verification:** Full `pickem_homepage` suite passed with 74 tests after Task 2 and 75 tests after Task 3.
- **Committed in:** `ca4cfda`

**Total deviations:** 2 process deviations  
**Impact on plan:** No product scope was expanded; the ordering change was required to prove tenant isolation through rendered response content.

## Known Stubs

None introduced. Stub scan found one pre-existing TODO in `pickem/pickem_homepage/views.py` outside this plan's modified dashboard block and placeholder attributes in the untouched public `home.html`.

## Threat Flags

None. No new endpoints, file access patterns, schema changes, cache layers, or auth bypasses were introduced. The tenant dashboard continues to use `family_member_required`.

## Verification

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.TenantDashboardIsolationTests --settings=pickem.test_settings --verbosity=2` - failed before implementation on missing scoped dashboard content, then passed after implementation, 5 tests.
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` - passed after Task 2, 74 tests.
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` - passed after Task 3 and final verification, 75 tests.
- `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - passed with the pre-existing 13 `pickem_api.userStats` `IntegerField(max_length=...)` warnings.

## Issues Encountered

None beyond the process deviations documented above. The Django warnings are pre-existing and unrelated to this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `04-02-PLAN.md` to move pick submit/edit into tenant URLs with server-derived writes. Remaining Phase 4 work still needs to migrate scores, standings, rules, profiles, message board AJAX, and shared navigation links.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/04-family-scoped-app-pages/04-01-SUMMARY.md`.
- Modified files exist: `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/templates/pickem/family_pool_home.html`, and `pickem/pickem_homepage/tests.py`.
- Task commits exist: `f676390`, `ca4cfda`, and `a350a93`.
- No tracked files were deleted by task commits.

---
*Phase: 04-family-scoped-app-pages*
*Completed: 2026-06-30*
