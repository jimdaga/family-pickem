# Requirements: Family Pickem — Family Logo Uploads

**Defined:** 2026-07-18  
**Core Value:** Families can run private pick'em pools with strict server-enforced data isolation.

## v1.1 Requirements

### Logo Experience

- [x] **LOGO-01**: An authorized family commissioner can select a local image from the family commissioner/settings page instead of entering a logo URL.
- [x] **LOGO-02**: Before saving, the commissioner can preview, zoom, reposition, and apply a fixed square crop to the selected logo.
- [x] **LOGO-03**: A commissioner can save a new logo, replace the current logo, or remove it and return the family to the default logo.
- [ ] **LOGO-04**: Family surfaces render the saved processed logo at the intended bounded display size with an accessible fallback/alt text.

### Image Security And Processing

- [x] **IMG-01**: The server accepts only decoder-verified JPEG, PNG, or WebP raster images; it rejects SVG, GIF, HTML, executables, unsupported formats, and spoofed extension/MIME claims.
- [x] **IMG-02**: The server rejects uploads exceeding configured byte and pixel limits, including decompression-bomb inputs, before resource exhaustion can affect the application.
- [x] **IMG-03**: The server validates crop inputs, removes original metadata/content by re-encoding, and persists only a generated fixed-size image asset with an application-generated name.
- [x] **IMG-04**: Logo mutations require the existing tenant-aware commissioner authorization and CSRF protection; user-supplied family IDs, object keys, URLs, and filenames cannot control storage or tenancy.

### Private Storage And Deployment

- [x] **S3-01**: Processed logos are stored under a server-derived `family-logos/` prefix in the existing private `family-pickem` S3 bucket in `us-east-1`.
- [x] **S3-02**: Application S3 permissions are least-privilege and prefix-limited; public ACL/policy access and object ownership bypasses are not introduced.
- [x] **S3-03**: The application receives S3 configuration and credentials through AWS Secrets Manager and the existing External Secrets Operator/Kubernetes flow, with no credentials committed to Git or manually managed Kubernetes Secrets.
- [ ] **S3-04**: The application delivers only controlled, correctly typed processed assets; uploaded originals are neither retained nor served from the application origin.

### Verification And Audit

- [x] **SAFE-01**: Automated tests cover allowed images; rejected types/headers/extensions; byte/pixel-limit failures; malformed crop data; and metadata-stripping re-encoding.
- [ ] **SAFE-02**: Automated tests prove unauthenticated, ordinary-member, wrong-family, forged tenant/object-key, and missing-CSRF requests cannot mutate or infer another family’s logo.
- [ ] **SAFE-03**: Create, replace, and remove actions are tenant-scoped, audit logged, and leave no referenced obsolete logo object.

## Future Requirements

### Media Enhancements

- **MEDIA-01**: Commissioners can manage multiple responsive logo derivatives.
- **MEDIA-02**: Direct browser-to-S3 uploads use scoped, expiring presigned POST policies.
- **MEDIA-03**: Families can select animated or vector logos after a separately assessed security design.

## Out of Scope

| Feature | Reason |
|---|---|
| Arbitrary external logo URLs | Replaced by managed uploads to remove broken UX and remote-content risk. |
| Original-file retention/download | Only re-encoded assets may be stored or served. |
| SVG, GIF, HEIC, and arbitrary file types | Not needed for a fixed logo and expands the active-content/parser attack surface. |
| Public S3 objects or public bucket policy | Conflicts with the existing Block Public Access security posture. |
| Direct browser S3 writes | Avoided for this bounded administrator flow; it adds policy/cleanup complexity. |

## Traceability

| Requirement | Phase | Status |
|---|---:|---|
| LOGO-01 | Phase 7 | Complete |
| LOGO-02 | Phase 7 | Complete |
| LOGO-03 | Phase 7 | Complete |
| LOGO-04 | Phase 7 | Pending |
| IMG-01 | Phase 6 | Complete |
| IMG-02 | Phase 6 | Complete |
| IMG-03 | Phase 6 | Complete |
| IMG-04 | Phase 6 | Complete |
| S3-01 | Phase 6 | Complete |
| S3-02 | Phase 8 | Complete |
| S3-03 | Phase 8 | Complete |
| S3-04 | Phase 7 | Pending |
| SAFE-01 | Phase 6 | Complete |
| SAFE-02 | Phase 8 | Pending |
| SAFE-03 | Phase 8 | Pending |

**Coverage:**

- v1.1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-07-18*  
*Last updated: 2026-07-18 after v1.1 scope confirmation*
