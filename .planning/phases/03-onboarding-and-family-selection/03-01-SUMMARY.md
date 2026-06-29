---
phase: 03-onboarding-and-family-selection
plan: 01
subsystem: onboarding-routing
tags: [django, tenant-authz, onboarding, templates, tests]

requires:
  - phase: 01-domain-schema-foundation
    provides: [Family, Pool, FamilyMembership tenant domain models]
  - phase: 02-authorization-foundation
    provides: [get_user_family_memberships, family_member_required]
provides:
  - Authenticated root routing by active family membership count.
  - No-family onboarding shell that avoids legacy global private home data.
  - Active-family picker shell and protected family/pool tenant entry page.
  - Focused routing and negative authorization tests.
affects: [phase-03-onboarding-and-family-selection, phase-04-family-scoped-app-pages]

tech-stack:
  added: []
  patterns: [Django client routing tests, Phase 2 browser tenant guard reuse, default active pool resolver]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/onboarding.html
    - pickem/pickem_homepage/templates/pickem/family_picker.html
    - pickem/pickem_homepage/templates/pickem/family_pool_home.html
  modified:
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Authenticated root requests now route before legacy homepage data is queried."
  - "Tenant entry uses the Phase 2 family_member_required guard instead of legacy commissioner/superuser checks."
  - "Families without an active pool appear in the picker with a safe setup-needed state instead of falling back to global data."

patterns-established:
  - "Membership-count routing: zero active memberships -> onboarding, one with active pool -> tenant URL, multiple -> picker."
  - "Default active pool lookup prefers is_default active pools, then first active pool in deterministic season/slug order."
  - "Phase 3 shell templates provide entry points while leaving create/join mutations to later plans."

requirements-completed: [INV-03, INV-04, AUTHZ-01]

coverage:
  - id: D1
    description: "Anonymous visitors still render the public root homepage."
    requirement: INV-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.PostLoginTenantRoutingTests.test_anonymous_root_still_renders_public_homepage"
        status: pass
    human_judgment: false
  - id: D2
    description: "Signed-in users with no active family membership route to onboarding before legacy private home data renders."
    requirement: INV-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.PostLoginTenantRoutingTests.test_authenticated_user_with_no_active_membership_routes_to_onboarding"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.PostLoginTenantRoutingTests.test_onboarding_has_no_global_private_home_data"
        status: pass
    human_judgment: false
  - id: D3
    description: "Signed-in users with one active membership route to that family's default active pool URL."
    requirement: INV-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.PostLoginTenantRoutingTests.test_authenticated_user_with_one_active_membership_routes_to_default_pool"
        status: pass
    human_judgment: false
  - id: D4
    description: "Signed-in users with multiple active memberships route to a picker listing only active families."
    requirement: INV-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.PostLoginTenantRoutingTests.test_authenticated_user_with_multiple_active_memberships_routes_to_picker"
        status: pass
    human_judgment: false
  - id: D5
    description: "Direct family/pool tenant entry requires active family membership and valid pool-family consistency."
    requirement: AUTHZ-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.PostLoginTenantRoutingTests.test_outsider_direct_tenant_entry_is_denied"
        status: pass
    human_judgment: false

duration: 3min 21s
completed: 2026-06-29
status: complete
---

# Phase 03 Plan 01: Post-Login Routing And Onboarding Shell Summary

Signed-in users now enter onboarding, a family picker, or a protected family/pool bridge before legacy global homepage data can render.

## Performance

- **Duration:** 3min 21s
- **Started:** 2026-06-29T12:56:10Z
- **Completed:** 2026-06-29T12:59:31Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added focused tests for anonymous root access, no-family onboarding routing, one-family default-pool routing, multi-family picker routing, active-only picker visibility, and outsider tenant-entry denial.
- Added authenticated root routing in `index()` before legacy standings, picks, posts, stats, or private user data queries run.
- Added `onboarding`, `family_picker`, and protected `family_pool_home` routes and templates.

## Task Commits

1. **Task 1: Add routing tests for membership-count entry** - `33ff187` (test)
2. **Task 2: Implement onboarding, picker, and tenant entry views** - `2d00445` (feat)
3. **Task 3: Add focused onboarding and picker templates** - `9b02f01` (feat)

**Plan metadata:** recorded in the final `docs(03-01)` commit.

## Files Created/Modified

- `pickem/pickem_homepage/tests.py` - Added membership-count routing and direct-entry authorization tests.
- `pickem/pickem_homepage/views.py` - Added default active pool helpers, onboarding/picker/tenant views, and authenticated root routing.
- `pickem/pickem_homepage/urls.py` - Added onboarding, family picker, and readable tenant pool routes.
- `pickem/pickem_homepage/templates/pickem/onboarding.html` - Added no-family onboarding shell with create and join entry paths.
- `pickem/pickem_homepage/templates/pickem/family_picker.html` - Added active-family/default-pool picker with setup-needed empty state.
- `pickem/pickem_homepage/templates/pickem/family_pool_home.html` - Added lightweight tenant pool bridge page with current family/pool context.

## Decisions Made

- Kept anonymous `/` behavior unchanged and routed only authenticated root requests.
- Reused `family_member_required` for tenant entry so membership and pool-family consistency stay server-enforced.
- Left create-family and join-family mutations to later Phase 3 plans while exposing shell entry paths.

## Deviations from Plan

None - plan executed as scoped.

## Known Stubs

- `pickem/pickem_homepage/templates/pickem/onboarding.html` links to `/families/create/` and submits invite codes to `/families/join/`; these are intentional shell entry paths for 03-02 and 03-03.
- `pickem/pickem_homepage/templates/pickem/family_pool_home.html` links to existing global gameplay pages as compatibility bridges until Phase 4 migrates those pages into tenant context.

## Threat Flags

None.

## Verification

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` - passed, 51 tests.
- `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - passed with 13 pre-existing `pickem_api.userStats` IntegerField `max_length` warnings.

## Self-Check: PASSED

- Created files exist: onboarding, family picker, and family pool home templates.
- Task commits exist: `33ff187`, `2d00445`, `9b02f01`.
- No tracked files were deleted by task commits.
