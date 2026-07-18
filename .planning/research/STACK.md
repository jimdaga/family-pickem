# Stack Research

**Domain:** Secure family-logo image upload for a Django application  
**Researched:** 2026-07-18  
**Confidence:** HIGH

## Recommended Stack

| Technology | Version | Purpose | Why Recommended |
|---|---:|---|---|
| Pillow | Pin current compatible release | Server-side decode, normalize, crop, and re-encode | The project already uses Django/Python; decoding and emitting a newly encoded raster removes original payload/metadata. |
| Cropper.js | 2.1.1 | Browser preview, square crop, zoom, and repositioning | Active MIT-licensed, dependency-free JavaScript cropper with a modern v2 component API. |
| django-storages + boto3 | Existing project dependency | Private S3 object persistence | Matches existing Django S3 configuration and AWS account. |
| S3 | Existing `family-pickem`, us-east-1 | Object storage | Existing bucket has Block Public Access, bucket-owner-enforced ownership, and SSE-S3. |

## Recommended Pattern

1. Browser accepts only a local candidate file and gives a client-side crop preview; this is usability only, never a trust boundary.
2. Authenticated form POST uploads the original to Django over TLS with CSRF protection. Do not grant direct browser S3 write access for this small, sensitive admin flow.
3. Server rejects files over the byte cap, opens only an allowlist of raster formats (JPEG/PNG/WebP), treats Pillow decompression-bomb warnings as errors, applies a hard pixel cap, converts/crops to a fixed square, and re-encodes to a generated WebP/PNG asset.
4. Store only the generated filename/object key, never the supplied filename or a client-controlled URL. Serve an image response with a fixed image Content-Type, `X-Content-Type-Options: nosniff`, and a strict content disposition.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|---|---|---|
| Cropper.js | Hand-rolled canvas cropper | Only if the fixed v2 UI cannot meet the desired interaction after a prototype. |
| Server-mediated upload | Browser presigned S3 upload | Consider later for large/low-trust media volumes; it adds policy, expiry, cleanup, and validation complexity. |
| Re-encoded raster output | Preserve original upload | Never for this feature; it retains untrusted bytes and metadata. |

## What Not to Use

| Avoid | Why | Use Instead |
|---|---|---|
| SVG/GIF/HEIC upload acceptance | Active/vector or animated formats broaden the parser and XSS surface without a logo need. | JPEG, PNG, and WebP only. |
| Extension/MIME-header checks alone | Both are client-controlled and spoofable. | Decoder-based format verification plus re-encoding. |
| Public S3 ACL/object URLs | Violates the bucket's Block Public Access posture. | Private objects with controlled delivery. |

## Sources

- https://fengyuanchen.github.io/cropperjs/v2/ — Cropper.js v2 documentation
- https://github.com/fengyuanchen/cropperjs — v2.1.1 release and MIT license
- https://pillow.readthedocs.io/en/stable/handbook/security.html — image pixel-limit guidance
- https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html — upload validation and rewrite guidance

