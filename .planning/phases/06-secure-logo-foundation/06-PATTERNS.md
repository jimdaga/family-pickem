# Phase 6 Pattern Mapping — Secure Logo Foundation

## Scope guardrails

This map covers only Phase 6 requirements **IMG-01–04, S3-01, SAFE-01**. It deliberately excludes Cropper.js/interactive preview and replacement/removal consumer flows (Phase 7), plus IAM/ESO, broad adversarial authorization coverage, audit action expansion, and obsolete-object cleanup (Phase 8).

The approved Phase 6 UI contract is a multipart, tenant-scoped settings form with a native chooser and server processing—not a direct-to-S3 browser workflow. Reuse the current settings endpoint rather than adding a global commissioner endpoint.

## Model and migration analogs

| Need | Closest project pattern | Phase 6 implementation implication |
|---|---|---|
| Family-owned persisted reference | [`pickem/pickem_api/models.py:54-86`](../../../pickem/pickem_api/models.py) defines `Family` and currently has `logo_url` at line 61. | Replace this arbitrary `CharField` with nullable/blank `logo = ImageField(...)` backed by a dedicated storage class. The database stores the generated name only; do not retain an external URL. Keep no-logo nullable so static default fallback remains possible. |
| Current schema convention | [`pickem/pickem_api/migrations/0076_add_family_logo_url.py`](../../../pickem/pickem_api/migrations/0076_add_family_logo_url.py) introduced the existing field; latest migration is [`0089_rename_seasoned_default_pool_names.py:35-43`](../../../pickem/pickem_api/migrations/0089_rename_seasoned_default_pool_names.py). | Add a new `0090_...` migration depending on `0089`; remove `logo_url` and add `logo`. Do not attempt to download/migrate prior remote URLs; they are untrusted and are intentionally replaced by the default when unset. |
| Admin model display | [`pickem/pickem_api/admin.py:40-46`](../../../pickem/pickem_api/admin.py) lists and exposes `logo_url`. | Update admin list/fields from `logo_url` to `logo`, preserving the existing model-admin structure. |
| Tenant ownership | [`pickem/pickem_api/models.py:95-134`](../../../pickem/pickem_api/models.py) scopes pools to families; logo belongs on `Family`, not `Pool`. | Storage key should derive from `locked_family.id` plus server UUID; never accept family id/key/path/name from request data. |

Suggested server key shape: storage `location = "family-logos"` plus an `upload_to` callable returning `<family-pk>/<uuid>.webp`. This guarantees a final `family-logos/<family-pk>/<uuid>.webp` key without a user filename or duplicate prefix.

## Storage and settings analogs

| Need | Closest project pattern | Phase 6 implementation implication |
|---|---|---|
| Existing S3 configuration | [`pickem/pickem/settings.py:322-332`](../../../pickem/pickem/settings.py) conditionally enables the generic `S3Boto3Storage` when `AWS_STORAGE_BUCKET_NAME` is set and reads the existing bucket/region credentials. | Create `pickem/pickem_api/storage.py` with `FamilyLogoStorage(S3Boto3Storage)`, not a global storage rewrite. Set `location = "family-logos"`, `default_acl = None`, `file_overwrite = False`, signed query strings, and output-only WebP object parameters. This uses the existing private `family-pickem` bucket/`us-east-1` configuration. |
| Test storage convention | [`pickem/pickem/test_settings.py:33-35`](../../../pickem/pickem/test_settings.py) forces `FileSystemStorage` in tests. | Keep `FamilyLogoStorage` configurable/testable through Django’s storage API; unit tests must not contact S3. Use temporary/local storage or patch the field storage when exercising persistence. |
| No existing media abstraction | `rg` finds no `ImageField`, `FileField`, `ContentFile`, or project S3 subclass. | This is a new small, dedicated seam. Do not overload static-file settings or send originals to static storage. |

Phase 6 must not add IAM, ESO manifests, or credentials. Settings currently permit local test storage; Phase 8 owns secret topology and least-privilege policy.

## Image processor/service pattern

There is no existing Pillow/media service in the repository. Create an isolated pure service, e.g. `pickem/pickem_api/logo_processing.py`, so decoding and canonicalization can be tested without HTTP, database, or S3.

Recommended public seam:

```python
class LogoValidationError(Exception):
    code: str

def process_family_logo(uploaded_file, crop_data=None) -> ContentFile:
    """Return only a fresh 256×256 WebP asset or raise LogoValidationError."""
```

Use the approved research values: **5 MiB source-byte limit**, **16 megapixel decoded-input limit**, **256×256 WebP output**. The service must:

1. Check `uploaded_file.size` before decoder work; ignore its filename, extension, and claimed content type for trust decisions.
2. Open with Pillow’s decoder allowlist `{JPEG, PNG, WEBP}`, `verify()`, then reopen and fully `load()` under `warnings.simplefilter("error", Image.DecompressionBombWarning)`. Convert `UnidentifiedImageError`, `OSError`, and decompression-bomb error/warning to stable application errors.
3. Verify `image.format` after decoder work, calculate `width * height` before transform, and reject unsupported/decompression-risk inputs.
4. Parse an explicit crop schema defensively (integer, finite/bounded source rectangle; no client object key/URL/family data). Phase 7 supplies crop UI; Phase 6’s parser is the server boundary. A missing crop may safely use the center square if that is the plan’s chosen default.
5. Crop and resize with LANCZOS, convert as necessary, and save a fresh `BytesIO` as WebP. Do not copy `info`, EXIF, ICC, PNG text chunks, original filename, or original bytes.

The view/service boundary must persist only this returned `ContentFile` through `locked_family.logo.save(generated_name, processed_file, save=False)`. Do not expose a general `storage.save(request.POST[...])` path.

## Form, authorization, and view analogs

| Need | Closest project pattern | Phase 6 implementation implication |
|---|---|---|
| Existing authorized mutation route | [`pickem/pickem_homepage/views.py:1302-1398`](../../../pickem/pickem_homepage/views.py) decorates `family_pool_admin_settings` with `@family_member_required(minimum_role=ADMIN)`, derives `family`/`pool` from `request.tenant_context`, wraps mutation in `transaction.atomic()`, and locks both rows. | Extend this exact endpoint/seam. Never read family/pool/id/key from POST; process only `request.FILES['logo']` after form validation and use the already locked family. The decorator supports both family admin and owner; `pickem_api.authz.py:140-175` also grants a synthetic owner context to a site superuser. |
| Tenant enforcement details | [`pickem/pickem_homepage/authz.py:16-39`](../../../pickem/pickem_homepage/authz.py) converts auth failures into login redirect/404/403; [`pickem/pickem_api/authz.py:61-111`](../../../pickem/pickem_api/authz.py) resolves pools only within their family. | Preserve decorator ordering and URL shape. Do not create a free-standing API that takes a family reference. Existing middleware + `{% csrf_token %}` provides the required CSRF protection; do not add `csrf_exempt`. |
| Existing settings form | [`pickem/pickem_homepage/forms.py:224-278`](../../../pickem/pickem_homepage/forms.py) has `FamilyAdminSettingsForm` with unsafe `logo_url` and URL validator. | Remove `logo_url`/`clean_logo_url`; add a `logo` `FileField(required=False)` using native `ClearableFileInput`/`FileInput` with chooser-only `accept="image/jpeg,image/png,image/webp"`, standard input classes, help copy, and form-level invocation of the pure processor or a clear view-level service call. Do not regard `accept`, extension, or browser MIME as validation. Pass `request.FILES` as the second positional form argument: `FamilyAdminSettingsForm(request.POST, request.FILES, initial=initial)`. |
| Existing audit metadata helper | [`pickem/pickem_homepage/views.py:1270-1299`](../../../pickem/pickem_homepage/views.py) creates before/after metadata, and lines 1360-1369 record `POOL_SETTINGS_UPDATED`. | Update metadata to represent a boolean/server-generated logo state only—never file bytes, original name, MIME claim, object key, or storage URL. Dedicated logo lifecycle audit actions remain Phase 8. |
| Existing locked save | [`pickem/pickem_homepage/views.py:1322-1378`](../../../pickem/pickem_homepage/views.py) uses locked instances and one redirect after success. | Process source before final save where failure leaves the existing logo unchanged; save canonical field under the lock and preserve the post/redirect/message behavior. Replacement cleanup is Phase 8, so do not delete old object in Phase 6. |

## Template integration analogs

| Need | Closest project pattern | Phase 6 implementation implication |
|---|---|---|
| Form transport and CSRF | [`family_admin_settings.html:32-33`](../../../pickem/pickem_homepage/templates/pickem/family_admin_settings.html) has a POST form with `{% csrf_token %}` but **no** multipart encoding. | Add `enctype="multipart/form-data"`; preserve token and the sole `Save Settings` submit action. |
| Current unsafe URL UI | [`family_admin_settings.html:62-71`](../../../pickem/pickem_homepage/templates/pickem/family_admin_settings.html) renders `form.logo_url`. | Replace this entire section with the approved native file field, 96px default/current server thumbnail, allowed formats/5MB copy, `aria-describedby`, and field error `role="alert"`. Do not add local blob preview, Cropper.js, separate upload button, URL/key control, removal action, or direct S3 logic. |
| Existing default asset | [`family_pool_home.html:27-32`](../../../pickem/pickem_homepage/templates/pickem/family_pool_home.html) falls back to `{% static 'images/logo.png' %}` but currently renders external `logo_url` and inline `onerror`. | Phase 6 must remove legacy URL references in admin/form paths and preserve default fallback. Consumer-surface canonical rendering and removal of all remote/onerror logo usage should be scheduled precisely as Phase 7 work; do not silently leave a model-field removal that crashes templates. |
| Other affected rendering | `logo_url` is also referenced in [`family_picker.html:46-47,90-91`](../../../pickem/pickem_homepage/templates/pickem/family_picker.html) and [`pickem_api/admin.py:40-46`](../../../pickem/pickem_api/admin.py). | Update all direct model field references required for the migration to avoid runtime errors. The full controlled delivery contract belongs to Phase 7; Phase 6 may render only default/static or an available canonical field reference in the settings response as the UI-SPEC directs. |

## Test analogs and focused test placement

| Test area | Closest project pattern | Phase 6 tests to add/replace |
|---|---|---|
| Tenant/CSRF regression | [`pickem/pickem_homepage/tests.py:4542-4605`](../../../pickem/pickem_homepage/tests.py) proves tenant-derived settings mutations ignore injected IDs; [`4607-4677`](../../../pickem/pickem_homepage/tests.py) covers roles and CSRF. | Keep these tests current after removing `logo_url`; add a focused valid-logo multipart happy path authorized as existing admin/owner. Phase 8 owns the full forged-key/wrong-family/missing-CSRF adversarial matrix. |
| Legacy URL replacement | [`tests.py:4074-4165`](../../../pickem/pickem_homepage/tests.py) tests accepting/rejecting URL strings and remote `onerror` fallback. | Delete/replace URL acceptance tests. Assert no URL field/output remains in settings, no-logo families fall back to default, and legacy migration leaves no managed asset. |
| Form conventions | [`FamilyAdminSettingsFormTests` at `tests.py:6700-6733`](../../../pickem/pickem_homepage/tests.py) creates baseline POST payloads and instantiates form directly. | Change fixture payload from `logo_url` to no file/files argument. Test visible native file widget attributes/help/error association as needed by UI-SPEC. |
| Processor security unit coverage | No processor analog exists. | Add `pickem/pickem_api/tests/test_logo_processing.py` (or current app test module if suite organization requires) using in-memory Pillow bytes and `SimpleUploadedFile`: JPEG/PNG/WebP acceptance; SVG/GIF/HTML/executable/random/malformed; spoofed filename/content_type; byte cap; pixel cap; mocked decompression warning; malformed crop; output dimensions/format; and EXIF/text sentinel removal. Assert each failure occurs before model/storage persistence. |
| Storage-name invariant | No storage test analog exists. | Test upload callable/dedicated storage with a fixed UUID/mock: generated `.webp`, family-scoped path, one `family-logos/` prefix, no source filename, and output WebP content type. |

## Sequencing for an executable plan

1. Build `logo_processing` and exhaustive pure unit tests first. This creates the security boundary without a persistence route.
2. Add dedicated storage, `Family.logo` migration/admin updates, and regression-safe template/model reference updates. Keep test settings local.
3. Convert the settings form/template to multipart native chooser and integrate the processor into the already-decorated/locked settings mutation. Add focused valid/invalid multipart tests and preserve existing tenant protections.

## Explicitly deferred

- Cropper.js, local image/blob preview, zoom/reposition controls, and user-facing crop UX (Phase 7).
- Replace/remove UX, stale-object deletion, audit action expansion, and the complete hostile tenant/object-key/CSRF matrix (Phase 8).
- IAM policies, AWS Secrets Manager/ESO/Helm changes, credentials, public/private delivery endpoint design (Phase 8).
- Direct browser-to-S3 uploads, SVG/GIF/vector/animated formats, originals, user-selected object names, and arbitrary image URLs (out of scope).

## PATTERN MAPPING COMPLETE

