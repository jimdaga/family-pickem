---
phase: 06-secure-logo-foundation
plan: "01"
subsystem: security
tags: [django, pillow, image-upload, webp, validation]
requires:
  - phase: 05-family-admin-experience
    provides: Tenant-scoped family administration foundation
provides:
  - Decoder-verified JPEG, PNG, and WebP canonicalization into fresh 256px WebP assets
  - Stable validation codes for hostile, oversized, malformed, and invalid-crop inputs
  - Isolated regression coverage for source-byte, pixel, metadata, and decoder boundaries
affects: [06-02, 06-03, 07-commissioner-upload-and-delivery-experience]
tech-stack:
  added: []
  patterns: [verify-reopen-load image validation, fresh WebP canonicalization, strict square crop validation]
key-files:
  created:
    - pickem/pickem_api/logo_processing.py
    - pickem/pickem_api/tests/test_logo_processing.py
  modified:
    - pickem/pickem_api/tests/__init__.py
    - pickem/pickem_api/tests/legacy.py
key-decisions:
  - "Trust Pillow decoder verification and a restricted reopen, never upload metadata, names, or MIME claims."
  - "Reject more than 16,000,000 advertised pixels before load or image transforms."
  - "Use one fresh 256x256 WebP output with no copied source metadata."
patterns-established:
  - "Logo processing remains a pure service without HTTP, model, storage, or AWS coupling."
  - "Image test modules live in a package while legacy dotted test labels remain re-exported."
requirements-completed: [IMG-01, IMG-02, IMG-03, SAFE-01]
coverage:
  - id: D1
    description: Decoder-verified JPEG, PNG, and WebP inputs become generated 256px WebP files.
    requirement: IMG-01
    verification:
      - kind: unit
        ref: pickem_api.tests.test_logo_processing.FamilyLogoProcessorTests.test_decoder_verified_jpeg_png_and_webp_become_fresh_webp
        status: pass
    human_judgment: false
  - id: D2
    description: Hostile, malformed, spoofed, oversized, and decompression-risk inputs fail with stable validation codes before transforms.
    requirement: IMG-02
    verification:
      - kind: unit
        ref: pickem_api.tests.test_logo_processing.FamilyLogoProcessorTests
        status: pass
    human_judgment: false
  - id: D3
    description: Strict client crop rectangles are bounded squares and canonical output contains no copied source metadata.
    requirement: IMG-03
    verification:
      - kind: unit
        ref: pickem_api.tests.test_logo_processing.FamilyLogoProcessorTests.test_crop_contract_requires_strict_bounded_square_integer_rectangle
        status: pass
      - kind: unit
        ref: pickem_api.tests.test_logo_processing.FamilyLogoProcessorTests.test_fresh_webp_omits_source_png_text_metadata
        status: pass
    human_judgment: false
  - id: D4
    description: The pure processor has no database, storage, AWS, or HTTP persistence seam.
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "cd pickem && ../venv/bin/python manage.py test pickem_api.tests.test_logo_processing --settings=pickem.test_settings --verbosity=2"
        status: pass
    human_judgment: false
duration: 7 min
completed: 2026-07-18
status: complete
---

# Phase 06 Plan 01: Specify the pure processor’s allowed and hostile inputs Summary

**A fail-closed Pillow boundary now converts only decoder-proven JPEG, PNG, and WebP uploads into fresh 256px WebP assets.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-18T21:13:00Z
- **Completed:** 2026-07-18T21:20:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added a pure image processor with byte, decoded-pixel, format, crop, and decompression protections.
- Re-encodes all accepted images into generated WebP output without source metadata, filename, or byte reuse.
- Added in-memory security regression tests and preserved existing `pickem_api.tests.*` labels while introducing focused test modules.

## Task Commits

1. **Task 1: Specify the pure processor’s allowed and hostile inputs** - `9de3240` (test)
2. **Task 2: Implement bounded decoder verification and canonical WebP generation** - `ebd5ed2` (feat)

## Files Created/Modified

- `pickem/pickem_api/logo_processing.py` - Bounded decoder verification, crop validation, and generated WebP canonicalization.
- `pickem/pickem_api/tests/test_logo_processing.py` - In-memory allowed-format and hostile-input regression suite.
- `pickem/pickem_api/tests/__init__.py` - Re-exports legacy tests after modularizing the test location.
- `pickem/pickem_api/tests/legacy.py` - Previous API test suite retained under the package.

## Decisions Made

- Decoder verification and a restricted reopen are the acceptance boundary; browser filename and MIME claims are ignored.
- The explicit 16 MP limit is checked before `load()`, EXIF normalization, crop, or resize.
- Canonical output is always generated as a fresh 256x256 WebP asset.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking test layout] Converted the legacy API test module into a package.**
- **Found during:** Task 1 (Specify the pure processor’s allowed and hostile inputs)
- **Issue:** The required `pickem_api.tests.test_logo_processing` dotted label cannot coexist with the existing `pickem_api/tests.py` module without hiding the legacy suite.
- **Fix:** Moved the legacy module to `tests/legacy.py` and re-exported it from `tests/__init__.py`, preserving existing dotted test labels.
- **Files modified:** `pickem/pickem_api/tests/__init__.py`, `pickem/pickem_api/tests/legacy.py`
- **Verification:** `pickem_api.tests.UserProfileModelTest` ran successfully under its historical dotted label.
- **Committed in:** `9de3240` (part of Task 1)

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking test layout).
**Impact on plan:** Necessary to add the required focused test module without losing the pre-existing API test suite; no product scope expanded.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 06-02 and 06-03 can use `process_family_logo()` as the only image-byte acceptance boundary before storage and form integration.

## Self-Check: PASSED

---
*Phase: 06-secure-logo-foundation*
*Completed: 2026-07-18*
