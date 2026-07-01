---
phase: 05-family-admin-experience
plan: 03
subsystem: tenant-member-admin
tags: [django, tenant-authz, audit-log, csrf, tdd, tailwind]

requires:
  - phase: 05-family-admin-experience
    provides: [tenant admin hub, tenant admin settings pattern, owner/admin navigation baseline]
provides:
  - Tenant-scoped member admin page at /families/<family_slug>/pools/<pool_slug>/admin/members/.
  - Owner-only member role/status update route with current-family membership lookup.
  - Transactional last-active-owner protection for demotion and deactivation.
  - MEMBERSHIP_UPDATED audit logs with safe before/after metadata for successful mutations.
  - Negative coverage for admins, members, outsiders, inactive actors, forged cross-family membership IDs, and CSRF.
affects: [phase-05-family-admin-experience, tenant-member-admin, family-audit-log]

tech-stack:
  added: []
  patterns: [Django command form, request.tenant_context scoped mutation, select_for_update ownership invariant, transaction plus audit log]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/family_admin_members.html
    - .planning/phases/05-family-admin-experience/05-03-SUMMARY.md
  modified:
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Member list access is admin+ but role/status mutation POSTs require current actor owner role server-side."
  - "Membership updates resolve target rows by family=request.tenant_context.family and membership id, ignoring forged user/family identifiers."
  - "The last active owner invariant is checked inside the same transaction as the membership update."

patterns-established:
  - "Owner-sensitive member changes use select_for_update current-family lookups plus same-transaction invariant checks before saving."
  - "Membership audit metadata records target membership/user, actor, previous role/status, and new role/status without request secrets."

requirements-completed: [AUTHZ-03, AUTHZ-05, SEC-01]

coverage:
  - id: D1
    description: "Admins and owners can view current-family active and inactive memberships without leaking another family."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_member_list_shows_current_family_members_only_to_admins_and_owners"
        status: pass
    human_judgment: false
  - id: D2
    description: "Only owners can perform role/status mutations; admins see operational member data but no mutation controls."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_admin_cannot_perform_owner_sensitive_role_or_status_mutations"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_member_list_owner_controls_and_admin_readonly_state_are_visible"
        status: pass
    human_judgment: false
  - id: D3
    description: "Last active owner cannot be demoted or deactivated."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_last_active_owner_cannot_be_demoted_or_deactivated"
        status: pass
    human_judgment: false
  - id: D4
    description: "Forged cross-family membership IDs and forged user/family body IDs do not leak or mutate rows."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_forged_cross_family_membership_id_does_not_leak_or_mutate"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_owner_can_update_member_role_status_and_audit_safe_metadata"
        status: pass
    human_judgment: false
  - id: D5
    description: "Successful membership mutations create safe MEMBERSHIP_UPDATED audit metadata."
    requirement: SEC-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_owner_can_update_member_role_status_and_audit_safe_metadata"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-07-01
status: complete
---

# Phase 05 Plan 03: Member Admin Summary

Tenant-scoped member administration with owner-only role/status mutation, last-owner safety, and safe audit logging.

## Performance

- **Duration:** 14min
- **Started:** 2026-07-01T16:27:00Z
- **Completed:** 2026-07-01T16:41:41Z
- **Tasks:** 3
- **Files modified:** 6 plan-relevant files

## Accomplishments

- Added `/families/<family_slug>/pools/<pool_slug>/admin/members/` and `/admin/members/update/` routes under tenant admin context.
- Added `FamilyMembershipUpdateForm` and owner-only POST handling that ignores forged family/user IDs and locks target memberships by current family.
- Enforced last-active-owner protection transactionally before demoting or deactivating an owner.
- Added `MEMBERSHIP_UPDATED` audit entries with previous/new role/status, target membership/user, and actor metadata.
- Rendered a mobile-friendly members page where owners see controls and admins see read-only operational member data.

## Task Commits

1. **Task 1: Add membership management negative tests** - `095bb3a` (test)
2. **Task 2: Implement owner-protected membership mutations** - `6f9aaf9` (feat)
3. **Task 3: Render practical member management UI** - `d69ce71` (test)

**Plan metadata:** captured in the final docs commit after STATE/ROADMAP updates.

## Files Created/Modified

- `pickem/pickem_homepage/forms.py` - Added `FamilyMembershipUpdateForm`.
- `pickem/pickem_homepage/views.py` - Added members list/update views, audit metadata helper, hub members link, and transactional owner safety logic.
- `pickem/pickem_homepage/urls.py` - Added tenant admin member list and update routes.
- `pickem/pickem_homepage/templates/pickem/family_admin_members.html` - Added responsive member table/card UI with owner controls and admin read-only states.
- `pickem/pickem_homepage/tests.py` - Added TDD coverage for member listing, owner-only mutation, last-owner safety, forged IDs, CSRF, and audit metadata.

## Decisions Made

- Used a dedicated POST endpoint for membership updates so authorization and transactional safety are centralized server-side.
- Kept admins read-only for member role/status controls in this plan because D-05/D-27 mark those mutations owner-sensitive.
- Used existing `FamilyAuditLog.Action.MEMBERSHIP_UPDATED` rather than adding a new action.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tightened forged-ID audit assertion**
- **Found during:** Task 2
- **Issue:** The RED test checked for any `MEMBERSHIP_UPDATED` audit in the other family, but the fixture intentionally creates one unrelated other-family audit row.
- **Fix:** Scoped the assertion to the forged target membership id so it proves no mutation/audit occurred for the attempted cross-family target.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `6f9aaf9`

**Total deviations:** 1 auto-fixed (Rule 1). **Impact on plan:** Test precision improved; product/security scope unchanged.

## Issues Encountered

- The local-server curl to `/families/smith-family/pools/smith-main/admin/members/` returned 404 because the running development database does not contain the test fixture slugs. Authenticated owner/admin/member behavior was verified by Django integration tests.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None introduced by this plan. Stub scan found pre-existing placeholder attributes in older form widgets and a pre-existing TODO in legacy scoring logic; neither was touched for Plan 05-03.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: tenant-member-admin-route | `pickem/pickem_homepage/views.py` | New admin member routes expose operational member data and accept role/status POSTs; mitigated by tenant guards, owner-only mutation, current-family lookups, CSRF, and tests. |
| threat_flag: last-owner-invariant | `pickem/pickem_homepage/views.py` | Membership updates can remove owner access if unchecked; mitigated by transaction-scoped active-owner count before owner demotion/deactivation. |
| threat_flag: membership-audit-metadata | `pickem/pickem_homepage/views.py` | Membership mutations write audit metadata; tests assert safe before/after metadata without request secrets. |

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2` - 18 tests.
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - no issues.
- PASS: `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` - no changes detected.
- PASS: `git diff --check` - no whitespace errors.
- PASS: `curl -s -I --max-time 5 http://localhost:8000/families/smith-family/pools/smith-main/admin/members/ | head -20` - local server responded; 404 expected for absent dev fixture slugs.

## Next Phase Readiness

Plan 05-04 can build invite management using the same admin+ view / scoped mutation / audit pattern. Member role/status controls are now owner-only and current-family scoped.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/05-family-admin-experience/05-03-SUMMARY.md`.
- Created/modified plan files exist.
- Task commits exist: `095bb3a`, `6f9aaf9`, and `d69ce71`.
- No tracked files were deleted by task commits.

---
*Phase: 05-family-admin-experience*
*Completed: 2026-07-01*
