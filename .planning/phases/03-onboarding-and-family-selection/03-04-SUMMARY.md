---
phase: 03-onboarding-and-family-selection
plan: 04
subsystem: onboarding-family-switcher
tags: [django, tenant-authz, context-processors, navigation, tests]

requires:
  - phase: 01-domain-schema-foundation
    provides: [Family, Pool, FamilyMembership tenant domain models]
  - phase: 02-authorization-foundation
    provides: [get_user_family_memberships, require_tenant_context, tenant route guards]
  - phase: 03-onboarding-and-family-selection
    provides: [onboarding routes, create-family flow, invite flow, tenant pool entry route]
provides:
  - Server-derived current family and pool template context.
  - Active-membership-only family switcher choices.
  - Desktop and mobile header switcher controls for explicit tenant URLs.
  - No-family header actions for create-family and join-family onboarding.
affects: [phase-03-onboarding-and-family-selection, phase-04-family-scoped-app-pages]

tech-stack:
  added: []
  patterns: [Django context processor tenant navigation, active-membership switcher data, template response isolation assertions]

key-files:
  created:
    - .planning/phases/03-onboarding-and-family-selection/03-04-SUMMARY.md
  modified:
    - pickem/pickem/context_processors.py
    - pickem/pickem/settings.py
    - pickem/pickem_homepage/templates/pickem/base.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Switcher choices are derived only from get_user_family_memberships() for the authenticated user."
  - "Explicit tenant route context is resolved through require_tenant_context() before it is exposed to templates."
  - "The header switcher targets each family default active pool and does not replace server-side tenant guards."

patterns-established:
  - "Shared tenant navigation context lives in a context processor and returns safe empty values for anonymous or no-family users."
  - "Header/mobile switcher links use readable /families/<family_slug>/pools/<pool_slug>/ URLs."
  - "Template tests assert absence of inactive memberships and outsider families to guard against family leakage."

requirements-completed: [TEN-01, AUTHZ-01, INV-04]

coverage:
  - id: D1
    description: "Tenant pages expose current family and pool context in shared navigation."
    requirement: INV-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilySwitcherContextTests.test_one_family_user_sees_current_family_and_pool_in_header_context"
        status: pass
    human_judgment: false
  - id: D2
    description: "Multi-family switcher choices include only the authenticated user's active memberships."
    requirement: AUTHZ-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilySwitcherContextTests.test_multi_family_switcher_lists_only_authenticated_active_memberships"
        status: pass
    human_judgment: false
  - id: D3
    description: "No-family users see onboarding create/join actions instead of unrelated family switcher entries."
    requirement: TEN-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilySwitcherContextTests.test_no_family_user_sees_onboarding_actions_without_family_leakage"
        status: pass
    human_judgment: false
  - id: D4
    description: "Existing homepage routes continue rendering with the new context processor."
    verification:
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2"
        status: pass
      - kind: manual_procedural
        ref: "curl -s --max-time 5 http://localhost:8000 | head -40"
        status: pass
    human_judgment: false

duration: 2min 56s
completed: 2026-06-29
status: complete
---

# Phase 03 Plan 04: Header/Mobile Family Switcher Summary

Server-scoped family navigation now shows current tenant context and switches only between authenticated active memberships.

## Performance

- **Duration:** 2min 56s
- **Started:** 2026-06-29T13:32:44Z
- **Completed:** 2026-06-29T13:35:40Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added isolation tests proving current family/pool context, active-only multi-family switch options, inactive membership exclusion, outsider family exclusion, and no-family onboarding actions.
- Added `family_switcher_context` and registered it globally so templates receive safe `current_family`, `current_pool`, `current_membership`, and `family_switcher_choices` values.
- Updated desktop and mobile header navigation to show current family/default pool, switch to explicit tenant URLs, and offer create/join actions when the user has no active family.

## Task Commits

1. **Task 1: Add switcher context isolation tests** - `a99eb86` (test)
2. **Task 2: Provide current family switcher data** - `f248315` (feat)
3. **Task 3: Update desktop and mobile header switcher** - `42c2911` (feat)

**Plan metadata:** recorded in the final `docs(03-04)` commit.

## Files Created/Modified

- `pickem/pickem_homepage/tests.py` - Added `FamilySwitcherContextTests` for current context, active-only switcher choices, and no-family onboarding actions.
- `pickem/pickem/context_processors.py` - Added a tenant navigation context processor using active memberships and authorized tenant route resolution.
- `pickem/pickem/settings.py` - Registered the new context processor.
- `pickem/pickem_homepage/templates/pickem/base.html` - Added focused desktop and mobile family switcher/onboarding controls.

## Decisions Made

- Reused Phase 2 authorization helpers for current context resolution rather than trusting route kwargs or client state.
- Kept switch targets to default active pools only, matching Phase 3 scope and deferring multi-pool UI.
- Kept the UI update constrained to the existing header/mobile menu patterns without broad redesign or Tailwind migration work.

## Deviations from Plan

### Auto-fixed Issues

None.

### Process Deviations

**1. Test-first task produced an expected red state before implementation**
- **Found during:** Task 1
- **Issue:** The plan was not marked TDD, but Task 1 required tests for behavior that did not exist until Tasks 2 and 3.
- **Fix:** Committed the isolation tests after confirming they failed only for missing context/header hooks, then implemented the provider and header updates in separate commits.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** Final `pickem_homepage` suite passed after Tasks 2 and 3.
- **Committed in:** `a99eb86`

**Total deviations:** 1 process deviation  
**Impact on plan:** No behavior scope changed; final verification passed.

## Known Stubs

None introduced. Stub scan found one pre-existing unrelated TODO in `pickem/pickem_homepage/views.py`.

## Threat Flags

None. This plan added no new endpoints, auth paths, file access, or schema changes. The new template context is derived server-side from active memberships and authorized tenant resolution.

## Verification

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilySwitcherContextTests --settings=pickem.test_settings --verbosity=2` - initially failed before implementation because `current_family`, `current_pool`, and switcher header hooks did not exist.
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilySwitcherContextTests --settings=pickem.test_settings --verbosity=2` - passed after implementation, 3 tests.
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` - passed, 69 tests.
- `curl -s --max-time 5 http://localhost:8000 | head -40` - passed, returned public homepage HTML.

All Django test commands reported the existing 13 `pickem_api.userStats` `IntegerField(max_length=...)` warnings.

## Issues Encountered

None beyond the expected test-first red state documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

03-05 can run final Phase 3 verification. Phase 4 can use the shared header context and explicit tenant URLs while migrating gameplay pages to tenant-scoped data.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/03-onboarding-and-family-selection/03-04-SUMMARY.md`.
- Modified files exist: `pickem/pickem/context_processors.py`, `pickem/pickem/settings.py`, `pickem/pickem_homepage/templates/pickem/base.html`, and `pickem/pickem_homepage/tests.py`.
- Task commits exist: `a99eb86`, `f248315`, and `42c2911`.
- No tracked files were deleted by task commits.

---
*Phase: 03-onboarding-and-family-selection*
*Completed: 2026-06-29*
