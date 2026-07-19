# Phase 7: Commissioner Upload and Delivery Experience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-18
**Phase:** 07-Commissioner Upload and Delivery Experience
**Areas discussed:** Crop editor, save and replacement flow, removal flow, family-logo surfaces

---

## Crop editor

| Decision | Alternatives considered | Selected |
|---|---|---|
| Editor layout | Large preview; compact preview; modal | Large preview |
| Commit point | Save settings; separate Apply; automatic | Save settings |
| Reset | Reset crop; clear selection; both | Reset crop |
| Framing | Square crop; final preview only; circular mask | Square crop with rounded display |
| Transparency | Neutral surface; white; checkerboard | Neutral light/dark-aware surface |

**Notes:** The crop remains square. Rounded corners are presentation, so transparent and opaque source images both work in the same frame.

---

## Save and replacement flow

| Decision | Alternatives considered | Selected |
|---|---|---|
| Unsaved replacement | Keep saved logo; temporary page-wide preview; hide old logo | Keep saved logo |
| Success feedback | Standard redirect/message; inline; toast | Standard redirect/message |
| Validation failure | Preserve other edits/old logo; reset; keep editor | Preserve edits/old logo |
| Default crop | Optional adjustment; require interaction; separate confirmation | Optional adjustment |

---

## Removal flow

| Decision | Alternatives considered | Selected |
|---|---|---|
| Removal control | Confirmed staged button; immediate; checkbox | Confirmed staged button |
| Commit timing | Save settings; immediate; second confirmation | Save settings |
| Unsaved selection action | Clear selection; shared removal action; hide action | Clear selection |
| Confirmation copy | Explain staged default; short; mention storage deletion | Explain staged default |

---

## Family-logo surfaces

| Decision | Alternatives considered | Selected |
|---|---|---|
| Placement | Settings/picker/home; settings/home; settings only | Settings/picker/home |
| Prominence | Compact mark; large banner; picker only | Compact mark |
| Accessible name | Decorative; family-name alt; vary by page | Decorative beside visible name |
| Fallback | Existing default; initials tile; no mark | Existing default |

## the agent's Discretion

- Exact Cropper.js wiring, responsive sizing, and compact rendered-mark dimensions.

## Deferred Ideas

None.
