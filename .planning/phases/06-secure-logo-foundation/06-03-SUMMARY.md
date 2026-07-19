---
phase: 06-secure-logo-foundation
plan: "03"
subsystem: security
tags: [django, multipart, csrf, upload-handler, webp, helm]
requires:
  - phase: 06-secure-logo-foundation
    provides: Canonical image processor and private Family.logo storage
provides:
  - Pre-CSRF, route-scoped streaming 5 MiB logo source guard
  - Tenant-locked canonical logo mutation with storage compensation
  - Accessible multipart family-logo settings control
affects: [07-commissioner-upload-and-delivery-experience, 08-private-aws-delivery-and-adversarial-verification]
tech-stack:
  added: []
  patterns: [pre-CSRF upload-handler installation, generated asset DB compensation]
key-files:
  created:
    - pickem/pickem_homepage/upload_handlers.py
  modified:
    - pickem/pickem_homepage/middleware.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/templates/pickem/family_admin_settings.html
    - infra/app/values-dev.yaml
    - infra/app/values-prd.yaml
key-decisions:
  - "Install the route-specific streaming handler immediately before CSRF rather than in the view."
  - "Use a 6m ingress envelope for multipart framing while retaining the exact 5 MiB source cap."
  - "Compensate only the newly generated storage key when row or audit persistence fails."
patterns-established:
  - "Logo source bytes reach storage only after the pure canonicalizer succeeds."
  - "Settings upload errors return the bound form without messages, redirects, or mutation."
requirements-completed: [IMG-01, IMG-02, IMG-03, IMG-04, SAFE-01]
coverage:
  - id: D1
    description: Exact 5 MiB streaming logo guard aborts the next byte with a stable error marker.
    requirement: IMG-02
    verification:
      - kind: unit
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests.test_streaming_handler_marks_and_aborts_only_after_exact_five_mib
        status: pass
    human_judgment: false
  - id: D2
    description: Authorized settings uploads are converted to a server-owned WebP and invalid bytes preserve the prior logo.
    requirement: IMG-01
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests
        status: pass
    human_judgment: false
  - id: D3
    description: The settings page presents only the multipart native chooser and static/current server imagery.
    requirement: IMG-04
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests.test_admin_uploads_only_canonical_logo_and_settings_template_is_multipart
        status: pass
    human_judgment: false
  - id: D4
    description: Development and production ingress overlays retain a 6m multipart envelope.
    requirement: SAFE-01
    verification:
      - kind: other
        ref: helm template family-pickem-{dev,prd} charts/family-pickem -f infra/app/values-{dev,prd}.yaml
        status: pass
    human_judgment: false
duration: 35 min
completed: 2026-07-18
status: complete
---

# Phase 06 Plan 03: Secure settings upload integration Summary

**Tenant-authorized family settings now stream-limit untrusted logo sources, persist only canonical WebP output, and render an accessible server-owned upload state.**

## Performance

- **Duration:** 35 min
- **Completed:** 2026-07-18
- **Tasks:** 4
- **Files modified:** 9

## Accomplishments

- Installed a route-specific upload handler before CSRF and configured both deployed ingress overlays with a 6m request envelope.
- Bound the existing tenant-admin form to `request.FILES`, canonicalized accepted images, and persisted the locked family row before recording boolean-only audit metadata.
- Added compensating deletion for a newly stored generated logo when later DB/audit persistence fails.
- Replaced the URL-shaped UI with a multipart native chooser, static/current thumbnail, safe help text, and linked error alert.

## Task Commits

1. **Task 1: Enforce the 5 MiB source limit at the edge and while Django streams the request** - `ee1bbb1`
2. **Task 2: Add focused multipart settings mutation and UI-contract tests** - `325eda6`, `3e6aec1`
3. **Task 3: Integrate canonical processing into the locked tenant settings mutation** - `588cde3`
4. **Task 4: Render the approved accessible upload foundation** - `0f70912`

## Files Created/Modified

- `pickem/pickem_homepage/upload_handlers.py` - Exact source-byte streaming guard.
- `pickem/pickem_homepage/middleware.py` - Pre-CSRF handler installation for only the settings route.
- `pickem/pickem_homepage/forms.py` and `views.py` - Canonical upload binding and locked persistence.
- `pickem/pickem_homepage/templates/pickem/family_admin_settings.html` - Native accessible chooser and static/current logo state.
- `infra/app/values-dev.yaml`, `infra/app/values-prd.yaml` - Nginx multipart envelope.

## Decisions Made

- The source limit is enforced by streamed chunks, not browser metadata or post-spool validation.
- A processor error returns the bound form before storage, database, audit, messaging, or redirect paths.
- Old logo objects are intentionally retained; lifecycle cleanup remains Phase 8 scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Test isolation] Use local temporary storage for integration coverage.**
- **Found during:** Task 2
- **Issue:** The dedicated S3-backed field storage correctly has no bucket configured under test settings, so an integration save would attempt a live storage connection.
- **Fix:** The focused integration test swaps only its field instance to a temporary local `FileSystemStorage` and restores it during cleanup.
- **Verification:** Focused and full homepage/API logo suites pass without AWS access.
- **Committed in:** `325eda6`

**Total deviations:** 1 auto-fixed (1 Rule 3 test isolation).
**Impact on plan:** Enables the planned local-storage proof without changing production storage behavior.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required in this plan.

## Next Phase Readiness

Phase 7 can build preview/cropping UX over this server boundary. Phase 8 still owns IAM/ESO delivery policy, stale-object lifecycle, and adversarial end-to-end verification.

## Self-Check: PASSED

---
*Phase: 06-secure-logo-foundation*
*Completed: 2026-07-18*
