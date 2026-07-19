---
phase: 07-commissioner-upload-and-delivery-experience
plan: "01"
subsystem: ui
tags: [django, pillow, cropperjs, image-upload, security]
requires:
  - phase: 06-secure-logo-foundation
    provides: Canonical image processor, private logo storage, and locked settings mutation
provides:
  - Strict crop and staged-removal form contract
  - Authorized crop forwarding and boolean-only removal audit data
  - Locally pinned Cropper.js 2.1.1 assets
affects: [07-02, family-logo-editor]
tech-stack:
  added: [cropperjs@2.1.1]
  patterns: [strict hidden crop validation, staged logo removal]
key-files:
  created:
    - pickem/pickem_homepage/static/vendor/cropperjs/cropper.js
    - pickem/pickem_homepage/static/vendor/cropperjs/cropper.css
  modified:
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/tests.py
    - package.json
    - package-lock.json
key-decisions:
  - "Crop coordinates are accepted only as complete ASCII decimal square mappings."
  - "Removal clears only the Family.logo reference; object lifecycle remains Phase 8 scope."
  - "Cropper.js 2.1.1 is copied from the local npm package, never loaded from a CDN."
patterns-established:
  - "Browser crop coordinates are untrusted input; Phase 6 owns final bounds validation and canonicalization."
requirements-completed: [LOGO-01, LOGO-02, LOGO-03, S3-04]
coverage:
  - id: D1
    description: Strict all-or-nothing crop fields and replacement/removal exclusion preserve the existing logo on invalid input.
    requirement: LOGO-01
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests
        status: pass
    human_judgment: false
  - id: D2
    description: Authorized cropped replacement and staged removal use the canonical processor and boolean-only audit metadata.
    requirement: LOGO-03
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests.test_remove_logo_clears_reference_and_audits_presence_only
        status: pass
    human_judgment: false
  - id: D3
    description: Cropper.js is lockfile-pinned and emitted as local static assets.
    requirement: LOGO-02
    verification:
      - kind: other
        ref: npm run build:logo-editor-assets
        status: pass
    human_judgment: false
duration: 18 min
completed: 2026-07-19
status: complete
---

# Phase 07 Plan 01: Crop and removal contract Summary

**The authorized settings mutation now accepts strict source-image crop coordinates or a staged logo removal, while local Cropper.js assets are ready for progressive enhancement.**

## Accomplishments

- Added all-or-none ASCII decimal crop fields and explicit replacement/removal mutual exclusion before any mutation.
- Forwarded only validated coordinates with the original uploaded source to the existing Phase 6 canonicalizer.
- Added locked, audited reference-only removal without deleting old storage objects.
- Pinned Cropper.js 2.1.1 and added deterministic local asset and finite Tailwind build scripts.

## Task Commits

1. **Task 1: Define strict staged crop and removal inputs** — `03ee837`
2. **Task 2: Persist crop-based replacement and staged removal** — `a923896`
3. **Task 3: Install vetted local Cropper.js package and build seam** — `e71f1f5`

## Verification

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests pickem_api.tests.test_logo_processing pickem_api.tests.test_family_logo_storage --settings=pickem.test_settings --verbosity=1` — passed (332 tests).
- `npm run build:css:once` and `npm run build:logo-editor-assets` — passed; generated local JS and CSS assets are non-empty.

## Deviations from Plan

### Auto-fixed Issues

1. **[Rule 3 - package artifact compatibility] Cropper.js 2.1.1 distributes component styles in its JavaScript bundle, not a standalone CSS file.**
   - The deterministic build emits a documented local CSS marker alongside the official local JS so the next plan has stable static paths without inventing a third-party stylesheet.

**Total deviations:** 1 auto-fixed. No security boundary or scope expansion.

## Next Phase Readiness

Plan 07-02 can load the local assets and build the progressive editor without accepting canvas/blob upload bytes. Phase 8 still owns stale-object cleanup and delivery infrastructure.

## Self-Check: PASSED
