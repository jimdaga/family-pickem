# Roadmap: Family Logo Uploads

**Milestone:** v1.1  
**Created:** 2026-07-18  
**Current focus:** Phase 6 — Secure Logo Foundation

## Phase 6: Secure Logo Foundation

**Goal:** Establish a tenant-safe logo data model and server-side image processing boundary before any upload UI can persist content.

**Requirements:** IMG-01, IMG-02, IMG-03, IMG-04, S3-01, SAFE-01

**Success criteria:**

1. The Family model persists a server-owned logo object reference, replacing arbitrary user-entered logo URLs without breaking default-logo fallbacks.
2. The server accepts only decoder-verified JPEG, PNG, and WebP inputs within explicit byte and pixel limits; unsupported, spoofed, malformed, and decompression-bomb inputs fail safely.
3. Crop inputs are bounded and validated; the only persisted logo is a generated fixed-size, metadata-free raster asset with a server-generated object key under `family-logos/`.
4. Tenant-aware commissioner authorization and CSRF are enforced before any logo mutation, and tests cover hostile file/crop/key/tenant input.

## Phase 7: Commissioner Upload and Delivery Experience

**Goal:** Replace the logo URL field with a clear commissioner flow that previews, crops, saves, replaces, removes, and renders a processed family logo.

**Requirements:** LOGO-01, LOGO-02, LOGO-03, LOGO-04, S3-04

**Success criteria:**

1. A family owner/admin using the existing commissioner/settings page can select a local image and see a fixed-square Cropper.js preview with zoom/reposition controls.
2. Save, replace, and remove actions preserve tenant context, surface useful validation feedback, and render the resulting logo/fallback consistently in family UI.
3. Browser behavior cannot bypass server validation; templates render only the controlled processed-asset URL with safe image response handling.
4. The former arbitrary URL entry path is removed from the commissioner experience.

## Phase 8: Private AWS Delivery and Adversarial Verification

**Goal:** Finish the production S3/ESO integration and prove the complete upload lifecycle withstands authorization, storage, and malicious-input attacks.

**Requirements:** S3-02, S3-03, SAFE-02, SAFE-03

**Success criteria:**

1. The application has prefix-limited S3 permissions for `family-logos/` without public ACL/policy access, and the existing bucket’s Block Public Access/ownership/encryption posture remains intact.
2. Development and production consume required S3 settings/credentials through the existing AWS Secrets Manager → ESO → Helm/Kubernetes flow; no credentials appear in Git or manually managed Kubernetes Secrets.
3. Tests prove unauthenticated, ordinary-member, wrong-family, forged tenant/object-key, and missing-CSRF requests cannot mutate or infer another family’s logo.
4. Create/replace/remove actions produce tenant-scoped audit entries and correctly clean up obsolete assets without deleting a currently referenced logo.

## Requirement Coverage

| Requirement | Phase | Status |
|---|---:|---|
| LOGO-01 | 7 | Pending |
| LOGO-02 | 7 | Pending |
| LOGO-03 | 7 | Pending |
| LOGO-04 | 7 | Pending |
| IMG-01 | 6 | Pending |
| IMG-02 | 6 | Pending |
| IMG-03 | 6 | Pending |
| IMG-04 | 6 | Pending |
| S3-01 | 6 | Pending |
| S3-02 | 8 | Pending |
| S3-03 | 8 | Pending |
| S3-04 | 7 | Pending |
| SAFE-01 | 6 | Pending |
| SAFE-02 | 8 | Pending |
| SAFE-03 | 8 | Pending |

**Coverage:** 15/15 requirements mapped ✓

## Phase Ordering

Phase 6 constructs the server-side security boundary first. Phase 7 adds the commissioner experience on top of canonical processed assets. Phase 8 applies least-privilege cloud delivery and validates the whole lifecycle against hostile and cross-family cases.

---
*Roadmap created: 2026-07-18 for milestone v1.1*
