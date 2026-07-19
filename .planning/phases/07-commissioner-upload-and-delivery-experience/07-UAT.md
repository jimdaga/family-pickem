---
status: testing
phase: 07-commissioner-upload-and-delivery-experience
source: [07-VERIFICATION.md]
started: 2026-07-19T02:05:00Z
updated: 2026-07-19T02:05:00Z
---

## Current Test

number: 1
name: Crop/editor and lifecycle
expected: |
  A local-only large neutral rounded-square editor supports drag, zoom, Reset,
  replacement, Clear selection, and staged removal with no network mutation
  before Save settings. Browser cleanup removes prior Cropper/object-URL state.
awaiting: user response

## Tests

### 1. Crop/editor and lifecycle

expected: As a family owner/admin, open Admin Settings at desktop and mobile widths. Select transparent and opaque files; drag/reposition, adjust zoom, Reset, select a replacement, Clear selection, confirm/remove, decline removal, and navigate away after each state. The editor is a large neutral rounded square with dimmed outside region; Reset retains the selected file; Clear restores the saved/default server mark; confirmation reads “Remove family logo? Your family will use the default logo after you save settings.”; no network mutation occurs before Save; picker/lobby remain unchanged until redirect after Save. In devtools, the previous Cropper component subtree and `blob:` URL disappear after replacement, clear, removal, and `pagehide`.
result: pending

### 2. EXIF and rejected-file behavior

expected: Select an EXIF-rotated JPEG and submit; then submit an invalid image while changing a normal setting. The rotated image either has aligned crop coordinates or submits none so the server applies a centered crop. On rejection, ordinary edits and the prior server logo remain, the chooser receives its error, and the file must be selected again.
result: pending

### 3. Persisted rendering and accessibility

expected: Save a valid logo and inspect settings, family picker, and family lobby in light/dark and mobile/desktop; repeat after staged removal followed by Save. Settings has its 96px editor preview; picker/lobby use a compact rounded-square decorative mark beside visible family name; transparent and opaque marks look intentional; removal restores the same default Family Pick'em mark everywhere.
result: pending

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
