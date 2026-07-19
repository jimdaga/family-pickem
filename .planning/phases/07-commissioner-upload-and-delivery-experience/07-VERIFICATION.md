---
phase: 07-commissioner-upload-and-delivery-experience
verified: 2026-07-19T02:05:00Z
status: human_needed
score: 6/8 must-haves verified
behavior_unverified: 2
behavior_unverified_items:
  - truth: "An authorized commissioner can use the fixed-square Cropper editor to preview, drag/reposition, zoom, reset, clear, replace, and stage removal without a network mutation before Save settings."
    test: "Use an authenticated family-admin settings page with transparent, opaque, and EXIF-rotated images at desktop and mobile widths; inspect the Network panel before Save and exercise Reset, Clear selection, replacement, removal cancel/confirm, and pagehide."
    expected: "Only the normal multipart Save settings request mutates state; a selected object's URL and Cropper v2 subtree are gone after every disposal transition; rotated JPEGs submit no crop fields and use the server-centred crop."
    why_human: "The repository has no browser DOM test harness, and this verifier has no available Node REPL browser runtime. Django tests cannot exercise browser-managed File, object-URL, custom-element, pointer, or pagehide behavior."
  - truth: "The commissioned rounded-square crop/editor and compact logo marks remain usable and visually intentional for transparent and opaque logos in light/dark and mobile layouts."
    test: "Inspect the authenticated settings page, family picker, and family lobby after a successful save and after removal at desktop and mobile widths."
    expected: "Settings shows the 96px rounded-square neutral editor; picker/lobby show the compact neutral h-8 w-8 mark beside its visible family name, with the shared default fallback after removal."
    why_human: "Rendered responsive layout and visual treatment cannot be established by server-rendered template assertions."
---

# Phase 7: Commissioner Upload and Delivery Experience — Verification Report

**Phase Goal:** Replace the logo URL field with a clear commissioner flow that previews, crops, saves, replaces, removes, and renders a processed family logo.

**Verified:** 2026-07-19

**Status:** human_needed — no implementation gap was found, but the two browser-dependent interaction/visual truths must not be represented as automated proof.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | An authorized family owner/admin can select a local image and see a fixed-square Cropper.js preview with zoom/reposition controls on the existing settings page. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | The native multipart chooser, local Cropper 2.1.1 assets, fixed-square component construction, zoom/reset controls, and local-only state controller are present and wired in `family_admin_settings.html` and `family-logo-editor.js`. `node --check` passes. Actual custom-element/pointer behavior needs browser UAT. |
| 2 | Save, replacement, and removal preserve tenant context, provide useful errors, and render the persisted logo/default consistently. | ✓ VERIFIED | `FamilyAdminSettingsForm.clean()` rejects partial/malformed crop fields and replacement+removal tampering; `family_pool_admin_settings` remains `family_member_required(ADMIN)`, locks tenant rows, forwards only validated crop data, preserves the old reference on error, and clears only the locked `Family.logo` reference for removal. The 63 focused tests include crop forwarding, old-reference preservation, removal/audit, and upload/removal cross-surface rendering. |
| 3 | Browser behavior cannot replace server validation; templates render only the controlled processed URL or static fallback with safe image handling. | ✓ VERIFIED | No direct upload API, `fetch`, `FormData`, canvas output, `getCroppedCanvas`, or v1 `destroy()` is present in the editor. The only form mutation is normal multipart Save settings. The Phase 6 pre-CSRF route-specific upload limiter remains before Django CSRF middleware; the server canonicalizer remains the sole decoder/re-encoder. Templates branch only on `Family.logo.url` or `{% static 'images/familypickem.png' %}`. |
| 4 | The former arbitrary family-logo URL entry path is absent from the commissioner experience. | ✓ VERIFIED | `rg logo_url` finds no live Family model/form/view/template reference; remaining matches are historical migrations, unrelated email/NFL-template variable names, and negative assertions. The settings template exposes only the native `logo` chooser. |
| 5 | A normal multipart POST accepts only an original file with either no crop mapping or four strict equal, non-negative decimal crop integers. | ✓ VERIFIED | `FamilyAdminSettingsForm` creates `crop_data` only for a complete ASCII-decimal square mapping; server-side `process_family_logo` revalidates bounds after EXIF normalization. Focused tests cover valid forwarding, partial/non-square failures, and old-logo preservation. |
| 6 | A confirmed removal is staged until Save; forged replacement/removal is rejected and cannot discard the existing asset reference. | ✓ VERIFIED | Client state sets hidden `remove_logo` only after the exact native confirmation; normal submit is the sole commit. Server rejects simultaneous `logo`/`remove_logo`, and the focused integration test proves the stored reference is preserved. |
| 7 | Cropper assets are local and pinned, not CDN-hosted; local preview data is never serialized as upload bytes or server markup. | ✓ VERIFIED | `cropperjs: 2.1.1` is exact and integrity-locked in `package-lock.json`; `npm run build:logo-editor-assets` copies the local package to static vendor paths. The static controller only calls `URL.createObjectURL`, writes four integer fields, and submits the native file. Server-rendered source tests reject `blob:` and legacy URL values. |
| 8 | Cropper object-URL/component cleanup, EXIF safe fallback, and rounded-square light/dark/mobile presentation hold during real browser transitions. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | The controller removes the v2 subtree, clears its source, nulls references, revokes the object URL on replace/clear/remove/pagehide, and clears crop fields for non-upright JPEG EXIF orientation. These transition/visual claims have no executable browser test. |

**Score:** 6/8 truths verified; 2 present but behavior-unverified; 0 failed.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `package.json` / `package-lock.json` | Pinned local Cropper dependency and reproducible asset build | ✓ EXISTS + SUBSTANTIVE | Exact `cropperjs@2.1.1`; lockfile has registry integrity; static build completes and emitted JS is nonempty. |
| `pickem/pickem_homepage/forms.py` | Strict crop/removal form contract | ✓ EXISTS + SUBSTANTIVE | `FamilyAdminSettingsForm` explicitly declares crop fields and removal field; its `clean()` is wired by the settings route. The generic artifact tool's “missing export” is a Python false positive, not a missing class. |
| `pickem/pickem_homepage/views.py` | Locked tenant crop forwarding and removal persistence | ✓ EXISTS + SUBSTANTIVE | `family_pool_admin_settings` is a real decorated view, uses locks/transactions/audit, calls `process_family_logo`, and is routed by Django. The generic “missing export” result is likewise a Python false positive. |
| `family_admin_settings.html` | Accessible no-JS baseline and enhancement hooks | ✓ EXISTS + SUBSTANTIVE | Multipart form, visible chooser/help/errors, hidden crop/removal fields, controlled current/default branch, local assets, and action hooks are all rendered. |
| `family-logo-editor.js` | Local-only guarded Cropper v2 controller | ✓ EXISTS + SUBSTANTIVE | 262-line controller has no remote/direct-upload path, composes registered v2 elements, and supplies staged-state/lifecycle logic. Functional custom-element behavior is routed to human UAT. |
| `family_picker.html` / `family_pool_home.html` | Compact accessible controlled family marks | ✓ EXISTS + SUBSTANTIVE | Both template variants use the same canonical-or-static branch, bounded `h-8 w-8` rounded-square/object-contain frame, and `alt="" aria-hidden="true"` adjacent to visible names. |
| `pickem/pickem_homepage/tests.py` | Server, render, and delivery regressions | ✓ EXISTS + SUBSTANTIVE | `FamilyLogoUploadFoundationTests` covers form, POST, tampering, audit, settings/picker/lobby delivery, fallback, and accessibility contracts. |

**Artifacts:** 7/7 substantive and wired. No stub or placeholder implementation was found.

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Native file input + hidden crop fields | `FamilyAdminSettingsForm.clean()` | Ordinary multipart POST | ✓ WIRED | Template field names match declared form fields; view binds `request.POST` and `request.FILES`; form produces only strict `crop_data`. |
| Validated form crop/file | `process_family_logo()` | Locked authorized settings view | ✓ WIRED | View invokes the Phase 6 canonicalizer only with `form.cleaned_data['logo']` and `crop_data`. |
| Staged removal hidden field | locked `Family.logo` reference | Regular Save settings POST | ✓ WIRED | Client only stages; server clears the locked reference inside the existing transaction and audit path. |
| `Family.logo` | settings/picker/lobby image rendering | `.url` branch; static fallback otherwise | ✓ WIRED | All three agreed surfaces use `Family.logo.url` only when present; no originals, old URL field, or browser object URL is rendered. |
| Local file selection | Cropper v2 preview / cleanup lifecycle | object URL, component subtree removal, `pagehide` | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Static wiring is substantive and no forbidden alternate transport is present, but browser transitions require the human checks below. |

**Wiring:** 4/5 verified; 1 behavior-unverified; none unwired.

## Requirements Coverage

| Requirement | Status | Evidence / blocking issue |
|---|---|---|
| LOGO-01: authorized commissioner selects a local image instead of URL | ✓ SATISFIED | Admin-only tenant route, native file chooser, and legacy URL field removal are covered by settings tests. |
| LOGO-02: preview, zoom, reposition, fixed-square crop | ? NEEDS HUMAN | Controller and local Cropper v2 wiring exist, but actual interaction/EXIF behavior has no browser automation. |
| LOGO-03: save, replace, remove, return to default | ✓ SATISFIED | Server integration covers save/replacement/removal and audit; local staged interactions need the browser check listed below. |
| LOGO-04: bounded rendering with accessible fallback/alt | ? NEEDS HUMAN | Source/template contracts are verified; final responsive visual appearance needs inspection. |
| S3-04: controlled correctly typed processed delivery; originals not served from app origin | ✓ SATISFIED (Phase 7 scope) | Phase 6 canonicalizer writes generated WebP only; `FamilyLogoStorage` supplies `ContentType: image/webp` and private signed URLs; Phase 7 templates only render generated `.url` or static fallback. Phase 8 still owns IAM/ESO and hostile authorization/lifecycle audits. |

## Security and Scope Audit

- **Tenant/CSRF/size safety retained:** the settings view remains family-admin protected; `FamilyLogoUploadHandlerMiddleware` is still ordered before `CsrfViewMiddleware`; normal Django CSRF remains on the multipart form.
- **No direct browser storage/upload:** no `fetch`, `XMLHttpRequest`, `FormData`, canvas export, or separate POST/delete code is present in the editor.
- **No URL/filename/object-key control:** no live `logo_url` path remains; templates read server-owned `Family.logo` only.
- **Package provenance:** the local vendor JS identifies Cropper.js 2.1.1; lockfile resolves the official npm tarball with integrity; no Cropper CDN reference exists.
- **Phase fences respected:** no IAM/ESO changes, public endpoint, signed-url policy rewrite, adversarial cross-family matrix expansion, or old-object deletion was introduced.

## Anti-Patterns Found

None blocking.

The generic artifact checker reported two “Missing export” warnings for Python symbols in Plan 07-01. Manual source inspection confirms `class FamilyAdminSettingsForm` and `def family_pool_admin_settings` exist and are used; this is tool-language mismatch, not an application defect.

## Automated Evidence

- `node --check pickem/pickem_homepage/static/js/family-logo-editor.js` — passed.
- `npm run build:logo-editor-assets` — passed; generated local Cropper JS/CSS paths exist and JS is nonempty.
- `npm run build:css:once` — passed (only existing Browserslist freshness warnings).
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyLogoUploadFoundationTests --settings=pickem.test_settings --verbosity=1` — passed, 63 tests.
- `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=1` — passed, 644 tests with 4 expected skips.
- `manage.py check` and `makemigrations --check --dry-run` under test settings — passed; no migration changes.
- `git diff --check` — passed.
- `curl http://localhost:8000/` — returned HTTP 200 public HTML. Authenticated renderer/crop interaction cannot be exercised with curl alone.

## Human Verification Required

### 1. Crop/editor and lifecycle

**Test:** As a family owner/admin, open Admin Settings at desktop and mobile widths. Select transparent and opaque files; drag/reposition, adjust zoom, Reset, select a replacement, Clear selection, confirm/remove, decline removal, and navigate away after each state.

**Expected:** The local editor is a large neutral rounded square with dimmed outside region; Reset retains the selected file; Clear restores the saved/default server mark; confirmation text is exactly “Remove family logo? Your family will use the default logo after you save settings.”; no network mutation occurs before Save; picker/lobby stay unchanged until redirect after Save.

**Lifecycle check:** In browser devtools, confirm the prior Cropper component subtree disappears and its `blob:` URL is no longer loadable after replacement, clear, removal, and `pagehide`.

### 2. EXIF and rejected-file behavior

**Test:** Select an EXIF-rotated JPEG and submit; then submit an invalid image while changing a normal setting.

**Expected:** The rotated image either has demonstrably aligned crop coordinates or sends no crop fields so the server uses centered crop. After rejection, ordinary edits and prior server logo remain, error is associated with the chooser, and the browser requires choosing the file again.

### 3. Persisted rendering/accessibility

**Test:** Save a valid logo, then inspect settings, family picker, and family lobby in light/dark and mobile/desktop; repeat after staged removal followed by Save.

**Expected:** Settings has its 96px editor preview; picker/lobby each show a compact rounded-square mark beside visible family name with decorative empty alt text; transparent and opaque marks look intentional; post-removal all surfaces use the same default Family Pick'em mark.

## Deferred to Phase 8

Least-privilege S3 IAM/prefix policy, ESO/AWS Secrets Manager delivery, the full hostile authorization matrix, and physical stale-object cleanup are deliberately outside this phase. They are tracked as S3-02, S3-03, SAFE-02, and SAFE-03 in Phase 8.
