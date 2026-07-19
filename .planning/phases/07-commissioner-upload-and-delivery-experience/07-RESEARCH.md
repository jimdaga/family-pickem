# Phase 7 Research: Commissioner Upload and Delivery Experience

**Phase goal:** Add the commissioner-facing preview, fixed-square crop, staged replace/remove, and bounded family-logo rendering experience without weakening the Phase 6 server-side upload boundary.

## User Constraints

### Crop editor
- **D-01:** Use a large rounded-square preview with drag-to-reposition and a simple zoom slider.
- **D-02:** Keep a fixed square crop with a dimmed outside area; rounded corners are display treatment, not a circular crop.
- **D-03:** Crop changes are staged locally and commit only through the existing Save settings action; no separate Apply/upload action.
- **D-04:** A centered square crop is valid by default; crop adjustment is optional. Reset returns crop/zoom to that centered default while retaining the selected file.
- **D-05:** Transparent pixels display over the normal neutral light/dark-aware card surface; opaque images fill the same rounded-square frame.

### Save and replacement flow
- **D-06:** An unsaved replacement appears only in the crop editor. Existing saved logo rendering elsewhere does not change until Save settings succeeds.
- **D-07:** Reuse the existing redirect and standard success message after a successful create or replacement.
- **D-08:** On server validation failure, preserve non-file settings and the prior saved logo, show a clear chooser error, and require reselection of the browser-cleared file.

### Removal flow
- **D-09:** Show Remove logo only for a saved logo. It opens a confirmation: “Remove family logo? Your family will use the default logo after you save settings.”
- **D-10:** Confirmed removal is staged until Save settings; navigating away or canceling leaves the saved logo unchanged.
- **D-11:** An unsaved local replacement offers Clear selection, returning the editor to the saved/default asset; it must not delete the saved logo.

### Family-logo surfaces
- **D-12:** Render the processed logo or default fallback in settings, the family picker, and the family home/dashboard.
- **D-13:** Outside settings, use a compact rounded-square brand mark beside the family name; retain the 96px editor preview in settings.
- **D-14:** When adjacent visible text already names the family, treat the mark as decorative (`alt=""`).
- **D-15:** Missing or staged-for-removal logos use the existing default Family Pick’em mark in the same rounded-square frame.

### the agent's Discretion
- Choose the exact Cropper.js integration mechanics, responsive breakpoints, and compact rendered-logo dimensions while honoring the fixed square crop and the established Tailwind design tokens.

### Deferred Ideas
None — discussion stayed within Phase 7 scope.

## Project Constraints (from AGENTS.md)

- [VERIFIED: `AGENTS.md`] The existing development server is already available at `http://localhost:8000`; do not start another server. Validate rendered UI with `curl` and inspect HTML.
- [VERIFIED: `AGENTS.md`] Account for JavaScript-driven DOM behavior when changing CSS/templates; static HTML alone is not sufficient visual proof.
- [VERIFIED: `AGENTS.md`] Use Django ORM and established Django naming conventions; keep tenant authorization through the existing commissioner/family-admin mechanisms.
- [VERIFIED: `AGENTS.md`] Tailwind is the active UI system; extend existing Tailwind tokens/classes rather than reintroducing Bootstrap patterns.
- [VERIFIED: `AGENTS.md`] Run Django tests from `pickem` using the existing project test settings; preserve environment-based AWS configuration and do not put credentials in source.

## Standard Stack

| Concern | Decision | Why |
|---|---|---|
| Browser crop UI | [VERIFIED: Cropper.js official docs + npm registry] Add `cropperjs@2.1.1` and its distributed CSS through the repository's existing root npm/Tailwind toolchain. | The official current docs identify 2.1.1; its selection API exposes square selection coordinates and an element template with image movement/shade controls. |
| Client preview source | [CITED: https://developer.mozilla.org/en-US/docs/Web/API/URL/revokeObjectURL_static] Use `URL.createObjectURL(selectedFile)` solely for the local editor and revoke it whenever the file/editor is reset, cleared, replaced, or the page unloads. | It previews user-local bytes without a pre-save network upload and releases the browser reference afterward. |
| Crop submission | [VERIFIED: `pickem/pickem_api/logo_processing.py:38-108`] Submit four hidden normal form fields—`crop_x`, `crop_y`, `crop_width`, `crop_height`—as non-negative integer pixels in the EXIF-normalized source-image coordinate space. | `process_family_logo(uploaded_file, crop_data)` already accepts exactly `x`, `y`, `width`, and `height`, requires a bounded square, and otherwise selects a centered square. |
| Server mutation | [VERIFIED: `pickem/pickem_homepage/views.py:1302-1430`] Keep the existing regular multipart POST, pre-CSRF stream limit, tenant-admin decorator, locked row, canonicalizer, storage compensation, audit, redirect, and message path. | Phase 7 is a UI/data-binding layer, not a new API or browser-to-S3 upload path. |
| Controlled rendering | [VERIFIED: `pickem/pickem_api/models.py:55-72`, `pickem/pickem_api/storage.py:6-16`] Render only `Family.logo.url` (the server-derived canonical WebP reference) or existing static default assets; never render an original local preview after navigation and never reintroduce a URL field. | Existing private logo storage signs URLs and stores only generated `.webp` keys under `family-logos/`. |

### Package Legitimacy Audit

| Package | Evidence | Verdict | Planner action |
|---|---|---|---|
| `cropperjs` | [VERIFIED: Cropper.js official site `https://fengyuanchen.github.io/cropperjs/`; npm registry] Official documentation identifies Cropper.js 2.1.1; `npm view cropperjs version` returned `2.1.1`; GSD legitimacy check returned `OK`; no `postinstall` script was reported. | OK | Add and lock the dependency in `package.json`/`package-lock.json`; import only its official package/CSS. |

## Architecture Patterns

### 1. Use one progressively enhanced, local-only editor

1. [VERIFIED: `pickem/pickem_homepage/templates/pickem/family_admin_settings.html:64-82`] Keep the existing native, accessible file input as the no-JavaScript path; the server's default centered crop must continue to work when crop fields are absent.
2. [CITED: https://fengyuanchen.github.io/cropperjs/v2/migration.html] Instantiate Cropper.js v2 around an `img` whose source is the selected object URL. Configure a single `<cropper-selection>` with `aspectRatio=1`, `initialAspectRatio=1`, `movable`, and non-resizable selection; use the cropper shade for the dimmed outside area.
3. [CITED: https://fengyuanchen.github.io/cropperjs/v2/api/cropper-selection.html] Read the selection's `x`, `y`, `width`, and `height` on selection change / before submit, normalize only to integer source pixels, and write the four hidden fields. Preserve an exact square by deriving one side value for width and height.
4. [CITED: https://fengyuanchen.github.io/cropperjs/v2/migration.html] Implement Reset with the v2 image-transform reset plus selection reset; that returns to the centered default while retaining the selected `File` and object URL.
5. [VERIFIED: `pickem/pickem_api/logo_processing.py:95-108`] Do not use Cropper's canvas/output as upload data. Submit the original selected file plus coordinates; Pillow remains the authority that normalizes EXIF, validates bounds, crops, and emits the sole 256px WebP output.

### 2. Establish an exact coordinate contract

- [VERIFIED: `pickem/pickem_api/logo_processing.py:101-106`] The server calls `ImageOps.exif_transpose()` before validating crop coordinates, so the browser coordinate system must correspond to the orientation-normalized preview.
- [CITED: https://fengyuanchen.github.io/cropperjs/v2/migration.html] Cropper.js v2's selection exposes `x`, `y`, `width`, and `height`; its image transform/selection API is sufficient to map a visual fixed-square selection to image pixels.
- [ASSUMED: implementation detail to verify with an EXIF fixture] Decode the selected file in the browser using `createImageBitmap(file, { imageOrientation: 'from-image' })` or an equivalent orientation-normalizing raster preview before initializing Cropper. The implementation must prove an EXIF-rotated JPEG produces coordinates accepted by the server for the same apparent crop; if that cannot be guaranteed, clear crop fields and rely on the server centered crop rather than submit mismatched coordinates.
- [VERIFIED: `pickem/pickem_api/logo_processing.py:20-64`] Serialize strict base-10 integer strings (no decimal, exponential, negative, or boolean-like values). The service rejects malformed/non-square/out-of-bounds values, so client values are ergonomic hints, not authority.

### 3. Model staged replacement and staged removal as form state

1. [VERIFIED: `pickem/pickem_homepage/views.py:1335-1427`] Add a boolean `remove_logo` form field, validate it server-side, and have the existing POST path clear only the locked family logo reference on save. It must participate in change/audit metadata and preserve the replace compensation behavior.
2. [VERIFIED: `07-CONTEXT.md` D-06 through D-11] Keep three mutually exclusive client states: `saved`, `selected-file`, and `remove-staged`. A selected file clears `remove-staged`; confirmed removal clears the file input/crop fields and previews the static default; Clear selection returns to saved/default state.
3. [VERIFIED: `pickem/pickem_homepage/views.py:1302-1430`] On a rejected POST, the browser cannot retain/repopulate the file input. Re-render bound ordinary fields and old server logo, render the safe logo error, and have no JavaScript attempt to restore a File or object URL.
4. [VERIFIED: `07-CONTEXT.md` D-07] On successful create, replace, or remove, continue to redirect to the settings route and use the established `Settings updated.` message rather than adding an asynchronous/toast mutation channel.

### 4. Keep rendered marks bounded, rounded, and accessible

1. [VERIFIED: `pickem/pickem_homepage/templates/pickem/family_admin_settings.html:67-72`] Preserve the 96px (`h-24 w-24`) rounded-square, neutral `bg-gray-50 dark:bg-bg-dark`, overflow-hidden editor frame and make both current/default and local preview images `object-contain` within it.
2. [VERIFIED: `07-CONTEXT.md` D-13 through D-15] On picker/home, use a compact `h-8 w-8` (or equivalent Tailwind responsive minimum) `rounded-lg overflow-hidden object-contain` neutral frame beside the family name; use `alt=""` and `aria-hidden="true"` only when immediately adjacent family-name text is visible.
3. [VERIFIED: `pickem/pickem_homepage/templates/pickem/family_picker.html:47,89`, `family_pool_home.html:27-33`] Replace the current `rounded-full` and name-repeating alt text consistently in both picker variants and the lobby hero. Ensure the fallback path uses the same wrapper/dimensions.
4. [VERIFIED: requirements S3-04] All post-save template image `src` values must derive only from the canonical `Family.logo` or static fallback; do not expose uploaded originals, blob URLs, user filenames, or arbitrary external URLs in server-rendered HTML.

## Don't Hand-Roll

| Do not build | Use instead | Reason |
|---|---|---|
| Drag/zoom transform math, pointer gestures, crop shade | [VERIFIED: Cropper.js official docs] Cropper.js v2 selection/image/canvas components | The library supplies mobile pointer interactions, selection constraints, shade, and crop coordinate state. |
| Client-side file security/canonical output | [VERIFIED: `pickem/pickem_api/logo_processing.py`] Existing `process_family_logo` and pre-CSRF upload guard | A browser preview is bypassable; Phase 6 owns decoder verification, caps, metadata stripping, and storage. |
| A separate upload/crop endpoint or presigned browser upload | [VERIFIED: `.planning/REQUIREMENTS.md`] Existing CSRF-protected multipart settings form | Direct browser S3 writes are explicitly out of scope and would bypass the established persistence/audit seam. |
| Custom confirmation modal framework | [ASSUMED: browser-standard implementation] Native `window.confirm` for the exact removal confirmation | It supplies an accessible, dependency-free staged confirmation; no product value justifies a new modal subsystem. |
| Browser image decoding/type acceptance as validation | [VERIFIED: `pickem/pickem_api/logo_processing.py`] Server-side decoder verification and re-encoding | MIME/name/browser decoder outcomes do not establish file safety. |

## Common Pitfalls

1. **Cropper v1 snippets are incompatible with v2.** [CITED: https://fengyuanchen.github.io/cropperjs/v2/migration.html] Do not use `getData`, `setData`, `getCroppedCanvas`, or `destroy`; v2 uses `<cropper-selection>` properties/methods and image transforms.
2. **EXIF orientation can invalidate a visually correct crop.** [VERIFIED: `pickem/pickem_api/logo_processing.py:101-106`] The preview coordinate space must match Pillow's normalized source. Add a rotated-JPEG test and fail safely/fall back to the server centered crop if it does not.
3. **Object URLs are resources, not permanent saved URLs.** [CITED: https://developer.mozilla.org/en-US/docs/Web/API/URL/revokeObjectURL_static] Revoke each previous object URL once no longer used; never store it in hidden fields, localStorage, database data, or rendered markup.
4. **Do not trust hidden crop fields.** [VERIFIED: `pickem/pickem_api/logo_processing.py:38-64`] They are user controlled. The server must parse them strictly and reject them before image transform; no coercion or crop clamping belongs in the view.
5. **Keep selection and removal mutually exclusive.** [VERIFIED: `07-CONTEXT.md` D-09 through D-11] A staged removal must not silently discard a newly chosen file or delete storage before Save settings.
6. **File inputs clear after an error by browser design.** [VERIFIED: `07-CONTEXT.md` D-08] Render the previous server-controlled logo and all normal submitted fields, but require a deliberate reselect; never try to synthesize or repopulate a File.
7. **Current templates are inconsistent.** [VERIFIED: `family_picker.html:47,89`, `family_pool_home.html:27-33`] The picker currently uses `rounded-full` and family-name alt text; the lobby uses no rounded wrapper and alternate fallback asset. Phase 7 must unify the visual/fallback/accessibility contract.
8. **Old object cleanup is not a Phase 7 expansion.** [VERIFIED: `.planning/REQUIREMENTS.md`] Phase 8 owns obsolete-object lifecycle/authorization proof. Phase 7 may clear the DB reference during a saved removal but should not introduce broad deletion-policy work without its Phase 8 audit/cleanup design.

## Validation Architecture

### Automated checks

| Layer | What to prove | Test location / command |
|---|---|---|
| Form/service | Crop field contract, omitted coordinates centered, valid integer coordinates forwarded, malformed coordinates reject without changing the previous logo; staged `remove_logo` clears the DB reference only on POST. | Extend `pickem/pickem_homepage/tests.py` `FamilyLogoUploadFoundationTests` or create focused form/view tests; run `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests --settings=pickem.test_settings`. |
| Route integration | Owner/admin can create/replace/remove through the existing settings POST; invalid image keeps old reference and ordinary edits; remove is audit logged and no server-rendered original URL appears. | Focused Django test class with temporary `FileSystemStorage`, following the Phase 6 setup. |
| Template contract | Settings has multipart input, hidden crop fields, editor hooks and no external-URL field; picker/home use a compact rounded-square wrapper, canonical/default source, and empty alt where adjacent text names the family. | Django response assertions plus `rg -n 'logo_url|rounded-full|alt="{{ choice.family.name }} logo"' pickem/pickem_homepage`. |
| Frontend unit/DOM | File choose creates local preview; slider/drag update exact hidden integer coordinates; Reset recenters; Clear selection restores saved/default state; staged removal only submits on Save; object URL is revoked. | Add a small DOM-testable controller module only if the repository has a JS test harness; otherwise use browser UAT/manual verification before marking the phase complete. |
| Browser UAT | On desktop/mobile, verify drag/slider, rounded square transparency surface, confirmation wording, server error/reselection flow, redirect success, and compact picker/lobby marks. | Existing local server with the browser tool; also use `curl http://localhost:8000` to inspect server HTML as required by AGENTS.md. |

### Phase gates

- [VERIFIED: `.planning/REQUIREMENTS.md`] Phase 7 completion requires LOGO-01 through LOGO-04 and S3-04 only; do not mark S3-02/S3-03/SAFE-02/SAFE-03 complete here.
- [VERIFIED: `.planning/phases/06-secure-logo-foundation/06-VERIFICATION.md`] Retain all Phase 6 processor, multipart-size, tenant-lock, and local-storage test guarantees when adding crop/removal data binding.

## Code Examples

### Server crop adapter shape

```python
# In the form clean method: require all crop values or none.
crop_fields = ("crop_x", "crop_y", "crop_width", "crop_height")
crop_values = [cleaned_data.get(name) for name in crop_fields]
if any(value is None for value in crop_values) and any(value is not None for value in crop_values):
    raise forms.ValidationError("Choose the logo again and save settings.")
crop_data = None if all(value is None for value in crop_values) else {
    "x": crop_values[0], "y": crop_values[1],
    "width": crop_values[2], "height": crop_values[3],
}
processed_logo = process_family_logo(form.cleaned_data["logo"], crop_data)
```

- [VERIFIED: `pickem/pickem_api/logo_processing.py:78-130`] The actual form should make the all-or-none crop rule explicit and let the existing strict processor reject untrusted crop values; do not coerce or clamp in JavaScript or the view.

### Controlled source and staged state shape

```javascript
// Browser state only; never serialize objectUrl or output bytes.
const state = { objectUrl: null, mode: 'saved' }; // saved | selected-file | remove-staged

function selectFile(file) {
  cleanupObjectUrl();
  state.objectUrl = URL.createObjectURL(file);
  state.mode = 'selected-file';
  // initialize Cropper against state.objectUrl; update crop hidden inputs
}

function clearSelection() {
  cleanupObjectUrl();
  form.logo.value = '';
  clearCropHiddenFields();
  state.mode = 'saved';
  // restore current canonical/default renderer, no storage mutation
}
```

- [CITED: https://developer.mozilla.org/en-US/docs/Web/API/URL/revokeObjectURL_static] `cleanupObjectUrl()` must call `URL.revokeObjectURL()` after the editor no longer displays the URL.
- [VERIFIED: `07-CONTEXT.md` D-03, D-06, D-09 through D-11] Only the existing form submit is a commit point; state transitions above must never POST/upload/delete by themselves.

## Sources

- [CITED: https://fengyuanchen.github.io/cropperjs/] Current Cropper.js official site and version.
- [CITED: https://fengyuanchen.github.io/cropperjs/v2/migration.html] Cropper.js v2 component/model migration API, including selection/image transform/reset equivalents.
- [CITED: https://fengyuanchen.github.io/cropperjs/v2/api/cropper-selection.html] Selection coordinates, fixed aspect-ratio, movement, reset, and canvas APIs.
- [CITED: https://developer.mozilla.org/en-US/docs/Web/API/URL/revokeObjectURL_static] Object URL lifecycle.
- [VERIFIED: `package.json`, `package-lock.json`, `npm view cropperjs version`, GSD package-legitimacy check] Local dependency/toolchain and package legitimacy evidence.
- [VERIFIED: `pickem/pickem_api/logo_processing.py`, `pickem/pickem_homepage/forms.py`, `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/templates/pickem/family_admin_settings.html`, `family_picker.html`, `family_pool_home.html`, `pickem/pickem_homepage/tests.py`, `.planning/REQUIREMENTS.md`, `07-CONTEXT.md`] Project seams, phase boundary, and existing protections.

## Open Questions / Blockers

None. The planner must make the EXIF-normalized browser-preview coordinate behavior an explicit tested acceptance criterion; it is a technical implementation check, not a new product decision.
