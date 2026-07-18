# Project Research Summary

**Project:** Family Pickem Multi-Tenancy  
**Domain:** Secure family-logo image upload  
**Researched:** 2026-07-18  
**Confidence:** HIGH

## Executive Summary

Use Cropper.js 2.1.1 for an ergonomic local square-crop preview, but treat it only as a UI aid. Django must receive, authorize, validate, decode, crop, and re-encode each upload itself. The persisted asset must be a generated fixed-size raster object, never the original upload or a client-provided URL.

The existing `family-pickem` S3 bucket in `us-east-1` already has strong foundations: all Block Public Access switches enabled, bucket-owner-enforced ownership, and SSE-S3. The milestone should extend it with a `family-logos/` prefix and least-privilege application access through the existing AWS Secrets Manager → ESO → Kubernetes deployment path. Objects remain private; delivery must be app-controlled or use short-lived signed reads.

## Key Findings

### Recommended Stack

- **Cropper.js 2.1.1:** MIT-licensed client crop/preview UI.
- **Pillow:** authoritative server-side image decode, size checking, crop, and re-encode.
- **django-storages/boto3 + existing S3 bucket:** private persistence using the project’s current AWS configuration.

### Must Have

- Commissioner-page upload, preview, fixed square crop, save/replace/remove.
- JPEG/PNG/WebP decoder allowlist; byte and pixel limits; metadata-stripping re-encode.
- Tenant-aware authorization, CSRF, generated S3 object keys, private delivery, audit coverage, and hostile-input tests.

### Defer

- Direct browser-to-S3 uploads, original-file retention, animated/vector formats, multiple derivatives, and user-defined external URLs.

## Implications for Roadmap

### Phase 6: Secure Logo Domain and Storage Foundation

Establish the family-logo persistence model, bounded validation/re-encoding service, generated S3 naming, and test harness before exposing an upload UI.

### Phase 7: Commissioner Upload and Delivery Experience

Replace the URL field with Cropper.js preview/crop/save/remove UI, render the processed family logo, and ensure tenant authorization/audit behavior.

### Phase 8: AWS Deployment and Adversarial Verification

Add least-privilege AWS/ESO configuration and verify S3 policy, Kubernetes secret injection, hostile inputs, cross-family denial, replacement cleanup, and full regression coverage.

## Phase Ordering Rationale

The server-side trust boundary must exist before the browser can save an upload. Delivery must be integrated after canonical assets are defined. Cloud permissions and hostile-input tests gate the release because private storage and re-encoding, not client-side file pickers, are the security controls.

## Sources

- https://fengyuanchen.github.io/cropperjs/v2/
- https://github.com/fengyuanchen/cropperjs
- https://pillow.readthedocs.io/en/stable/handbook/security.html
- https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- https://docs.djangoproject.com/en/4.2/topics/security/#user-uploaded-content
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html

---
*Research completed: 2026-07-18*  
*Ready for roadmap: yes*
