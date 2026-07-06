---
phase: 05-family-admin-experience
plan: 05
subsystem: tenant-manual-pick-admin
tags: [django, tenant-authz, manual-picks, audit-log, csrf, tdd, tailwind]

requires:
  - phase: 05-family-admin-experience
    provides: [tenant admin hub, command forms, safe audit metadata pattern, invite/member admin authorization patterns]
provides:
  - Tenant-scoped manual pick page at /families/<family_slug>/pools/<pool_slug>/admin/picks/.
  - JSON current-pool pick retrieval for active current-family users with Phase 2 denial split.
  - Admin+ manual pick create/update using server-derived pool, user, game, season, week, competition, and correctness values.
  - MANUAL_PICK_UPDATED audit metadata for every successful manual pick mutation.
  - Negative tests for forged users, games, pool/season/week/competition/body fields, JSON denials, and CSRF.
affects: [phase-05-family-admin-experience, tenant-manual-pick-admin, family-audit-log, tenant-pick-isolation]

tech-stack:
  added: []
  patterns: [Django command form, request.tenant_context scoped mutation, JSON-aware tenant denial helper, pool/user/game pick identity, transaction plus audit log]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/family_admin_picks.html
    - .planning/phases/05-family-admin-experience/05-05-SUMMARY.md
  modified:
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Manual pick admin uses explicit tenant admin URLs and family_member_required(admin) for browser pages."
  - "JSON user-pick retrieval uses a local JSON-aware tenant context resolver so anonymous requests return 401 JSON instead of login redirects."
  - "Manual pick writes reuse the Phase 4 pool-user-game pick identity and reset correctness server-side on admin override."

patterns-established:
  - "Manual pick target users resolve through active FamilyMembership rows for request.tenant_context.family."
  - "Manual pick games resolve by request.tenant_context.pool season, competition, submitted week, and game id before selected team validation."
  - "Successful manual pick writes record previous/new pick, target user id, game id, week, and actor id in FamilyAuditLog metadata."

requirements-completed: [AUTHZ-03, AUTHZ-05, SEC-01]

coverage:
  - id: D1
    description: "Admins and owners can retrieve current-pool picks for active current-family users only."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_admin_and_owner_can_retrieve_current_pool_picks_for_active_family_users_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "Manual pick create/update is current-pool scoped and ignores forged user, pool, season, week, competition, correctness, and pick identifiers."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_manual_pick_submission_server_derives_scope_and_writes_audit"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_manual_pick_update_records_previous_pick_and_ignores_correctness_forgery"
        status: pass
    human_judgment: false
  - id: D3
    description: "Cross-family target users, wrong-scope games, invalid team slugs, unauthorized actors, JSON denials, and CSRF failures do not mutate picks."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_manual_pick_submission_rejects_invalid_team_cross_family_user_and_wrong_game_scope"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_manual_pick_access_denies_member_outsider_inactive_anonymous_and_csrf"
        status: pass
    human_judgment: false
  - id: D4
    description: "Manual pick admin UI renders current family/pool context, member selector, week selector, game controls, and admin hub link."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_manual_pick_page_lists_current_family_users_and_current_pool_games"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_admin_and_owner_admin_hub_render_only_current_family_audit_rows"
        status: pass
    human_judgment: true
    rationale: "Manual owner/admin browser QA is still required to exercise the rendered form against real dev data."
  - id: D5
    description: "Every successful manual pick mutation writes MANUAL_PICK_UPDATED audit metadata."
    requirement: SEC-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_manual_pick_submission_server_derives_scope_and_writes_audit"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_manual_pick_update_records_previous_pick_and_ignores_correctness_forgery"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-07-01
status: complete
---

# Phase 05 Plan 05: Manual Pick Admin Summary

Tenant-scoped manual pick administration with current-family user validation, current-pool game validation, JSON-safe denials, and audit logging.

## Performance

- **Duration:** 6min
- **Started:** 2026-07-01T16:54:50Z
- **Completed:** 2026-07-01T17:00:35Z
- **Tasks:** 3
- **Files modified:** 5 plan-relevant files

## Accomplishments

- Added `/families/<family_slug>/pools/<pool_slug>/admin/picks/` for admin+ manual pick management.
- Added `/admin/picks/user-picks/` JSON retrieval with anonymous 401 JSON, non-member/inactive 404 JSON, and member 403 JSON behavior.
- Added `FamilyManualPickForm` and scoped server-side resolution for active current-family target users and current-pool games.
- Reused the Phase 4 pool/user/game `GamePicks` identity convention and reset `pick_correct` server-side on manual overrides.
- Added `MANUAL_PICK_UPDATED` audit rows with previous pick, new pick, target user id, game id, week, and actor id.
- Rendered a Tailwind admin picks page with family/pool context, week selector, member selector, game controls, empty states, and admin hub navigation.

## Task Commits

1. **Task 1: Add manual pick tenant-scope tests** - `b7a3c06` (test)
2. **Task 2: Implement pool-scoped manual pick retrieval and mutation** - `c168bbb` (feat)
3. **Task 3: Render manual pick admin UI** - `7e79f33` (test)

**Plan metadata:** captured in the final docs commit after STATE/ROADMAP updates.

## Files Created/Modified

- `pickem/pickem_homepage/forms.py` - Added `FamilyManualPickForm`.
- `pickem/pickem_homepage/views.py` - Added manual pick week/user/game helpers, browser page handler, JSON pick retrieval, scoped mutation, and audit logging.
- `pickem/pickem_homepage/urls.py` - Added tenant admin manual pick page and JSON retrieval routes.
- `pickem/pickem_homepage/templates/pickem/family_admin_picks.html` - Added operational Tailwind manual pick admin page.
- `pickem/pickem_homepage/tests.py` - Added TDD coverage for scoped retrieval, scoped writes, forged body fields, JSON denials, CSRF, and hub link.

## Decisions Made

- Used the existing `GamePicks` model and Phase 4 pool/user/game identity convention; no migrations were introduced.
- Kept manual pick mutation as a CSRF-protected browser POST and added JSON only for pick retrieval.
- Implemented JSON authorization locally through `require_tenant_context()` rather than decorating the JSON route with browser redirect behavior.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The manual pick browser route needs a template to be valid, so the new `family_admin_picks.html` template was included with the implementation commit rather than leaving an intermediate commit that could not render the route.
- Local curl to `/families/smith-family/pools/smith-main/admin/picks/` returned 404 because the running development database does not contain the test fixture slugs. Authenticated behavior was verified through Django integration tests.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None introduced by this plan. Stub scan found pre-existing placeholder attributes in legacy forms and a pre-existing TODO in legacy pick rendering logic; neither was introduced or changed for Plan 05-05.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: manual-pick-admin-route | `pickem/pickem_homepage/views.py` | New admin route can create or update score-affecting picks; mitigated by tenant admin guard, active current-family user lookup, current-pool game lookup, team slug validation, CSRF, and tests. |
| threat_flag: manual-pick-json-retrieval | `pickem/pickem_homepage/views.py` | New JSON route returns user pick state; mitigated by JSON-aware Phase 2 denial split, active current-family target lookup, pool-scoped pick filter, and non-leaking 404 tests. |

## Verification

- PASS: RED run failed before implementation with missing `family_pool_admin_picks` and `family_pool_admin_pick_user_picks` routes while existing admin tests stayed green.
- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2` - 30 tests.
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - no issues.
- PASS: `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` - no changes detected.
- PASS: `git diff --check` - no whitespace errors.
- PASS with expected dev-data limitation: `curl -s -I --max-time 5 http://localhost:8000/families/smith-family/pools/smith-main/admin/picks/ | head -20` - local server responded with 404 for absent fixture slugs.

## Next Phase Readiness

Plan 05-06 can use the same tenant admin route pattern, bounded week validation, scoped target lookup, and `FamilyAuditLog` metadata pattern for week-winner and bonus controls.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/05-family-admin-experience/05-05-SUMMARY.md`.
- Created/modified plan files exist.
- Task commits exist: `b7a3c06`, `c168bbb`, and `7e79f33`.
- No tracked files were deleted by task commits.

---
*Phase: 05-family-admin-experience*
*Completed: 2026-07-01*
