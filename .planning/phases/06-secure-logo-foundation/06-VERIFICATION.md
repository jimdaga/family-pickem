---
phase: 06-secure-logo-foundation
verified: 2026-07-18
status: passed
verifier: generic-agent-workaround
---

# Phase 06 Verification: Secure Logo Foundation

## Verdict

**Passed.** The Phase 06 implementation provides the planned fail-closed, server-side logo foundation. It is intentionally limited to the native chooser and server-side center crop; preview/cropper UX, direct browser S3 uploads, IAM/ESO provisioning, delivery policy, and old-object cleanup remain fenced to later phases.

## Requirement and Must-Have Evidence

| Requirement | Result | Evidence |
|---|---|---|
| IMG-01 | Pass | `process_family_logo()` ignores name/MIME claims, permits only Pillow-decoded JPEG/PNG/WebP, verifies and reopens the stream, then emits a fresh 256x256 WebP. The authorized family-admin route is the only mutation route and persists that output. |
| IMG-02 | Pass | The pure boundary rejects source bytes above 5 MiB before decoder work, promotes Pillow decompression warnings to errors, checks reopened dimensions before `load()` or transforms, and rejects malformed/unsupported streams with stable codes. The route-specific streaming handler aborts the logo at byte 5 MiB + 1. Dev and production ingress both render a 6m multipart envelope. |
| IMG-03 | Pass | Crop input validation is strict and bounded; the route currently uses the safe server center crop. The output is re-encoded without source filename, bytes, EXIF, or PNG text metadata. Storage names are family-id/UUID `.webp` keys under `family-logos/`. |
| IMG-04 | Pass | `family_admin_settings.html` uses a multipart native `FileField`, an explicit JPEG/PNG/WebP accept hint, current/default logo display, linked help/error text, and safe server-side error rendering. No browser preview/cropper/direct-S3 path was added. |
| S3-01 | Pass | `FamilyLogoStorage` is a dedicated `S3Boto3Storage` subclass with `location = "family-logos"`, no ACL, signed query URLs, no overwrite, `image/webp` content type, and private immutable cache metadata. `Family.logo` is nullable and uses only its server-generated upload callable. Migration 0090 removes the prior arbitrary `logo_url` field without fetching its values. |
| SAFE-01 | Pass | The processor has no HTTP/model/storage/AWS coupling. The authorized view holds tenant family/pool rows in a transaction, processes before storage, saves the generated key with `save=False`, persists the locked row, records boolean-only logo audit metadata, and deletes the new key if row or audit persistence fails. |

## Security Wiring Review

- `FamilyLogoUploadHandlerMiddleware` occurs immediately before Django's CSRF middleware in `MIDDLEWARE`; its `process_view` resolves and limits only the `family_pool_admin_settings` multipart POST before CSRF causes request-file parsing.
- `FamilyLogoUploadSizeLimitHandler` records only a stable request-local `file_too_large` marker and raises `StopUpload` at the first byte over the cap. The view renders a bound form and does not call processor, storage, DB, audit, messages, or redirect for that marker.
- The 16 MP assertion precedes `source.load()`, EXIF normalization, crop, resize, and encode. The regression test mocks the reopened image and proves neither load nor transforms run.
- All live family-logo rendering uses `Family.logo`; missing values fall back to a static application logo. A repository search found no remaining live `Family.logo_url` reader/editor (only historical migration and unrelated email/team-variable uses of the same identifier).

## Automated Evidence

Passed locally on 2026-07-18:

```bash
cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py test pickem_api.tests.test_logo_processing pickem_api.tests.test_family_logo_storage pickem_homepage.tests.FamilyLogoUploadFoundationTests pickem_superadmin.tests.test_families --settings=pickem.test_settings --verbosity=2
cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=1
helm template family-pickem-dev charts/family-pickem -f infra/app/values-dev.yaml
helm template family-pickem-prd charts/family-pickem -f infra/app/values-prd.yaml
```

Results: Django check passed; migration dry-run reported no changes; the focused suite passed 67 tests; the full suite passed 633 tests (4 expected skips); both rendered Ingress manifests contain `nginx.ingress.kubernetes.io/proxy-body-size: 6m`.

## Warnings

- `git diff --check HEAD~12..HEAD` reports two trailing-whitespace warnings in `06-02-SUMMARY.md`. They are documentation-only and do not affect application behavior or this phase's security properties.
- This phase deliberately does not establish AWS IAM/External Secrets Operator policy or prove private delivery in a deployed cluster. Those are Phase 8 requirements, not evidence claimed here.

## Human Verification

None required for Phase 06 completion. Phase 8 should perform its separately planned deployed-AWS/ESO and adversarial delivery verification.
