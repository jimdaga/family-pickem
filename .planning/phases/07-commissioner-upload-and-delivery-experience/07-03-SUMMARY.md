---
phase: 07-commissioner-upload-and-delivery-experience
plan: 03
subsystem: ui
tags: [django, templates, accessibility, image-delivery, regression-tests]
requires:
  - phase: 07-commissioner-upload-and-delivery-experience
    provides: Canonical processed-logo storage, staged removal, and local crop editor.
provides:
  - Compact canonical-or-default family marks on picker and lobby surfaces.
  - Decorative image semantics beside visible family names.
  - Cross-surface persisted upload/removal delivery regression coverage.
affects: [08-private-aws-delivery-adversarial-verification]
tech-stack:
  added: []
  patterns: [persisted-logo-or-static-fallback, decorative-adjacent-brand-mark]
key-files:
  created: []
  modified:
    - pickem/pickem_homepage/templates/pickem/family_picker.html
    - pickem/pickem_homepage/templates/pickem/family_pool_home.html
    - pickem/pickem_homepage/tests.py
key-decisions:
  - "Picker and lobby read only the persisted Family.logo URL or the shared familypickem.png fallback."
  - "Marks next to visible family names are decorative and use empty alt text with aria-hidden."
patterns-established:
  - "All non-editor family-brand surfaces use compact neutral rounded-square object-contain frames."
requirements-completed: [LOGO-03, LOGO-04, S3-04]
coverage:
  - id: D1
    description: "Picker member/superadmin choices and lobby render only persisted canonical logo URLs or the common static fallback in decorative rounded-square marks."
    requirement: LOGO-04
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests
        status: pass
    human_judgment: false
  - id: D2
    description: "A saved upload renders its canonical WebP URL across settings, picker, and lobby; persisted removal restores the static fallback without reflecting blob, legacy, or original-upload values."
    requirement: S3-04
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests.test_uploaded_and_removed_logo_render_only_persisted_canonical_or_default_sources
        status: pass
    human_judgment: false
  - id: D3
    description: "Crop interaction, responsive framing, and browser file-reselection behavior have an explicit manual UAT backstop."
    requirement: LOGO-03
    verification:
      - kind: manual_procedural
        ref: .planning/phases/07-commissioner-upload-and-delivery-experience/07-VALIDATION.md#manual-only-verifications
        status: unknown
    human_judgment: true
    rationale: "Drag/zoom, mobile layout, and browser-managed file-input reset cannot be proven by the Django integration suite."
duration: 9 min
completed: 2026-07-19
status: complete
---

# Phase 07 Plan 03: Family logo delivery Summary

**Picker and lobby now show compact, accessible family marks that resolve solely to the persisted canonical logo or the shared static fallback.**

## Accomplishments

- Replaced inconsistent picker/lobby logo markup with a common neutral rounded-square `object-contain` presentation.
- Rendered `Family.logo.url` only for a persisted logo; otherwise every agreed surface uses the existing shared Family Pick'em static-mark asset.
- Treated marks adjacent to visible family names as decorative (`alt="" aria-hidden="true"`).
- Added upload-to-render and removal-to-fallback integration coverage across settings, picker, and lobby.

## Task Commits

1. **Task 1: Unify compact controlled logo rendering on picker and family home** — `54af667`
2. **Task 2: Run Phase 7 integration regression and record final validation evidence** — `63c297a`

## Verification

- Focused `FamilyLogoUploadFoundationTests`: passed, 63 tests.
- Full Django suite: passed, 644 tests with 4 expected skips.
- Django checks and migration dry run: passed with no pending migrations.
- `npm run build:css:once`, `npm run build:logo-editor-assets`, and `git diff --check`: passed.
- Local public-page curl: HTTP 200 with expected Family Pick'em HTML.

## Decisions Made

- The static default mark matches the settings editor rather than the older inconsistent public-site mark used by earlier picker/lobby markup.
- The logo remains display-only outside settings; browser-local crop or removal state cannot change picker/lobby until the authorized settings POST succeeds and redirects.

## Deviations from Plan

### Auto-fixed Issues

1. **[Rule 1 - verification command precision] Narrowed the planned legacy-mark source check to logo markup instead of rejecting unrelated circular UI elements.**
   - **Issue:** The plan's broad `rounded-full` search matched badges, avatars, and unrelated lobby decoration.
   - **Fix:** Kept the actual source/alt legacy checks strict and covered the changed logo frames with integration assertions.
   - **Verification:** Focused and full Django suites passed.

**Total deviations:** 1 auto-fixed. No security boundary or Phase 8 infrastructure scope changed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 8 can now focus on private AWS delivery, ESO/IAM, adversarial authorization verification, and object lifecycle without changing the browser upload or surface-rendering contract. Manual browser UAT for crop interaction and rejected-file reselection remains pending and is documented in `07-VALIDATION.md`.

## Self-Check: PASSED

---
*Phase: 07-commissioner-upload-and-delivery-experience*
*Completed: 2026-07-19*
