---
phase: 05-family-admin-experience
plan: 06
subsystem: tenant-week-winner-admin
tags: [django, tenant-authz, week-winners, audit-log, csrf, tdd, legacy-denial]

requires:
  - phase: 05-family-admin-experience
    provides: [tenant admin hub, manual pick admin patterns, JSON-aware denial helper, audit metadata patterns]
provides:
  - Tenant-scoped week-winner admin page at /families/<family_slug>/pools/<pool_slug>/admin/winners/.
  - Current-family candidate display from current-pool scored picks.
  - Current-pool winner override with integer week validation before dynamic field names.
  - WEEK_WINNER_UPDATED audit metadata for every successful override.
  - Disabled legacy global commissioner page and JSON mutation/retrieval endpoints.
affects: [phase-05-family-admin-experience, tenant-week-winner-admin, family-audit-log, legacy-commissioner-closure]

tech-stack:
  added: []
  patterns: [Django command form, bounded dynamic field construction, request.tenant_context scoped mutation, transaction plus audit log, legacy JSON denial]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/family_admin_winners.html
    - .planning/phases/05-family-admin-experience/deferred-items.md
    - .planning/phases/05-family-admin-experience/05-06-SUMMARY.md
  modified:
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Week-winner admin uses explicit tenant admin URLs and family_member_required(admin) for browser access."
  - "Week numbers are validated as integers in 1..18 before constructing week winner or bonus field names."
  - "Legacy commissioner page and JSON handlers now deny globally instead of rendering or mutating global tools."

patterns-established:
  - "Winner target users resolve through active FamilyMembership rows for request.tenant_context.family."
  - "Winner standings resolve through userSeasonPoints rows filtered by request.tenant_context.pool and pool season."
  - "Successful winner overrides reset prior current-pool week winners, recalculate affected totals, and write WEEK_WINNER_UPDATED audit metadata."

requirements-completed: [AUTHZ-03, AUTHZ-05, SEC-01]

coverage:
  - id: D1
    description: "Tenant admins can view current-family/current-pool week-winner candidates."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_winner_page_lists_current_family_candidates_and_current_pool_rows"
        status: pass
    human_judgment: false
  - id: D2
    description: "Winner overrides are current-pool scoped, recalculate totals, ignore forged family/pool/season/body fields, and audit metadata."
    requirement: SEC-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_winner_post_sets_current_pool_winner_bonus_total_and_audit"
        status: pass
    human_judgment: false
  - id: D3
    description: "Invalid week values and forged users or missing current-pool standings are rejected before unsafe dynamic field mutation."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_winner_post_rejects_invalid_weeks_before_dynamic_fields"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_winner_post_rejects_forged_users_and_missing_current_pool_standings"
        status: pass
    human_judgment: false
  - id: D4
    description: "Member, outsider, inactive, anonymous, and CSRF winner access/mutation denials preserve tenant authorization boundaries."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_winner_access_denies_member_outsider_inactive_anonymous_and_csrf"
        status: pass
    human_judgment: false
  - id: D5
    description: "Legacy global commissioner page and JSON endpoints are disabled without login redirects, HTML JSON denials, or global mutation."
    requirement: SEC-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_legacy_commissioner_routes_are_disabled_without_login_html_or_global_mutation"
        status: pass
      - kind: manual_procedural
        ref: "curl -s -i --max-time 5 http://localhost:8000/commissioners/ | head -20"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-07-01
status: complete
---

# Phase 05 Plan 06: Week-Winner Admin Summary

Tenant-scoped week-winner administration with bounded week validation, current-pool standings mutation, audit logging, and closed legacy commissioner paths.

## Performance

- **Duration:** 18min
- **Started:** 2026-07-01T16:52:00Z
- **Completed:** 2026-07-01T17:10:07Z
- **Tasks:** 3
- **Files modified:** 6 plan-relevant files

## Accomplishments

- Added `/families/<family_slug>/pools/<pool_slug>/admin/winners/` for admin+ week-winner management.
- Added `FamilyWeekWinnerForm` to validate `week_number` as integer 1..18 before building `week_{n}_winner` and `week_{n}_bonus`.
- Scoped winner candidates to current-pool scored picks and active current-family members with current-pool `userSeasonPoints` rows.
- Scoped winner overrides to current-pool rows, reset prior winners for that week, recalculated affected totals, and wrote `WEEK_WINNER_UPDATED` audit metadata.
- Disabled legacy `/commissioners/`, `set-week-winner`, `submit-manual-pick`, `get-user-picks`, and banner mutation handlers as global admin surfaces.

## Task Commits

1. **Task 1: Add week-winner and legacy denial tests** - `2cc5e94` (test)
2. **Task 2/3: Implement week-winner admin and disable legacy commissioner surfaces** - `e8ef14a` (feat)

**Plan metadata:** captured in the final docs commit after STATE/ROADMAP updates.

## Files Created/Modified

- `pickem/pickem_homepage/forms.py` - Added `FamilyWeekWinnerForm`.
- `pickem/pickem_homepage/views.py` - Added winner helpers/view, bounded dynamic field handling, audit metadata, and denial-only legacy handlers.
- `pickem/pickem_homepage/urls.py` - Added tenant admin winners route.
- `pickem/pickem_homepage/templates/pickem/family_admin_winners.html` - Added operational Tailwind winner admin page.
- `pickem/pickem_homepage/tests.py` - Added TDD coverage for candidates, scoped mutation, invalid weeks, forged users, denials, CSRF, audit logging, and legacy closure.
- `.planning/phases/05-family-admin-experience/deferred-items.md` - Logged unrelated dirty-template broad-suite failures.

## Decisions Made

- Used the existing `userSeasonPoints` dynamic fields after strict integer range validation rather than changing the schema.
- Kept winner mutation as a CSRF-protected browser POST; no new JSON winner mutation endpoint was introduced.
- Returned 404 for the legacy browser page and generic JSON 401/404 for old JSON routes to avoid login HTML and tenant/global disclosure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tightened over-broad RED assertion**
- **Found during:** Task 2 verification
- **Issue:** A test asserted the other pool id did not appear anywhere in audit metadata, but that id could equal legitimate week/user values in fixture data.
- **Fix:** Changed the assertion to verify no `pool_id` or `family_id` forged metadata keys are present.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** Focused `FamilyAdminExperienceTests` passed.
- **Committed in:** `e8ef14a`

**Total deviations:** 1 auto-fixed (Rule 1). **Impact on plan:** Test correctness fix only; no product scope change.

## Issues Encountered

- The broad app-level command failed 8 tests in pre-existing dirty frontend refactor templates outside this plan's commit set. Details were recorded in `deferred-items.md`.
- I did not alter the dirty `base.html`, `commissioners.html`, homepage, dashboard, rules, theme, logo, screenshot, or schema/logo migration work.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None introduced by this plan. Stub scan found pre-existing placeholder attributes in legacy forms and a pre-existing TODO in legacy pick rendering logic; neither was introduced or changed for Plan 05-06.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: week-winner-admin-route | `pickem/pickem_homepage/views.py` | New admin route mutates score-affecting weekly winner and bonus fields; mitigated by tenant admin guard, active current-family membership lookup, current-pool standings lookup, bounded week validation, CSRF, transaction, audit logging, and tests. |
| threat_flag: legacy-commissioner-denial | `pickem/pickem_homepage/views.py` | Legacy global commissioner routes remain URL-addressable; mitigated by denial-only page and JSON handlers with no global mutation. |

## Verification

- PASS: RED run failed before implementation with missing `family_pool_admin_winners` route and still-open legacy commissioner paths.
- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2` - 36 tests.
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - no issues.
- PASS: `git diff --check` - no whitespace errors.
- PASS: `curl -s -i --max-time 5 http://localhost:8000/commissioners/ | head -20` - returned HTTP 404 and did not render the legacy global commissioner dashboard.
- FAIL, deferred as out-of-scope: `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2` - 193 tests run, 8 failures in pre-existing dirty frontend refactor templates not modified by Plan 05-06.

## Next Phase Readiness

Plan 05-07 can treat tenant family-admin score-affecting browser workflows as migrated. Phase 6 still owns cron/background scoring hardening and should not assume those paths were changed here.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/05-family-admin-experience/05-06-SUMMARY.md`.
- Created/modified plan files exist.
- Task commits exist: `2cc5e94` and `e8ef14a`.
- No tracked files were deleted by task commits.

---
*Phase: 05-family-admin-experience*
*Completed: 2026-07-01*
