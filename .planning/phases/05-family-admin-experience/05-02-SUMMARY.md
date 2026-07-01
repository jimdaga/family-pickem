---
phase: 05-family-admin-experience
plan: 02
subsystem: tenant-admin-settings
tags: [django, tenant-authz, audit-log, csrf, tailwind, tdd]

requires:
  - phase: 05-family-admin-experience
    provides: [tenant admin hub route, owner/admin navigation baseline]
provides:
  - Tenant-scoped admin settings route at /families/<family_slug>/pools/<pool_slug>/admin/settings/.
  - Admin settings form for current family name, current pool name, and represented PoolSettings booleans.
  - Transaction-scoped settings mutations with FamilyAuditLog.Action.POOL_SETTINGS_UPDATED records.
  - Cross-family, forged-body, CSRF, role-denial, and banner metadata non-leakage coverage.
affects: [phase-05-family-admin-experience, tenant-admin-settings, family-audit-log]

tech-stack:
  added: []
  patterns: [Django Form command object, request.tenant_context scoped mutation, transaction plus audit log]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/family_admin_settings.html
    - .planning/phases/05-family-admin-experience/05-02-SUMMARY.md
  modified:
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Settings POST ignores client-supplied family_id, pool_id, banner ids, and other foreign identifiers; targets come from request.tenant_context."
  - "Family, Pool, and PoolSettings edits share FamilyAuditLog.Action.POOL_SETTINGS_UPDATED with metadata target_type=family_pool_settings."
  - "COMM-03 is covered as read-only current-family banner metadata; no banner editing UI or SiteBanner mutation was added."

patterns-established:
  - "Tenant admin command forms should validate only editable fields and let views bind family, pool, actor, and audit target server-side."
  - "Settings audit metadata should contain changed field names plus before/after values for represented settings only."

requirements-completed: [AUTHZ-03, AUTHZ-05, POOL-04, COMM-03, SEC-01]

coverage:
  - id: D1
    description: "Owners/admins can edit the current family display name, current pool display name, picks_lock_at_kickoff, and allow_tiebreaker."
    requirement: POOL-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_settings_post_updates_only_current_tenant_and_audits_safe_metadata"
        status: pass
    human_judgment: false
  - id: D2
    description: "Settings mutations are tenant scoped and forged body IDs cannot target another family, pool, or banner."
    requirement: AUTHZ-05
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_settings_post_updates_only_current_tenant_and_audits_safe_metadata"
        status: pass
    human_judgment: false
  - id: D3
    description: "Members, outsiders, inactive users, anonymous users, and CSRF-missing POSTs cannot mutate settings."
    requirement: AUTHZ-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests"
        status: pass
    human_judgment: false
  - id: D4
    description: "Settings mutations create scoped audit logs without raw secrets or CSRF/session metadata."
    requirement: SEC-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_settings_post_updates_only_current_tenant_and_audits_safe_metadata"
        status: pass
    human_judgment: false
  - id: D5
    description: "Settings page does not leak another family's banner metadata and does not deactivate SiteBanner rows."
    requirement: COMM-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_admin_and_owner_settings_page_renders_current_context_without_banner_leakage"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.FamilyAdminExperienceTests.test_settings_post_requires_csrf_and_does_not_deactivate_banners"
        status: pass
    human_judgment: false

duration: 4min 21s
completed: 2026-07-01
status: complete
---

# Phase 05 Plan 02: Admin Settings Summary

Tenant-scoped owner/admin settings for family name, pool name, and represented PoolSettings values with audit logging.

## Performance

- **Duration:** 4min 21s
- **Started:** 2026-07-01T03:09:45Z
- **Completed:** 2026-07-01T03:14:06Z
- **Tasks:** 3
- **Files modified:** 5 plan-relevant code files

## Accomplishments

- Added `/families/<family_slug>/pools/<pool_slug>/admin/settings/` behind `family_member_required(minimum_role=ADMIN)`.
- Added `FamilyAdminSettingsForm` and scoped POST handling for current `Family`, `Pool`, and `PoolSettings`.
- Added same-transaction `FamilyAuditLog.Action.POOL_SETTINGS_UPDATED` entries with safe before/after metadata.
- Added current-family banner metadata display without banner edit controls and without `SiteBanner` mutation/deactivation.
- Extended `FamilyAdminExperienceTests` for RED/GREEN coverage of settings authorization, forged IDs, CSRF, audit metadata, and hub navigation.

## Task Commits

1. **Task 1: Add settings authorization and scoping tests** - `85722ff` (test)
2. **Task 2: Implement scoped settings forms and mutations** - `57d7da9` (feat)
3. **Task 3: Wire admin hub/settings navigation and manual QA** - `b7bb86f` (test)

**Plan metadata:** captured in the final docs commit after STATE/ROADMAP updates.

## Files Created/Modified

- `pickem/pickem_homepage/forms.py` - Added `FamilyAdminSettingsForm`.
- `pickem/pickem_homepage/views.py` - Added settings metadata helper, settings route handler, and admin hub settings link target.
- `pickem/pickem_homepage/urls.py` - Added tenant admin settings URL.
- `pickem/pickem_homepage/templates/pickem/family_admin_settings.html` - Added settings UI and read-only current-family banner metadata.
- `pickem/pickem_homepage/tests.py` - Added settings authorization, scoping, audit, CSRF, banner, and hub navigation coverage.

## Decisions Made

- Used `POOL_SETTINGS_UPDATED` as the generic Phase 5 settings audit action for Family, Pool, and PoolSettings edits.
- Kept slugs stable when display names change; this avoids introducing route-breaking rename semantics.
- Displayed only current-family banner metadata read-only; no banner editing UI and no `SiteBanner` mutation path was introduced.

## Deviations from Plan

None - plan executed within the requested scope.

## Issues Encountered

- The local-server curl to `/families/smith-family/pools/smith-main/admin/settings/` returned 404 because the running development database does not contain the test fixture slugs. Authenticated owner/admin behavior was verified by Django integration tests.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None introduced by this plan. Stub scan found a pre-existing unrelated TODO in `pickem/pickem_homepage/views.py` around legacy scoring logic; it was not touched.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: tenant-admin-settings-route | `pickem/pickem_homepage/views.py` | New admin settings route accepts untrusted POST data; mitigated by `family_member_required`, server-derived tenant objects, Django form validation, CSRF, and tests. |
| threat_flag: audit-settings-metadata | `pickem/pickem_homepage/views.py` | Settings writes create audit metadata; tests assert metadata contains scoped IDs and no raw secret/CSRF data. |

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2` - 10 tests.
- PASS: `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` - no changes detected.
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - no issues.
- PASS: `git diff --check` - no whitespace errors.
- PASS: `curl -s -I --max-time 5 http://localhost:8000/families/smith-family/pools/smith-main/admin/settings/ | head -20` - local server responded; 404 expected for absent dev fixture slugs.

## Next Phase Readiness

Plan 05-03 can add member management into the admin hub. The settings route establishes the admin subpage pattern: tenant guard, command form, transaction-scoped write, safe audit log, and focused cross-family tests.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/05-family-admin-experience/05-02-SUMMARY.md`.
- Created/modified plan files exist.
- Task commits exist: `85722ff`, `57d7da9`, and `b7bb86f`.
- No tracked files were deleted by task commits.

---
*Phase: 05-family-admin-experience*
*Completed: 2026-07-01*
