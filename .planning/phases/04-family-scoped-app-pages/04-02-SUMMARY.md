---
phase: 04-family-scoped-app-pages
plan: 02
subsystem: auth
tags: [django, multi-tenancy, picks, authorization, csrf, tests]

requires:
  - phase: 04-family-scoped-app-pages
    provides: tenant dashboard context and Phase 3 family/pool URL shell
  - phase: 02-authorization-foundation
    provides: family_member_required and tenant context resolution
provides:
  - Tenant pick submit and edit routes under explicit family/pool URLs
  - Server-derived GamePicks writes scoped to request.tenant_context.pool and request.user
  - Legacy signed-in pick route redirects before global private mutation
  - Cross-family/body-tampering negative coverage for pick reads and writes
affects: [family-scoped-app-pages, scoring-hardening, production-migration]

tech-stack:
  added: []
  patterns:
    - Tenant gameplay mutation routes guarded by family_member_required
    - Narrow form validation for user-editable pick inputs only
    - Scoped object lookup before edit lock/team validation

key-files:
  created:
    - .planning/phases/04-family-scoped-app-pages/04-02-SUMMARY.md
  modified:
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/templates/pickem/picks.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "04-02: Tenant pick writes accept only selected game/team and tiebreakers; user, pool, season, week, game metadata, and correctness are server-derived."
  - "04-02: Signed-in legacy /picks/ and /picks/edit/ redirect to the resolved tenant picks page before reading or mutating private picks."
  - "04-02: Tenant pick IDs include pool, user, and game to avoid cross-pool collisions for the same user/game."
  - "04-02: Until tenant scores/standings routes ship in Plan 04-03, tenant picks empty-state links stay inside the pool dashboard instead of linking to global pages."

patterns-established:
  - "Use request.tenant_context.pool on every GamePicks read/write path for tenant picks."
  - "Use scoped GamePicks lookup by id, pool, and current user before returning edit state or lock/team validation errors."
  - "Do not render hidden ownership, tenant, season/week, or correctness fields on tenant pick forms."

requirements-completed: [AUTHZ-02, AUTHZ-05, POOL-03, SEC-03]

coverage:
  - id: D1
    description: "Tenant pick submit/edit routes live under explicit family/pool URLs and require active family membership."
    requirement: AUTHZ-02
    verification:
      - kind: integration
        ref: "pickem/pickem_homepage/tests.py#TenantPickFlowIsolationTests.test_outsider_cannot_get_or_post_tenant_picks_by_url_slug_tampering"
        status: pass
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2"
        status: pass
    human_judgment: false
  - id: D2
    description: "Pick saves derive pool, user, season/week/game metadata, and correctness server-side from tenant context and the resolved game."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem/pickem_homepage/tests.py#TenantPickFlowIsolationTests.test_tenant_post_creates_server_derived_pick_and_ignores_forged_fields"
        status: pass
      - kind: integration
        ref: "pickem/pickem_homepage/tests.py#TenantPickFlowIsolationTests.test_tenant_ajax_edit_uses_current_pool_and_user_lookup"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tenant pick reads and edit lookups are current-pool and current-user scoped while NFL game facts remain global reference data."
    requirement: POOL-03
    verification:
      - kind: integration
        ref: "pickem/pickem_homepage/tests.py#TenantPickFlowIsolationTests.test_tenant_get_picks_reads_only_current_pool_user_state"
        status: pass
      - kind: integration
        ref: "pickem/pickem_homepage/tests.py#TenantPickFlowIsolationTests.test_cross_pool_pick_id_edit_is_denied_before_lock_or_team_validation"
        status: pass
    human_judgment: false
  - id: D4
    description: "Cross-family URL, pick ID, and body tampering have automated negative coverage."
    requirement: SEC-03
    verification:
      - kind: integration
        ref: "pickem/pickem_homepage/tests.py#TenantPickFlowIsolationTests"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-06-30
status: complete
---

# Phase 04 Plan 02: Tenant Pick Submit/Edit Summary

**Tenant-scoped pick submission and editing with server-derived GamePicks ownership and tamper-resistant tests.**

## Performance

- **Duration:** 7min
- **Started:** 2026-06-30T00:11:26Z
- **Completed:** 2026-06-30T00:17:36Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added tenant pick submit and edit routes at `/families/<family_slug>/pools/<pool_slug>/picks/` and `/families/<family_slug>/pools/<pool_slug>/picks/edit/`.
- Replaced tenant pick saving with narrow validation and server-derived `GamePicks` ownership, pool, season/week/game fields, and correctness reset.
- Converted signed-in legacy pick routes into compatibility redirects so they cannot render or mutate global private picks.
- Updated the picks template to post/edit through tenant route names and stop rendering hidden server-owned pick fields.
- Added cross-family, cross-pool, and request-body tampering tests for tenant pick reads, submits, edits, and legacy redirects.

## Task Commits

1. **Task 1: Add tenant pick submit and edit tests** - `1c4038d` (test)
2. **Task 2: Implement tenant pick routes and server-derived writes** - `6f332f3` (feat)
3. **Task 3: Update picks template for tenant actions** - `e912ae5` (feat)

## Files Created/Modified

- `pickem/pickem_homepage/tests.py` - Adds `TenantPickFlowIsolationTests` for tenant GET/POST/edit, outsider denial, cross-pool ID denial, legacy redirects, and forged body fields.
- `pickem/pickem_homepage/forms.py` - Adds `PickSubmissionForm` for only `game_id`, selected `pick`, and optional tiebreakers.
- `pickem/pickem_homepage/urls.py` - Adds tenant pick submit/edit route names.
- `pickem/pickem_homepage/views.py` - Adds legacy redirect helper, server-derived pick save helper, guarded tenant submit/edit views, and pool/user-scoped edit lookup.
- `pickem/pickem_homepage/templates/pickem/picks.html` - Uses tenant route URLs for AJAX and removes hidden ownership/game metadata fields.

## Decisions Made

- Tenant pick IDs now include `pool.id`, `user.id`, and `game.id` so the same user can safely pick the same global game in different pools later.
- Tenant pick edit still accepts `pick_id`, but lookup is constrained by current pool and current user before lock/team validation, so cross-pool IDs return 404.
- Tenant picks empty-state score/standings links route back to the current pool dashboard until Plan 04-03 creates tenant score/standings route names.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing test import during RED setup**
- **Found during:** Task 1
- **Issue:** The first RED test run failed before exercising app behavior because the new test data used `Teams` without importing it.
- **Fix:** Added `Teams` to the test imports and re-ran the focused RED test class, which then failed on the expected missing tenant routes and unsafe legacy form path.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.TenantPickFlowIsolationTests --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `1c4038d`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test harness correction only; implementation scope stayed within the planned pick submit/edit surface.

## Issues Encountered

- The RED run confirmed the planned gap: tenant pick routes did not exist and legacy signed-in POST could enter the broad `GamePicksForm` save path.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. The empty hidden `pick` and tiebreaker fields in `picks.html` are intentional client-editable values populated by existing JavaScript before submit, not server-owned stubs.

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.TenantPickFlowIsolationTests --settings=pickem.test_settings --verbosity=2` (7 tests)
- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` (82 tests)
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`
- PASS: template acceptance grep confirmed tenant AJAX route names and no hidden `userEmail`, `userID`, `uid`, `slug`, `competition`, `gameWeek`, `gameyear`, `gameseason`, `pick_game_id`, `pick_correct`, `family`, or `pool` fields remain in `picks.html`.

## Next Phase Readiness

Plan 04-03 can add tenant scores, standings, weekly winners, and rules routes. Picks currently stay tenant-safe by linking tenant empty states back to the pool dashboard until those route names exist.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/04-family-scoped-app-pages/04-02-SUMMARY.md`.
- Task commits exist: `1c4038d`, `6f332f3`, `e912ae5`.
- Key files exist: `views.py`, `urls.py`, `forms.py`, `picks.html`, and `tests.py`.
- No unrelated files were staged or committed.

---
*Phase: 04-family-scoped-app-pages*
*Completed: 2026-06-30*
