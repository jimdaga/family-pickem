---
phase: 6
slug: secure-logo-foundation
status: approved
reviewed_at: 2026-07-18
shadcn_initialized: false
preset: none
created: 2026-07-18
---

# Phase 6 — UI Design Contract

> Visual and interaction contract for the safe logo foundation. This phase replaces the unsafe URL-shaped control with a constrained, accessible upload placeholder; it does **not** implement the Phase 7 Cropper.js preview, zoom, or repositioning workflow.

---

## Scope and Interaction Boundary

The work belongs on the existing tenant-scoped **Family Admin → Settings** page (`family_admin_settings.html`), inside Basic Settings, where the current “Family logo URL” control appears. It is available only through the existing admin/owner authorization route; there is no global commissioner console flow.

Phase 6 creates the display and server-form contract needed for the secure foundation:

- Replace the URL text field with a clearly labelled native file input named for the logo upload; retain the normal multipart form and CSRF token.
- Accept/help only `JPEG, PNG, or WebP` and communicate the initial guardrails: “Maximum file size: 5 MB. Images are processed into a square logo.” The server remains authoritative for every check.
- Provide an informational, non-interactive square logo placeholder (or current processed-logo thumbnail if one exists) beside/above the file input. It visually establishes the eventual 1:1 output without implying browser-side crop is active.
- On a server validation failure, preserve the other settings fields, place the error immediately after the upload field, and do not claim that an image was saved. The browser must not attempt to preview arbitrary selected bytes in Phase 6.
- On a successful settings save that includes a valid logo, use the established “Settings updated.” success message and render only the generated processed-logo reference on the next response.

The native chooser may visually filter to `.jpg,.jpeg,.png,.webp` using `accept`, but copy and implementation must state this is a convenience filter, not security validation.

### Explicit Phase 7/8 Fence

- **Phase 7:** Cropper.js, immediate local-image preview, a crop overlay, zoom/reposition controls, replace/remove interactions, controlled asset delivery, and all consumer-surface logo rendering.
- **Phase 8:** audit-event copy, obsolete-object cleanup states, IAM/ESO setup, and adversarial tenant/CSRF lifecycle verification.
- No drag-and-drop zone, image bytes rendered in a `blob:` preview, client-side MIME trust, direct-to-S3 upload, generic URL entry, or user-controlled storage key belongs to Phase 6.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable |
| Component library | none — Django templates and existing Tailwind utilities |
| Icon library | Font Awesome (existing use: `fa-image`, `fa-upload`, `fa-circle-info`) |
| Font | Inter, Urbanist, system-ui, sans-serif |

Use existing project classes and tokens rather than adding a new component system. The existing Settings card establishes the pattern: `rounded-lg border border-border-light dark:border-border-subtle bg-white dark:bg-surface shadow-sm`, with `p-5` inner content and Tailwind responsive grid utilities.

---

## Layout and Visual Hierarchy

1. Keep the page header and Basic Settings card unchanged.
2. Replace the full-width URL-field row with a full-width “Family logo” section (`md:col-span-2`) after the family/pool-name fields.
3. The section starts with a `text-sm font-semibold` label and a one-line explanation in the existing muted `text-xs` style. Do not make the upload treatment visually louder than the “Save Settings” action.
4. Below it, use a compact responsive row: a 96×96px (`w-24 h-24`) square preview/placeholder at the leading edge; upload field and help/error copy at the trailing edge. On narrow screens it stacks with the preview first. The preview uses `rounded-lg`, `border-border-light`, `bg-gray-50`, and dark counterparts; its contents use `object-contain` rather than crop, because Phase 6 is not the cropper experience.
5. The file input retains browser-native affordance and must carry the project’s standard input treatment (`input-base` or equivalent `w-full ... focus:ring-2 focus:ring-primary/20`). Do not invent a custom clickable card that hides keyboard/file-picker behavior.
6. Keep the existing footer placement and primary action: `Save Settings` remains the only submit CTA. Phase 6 does not add a separate Upload button.

### States

| State | Visual and behavioral contract |
|-------|-------------------------------|
| No saved logo | A bordered 96px square shows the existing default Family Pick'em mark, with alt text `Family Pick'em default logo`. Text below the label says the default is used until a processed image is saved. |
| Saved processed logo | The same fixed square displays the server-generated image with `object-contain`; alt text is `{family name} logo`. Never render an old external URL. |
| File selected (pre-submit) | Keep the placeholder/current server image. The native chooser displays its selected filename according to browser convention; adjacent text says `Your image will be checked and prepared after you save settings.` No browser preview/crop state is asserted. |
| Server validation error | Give the input an error border/ring (`border-red-600 focus:ring-red-500/20` light; `dark:border-red-400`) and a `text-red-600 dark:text-red-400` message directly below. Keep an error icon optional but never use color as the only signal. |
| Successful save | Use the existing Django messages surface, then show the new canonical thumbnail after redirect. Do not reveal internal S3 bucket names, object keys, decoder details, or validation implementation. |

---

## Spacing Scale

Declared values are existing multiples of 4.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon-to-copy and error-icon gaps |
| sm | 8px | Label-to-help and input-to-error spacing |
| md | 16px | Preview-to-control gap; compact section spacing |
| lg | 24px | Grid/section separation inside Basic Settings |
| xl | 32px | Header-level layout gaps |
| 2xl | 48px | Major section breaks |
| 3xl | 64px | Page-level spacing |

Exceptions: the 96px square preview is deliberate fixed media geometry (`w-24 h-24`), not a new general spacing token.

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 14px (`text-sm`) | 400 | 1.5 |
| Label | 14px (`text-sm`) | 600 | 1.5 |
| Heading | 20px (`text-xl`) | 600 | 1.25 |
| Display | 30px (`text-3xl`) | 600 | 1.2 |

Helper/constraint text uses the established 12px `text-xs`, regular weight, muted color. Validation text uses 14px `text-sm font-semibold`, matching other settings fields. Do not use all caps for the field label; reserve existing small uppercase styling for page context (“Family Admin”).

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#F0F2F5` light / `#0B0E13` dark | Page background |
| Secondary (30%) | `#FFFFFF` light / `#121821` dark | Settings card and upload preview surface |
| Accent (10%) | `#0B3D91` light / `#3B82F6` dark | Save Settings button, focused file field, informational icon only |
| Destructive | `#DC2626` light / `#F87171` dark | Invalid-upload border and error text only |

Accent is reserved for the primary save action, keyboard focus indication, and non-error informational affordances. It must not be used to represent an unsaved image as secure or complete. Preserve the project token classes (`bg-primary`, `focus:ring-primary/20`, `text-text-secondary-light dark:text-text-secondary`) instead of hard-coded substitutes.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Field label | `Family logo` |
| Field help | `Choose a JPEG, PNG, or WebP image up to 5 MB. We’ll securely process it into a square logo when you save settings.` |
| No-logo supporting text | `Your family is using the default Family Pick'em logo.` |
| Selected-file supporting text | `Your image will be checked and prepared after you save settings.` |
| Primary CTA | `Save Settings` |
| Empty state heading | `Use your family logo` |
| Empty state body | `Choose an image below, then save settings. The default logo stays in place until a valid image is saved.` |
| Unsupported-file error | `Choose a JPEG, PNG, or WebP image, then try again.` |
| File-too-large error | `Choose an image smaller than 5 MB, then try again.` |
| Invalid-image error | `We couldn’t safely read that image. Choose a different JPEG, PNG, or WebP file.` |
| Crop-data error (defense-only) | `The logo selection could not be processed. Choose the image again and save settings.` |
| Destructive confirmation | Not applicable in Phase 6; logo removal is Phase 7. |

Error copy states the correction path without exposing a raw Pillow exception, MIME claim, storage path, URL, object name, or tenant detail.

---

## Accessibility Contract

- Use a visible `<label for>` tied to the native file input; do not rely on placeholder text or icon-only controls.
- Use `accept="image/jpeg,image/png,image/webp"` as a chooser hint and `aria-describedby` pointing to the help text and, when present, the field error.
- The error element uses `role="alert"` (or an equivalent page-level alert strategy) and has a stable ID. It follows the input in DOM order so keyboard and screen-reader users encounter it with the control.
- On a failed POST, focus the invalid logo input when it is the first error; otherwise preserve the project’s normal first-invalid-field focus behavior. Do not automatically open the file picker.
- The preview is informative: current/default image has meaningful alt text; a decorative upload icon is `aria-hidden="true"`. The preview container must not be a focusable pseudo-button in Phase 6.
- Maintain a visible `focus:outline-none focus:ring-2 focus:ring-primary/20` focus indicator and normal browser keyboard activation for the native input. Color alone never communicates validation or selected-file state.
- Error and helper text meet existing light/dark contrast conventions (`text-red-600 dark:text-red-400`; `text-text-secondary-light dark:text-text-secondary`).

---

## Security-Visible Behavior

The UI must make the safety boundary understandable without disclosing internals:

- Describe allowed formats and file-size constraint before selection.
- Say that the image is checked/processed after submission; never suggest that `accept`, an extension, or a browser preview proves it is safe.
- Never offer a URL text field, editable object key, “paste image link,” or form value that implies a commissioner controls tenancy or storage location.
- Render only default/static or canonical server-provided logo data. Do not reintroduce `onerror` fallbacks to external URLs or raw selected-file previews.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not applicable |
| third-party registry | none | not applicable |

No package or component registry is introduced. Cropper.js evaluation and any related browser asset belong to Phase 7.

---

## Verification Checklist

- [ ] The former `Family logo URL` label, text input, URL help text, and arbitrary external URL copy are absent from the Family Admin Settings response.
- [ ] The logo control has a visible label, native file input, chooser `accept` hint, allowed-format/5 MB help text, and a square default/current server-image state.
- [ ] Validations use the defined concise correction copy, are associated to the input, and are announced/focusable without exposing technical or storage details.
- [ ] At mobile width, preview, file control, help, and error stack in logical order; at `md` and above, they align without making the file input too narrow.
- [ ] No selected-file browser preview, crop/zoom/reposition UI, remove action, direct S3 interaction, or user-controlled URL/key is implemented in this phase.
- [ ] Light and dark states reuse established Tailwind tokens and retain keyboard focus/contrast behavior.

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** pending
