# Phase 7: Commissioner Upload and Delivery Experience - Context

**Gathered:** 2026-07-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the commissioner-facing crop, preview, save/replace/remove, and controlled processed-logo rendering experience on the existing tenant-authorized family settings route. The browser may help create crop coordinates but cannot bypass Phase 6 server validation or storage controls. IAM/ESO setup, full adversarial authorization testing, and obsolete-object lifecycle cleanup remain Phase 8.

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and security boundary
- `.planning/ROADMAP.md` — Phase 7 goal, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` — LOGO-01 through LOGO-04 and S3-04 acceptance boundary.
- `.planning/phases/06-secure-logo-foundation/06-RESEARCH.md` — verified processing/storage constraints that Phase 7 must preserve.
- `.planning/phases/06-secure-logo-foundation/06-VERIFICATION.md` — Phase 6 security guarantees already proven.

### Established UX and implementation
- `.planning/phases/06-secure-logo-foundation/06-UI-SPEC.md` — existing settings-page typography, accessibility, and no-client-preview Phase 6 baseline that Phase 7 deliberately extends.
- `.planning/phases/06-secure-logo-foundation/06-01-SUMMARY.md` — pure processor crop contract and fixed WebP output.
- `.planning/phases/06-secure-logo-foundation/06-02-SUMMARY.md` — private generated storage/reference and default-rendering behavior.
- `.planning/phases/06-secure-logo-foundation/06-03-SUMMARY.md` — pre-CSRF multipart handler and locked tenant persistence seam.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pickem/pickem_api/logo_processing.py`: `process_family_logo(uploaded_file, crop_data=None)` already validates strict square crop coordinates and produces the only canonical 256px WebP output.
- `pickem/pickem_homepage/forms.py`: `FamilyAdminSettingsForm` already has the secure optional `logo` file input and MIME hint.
- `pickem/pickem_homepage/templates/pickem/family_admin_settings.html`: existing multipart form, 96px rounded-square current/default thumbnail, help/error structure, and Tailwind tokens provide the editor’s home.
- `pickem/pickem_api/models.py`: `Family.logo` points to generated private storage and has a null/default-fallback state.

### Established Patterns
- `pickem/pickem_homepage/views.py:family_pool_admin_settings` derives and locks tenant context, binds `request.FILES`, translates processor errors, compensates storage failures, and uses the standard redirect/message flow.
- Phase 6 renders only server-provided current/default imagery and deliberately has no browser-selected image preview; Phase 7 may add a local preview/crop UI but must keep server validation authoritative.
- Existing templates use Tailwind responsive utilities and dark-mode tokens; the rounded-square frame must use these rather than new visual foundations.

### Integration Points
- Extend the family settings form/view/template to carry browser crop data with the selected file, stage removal, and preserve the existing tenant/CSRF mutation path.
- Update `pickem/pickem_homepage/templates/pickem/family_picker.html` and `pickem/pickem_homepage/templates/pickem/family_pool_home.html` to use the processed controlled asset/default mark consistently.

</code_context>

<specifics>
## Specific Ideas

- The user expects many logos to be transparent. Rounded-square presentation with a neutral light/dark surface should make both transparent and opaque submissions look intentional.
- Preview and crop are useful editing affordances, not evidence that the browser file is safe or saved.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 7 scope.

</deferred>

---

*Phase: 07-Commissioner Upload and Delivery Experience*
*Context gathered: 2026-07-18*
