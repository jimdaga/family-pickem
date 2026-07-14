# Team Logo Contrast Presets Design

## Goal

Add an admin-editable way to fix low-contrast team logos anywhere the UI places a logo on a team-color background, without requiring repeated code edits whenever teams refresh branding.

## Approved Direction

Add a `logo_contrast_preset` field to the `Teams` model and expose it in Django admin. UI rendering for brand-backed team tiles should read this preset and apply one of a small set of visual treatments.

Initial presets:

- `default`
- `reverse-gradient`
- `white-burst`

## Scope

Apply the preset only in places where:

- a team logo is shown, and
- the surrounding background uses that team's brand colors

Do not apply it on neutral surfaces such as plain cards, tables, or standalone logos without a branded background.

## Rendering Behavior

The branded tile rendering should be centralized so picks, scores, and similar team-color cards do not each implement their own slug-based exceptions.

Preset behavior:

- `default`: current gradient treatment
- `reverse-gradient`: swap the normal and alternate team colors in the branded panel
- `white-burst`: keep the existing gradient and add a soft white burst/glow behind the logo

## Admin UX

The `Teams` admin should expose the preset as a simple choice field with concise help text explaining when to use each option.

## Data and Migration

- Add the model field with a default of `default`
- Use a Django migration to backfill existing rows safely

## Testing

Add regression coverage for:

- model/admin default behavior
- the helper/template path resolving the expected preset classes
- at least one rendered branded tile showing the new treatment hooks

## Follow-Up

The same setting should later be editable from the planned superadmin page, but Django admin is the first control surface.
