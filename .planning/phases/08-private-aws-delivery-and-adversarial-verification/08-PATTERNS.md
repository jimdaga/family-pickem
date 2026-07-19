# Phase 8: Private AWS Delivery and Adversarial Verification - Pattern Map

**Mapped:** 2026-07-18  
**Files analyzed:** 11 anticipated modified/new files  
**Analogs found:** 10 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pickem/pickem_api/storage.py` | service / storage adapter | file-I/O | same file: `FamilyLogoStorage` | exact |
| `pickem/pickem/settings.py` | config | configuration | same file: existing `AWS_STORAGE_*` block | exact |
| `pickem/pickem_homepage/views.py` | controller | request-response + file-I/O | same file: `family_pool_admin_settings` | exact |
| `pickem/pickem_api/tests/test_family_logo_storage.py` | test | file-I/O | same file: `FamilyLogoStorageTests` | exact |
| `pickem/pickem_homepage/tests.py` | test | request-response + file-I/O | same file: `FamilyLogoUploadFoundationTests` | exact |
| `charts/family-pickem/templates/external-secret-logo-storage.yaml` | deployment template | configuration / secret sync | `templates/external-secret-envvars.yaml` | exact |
| `charts/family-pickem/templates/deployment.yaml` | deployment template | configuration | same file: envFrom for migration/app containers | exact |
| `charts/family-pickem/values.yaml` | Helm configuration | configuration | same file: `externalSecrets` values | exact |
| `infra/app/values-dev.yaml` | environment config | configuration | same file: `externalSecrets` override | exact |
| `infra/app/values-prd.yaml` | environment config | configuration | same file: `externalSecrets` override | exact |
| `docs/...family-logo-storage...md` (runbook/provisioning evidence) | operations documentation | batch / external API | `infra/grafana-k8s-monitoring/README.md` and `skills/release-fp/SKILL.md` | role-match |

## Pattern Assignments

### `pickem/pickem_api/storage.py` (service/storage adapter, file-I/O)

**Analog:** existing `FamilyLogoStorage` in the same file (lines 11-65).

**Private object contract** (lines 11-21):

```python
class FamilyLogoStorage(S3Boto3Storage):
    """Keep generated logos private in S3, with an isolated local-dev fallback."""

    location = "family-logos"
    default_acl = None
    file_overwrite = False
    querystring_auth = True
    object_parameters = {
        "ContentType": "image/webp",
        "CacheControl": "private, max-age=31536000, immutable",
    }
```

Extend this class rather than introducing a second storage type. The dedicated `FAMILY_LOGO_*` values must be passed only to this storage backend, while retaining the current local `FileSystemStorage` fallback when logo bucket configuration is absent. Keep `location` as the one-and-only `family-logos` prefix source.

**Development fallback/delegation pattern** (lines 23-64):

```python
if not getattr(settings, "AWS_STORAGE_BUCKET_NAME", None):
    self._local_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, self.location),
        base_url=f"{settings.MEDIA_URL}{self.location}/",
    )
...
def url(self, name, parameters=None, expire=None, http_method=None):
    if self._local_storage:
        return self._local_storage.url(name)
    return super().url(name, parameters=parameters, expire=expire, http_method=http_method)
```

Replace the generic bucket predicate with the logo-specific configuration predicate and set the documented 300-second expiry at this seam; do not make callers select credentials or signing lifetime.

### `pickem/pickem/settings.py` (configuration)

**Analog:** existing generic S3 configuration block (lines 328-338).

```python
AWS_S3_ADDRESSING_STYLE = "virtual"

if 'AWS_STORAGE_BUCKET_NAME' in os.environ:
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

    AWS_STORAGE_BUCKET_NAME = os.environ['AWS_STORAGE_BUCKET_NAME']
    AWS_S3_REGION_NAME = os.environ['AWS_S3_REGION_NAME']
    AWS_S3_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
    AWS_S3_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
```

Add independent, environment-derived `FAMILY_LOGO_*` settings adjacent to this block. Do not change global static/default storage credentials to use the logo principal; the backup CronJob still consumes the generic AWS keys.

### `pickem/pickem_homepage/views.py` (controller, request-response/file-I/O)

**Analog:** `family_pool_admin_settings` (lines 1301-1443).

**Tenant authorization and locking** (lines 1301-1335):

```python
@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_settings(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    family = tenant_context.family
    pool = tenant_context.pool
    ...
    with transaction.atomic():
        locked_family = Family.objects.select_for_update().get(id=family.id)
        locked_pool = Pool.objects.select_for_update().get(
            id=pool.id,
            family=locked_family,
        )
```

All lifecycle work stays inside this route and derives the family/pool from `request.tenant_context`; never accept a family id, pool id, or object name from `POST` as authority.

**Current compensation pattern** (lines 1379-1397 and 1417-1434):

```python
old_logo_name = locked_family.logo.name
locked_family.logo.save('canonical.webp', processed_logo, save=False)
new_logo_name = locked_family.logo.name
try:
    locked_family.save(update_fields=update_fields)
    ...
except Exception:
    locked_family.logo.storage.delete(new_logo_name)
    locked_family.logo.name = old_logo_name
    raise
...
except Exception:
    if processed_logo is not None:
        locked_family.logo.storage.delete(new_logo_name)
        locked_family.logo.name = old_logo_name
    raise
```

Preserve this pre-commit compensation exactly. After the model and audit write both succeed, register deletion of only the captured prior generated key through `transaction.on_commit`; removals need the same capture-before-clear and post-commit callback. The helper must log a stable family/key correlation on S3 delete failure without logging presigned URLs or credentials.

**Cross-cutting on-commit analog:** invitation delivery uses the same ordering in `views.py` lines 844-852:

```python
transaction.on_commit(
    lambda inv=invitation, link=invite_link, code=raw_code: (
        send_family_invitation_email(
            invitation=inv,
            invite_link=link,
            invite_code=code,
        )
    )
)
```

Capture values as lambda default arguments so a later mutation cannot change the intended old key.

### `pickem/pickem_api/tests/test_family_logo_storage.py` (test, file-I/O)

**Analog:** `FamilyLogoStorageTests` (lines 9-49).

```python
@override_settings(AWS_STORAGE_BUCKET_NAME="", MEDIA_ROOT="/tmp/family-pickem-logo-test-media")
def test_without_a_bucket_storage_uses_local_media_urls(self):
    storage = FamilyLogoStorage()
    name = storage.save("test-logo.webp", ContentFile(b"webp"))
    self.addCleanup(storage.delete, name)
    self.assertTrue(storage.exists(name))
    self.assertEqual(storage.url(name), "/media/family-logos/test-logo.webp")
```

Expand this focused module using `override_settings` and `unittest.mock` rather than AWS access: prove dedicated settings choose S3 initialization, generic `AWS_*` credentials cannot satisfy configured logo storage, the fixed signing expiry is supplied, and the local fallback remains usable in tests/dev.

### `pickem/pickem_homepage/tests.py` (test, request-response/file-I/O)

**Analog:** `FamilyLogoUploadFoundationTests` (lines 6627-6889).

**Isolated storage seam** (lines 6628-6638):

```python
field = Family._meta.get_field('logo')
self._previous_logo_storage = field.storage
field.storage = FileSystemStorage(location=self._logo_storage_tmp.name)
self.addCleanup(setattr, field, 'storage', self._previous_logo_storage)
self.family.logo.storage = field.storage
```

Use this seam (or a narrowly scoped storage spy layered on it) for create/replace/remove assertions. Do not use real S3 in request tests.

**Real settings POST and audit assertion** (lines 6768-6780):

```python
response = self.client.post(self._settings_url(), {
    'family_name': self.family.name,
    'pool_name': self.pool.name,
    **self._default_scoring_fields(), 'remove_logo': 'true',
})
self.assertEqual(response.status_code, 302)
self.family.refresh_from_db()
self.assertFalse(self.family.logo.name)
audit = FamilyAuditLog.objects.filter(family=self.family).latest('created_at')
```

Add lifecycle tests here: successful replace deletes exactly the old name after commit; successful removal deletes exactly the old name after commit; create deletes no old key; an audit/database failure deletes only the newly-created object and retains the old reference. Add route-level anonymous, ordinary-member, wrong-family/pool, forged identity/key fields, and `Client(enforce_csrf_checks=True)` no-CSRF cases with no DB/storage/audit side effects.

**Authorization behavior source:** `pickem/pickem_homepage/authz.py` lines 16-36.

```python
except AuthenticationRequired:
    return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
except TenantNotFound:
    raise Http404()
except PermissionDeniedForTenant:
    return HttpResponseForbidden('Permission denied.')
```

Assert the existing redirect/403/404 semantics rather than adding new error handling, and always assert no side effects after the response.

### `charts/family-pickem/templates/external-secret-logo-storage.yaml` (deployment template, configuration/secret sync)

**Analog:** `charts/family-pickem/templates/external-secret-envvars.yaml` (lines 1-22).

```yaml
{{- if .Values.externalSecrets.enabled }}
apiVersion: external-secrets.io/v1
kind: ExternalSecret
...
  secretStoreRef:
    name: {{ .Values.externalSecrets.clusterSecretStore }}
    kind: ClusterSecretStore
  target:
    name: {{ include "family-pickem.fullname" . }}-envvars
    creationPolicy: Owner
    deletionPolicy: Retain
  dataFrom:
    - extract:
        key: {{ .Values.externalSecrets.envvarsKey }}
{{- end }}
```

Render a second owner-managed ExternalSecret with a distinct target and `logoStorageKey` value. Keep secret values out of the chart and retain the existing `ClusterSecretStore` reference. The planner should choose guards that fail safely/avoid a blank remote key in dev values.

### `charts/family-pickem/templates/deployment.yaml` (deployment template, configuration)

**Analog:** existing migration and application `envFrom` blocks (lines 31-58).

```yaml
initContainers:
  - name: {{ .Chart.Name }}-migrate
    ...
    envFrom:
    - secretRef:
        name: {{ include "family-pickem.fullname" . }}-envvars
...
containers:
  - name: {{ .Chart.Name }}
    ...
    envFrom:
    - secretRef:
        name: {{ include "family-pickem.fullname" . }}-envvars
```

Add the logo-storage Secret only to these two workloads. Do not alter `templates/backup-cronjob.yaml`, whose explicit generic AWS key references (lines 84-100) demonstrate why it must not receive the logo credentials.

### Helm values (configuration)

**Analogs:** `charts/family-pickem/values.yaml` lines 114-117 and `infra/app/values-{dev,prd}.yaml` lines 45-48 / 44-47.

```yaml
externalSecrets:
  enabled: true
  clusterSecretStore: aws-secrets-manager
  envvarsKey: family-pickem/dev/envvars
```

Add a named logo-storage remote key alongside `envvarsKey`, defaulting to an empty string in chart defaults and set to the environment-specific AWS Secrets Manager name in dev/prd values. This preserves the existing chart’s no-plaintext-secret convention.

### Operations/provisioning runbook (operations documentation, batch/external API)

**Analog:** `infra/grafana-k8s-monitoring/README.md` and `skills/release-fp/SKILL.md`.

The Grafana README’s documented sequence is the closest operational form: AWS Secrets Manager creation/update, ESO force-sync annotation, `kubectl get externalsecret`, then workload verification. The release skill supplies the project’s release gate: local checks, Helm renders, PR/review, GitHub Release trigger, and artifact verification. Follow that style with commands that use placeholders/environment-local shell variables, never literal access keys or secret JSON in Git.

## Shared Patterns

### Tenant Authorization

**Source:** `pickem/pickem_homepage/authz.py` lines 16-36; `pickem/pickem_homepage/views.py` lines 1301-1332.  
**Apply to:** all logo mutations and adversarial request tests.

Tenant identity comes solely from URL resolution plus `family_member_required(ADMIN)` and is re-locked in the transaction. Form data can carry crop/removal intent only; it cannot choose another family, pool, or storage key.

### Transaction and Storage Compensation

**Source:** `pickem/pickem_homepage/views.py` lines 1379-1434.  
**Apply to:** replacement/removal lifecycle changes.

Write the new canonical object before the DB row, compensate it on DB/audit failure, and use `transaction.on_commit` only for old-object cleanup. This codebase already uses `on_commit` for external effects at lines 844-852.

### Secret Delivery Isolation

**Source:** `charts/family-pickem/templates/external-secret-envvars.yaml` and `templates/deployment.yaml`.  
**Apply to:** logo-storage ExternalSecret/template/value changes.

The chart creates owner-managed secrets from the shared ClusterSecretStore and mounts them with `envFrom`. A separate target preserves least privilege and avoids exposing logo credentials to the backup CronJob.

### Verification Style

**Source:** `pickem/pickem_api/tests/test_family_logo_storage.py`, `FamilyLogoUploadFoundationTests`, `skills/release-fp/SKILL.md`.  
**Apply to:** all Phase 8 tests and release evidence.

Use isolated Django storage, request-level test clients, `override_settings`, mock/spies, `manage.py check`, migration dry run, focused/full tests, and rendered Helm charts. Runtime AWS/Kubernetes checks belong in an explicit staging/production runbook rather than in ordinary Django tests.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| IAM provisioning script or policy artifact (final path at planner discretion) | operations automation | batch / AWS API | The repository has AWS command documentation but no existing IAM policy/provisioning script. Use the documented AWS CLI approach from `08-RESEARCH.md`, keep secret values external, and provide idempotence/preflight checks. |

## Metadata

**Analog search scope:** `pickem/`, `charts/family-pickem/`, `infra/app/`, `infra/grafana-k8s-monitoring/`, `skills/release-fp/`, and phase artifacts.  
**Files scanned:** 17  
**Pattern extraction date:** 2026-07-18
