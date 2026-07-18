# Phase 6 Research: Secure Logo Foundation

**Phase goal:** Establish a tenant-safe logo data model and server-side image-processing boundary before an upload UI can persist content.

## User Constraints

- [VERIFIED: `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`] There is no Phase 6 `CONTEXT.md`; this plan must use the approved v1.1 roadmap and requirements as its decision source.
- [VERIFIED: `.planning/REQUIREMENTS.md`] The server must accept decoder-verified JPEG, PNG, and WebP only; reject all other formats and spoofed claims; enforce byte and pixel limits; validate crop input; re-encode; and persist an application-generated fixed-size asset.
- [VERIFIED: `.planning/ROADMAP.md`] Phase 6 covers IMG-01 through IMG-04, S3-01, and SAFE-01. The browser cropper, actual commissioner UI, delivery endpoint, IAM/ESO policy, full authorization attack matrix, audit lifecycle, replacement cleanup are deliberately later Phase 7/8 work.
- [VERIFIED: `pickem/pickem_api/models.py:54-88`] `Family.logo_url` is currently an arbitrary nullable `CharField`; the foundation must replace it with a server-owned file/object reference while preserving the no-logo default fallback.
- [VERIFIED: `pickem/pickem_homepage/authz.py`, `pickem/pickem_api/authz.py`] Tenant context is resolved from the URL and active membership; family owners and admins are authorized through `@family_member_required(minimum_role=ADMIN)`, while a site superuser gets synthetic owner access.
- [VERIFIED: `pickem/requirements.txt`] The installed stack is Django 4.2.30, Pillow 12.2.0, boto3 1.35.99, and django-storages 1.13.1. The request’s reference to Django 4.0.2 is stale relative to the pinned project dependency.

## Standard Stack

| Concern | Decision | Why |
|---|---|---|
| Model reference | [VERIFIED: `pickem/pickem_api/models.py`, Django file-field docs] Add `Family.logo` as a nullable `ImageField`/`FileField` using a dedicated server-owned storage class and remove `logo_url` in the same migration sequence. | The DB records only the generated object name, while storage owns bucket/prefix behavior. |
| Storage | [VERIFIED: `pickem/pickem/settings.py:324-332`, django-storages S3 docs] Create a dedicated `FamilyLogoStorage` subclass of the existing S3 backend with `location='family-logos'`, private default ACL, fixed WebP content type, and generated names. | Do not couple logo behavior to the global default/static storage configuration. |
| Image processing | [VERIFIED: `pickem/requirements.txt`, Pillow docs] Use existing Pillow 12.2.0; no new image-processing dependency. | Pillow supports format-restricted `Image.open`, verification, full pixel loading, crop/resize, and fresh encoding. |
| Output | [ASSUMED: product decision for planner confirmation] Emit one 256×256 WebP asset with `Content-Type: image/webp`, quality around 85, method 6, no EXIF/ICC/PNG text metadata. | A single fixed square canonical asset meets the bounded-delivery requirement; retaining PNG transparency is not required because WebP supports alpha. |
| Upload limits | [ASSUMED: product decision for planner confirmation] Set a 5 MiB request/file cap and a 16 megapixel decoded-input cap; reject anything exceeding either before transform. | These conservative limits are suitable for a small square logo and prevent routine oversized uploads without constraining normal photos. |

### Package Legitimacy Audit

- [VERIFIED: `pickem/requirements.txt`] Pillow, boto3, and django-storages are already direct, pinned dependencies; Phase 6 should add no package.
- [CITED: https://pillow.readthedocs.io/en/stable/] Pillow is the maintained PIL fork and its current docs describe the exact decoder, verification, and decompression-bomb APIs needed here.
- [CITED: https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html] django-storages supplies the Django File Storage API implementation for S3 and uses boto3; it is already installed in this repository.
- [VERIFIED: `.planning/research/STACK.md`] Cropper.js is intentionally not a Phase 6 dependency: its preview/crop UI belongs to Phase 7 and never establishes the server-side trust boundary.

## Architecture Patterns

### 1. Keep the mutation boundary tenant-derived

1. [VERIFIED: `pickem/pickem_homepage/authz.py`] Decorate the eventual POST handler with the existing `family_member_required(minimum_role=FamilyMembership.Role.ADMIN)` and use only `request.tenant_context.family`.
2. [VERIFIED: Django CSRF middleware in `pickem/pickem/settings.py`] Keep the handler a normal form POST with CSRF middleware active; do not use `csrf_exempt` or a JSON endpoint.
3. [VERIFIED: `pickem/pickem_homepage/views.py:1323-1366`] Inside `transaction.atomic()`, re-fetch the resolved family with `select_for_update()` before assigning the generated logo reference.
4. [VERIFIED: requirements IMG-04] Never accept family IDs/slugs, S3 keys, target URLs, filenames, MIME types, or output extension as authority-bearing form fields.

### 2. Separate byte validation from decoder/pixel validation

1. [CITED: https://docs.djangoproject.com/en/4.2/topics/security/#user-uploaded-content] Enforce the request body at ingress/proxy and enforce the uploaded-file `size` again in the Django form/service; framework-level checks alone do not prevent request-body DoS.
2. [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] Open with `formats=("JPEG", "PNG", "WEBP")`, inspect `image.format`, call `verify()`, reopen, then call `load()` while treating `DecompressionBombWarning` as an exception.
3. [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] Check `width * height <= MAX_INPUT_PIXELS` before crop/resize. Pillow notes that opening is lazy and decoding occurs on processing/load, so both stages are required.
4. [VERIFIED: requirements IMG-01/02] Ignore the browser filename, extension, and submitted `Content-Type`; they are display hints at most, not validation evidence.

### 3. Canonicalize and make crop coordinates a pure validation problem

- [ASSUMED: Phase 7 client contract] The future client posts `crop_x`, `crop_y`, `crop_width`, and `crop_height` as integer pixels in the unrotated decoded-image coordinate space.
- [ASSUMED: implementation choice] Parse coordinates with strict integer conversion, reject booleans/floats/scientific notation, require positive width/height, require square crop (`width == height`), and require `0 <= x`, `0 <= y`, `x + width <= source_width`, `y + height <= source_height`.
- [ASSUMED: implementation choice] Phase 6 may expose this as a pure service/form helper and test it without enabling persistence UI; Phase 7 binds it to Cropper.js request data.
- [VERIFIED: requirements IMG-03] Apply `ImageOps.exif_transpose()` before interpreting coordinates if orientation support is retained. Alternatively, document that Phase 7 coordinates use the raw decoder orientation; do not silently mix the two coordinate systems.
- [ASSUMED: implementation choice] Crop first, convert to `RGBA` only when transparency must be preserved or `RGB` otherwise, resize with `Image.Resampling.LANCZOS`, and save to a fresh `BytesIO` as WebP without copying `image.info`, EXIF, ICC profile, comments, or original bytes.

### 4. Make path generation server-only

- [VERIFIED: requirements S3-01] Generate the object name from the resolved family ID plus `uuid.uuid4().hex`, for example `family-logos/<family-id>/<uuid>.webp`; the user-supplied filename must never reach the key.
- [VERIFIED: `pickem/pickem/settings.py:324-332`] The current app already enables `S3Boto3Storage` whenever `AWS_STORAGE_BUCKET_NAME` is present and configures `AWS_S3_REGION_NAME`; preserve production bucket selection and add explicit logo storage settings rather than hard-coding credentials.
- [CITED: https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html] django-storages supports `location` prefixes, private default ACL behavior, `file_overwrite`, and S3 URL signing; Phase 6 should set the storage’s `location`/generated naming and leave controlled URL delivery to Phase 7.
- [VERIFIED: `.planning/research/ARCHITECTURE.md`] The target bucket is the existing private `family-pickem` bucket in `us-east-1`; no public ACLs, bucket policies, or direct browser writes belong in this phase.

### 5. Model migration and compatibility

- [VERIFIED: `pickem/pickem_homepage/forms.py:245-281`, `pickem/pickem_homepage/views.py:1274-1347`] Existing settings logic actively reads and writes `logo_url`; Phase 6 must change its model/form/view/template references together or intentionally hold a temporary compatibility state.
- [ASSUMED: recommended migration sequence] Add nullable `logo` first, deploy code that displays `logo` if present and otherwise falls back to the default static logo, remove arbitrary `logo_url` from the form/view/templates, run a data migration that sets no remote URLs as managed assets, then remove `logo_url` in a follow-up migration in this phase. Existing remote URL values must not be copied into S3 automatically because fetching them would reintroduce SSRF/content-validation risk.
- [VERIFIED: requirements IMG-04] A blank `Family.logo` means default logo; it must not mean an untrusted old URL remains displayable.

## Don’t Hand-Roll

| Do not build | Use instead | Reason |
|---|---|---|
| [VERIFIED: `.planning/research/SUMMARY.md`] Browser-only image type/crop validation | Pillow decoder verification plus server crop/re-encode | Browser checks can be bypassed. |
| [VERIFIED: Pillow docs] File-signature parser | `Image.open(..., formats=...)`, `verify()`, reopen and `load()` | Pillow already provides format-restricted decode and malformed-file detection primitives. |
| [VERIFIED: existing `pickem_api.authz.py`] New family-role lookup | `family_member_required` / `require_tenant_context` | A duplicate authorization scheme could drift from the established tenant boundary. |
| [VERIFIED: existing dependency `django-storages`] Raw boto3 storage glue in views | Dedicated django-storages backend/class | Storage behavior remains testable and decoupled from HTTP views. |
| [VERIFIED: `.planning/research/STACK.md`] A client-side cropper in Phase 6 | Defer Cropper.js to Phase 7 | Foundation must be complete without trusting or requiring frontend crop code. |

## Common Pitfalls

1. **`Image.verify()` is not the whole validation.** [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] `verify()` checks for broken content without decoding the image data and requires reopening the file before load; plan both verify and actual decode/load.
2. **Image headers can precede hostile trailing bytes.** [CITED: https://docs.djangoproject.com/en/4.2/topics/security/#user-uploaded-content] Django explicitly warns an HTML payload with a valid PNG header can pass Pillow-based `ImageField` verification. Persist only freshly encoded output; do not retain/serve the original.
3. **Pillow warnings must fail closed.** [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] Pillow emits a decompression-bomb warning above `MAX_IMAGE_PIXELS`; convert this warning to an error locally around the decoder and add a direct width×height cap.
4. **Global `Image.MAX_IMAGE_PIXELS` is process-wide.** [ASSUMED: implementation safety] Do not mutate the global setting per request in a concurrent WSGI process. Use local warning filtering plus explicit dimensions, or establish a startup-wide conservative setting with tests.
5. **EXIF orientation and crop coordinates can disagree.** [ASSUMED: implementation safety] Define whether coordinates target raw or normalized pixels and test a rotated-EXIF fixture. Normalizing orientation before validation is usually clearer, but Phase 7 must submit coordinates for that normalized preview.
6. **Default S3 storage is also static storage.** [VERIFIED: `pickem/pickem/settings.py:324-332`] Do not give a model field the unspecialized default storage without confirming the object prefix and content metadata; use a dedicated logo storage class.
7. **Storage writes are not database transactions.** [ASSUMED: implementation safety] Write the new generated object first, update the locked DB row second, and on DB failure delete the just-written key best-effort while logging the failure. Do not delete a previous logo in Phase 6; replacement cleanup/audit are Phase 8 requirements.
8. **Tests can accidentally use network S3.** [VERIFIED: `pickem/pickem/test_settings.py:33-35`] Test settings already select `FileSystemStorage`; explicitly override the dedicated logo storage to a temporary local storage or mock it, and assert no live AWS call occurs.
9. **Do not make the bucket public for convenience.** [CITED: https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html] AWS recommends Block Public Access and least privilege; delivery remains private/controlled until Phase 7/8.

## Code Examples

### Bounded canonicalization service (shape, not copy-paste final code)

```python
# pickem/pickem_homepage/logo_processing.py
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_INPUT_PIXELS = 16_000_000
OUTPUT_SIZE = 256

def canonical_logo(uploaded_file, crop):
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise LogoValidationError("file_too_large")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            uploaded_file.seek(0)
            with Image.open(uploaded_file, formats=tuple(ALLOWED_FORMATS)) as probe:
                if probe.format not in ALLOWED_FORMATS:
                    raise LogoValidationError("unsupported_format")
                probe.verify()

            uploaded_file.seek(0)
            with Image.open(uploaded_file, formats=tuple(ALLOWED_FORMATS)) as source:
                source.load()
                if source.width * source.height > MAX_INPUT_PIXELS:
                    raise LogoValidationError("too_many_pixels")
                normalized = ImageOps.exif_transpose(source)
                box = validate_square_crop(crop, normalized.size)
                result = normalized.crop(box).resize(
                    (OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS
                )
                output = BytesIO()
                result.save(output, format="WEBP", quality=85, method=6)
                output.seek(0)
                return output
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise LogoValidationError("invalid_image")
```

- [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] The example uses `formats`, `verify`, reopen, `load`, and the documented decompression-bomb warning/error behavior.
- [ASSUMED: implementation detail] The final implementation needs a project-specific `LogoValidationError`, structured logging, and a deterministic crop-data schema; it must not return raw Pillow exception text to the user.

### Dedicated S3 storage shape

```python
# pickem/pickem_api/storage.py
from storages.backends.s3boto3 import S3Boto3Storage

class FamilyLogoStorage(S3Boto3Storage):
    location = "family-logos"
    default_acl = None
    file_overwrite = False
    querystring_auth = True
    object_parameters = {
        "ContentType": "image/webp",
        "CacheControl": "private, max-age=31536000, immutable",
    }
```

- [CITED: https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html] django-storages documents prefix location, private default ACL, overwrite behavior, query-string authentication, and object parameters.
- [ASSUMED: implementation detail] Because output keys are already UUID-generated, `file_overwrite=False` is defense in depth rather than the primary collision control.

### Server-derived model field shape

```python
def family_logo_upload_to(instance, _filename):
    return f"{instance.pk}/{uuid.uuid4().hex}.webp"

class Family(models.Model):
    logo = models.ImageField(
        storage=FamilyLogoStorage(),
        upload_to=family_logo_upload_to,
        blank=True,
        null=True,
    )
```

- [ASSUMED: implementation detail] The `upload_to` callable may receive an unsaved instance, so Phase 6 should either save the family before a logo is possible (true for this existing settings flow) or use a UUID independent of `pk`; the storage prefix plus callable should yield exactly one `family-logos/` prefix, not duplicate it.

## Project Constraints

- [VERIFIED: `pickem/pickem_homepage/views.py:1300-1389`] The existing family settings POST already uses a tenant-derived `family`/`pool`, `transaction.atomic()`, row locks, and `FamilyAuditLog` for normal settings. Reuse its safety primitives but do not expand its existing `logo_url` behavior.
- [VERIFIED: `pickem/pickem_homepage/urls.py`] The current settings route is a family/pool route; planned mutation code must remain there or use an equivalently decorated tenant route, not the global `/commissioners/` routes.
- [VERIFIED: `pickem/pickem/settings.py:324-332`] Storage is enabled only when `AWS_STORAGE_BUCKET_NAME` exists, and settings currently index AWS credential environment variables directly. Phase 6 must keep local development/test storage viable and defer ESO/IAM secret topology to Phase 8.
- [VERIFIED: `pickem/pickem/test_settings.py`] The test suite runs against in-memory SQLite and local storage, so implementation should use `SimpleUploadedFile`, temporary/memory image bytes, and storage fakes/mocks rather than an S3 test account.
- [VERIFIED: `.planning/ROADMAP.md`] Do not do cloud IAM/External Secrets manifests, public/private delivery endpoint design, Cropper.js wiring, audit action additions, or old-object deletion in this phase unless they are necessary scaffolding; they are owned by Phases 7/8.

## Test Plan

### Unit tests for processor (SAFE-01)

- [VERIFIED: requirements SAFE-01] Valid JPEG, PNG, and WebP fixtures each produce a readable 256×256 WebP output whose format/content type is server-defined.
- [VERIFIED: requirements IMG-01] SVG, GIF, HTML, random bytes, executables, mismatch extension, mismatch declared MIME, and malformed/truncated raster data each fail with stable validation errors and create no storage object.
- [VERIFIED: requirements IMG-02] A mocked oversized `UploadedFile.size`, a synthetic decompression-bomb warning/error, and an image exceeding the explicit pixel cap each fail before persistence.
- [VERIFIED: requirements IMG-03] Negative/non-integer/fractional/zero/out-of-bounds/non-square crop fields fail; a valid crop is bounded; output omits sentinel EXIF/text metadata; output has no original filename/key.
- [ASSUMED: test technique] Generate image fixtures in memory with Pillow; use `warnings.catch_warnings`/mocking for a fast decompression-bomb case rather than committing a dangerous huge fixture.

### Model/storage and regression tests

- [VERIFIED: roadmap success criterion 1] Migration test: pre-existing family with `logo_url` ends with no managed logo and the template fallback works; do not fetch an old remote URL.
- [VERIFIED: S3-01] Assert generated names are family-derived UUID `.webp` names under the dedicated `family-logos/` location and never include a supplied filename.
- [VERIFIED: test settings] Assert processing uses local/fake storage under test and that output bytes are only the generated WebP artifact.
- [VERIFIED: IMG-04] A normal member cannot invoke a future mutation handler; authenticated admin/owner can. Full wrong-family, missing-CSRF, object-key forgery, audit, replace/remove cleanup scenarios are Phase 8’s SAFE-02/SAFE-03, but the Phase 6 handler must not accept those fields at all.

## Planning Recommendations

1. [ASSUMED: execution ordering] Make the first Phase 6 plan task a pure `logo_processing` module plus exhaustive unit tests, with no view/UI storage mutation exposed.
2. [ASSUMED: execution ordering] Make the second task add the dedicated storage class, `Family.logo` migration, and safe removal of `logo_url` rendering/input; test default fallback with a family that has no logo.
3. [ASSUMED: execution ordering] Make the final task add the narrow, tenant-decorated persistence seam only if Phase 7 needs it immediately; otherwise expose an internal service callable so Phase 7 can attach the multipart form. This preserves the roadmap guarantee that no upload UI persists content before the safety boundary is reviewed.
4. [ASSUMED: decision gate] Confirm the 5 MiB / 16 MP / 256px WebP defaults before implementation. They are secure working defaults, not values explicitly supplied by the user.

## Sources

- [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] Pillow `Image.open`, restricted formats, lazy loading, decompression-bomb warning/error, and `verify` behavior.
- [CITED: https://docs.djangoproject.com/en/4.2/topics/security/#user-uploaded-content] Django upload size, PNG-plus-HTML, and separate-origin security guidance.
- [CITED: https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html] django-storages S3 configuration, credential lookup, privacy defaults, prefix, object parameters, and signing behavior.
- [CITED: https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html] AWS least-privilege, private-bucket, Block Public Access, and application credential guidance.
- [VERIFIED: `pickem/requirements.txt`, `pickem/pickem/settings.py`, `pickem/pickem/test_settings.py`, `pickem/pickem_api/models.py`, `pickem/pickem_api/authz.py`, `pickem/pickem_homepage/authz.py`, `pickem/pickem_homepage/views.py`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`] Project-specific implementation and phase-boundary evidence.
