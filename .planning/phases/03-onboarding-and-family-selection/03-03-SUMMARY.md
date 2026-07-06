---
phase: 03-onboarding-and-family-selection
plan: 03
subsystem: onboarding-invites
tags: [django, tenant-onboarding, invites, csrf, audit, tests]

requires:
  - phase: 01-domain-schema-foundation
    provides: [FamilyInvitation, FamilyMembership, FamilyAuditLog tenant invite models]
  - phase: 02-authorization-foundation
    provides: [family_member_required tenant role guard]
  - phase: 03-onboarding-and-family-selection
    provides: [onboarding shell, create-family flow, tenant pool entry route]
provides:
  - Owner-only minimal member invite creation from family/pool context.
  - Hash-only invite code storage with one-time raw-code display.
  - Authenticated manual-code and invite-link acceptance.
  - Generic invalid invite failures for revoked, expired, exhausted, invalid, inactive, and mismatched invites.
  - Invite creation and acceptance audit logging.
affects: [phase-03-onboarding-and-family-selection, phase-05-family-admin-experience]

tech-stack:
  added: []
  patterns: [Django Form validation, secrets-backed invite codes, sha256 code hashing, transaction.atomic invite acceptance, generic denial messaging]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/join_family.html
  modified:
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/templates/pickem/family_pool_home.html
    - pickem/pickem_homepage/templates/pickem/onboarding.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Phase 3 invite creation is owner-only; admins and members are denied until full invite management policy in Phase 5."
  - "Invite links render a confirmation form and require POST for acceptance so the membership mutation remains CSRF-protected."
  - "Invite code normalization ignores case and non-alphanumeric separators for readable/manual entry, while persisting only a sha256-prefixed hash."

patterns-established:
  - "Owner invite creation returns the raw code/link only in the immediate tenant-home response."
  - "Invite acceptance performs lifecycle, active family, active pool, and pool-family consistency checks inside transaction.atomic before membership changes."
  - "Invalid invite outcomes reuse one generic form error and do not render family names."

requirements-completed: [INV-01, INV-03, AUTHZ-01, AUD-01]

coverage:
  - id: D1
    description: "Owners can create minimal member invites from family/pool context without raw code persistence."
    requirement: INV-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.InviteFlowTests.test_owner_can_create_member_invite_hash_only_with_defaults_and_audit"
        status: pass
    human_judgment: false
  - id: D2
    description: "Invite creation is owner-only, POST-only, and CSRF-protected."
    requirement: AUTHZ-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.InviteFlowTests.test_non_owners_cannot_create_phase_three_invites"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.InviteFlowTests.test_invite_creation_is_post_only_and_csrf_protected"
        status: pass
    human_judgment: false
  - id: D3
    description: "Authenticated users can join by manual code or invite link and land on the invited family/pool."
    requirement: INV-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.InviteFlowTests.test_manual_code_acceptance_creates_member_and_redirects_to_pool"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.InviteFlowTests.test_link_acceptance_requires_login_and_accepts_by_post"
        status: pass
    human_judgment: false
  - id: D4
    description: "Valid invites can reactivate inactive same-family memberships and audit acceptance."
    requirement: AUD-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.InviteFlowTests.test_valid_invite_reactivates_inactive_same_family_membership"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.InviteFlowTests.test_manual_code_acceptance_creates_member_and_redirects_to_pool"
        status: pass
    human_judgment: false
  - id: D5
    description: "Revoked, expired, exhausted, invalid, inactive-family, inactive-pool, and pool-family mismatch invites fail generically without membership changes."
    requirement: AUTHZ-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.InviteFlowTests.test_invalid_invite_failures_are_generic_and_do_not_create_membership"
        status: pass
    human_judgment: false

duration: 5min 46s
completed: 2026-06-29
status: complete
---

# Phase 03 Plan 03: Minimal Invite Creation And Acceptance Summary

Owner-created hash-only invites with CSRF-protected manual-code and link acceptance for authenticated family onboarding.

## Performance

- **Duration:** 5min 46s
- **Started:** 2026-06-29T13:11:10Z
- **Completed:** 2026-06-29T13:16:56Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added invite tests covering owner-only creation, hash-only persistence, fourteen-day/twenty-use defaults, CSRF enforcement, raw-code one-time display, audit logging, and generic invalid invite failures.
- Added secure invite creation with Python `secrets`, `code_hash` persistence only, owner role enforcement through `family_member_required`, and `INVITATION_CREATED` audit entries.
- Added authenticated join-by-code/link acceptance with transaction-scoped validation, membership creation/reactivation, invite use counting, acceptance audit records, and onboarding/template wiring.

## Task Commits

1. **Task 1: Add invite creation and acceptance tests** - `f14d552` (test)
2. **Task 2: Implement owner-only invite creation** - `975a01c` (feat, shared implementation commit)
3. **Task 3: Implement join-by-code and link acceptance** - `975a01c` (feat, shared implementation commit)

**Plan metadata:** recorded in the final `docs(03-03)` commit.

## Files Created/Modified

- `pickem/pickem_homepage/tests.py` - Added positive and negative invite creation/acceptance tests, including CSRF and generic failure assertions.
- `pickem/pickem_homepage/forms.py` - Added `JoinFamilyForm` for manual and link-based invite code submission.
- `pickem/pickem_homepage/views.py` - Added invite normalization/hash helpers, owner-only creation, validation, acceptance, and audit logic.
- `pickem/pickem_homepage/urls.py` - Added join, invite-link, and owner invite creation routes.
- `pickem/pickem_homepage/templates/pickem/join_family.html` - Added authenticated join form and generic error rendering.
- `pickem/pickem_homepage/templates/pickem/family_pool_home.html` - Added owner-only create-invite action and one-time raw invite display.
- `pickem/pickem_homepage/templates/pickem/onboarding.html` - Wired the join form to the named join route.

## Decisions Made

- Kept Phase 3 invite creation owner-only even though the eventual Phase 5 invite-management policy may permit admins.
- Made invite links GET-render a join confirmation page and POST-accept the invite to preserve CSRF protection on the membership mutation.
- Used existing audit actions: `INVITATION_CREATED` for creation and `MEMBERSHIP_CREATED`/`MEMBERSHIP_UPDATED` for acceptance/reactivation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed invite-link form construction**
- **Found during:** Task 3
- **Issue:** The initial link-acceptance view passed form data twice, raising `TypeError: BaseForm.__init__() got multiple values for argument 'data'`.
- **Fix:** Constructed the link form with explicit `data={...}` only on POST and `initial={...}` for GET display.
- **Files modified:** `pickem/pickem_homepage/views.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.InviteFlowTests pickem_api.tests.TenantDomainModelTest.test_family_invitation_stores_hash_only_and_lifecycle_fields --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `975a01c`

**2. [Process deviation] Shared implementation commit for Tasks 2 and 3**
- **Found during:** Commit boundary selection
- **Issue:** Owner creation and acceptance both depend on the same invite normalization, hashing, lifecycle validation, and audit helpers in `views.py`.
- **Fix:** Committed the shared production implementation once after the full invite test suite passed, while preserving the red test commit separately.
- **Files modified:** `forms.py`, `views.py`, `urls.py`, `family_pool_home.html`, `join_family.html`, `onboarding.html`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `975a01c`

**Total deviations:** 2 (Rule 1: 1, process: 1)  
**Impact on plan:** Behavior, security constraints, and verification were completed as planned; only the production commit boundary for Tasks 2 and 3 was combined because the implementation is intentionally shared.

## Issues Encountered

None beyond the auto-fixed form-construction bug above.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. The stub scan found only UI placeholder attributes and an existing unrelated TODO in the legacy scores view.

## Threat Flags

None. The new routes were explicitly planned and are covered by owner-only authorization, active family/pool validation, pool-family consistency checks, CSRF tests, generic invalid-invite failures, and audit tests.

## Verification

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.InviteFlowTests pickem_api.tests.TenantDomainModelTest.test_family_invitation_stores_hash_only_and_lifecycle_fields --settings=pickem.test_settings --verbosity=2` - passed, 9 tests.
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2` - passed, 113 tests.
- `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - passed with 13 pre-existing `pickem_api.userStats` `IntegerField(max_length=...)` warnings.

## Next Phase Readiness

03-04 can add the header/mobile family switcher with join/create entry points already available. Full invite listing, revocation, regeneration, advanced expiry/use-count editing, and invite audit UI remain deferred to Phase 5.

## Self-Check: PASSED

- Created file exists: `pickem/pickem_homepage/templates/pickem/join_family.html`.
- Modified files exist: `forms.py`, `views.py`, `urls.py`, `family_pool_home.html`, `onboarding.html`, and `tests.py`.
- Task commits exist: `f14d552` and `975a01c`.
- No tracked files were deleted by task commits.

---
*Phase: 03-onboarding-and-family-selection*
*Completed: 2026-06-29*
