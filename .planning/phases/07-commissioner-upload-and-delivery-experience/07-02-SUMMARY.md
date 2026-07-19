---
phase: 07-commissioner-upload-and-delivery-experience
plan: 02
subsystem: ui
tags: [django, cropperjs, progressive-enhancement, image-upload]
requires:
  - phase: 07-01
    provides: Strict crop/removal form contract and local Cropper.js assets.
provides:
  - Accessible native chooser with staged local crop/replacement/removal controls.
  - Local-only Cropper.js v2 editor that submits original files and optional source-pixel coordinates.
affects: [family-logo-rendering, phase-07-plan-03]
tech-stack:
  added: []
  patterns: [local object-URL lifecycle, conservative EXIF crop fallback]
key-files:
  created:
    - pickem/pickem_homepage/static/js/family-logo-editor.js
  modified:
    - pickem/pickem_homepage/templates/pickem/family_admin_settings.html
    - pickem/pickem_homepage/tests.py
key-decisions:
  - "Keep the native multipart chooser usable without JavaScript; the existing server-centered crop remains the fallback."
  - "For EXIF-rotated JPEGs, clear browser crop coordinates so Pillow deliberately uses its safe centered crop unless alignment is demonstrable."
  - "Dispose Cropper v2 by clearing its source/removing its component subtree and revoking the object URL; never call a v1 destroy API."
patterns-established:
  - "Browser image state is local, non-authoritative, and never serialized except four strict integer crop fields."
requirements-completed: [LOGO-01, LOGO-02, LOGO-03]
coverage:
  - id: D1
    description: Accessible multipart settings markup exposes native chooser, crop fields, staged actions, and controlled server/default previews.
    requirement: LOGO-01
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests
        status: pass
    human_judgment: false
  - id: D2
    description: Cropper v2 local editor stages drag/zoom/reset/replacement/removal without a separate upload or canvas submission.
    requirement: LOGO-02
    verification:
      - kind: other
        ref: node --check pickem/pickem_homepage/static/js/family-logo-editor.js
        status: pass
    human_judgment: true
    rationale: Browser drag, responsive layout, object-URL revocation, and EXIF fallback require real-browser inspection.
  - id: D3
    description: Rejected submissions retain bound ordinary values and the old controlled server logo while requesting a new file selection.
    requirement: LOGO-03
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests.test_settings_error_keeps_bound_values_and_old_server_logo
        status: pass
    human_judgment: false
duration: 22 min
completed: 2026-07-19
status: complete
---

# Phase 07 Plan 02: Progressive crop editor Summary

**Family administrators now get a local, rounded-square Cropper.js editing experience while the existing secure multipart Save Settings path remains the sole mutation.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-19T01:10:00Z
- **Completed:** 2026-07-19T01:32:56Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added a no-JavaScript-safe settings baseline with native chooser, hidden crop/removal contract, clear validation copy, and controlled current/default imagery.
- Added the local-only Cropper.js v2 controller with a fixed square selection, zoom, reset, replacement/clear/removal state machine, object-URL cleanup, and exact staged-remove confirmation.
- Added focused render/error contract coverage; invalid requests preserve ordinary bound values and old server imagery.

## Task Commits

1. **Task 1: Render the accessible no-JS editor baseline and test its server contract** — `2f7985c`
2. **Task 2: Implement the local-only Cropper.js controller with orientation-safe fallback** — `0f35ed5`

## Automated checks

- node --check on the logo editor script — passed.
- Focused homepage Django suite under test settings — passed (325 tests).
- npm build:logo-editor-assets — passed; both local Cropper assets are non-empty.
- Django check and migration dry-run under test settings — passed.
- Template safety assertion confirmed no legacy URL field, remote Cropper CDN, or circular avatar class in the settings template.
- `curl -I http://localhost:8000` — local Django server responded 200.

## Decisions Made

- Cropper's installed UMD bundle registers v2 custom elements but does not expose its constructor as a global; the controller composes the documented v2 component elements directly and uses their `$resetTransform()`/`$reset()` APIs.
- EXIF-orientated JPEGs are deliberately submitted without crop coordinates until browser/server alignment can be demonstrated, preserving the server's centered-crop fail-safe.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - dependency artifact compatibility] The local Cropper 2.1.1 UMD asset does not export a usable global constructor.**
- **Found during:** Task 2
- **Fix:** Compose the already-registered Cropper v2 custom elements directly instead of relying on an unavailable constructor, while retaining only v2 component lifecycle methods.
- **Verification:** JS syntax check, local asset build, and focused Django suite passed.
- **Committed in:** `0f35ed5`

**Total deviations:** 1 auto-fixed. No upload/storage security boundary changed.

## Issues Encountered

- The focused suite logs expected mocked ESPN/cache failures but completes successfully.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 07-03 can apply the same compact rounded-square canonical/default rendering to the family picker and home/dashboard. Browser UAT remains required for drag/zoom behavior, object-URL lifecycle, and the EXIF-centered fallback.

## Self-Check: PASSED

---
*Phase: 07-commissioner-upload-and-delivery-experience*
*Completed: 2026-07-19*
