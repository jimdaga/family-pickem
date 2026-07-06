---
phase: 05-family-admin-experience
plan: 04
subsystem: tenant-invite-admin
tags: [django, tenant-authz, invite-management, audit-log, csrf, tdd, tailwind]

requires:
  - phase: 05-family-admin-experience
    provides: [tenant admin hub, member admin pattern, safe audit metadata pattern]
provides:
  - Tenant-scoped invite management page at /families/<family_slug>/pools/<pool_slug>/admin/invites/.
  - Admin+ member-invite creation with owner-only admin-role invite allowlist.
  - Current-family invite listing with safe metadata only.
  - Scoped invite revoke and revoke-and-create replacement flows.
  - One-time raw invite code/link display on create and replacement responses only.
  - Negative coverage for members, outsiders, inactive actors, anonymous users, CSRF, and cross-family invitation IDs.
affects: [phase-05-family-admin-experience, tenant-invite-admin, family-audit-log]

tech-stack:
  added: []
  patterns: [Django command form, request.tenant_context scoped mutation, hash-only invite code storage, one-time raw-code render, transaction plus audit log]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/family_admin_invites.html
    - .planning/phases/05-family-admin-experience/05-04-SUMMARY.md
  modified:
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/templates/pickem/family_pool_home.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Invite management keeps the existing FamilyInvitation model and hash-only code storage; no email delivery or model redesign was added."
  - "Admins may create member invites only; owners may create member or admin invites through the explicit role allowlist."
  - "Replacement is implemented as revoke-and-create in one transaction, with the new raw code shown only on that response."

patterns-established:
  - "Invite mutations resolve target invitations by family=request.tenant_context.family and invitation id before revoking or replacing."
  - "Invitation audit metadata records safe role, expiry, use-count, max-use, revoked state, and replacement linkage without raw invite codes or hashes."

requirements-completed: [AUTHZ-03, AUTHZ-05, INV-02, SEC-01]

coverage:
  - id: D1
    description: "Admins and owners can create current-family member invites from the admin invite page."
    requirement: INV-02
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_admin_and_owner_can_create_member_invites_with_one_time_raw_display"
        status: pass
    human_judgment: false
  - id: D2
    description: "Persisted invite list shows safe metadata only and does not expose raw codes, hashes, or other-family invites."
    requirement: SEC-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_admin_invite_page_lists_safe_current_family_metadata_only"
        status: pass
    human_judgment: false
  - id: D3
    description: "Invite role creation is least-privilege: admins are member-only, owners can create member/admin invites."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_admin_cannot_create_admin_role_invite_but_owner_can"
        status: pass
    human_judgment: false
  - id: D4
    description: "Revoke and replacement are current-family scoped, transactional, and audit logged without raw codes."
    requirement: INV-02
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_invite_revoke_and_replace_are_current_family_scoped_and_audited"
        status: pass
    human_judgment: false
  - id: D5
    description: "Cross-family invitation IDs and unauthorized actors cannot list, revoke, replace, or create invites."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_cross_family_invitation_ids_cannot_be_revoked_or_replaced"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_invite_mutations_deny_member_outsider_inactive_anonymous_and_csrf"
        status: pass
    human_judgment: false
  - id: D6
    description: "Pool home invite affordance routes owners/admins to the admin invite management surface instead of duplicating create controls."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_nav_affordance_visible_only_for_tenant_admin_roles"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-07-01
status: complete
---

# Phase 05 Plan 04: Invite Admin Summary

Tenant-scoped invite management using existing hash-only FamilyInvitation records, one-time raw-code display, scoped revoke/replacement, and safe audit logging.

## Performance

- **Duration:** 6min
- **Started:** 2026-07-01T16:45:02Z
- **Completed:** 2026-07-01T16:51:21Z
- **Tasks:** 3
- **Files modified:** 6 plan-relevant files

## Accomplishments

- Added `/families/<family_slug>/pools/<pool_slug>/admin/invites/` for current-family invite list/create operations.
- Added scoped revoke and replace routes that resolve invitations by current family and never touch cross-family IDs.
- Added `FamilyInviteCreateForm` with role allowlists: admins create member invites only; owners can create member/admin invites.
- Rendered a practical invite admin page with safe metadata, mobile cards, and one-time raw invite code/link display after create/replace.
- Updated pool-home invite action to route owners/admins to invite management instead of duplicating inline create behavior.

## Task Commits

1. **Task 1: Add invite management safety tests** - `ca247e3` (test)
2. **Task 2: Implement admin invite create, list, revoke, and replacement** - `a4fc736` (feat)
3. **Task 3: Render invite admin page and consolidate old invite entry point** - `24fbb92` (feat)

**Plan metadata:** captured in the final docs commit after STATE/ROADMAP updates.

## Files Created/Modified

- `pickem/pickem_homepage/forms.py` - Added `FamilyInviteCreateForm`.
- `pickem/pickem_homepage/views.py` - Added admin invite list/create/revoke/replace handlers and safe invite audit helpers.
- `pickem/pickem_homepage/urls.py` - Added tenant admin invite routes.
- `pickem/pickem_homepage/templates/pickem/family_admin_invites.html` - Added invite create form, one-time code block, metadata table/cards, and revoke/replace actions.
- `pickem/pickem_homepage/templates/pickem/family_pool_home.html` - Replaced inline invite create affordance with admin invite management link.
- `pickem/pickem_homepage/tests.py` - Added invite admin TDD coverage for role policy, raw-code non-disclosure, scoped mutations, CSRF, and cross-family denials.

## Decisions Made

- Kept invite management on the existing `FamilyInvitation` model; no email delivery fields, raw-code fields, or migrations were introduced.
- Preserved the older Phase 3 owner-only invite creation endpoint for compatibility, but the pool-home UI now routes owner/admin users to the admin invite page.
- Implemented replacement as revoke-and-create with a new hash-only invite and a one-time raw-code response.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` failed with 8 assertions in pre-existing dirty frontend-refactor templates. Failures referenced public homepage text, dashboard markup/tenant data attributes, and rules wording that were already changed in the working tree outside Plan 05-04. The focused Plan 05-04 integration suite passed.
- Local curl to `/families/smith-family/pools/smith-main/admin/invites/` returned 404 because the running development database does not contain the test fixture slugs. Authenticated owner/admin/member behavior was verified by Django integration tests.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None introduced by this plan. Stub scan found pre-existing placeholder attributes in legacy forms and a pre-existing TODO in legacy scoring logic; neither was touched for Plan 05-04.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: invite-admin-route | `pickem/pickem_homepage/views.py` | New admin invite routes expose invite metadata and accept create/revoke/replace POSTs; mitigated by tenant admin guard, role allowlist, CSRF, current-family lookup, and tests. |
| threat_flag: raw-invite-code-display | `pickem/pickem_homepage/templates/pickem/family_admin_invites.html` | Raw invite codes leave the server only on create/replace responses; tests assert reload/list/audit do not expose raw codes or hashes. |
| threat_flag: invite-replacement | `pickem/pickem_homepage/views.py` | Replacement revokes an existing invite and creates a new one; mitigated by same-transaction current-family lookup and safe audit metadata. |

## Verification

- PASS: RED run failed before implementation with missing `family_pool_admin_invites`, `family_pool_admin_invite_revoke`, and `family_pool_admin_invite_replace` routes.
- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2` - 24 tests.
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - no issues.
- PASS: `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` - no changes detected.
- PASS: `git diff --check` - no whitespace errors.
- PASS with expected dev-data limitation: `curl -s -I --max-time 5 http://localhost:8000/families/smith-family/pools/smith-main/admin/invites/ | head -20` - local server responded with 404 for absent fixture slugs.
- FAIL out of scope: `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` - 8 failures from unrelated dirty frontend-refactor template output.

## Next Phase Readiness

Plan 05-05 can build tenant manual-pick admin tools using the same admin+ route, command form, current tenant lookup, CSRF, and safe audit metadata patterns.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/05-family-admin-experience/05-04-SUMMARY.md`.
- Created/modified plan files exist.
- Task commits exist: `ca247e3`, `a4fc736`, and `24fbb92`.
- No tracked files were deleted by task commits.

---
*Phase: 05-family-admin-experience*
*Completed: 2026-07-01*
