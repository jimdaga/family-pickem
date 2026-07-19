# Phase 8: Private AWS Delivery and Adversarial Verification - Research

**Researched:** 2026-07-18  
**Domain:** Private S3 asset delivery, IAM/Secrets Manager/ESO deployment, and Django adversarial lifecycle verification  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Private delivery
- **D-01:** Serve family logos directly from the existing private S3 bucket with short-lived signed URLs. Do not make objects or the bucket public and do not add a Django image-proxy endpoint.

### AWS credentials and deployment
- **D-02:** Use a dedicated least-privilege IAM principal for family-logo access, restricted to the `family-logos/` prefix in the existing `family-pickem` bucket in `us-east-1`.
- **D-03:** Store that principal's credentials and logo-storage configuration in a dedicated AWS Secrets Manager secret; synchronize them into the application namespace only through the existing ESO `ClusterSecretStore` and Helm ExternalSecret flow. No credentials may enter Git or manually-created Kubernetes Secrets.

### Object lifecycle
- **D-04:** After a successful replacement or removal database transaction, delete the now-obsolete generated S3 object immediately. Preserve compensation behavior so a failed database/audit mutation cannot orphan or break the currently referenced object.

### Release gate
- **D-05:** Require automated security coverage plus a staging upload/replace/remove smoke test and a production smoke test before release.

### the agent's Discretion
- Select the signed-URL lifetime, exact IAM/Secrets Manager names, and test mechanics consistent with the existing deployment conventions and AWS security guidance.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| S3-02 | Application S3 permissions are least-privilege and prefix-limited; public ACL/policy access and object ownership bypasses are not introduced. | A dedicated IAM user policy can allow only `GetObject`, `PutObject`, and `DeleteObject` on `family-pickem/family-logos/*`; the existing bucket already has all four Block Public Access settings and BucketOwnerEnforced ownership. |
| S3-03 | The application receives S3 configuration and credentials through AWS Secrets Manager and the existing External Secrets Operator/Kubernetes flow, with no credentials committed to Git or manually managed Kubernetes Secrets. | The existing `ClusterSecretStore` is Ready and the Helm `ExternalSecret` extraction pattern can create a separate, owner-managed logo secret in each app namespace. |
| SAFE-02 | Automated tests prove unauthenticated, ordinary-member, wrong-family, forged tenant/object-key, and missing-CSRF requests cannot mutate or infer another family’s logo. | Existing tenant decorators/form POST route, Django CSRF test client, and isolated test storage support direct negative and no-side-effect tests. |
| SAFE-03 | Create, replace, and remove actions are tenant-scoped, audit logged, and leave no referenced obsolete logo object. | The locked view already holds family/pool rows, writes the new object before DB/audit mutation, and compensates failed new writes; Phase 8 adds post-commit deletion of the captured old key plus lifecycle tests. |
</phase_requirements>

## Summary

The application already has the right application boundary: generated WebP files are held under `family-logos/`, URLs are signed by `FamilyLogoStorage`, writes are initiated only through the tenant-derived admin settings route, and tests replace model storage with a local filesystem. The remaining production work is to keep logo S3 credentials distinct from the existing broad application/backup credentials, bind them explicitly to this storage backend, and prove that object replacement/removal leaves only the live reference.

The live AWS audit is favorable: `family-pickem` resolves to `us-east-1`, has all four S3 Block Public Access switches enabled, has `BucketOwnerEnforced` ownership controls, has AES256 default encryption, and has no bucket policy. The account has no existing logo-named IAM user or local policy. [VERIFIED: read-only AWS CLI audit, 2026-07-18] The existing `aws-secrets-manager` `ClusterSecretStore` is Ready and its production `ExternalSecret` extracts `family-pickem/prd/envvars`; that pattern is suitable for a separate logo secret. [VERIFIED: live Kubernetes read-only audit, 2026-07-18]

**Primary recommendation:** Create a dedicated `family-pickem-{env}-logo-storage` IAM user/policy and `family-pickem/{env}/family-logo-storage` Secrets Manager secret, render a second ESO `ExternalSecret` for it, use `FAMILY_LOGO_*` settings only in `FamilyLogoStorage`, and make the view synchronously delete its captured old key through `transaction.on_commit()` after DB/audit success.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Canonical logo object read/write/delete | Database / Storage | API / Backend | S3 persists the controlled object; Django decides its server-derived key and lifecycle. |
| Signed URL generation | API / Backend | Database / Storage | django-storages/boto3 signs a read for a stored, server-controlled name; the browser receives only the resulting URL. |
| IAM prefix and public-access protection | Database / Storage | Deployment | S3/IAM own authorization to bucket resources; Helm only delivers the constrained credentials. |
| Secrets delivery | Deployment | API / Backend | Secrets Manager and ESO supply Kubernetes Secret data; settings explicitly consume logo-only environment names. |
| Tenant/CSRF/object-key attack defense | API / Backend | Browser / Client | Route identity, membership, CSRF, form allowlist, row locking, and audit are enforced before any storage mutation. |
| Release smoke evidence | Deployment | API / Backend | Deployed workloads and AWS policy must be observed in staging and production after automated tests pass. |

## Standard Stack

### Core

| Library / service | Version | Purpose | Why Standard |
|---|---:|---|---|
| Django | 4.2.30 [VERIFIED: `pickem/requirements.txt`] | Tenant POST, transaction and CSRF boundary | Existing project framework and test harness. |
| django-storages + boto3 | 1.13.1 / 1.35.99 [VERIFIED: `pickem/requirements.txt`] | S3 storage and SigV4 GET URL generation | Already used by `FamilyLogoStorage`; no new package is required. |
| Amazon S3 | existing `family-pickem`, `us-east-1` [VERIFIED: read-only AWS CLI audit] | Private canonical logo objects | Existing bucket already satisfies the no-public-ACL ownership baseline. |
| IAM + AWS Secrets Manager | existing AWS account | Dedicated object policy and encrypted secret | AWS supports resource-scoped S3 policies and JSON secret values. [CITED: https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-policy-language-overview.html] |
| External Secrets Operator | existing v1 `ClusterSecretStore` [VERIFIED: live Kubernetes read-only audit] | AWS Secrets Manager → namespace Secret synchronization | Existing chart and cluster already use this exact flow. |

### Supporting

| Component | Purpose | When to Use |
|---|---|---|
| `transaction.on_commit()` | Run old-object deletion only after DB/audit commit | Every successful replace/remove path. It executes synchronously after the outer transaction commits; do not schedule delete before commit. |
| Django `TestCase` + `Client(enforce_csrf_checks=True)` | Verify tenant and CSRF denials | New SAFE-02 request-level tests. |
| `unittest.mock` storage spy/fake | Verify exact old-key deletion and failure compensation without AWS | SAFE-03 lifecycle and signed-storage configuration tests. |
| `aws iam simulate-principal-policy` | Verify policy allows only intended prefix/actions | Provisioning/release verification against the new IAM user ARN. |

### Alternatives Considered

| Instead of | Could Use | Why it is not selected |
|---|---|---|
| Direct signed S3 GET | Public bucket/CloudFront/public URL | Contradicts D-01 and would broaden the exposure boundary. |
| Dedicated logo Secret and env names | Add logo credentials to existing `envvars` secret | The existing shared env secret feeds the backup CronJob, so that would expose logo credentials to an unrelated workload. [VERIFIED: `charts/family-pickem/templates/backup-cronjob.yaml`] |
| Synchronous post-commit delete | Delete old object before database commit | A later DB/audit failure would break the currently referenced asset, violating D-04. |
| Existing ESO extraction | Manually create a Kubernetes Secret | Contradicts D-03 and is not reconciled/auditable from AWS Secrets Manager. |

**Installation:** none. This phase must not add an external application package.

## Package Legitimacy Audit

No package installation is planned. Django, boto3, and django-storages are already pinned project dependencies, so there is no package legitimacy gate to run.

## Architecture Patterns

### System Architecture Diagram

```text
Commissioner multipart POST
  -> tenant URL + CSRF + admin membership decorator
  -> locked Family/Pool rows + Pillow-generated WebP
  -> FamilyLogoStorage (logo-only credentials)
  -> private S3: family-pickem/family-logos/<family-id>/<uuid>.webp
  -> DB row + FamilyAuditLog commit
       | failure: delete only newly written key; retain existing row/key
       v success
     on_commit: delete captured prior key (replace/remove only)

Family page rendering
  -> controlled `Family.logo.name`
  -> FamilyLogoStorage.url(..., expire=300)
  -> short-lived SigV4 GET URL
  -> private S3 object

AWS Secrets Manager (`family-pickem/{env}/family-logo-storage`)
  -> existing ClusterSecretStore `aws-secrets-manager`
  -> Helm-rendered logo ExternalSecret
  -> namespace `*-logo-storage` Kubernetes Secret
  -> app + migration containers only (not backup CronJob)
```

### Pattern 1: Explicit logo-only storage configuration

**What:** Extend `FamilyLogoStorage` with a boto3 session/configuration using dedicated `FAMILY_LOGO_*` values: bucket name, region, access key, secret key, and a fixed 300-second query-string expiry. Preserve the existing filesystem fallback only when logo bucket configuration is absent.

**When to use:** Production always sets the full dedicated configuration. Development/tests omit it and continue to use isolated local media.

**Why:** `FamilyLogoStorage` currently decides S3 use from the generic `AWS_STORAGE_BUCKET_NAME`, and project settings assign generic `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. That coupling cannot prove the logo principal is dedicated. [VERIFIED: `pickem/pickem_api/storage.py`, `pickem/pickem/settings.py`]

**Configuration contract:**

```text
FAMILY_LOGO_STORAGE_BUCKET_NAME=family-pickem
FAMILY_LOGO_AWS_S3_REGION_NAME=us-east-1
FAMILY_LOGO_AWS_ACCESS_KEY_ID=<dedicated principal access key>
FAMILY_LOGO_AWS_SECRET_ACCESS_KEY=<dedicated principal secret>
FAMILY_LOGO_AWS_QUERYSTRING_EXPIRE=300
```

`300` seconds is the recommended phase default: it is short relative to the existing private immutable object cache header but practical for page rendering. S3 treats presigned URLs as bearer tokens, and the signing principal must have the operation permission; AWS permits much longer SDK lifetimes, so the shorter application setting is deliberate. [CITED: https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html]

### Pattern 2: Minimal identity policy and separate ESO target

**What:** Provision one IAM user/policy per environment (`family-pickem-dev-logo-storage`, `family-pickem-prd-logo-storage`) and one JSON Secrets Manager secret per environment (`family-pickem/dev/family-logo-storage`, `family-pickem/prd/family-logo-storage`). Add Helm values for the remote secret key and a second `ExternalSecret` target. Inject that target into migrate/app containers, not the backup CronJob.

**IAM policy shape:**

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "FamilyLogoObjectsOnly",
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
    "Resource": "arn:aws:s3:::family-pickem/family-logos/*"
  }]
}
```

Do not grant `s3:PutObjectAcl`, bucket-policy actions, public ACL actions, or broad bucket/object wildcards. `ListBucket` is deliberately absent because the logo flow uses server-generated names and does not need listing; if an actual django-storages call requires it during implementation, add only `s3:ListBucket` on the bucket ARN with `s3:prefix: family-logos/*`, then prove the condition with IAM simulation. AWS documents that object actions use prefix object ARNs and that `s3:prefix` restricts listing. [CITED: https://docs.aws.amazon.com/AmazonS3/latest/userguide/security_iam_service-with-iam.html] [CITED: https://docs.aws.amazon.com/AmazonS3/latest/userguide/amazon-s3-policy-keys.html]

The existing bucket controls must remain unchanged: all Block Public Access flags true, BucketOwnerEnforced ownership, and no public bucket policy. Object Ownership with BucketOwnerEnforced disables ACLs. [CITED: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html]

### Pattern 3: Post-commit old-object cleanup with pre-commit compensation

**What:** Capture the prior `logo.name` before replacement/removal. Keep the existing "write new object, then database row/audit" flow and delete the new key on DB/audit exception. Register old-key deletion with `transaction.on_commit()` only after the row and audit record are complete.

**When to use:**

- Create: no prior key, therefore no old-object delete.
- Replace: new generated key is persisted; old key is deleted only after commit.
- Remove: DB reference is cleared/audited; former key is deleted only after commit.

**Failure policy:** A database/audit failure must delete the new object and restore the in-memory old name, exactly as the current code does. A post-commit S3 delete cannot be rolled back by the database; it must be attempted immediately, logged with a stable key/family correlation value, and surfaced to operational monitoring if it fails. Tests must demonstrate successful deletion and that no delete is registered/executed on failed mutation. Do not falsely claim cross-service atomicity.

### Pattern 4: Request-level negative tests, not only decorator unit tests

**What:** Test the real settings POST with family/pool routes, local fake storage, and database assertions. Include anonymous, member-role, cross-family/cross-pool, forged `family_id`/`pool_id`/`logo` name/key form fields, and missing CSRF cases.

**Why:** The decorator and form intentionally derive the target from `request.tenant_context`, but SAFE-02 requires proof that actual requests cannot mutate or infer a different family. [VERIFIED: `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/authz.py`]

## Don’t Hand-Roll

| Problem | Don’t Build | Use Instead | Why |
|---|---|---|---|
| S3 request signing | Custom HMAC/signed-URL implementation | boto3 via django-storages | SigV4 expiry and credential signing are security-sensitive and already supported. |
| Image authorization policy | Browser-selected key/family fields | Existing tenant context + locked DB rows | Client inputs cannot be authority-bearing. |
| Secret synchronization | Ad hoc `kubectl create secret`/committed manifest | Existing ESO `ClusterSecretStore` + Helm `ExternalSecret` | Preserves the production reconciliation and no-Git-secret boundary. |
| Delete ordering | Manual before-commit S3 delete | `transaction.on_commit` plus existing compensation | Prevents a failed audit/DB mutation from destroying a still-referenced logo. |
| IAM validation | Visual policy review only | AWS IAM policy simulation plus bucket-control readback | Proves permitted/denied action/prefix combinations. |

## Common Pitfalls

1. **A signed URL is a bearer token.** Keep its lifetime at 300 seconds, never log it, and do not make the object public. [CITED: https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html]
2. **Generic `AWS_*` credentials are broader than the dedicated feature boundary.** Do not merely add logo keys to `family-pickem/{env}/envvars`; the backup CronJob reads that Secret. [VERIFIED: Helm chart]
3. **`on_commit()` is not a distributed transaction.** It protects the ordering, but an S3 delete outage after commit can leave an unreferenced old object. Record/alert it rather than deleting pre-commit or pretending it is impossible.
4. **A storage class `location` already prepends `family-logos/`.** IAM resource ARNs must contain that prefix exactly once, while model `upload_to` stays relative (`<family-id>/<uuid>.webp`). [VERIFIED: `pickem/pickem_api/storage.py`, `pickem/pickem_api/models.py`]
5. **Do not grant ACL permissions as a workaround.** The bucket is BucketOwnerEnforced and the storage contract uses `default_acl=None`; adding ACL calls would fail or broaden access. [VERIFIED: AWS audit] [CITED: AWS S3 bucket policy documentation]
6. **Do not inspect downloaded originals or user-selected URLs.** Continue re-encoding the server-generated WebP and rendering only `Family.logo`; remote URL import and direct browser S3 upload are out of scope. [VERIFIED: Phase 6/7 verification and D-01]
7. **A post body can forge any hidden field.** Tests must assert ignored/rejected foreign identity and object-key values, no storage mutation, and no differential response that reveals another family’s logo.
8. **ESO refresh is asynchronous.** The release runbook must wait for `ExternalSecret` Ready/refresh status and verify the workload receives the new secret before the staging upload smoke test.

## Code Examples

### Storage configuration seam

```python
# Shape only: pickem_api/storage.py
class FamilyLogoStorage(S3Boto3Storage):
    location = "family-logos"
    default_acl = None
    file_overwrite = False
    querystring_auth = True
    querystring_expire = 300

    def __init__(self, *args, **kwargs):
        kwargs.update({
            "bucket_name": settings.FAMILY_LOGO_STORAGE_BUCKET_NAME,
            "region_name": settings.FAMILY_LOGO_AWS_S3_REGION_NAME,
            "access_key": settings.FAMILY_LOGO_AWS_ACCESS_KEY_ID,
            "secret_key": settings.FAMILY_LOGO_AWS_SECRET_ACCESS_KEY,
        })
        super().__init__(*args, **kwargs)
```

The final code must preserve the current local `FileSystemStorage` fallback and avoid evaluating production-only settings when they are unset in test/dev.

### Correct cleanup ordering

```python
old_logo_name = locked_family.logo.name
# Save generated new object, persist locked family + audit in transaction.

if old_logo_name:
    transaction.on_commit(
        lambda: delete_obsolete_family_logo(storage, old_logo_name, family_id=locked_family.id)
    )
```

For removal, capture the old name before clearing the field and register the same callback after the audit record is created. The delete helper must take the captured name, never request data, route slug, or browser filename.

### Test shape for a forged object key

```python
response = client.post(settings_url, payload | {
    "family_id": other_family.id,
    "pool_id": other_pool.id,
    "logo_name": other_family.logo.name,
})
assert response.status_code in {302, 403, 404}
other_family.refresh_from_db()
assert other_family.logo.name == original_other_logo
storage.delete.assert_not_called()
```

The exact assertion splits by case: an authorized current-family update can redirect, but forged fields must neither select nor disclose the other family’s object; denied requests must not write current or other storage/DB rows.

## Project Constraints (from AGENTS.md)

- Do not start another local server; use the existing `http://localhost:8000` server and `curl` where runtime HTML validation is useful.
- Use Django ORM, normal Django naming, existing templates/routes, and project test commands; do not introduce raw SQL or a new authorization model.
- Local test/development must remain viable without AWS configuration; production uses environment configuration and Helm/ArgoCD.
- Tailwind work is unrelated to Phase 8; any deployment/template change still needs rendered Helm verification.
- Production publishing is triggered by a GitHub Release, not merely by a tag. Confirm the public Helm repository contains the target chart before advancing ArgoCD.
- Preserve existing dirty/untracked `pickem/media/` local upload artifacts; they are not phase source files.

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | Django `TestCase` / Django test client, Django 4.2.30 |
| Config file | `pickem/pickem/test_settings.py` |
| Quick run command | `cd pickem && ../venv/bin/python manage.py test pickem_api.tests.test_family_logo_storage pickem_homepage.tests.FamilyLogoUploadFoundationTests --settings=pickem.test_settings --verbosity=2` |
| Full suite command | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=1` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| S3-02 | Dedicated storage selects only `FAMILY_LOGO_*`, 300s signing, generated prefix; IAM allow/deny policy is simulated | Django unit + AWS CLI integration | focused Django command + `aws iam simulate-principal-policy` | ❌ Wave 0 expansion |
| S3-03 | Helm renders separate logo ExternalSecret/target and only app/migrate consume it; no plaintext credentials | Helm template + source regression | `helm template ... -f infra/app/values-{dev,prd}.yaml` + focused Django command | ❌ Wave 0 expansion |
| SAFE-02 | Anonymous/member/wrong-family/forged-key/missing-CSRF attempts have no logo DB/storage/audit side effect | Django request integration | focused Django command | ❌ Wave 0 expansion |
| SAFE-03 | Create/replace/remove audit correctly and delete exactly the obsolete key after commit; failed mutation compensates new key only | Django transaction/storage-spy integration | focused Django command | ❌ Wave 0 expansion |

### Sampling Rate

- **Per task commit:** focused Django tests plus `helm template` for chart tasks.
- **Per wave merge:** `manage.py check`, migration dry-run, focused app suites, and rendered dev/prd Helm charts.
- **Phase gate:** full Django suite, AWS policy/bucket-control read-only verification, deployed staging smoke, then production smoke before `$gsd-verify-work`/release.

### Wave 0 Gaps

- [ ] Expand `pickem/pickem_api/tests/test_family_logo_storage.py` for dedicated settings, 300-second URL expiry, and no generic-credential fallback in configured production mode.
- [ ] Expand `pickem/pickem_homepage/tests.py` `FamilyLogoUploadFoundationTests` (or a focused new class) for complete SAFE-02 and SAFE-03 transaction/storage-spy matrix.
- [ ] Add Helm assertions or a documented rendered-template verification command for separate ExternalSecret target, deployment/migrate-only injection, and no backup injection.
- [ ] Add a tracked staging/production logo smoke runbook with expected AWS/ESO checks and evidence fields.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | Yes | Existing login and normal Django session boundary before settings POST. |
| V3 Session Management | Yes | Django CSRF middleware/token; explicit enforced-CSRF client test. |
| V4 Access Control | Yes | `family_member_required(ADMIN)`, server-derived tenant context, locked family/pool lookup, object-key non-authority. |
| V5 Input Validation | Yes | Existing Pillow canonicalization, strict form crop parsing, ignore client identity/object fields. |
| V6 Cryptography | Yes | AWS SigV4 presigned URLs and Secrets Manager encryption; never hand-roll signatures/encryption. |
| V8 Data Protection | Yes | Private bucket, no ACL/public policy bypass, dedicated credentials, secret delivery through ESO. |
| V14 Configuration | Yes | Prefix-scoped IAM policy, no credentials in Git/manual namespace Secret, rendered Helm and AWS control checks. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Unauthorized family mutation / IDOR | Elevation of privilege | Tenant URL resolution, active-role decorator, locked tenant rows, negative route tests. |
| CSRF logo removal/replacement | Tampering | Existing CSRF middleware + `enforce_csrf_checks=True` test. |
| Forged S3 key or target family fields | Tampering / Information disclosure | No form field is authoritative; all key/name/family/pool values originate server-side; no response includes another asset. |
| Broad credential reuse | Elevation of privilege | Logo-only IAM user and secret; no injection into backup workload. |
| Public object/ACL exposure | Information disclosure | Block Public Access, BucketOwnerEnforced, no `PutObjectAcl`, private signed GET. |
| Delete-before-commit outage | Availability / Tampering | Pre-commit new-key compensation and post-commit old-key cleanup. |
| Presigned URL leakage/replay | Information disclosure | 300-second expiry, no logging, only controlled rendered asset URL. |

## Environment Availability

| Dependency | Required By | Available | Version / status | Fallback |
|---|---|---|---|---|
| AWS CLI | IAM/Secrets/bucket verification and provisioning | ✓ | aws-cli/2.7.23 | None for production provisioning; use reviewed CLI script/commands. |
| AWS account/bucket | S3-02/S3-03 | ✓ | `family-pickem`, `us-east-1`; private controls verified | Existing local filesystem fallback only for dev/test. |
| Kubernetes / ESO | S3-03 | ✓ | kubectl v1.30.3; `aws-secrets-manager` store Ready | Existing Helm/ESO flow; no manual K8s Secret fallback permitted. |
| Helm | chart render verification | ✓ | v3.7.2 | None; upgrade only if chart syntax requires it. |
| Python virtualenv | Django tests | ✓ | Python 3.10.6; Django 4.2.30 | None. |
| Docker | local deployment aid | ✓ | 29.4.0 | Not required for focused test suite. |

**Missing dependencies with no fallback:** none found.

**Missing dependencies with fallback:** none found.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | A 300-second signed URL lifetime is appropriate for all real production page loads. | Pattern 1 | Low; it is a locked-discretion default and can be tuned by an env value without changing privacy architecture. |
| A2 | `s3:ListBucket` is unnecessary for the current production logo call sequence. | Pattern 2 | Medium; validate with a staging real upload/replace/remove and IAM simulator; add only prefix-conditioned listing if a concrete django-storages call needs it. |
| A3 | The app/migrate deployment is the only workload that needs logo credentials. | Pattern 2 | Low; inspect any future worker workload before adding env injection. |

## Open Questions

None blocking planning. The plan should make the chosen IAM/secret names and `FAMILY_LOGO_AWS_QUERYSTRING_EXPIRE=300` visible in values/runbook rather than hard-coding them into application code.

## Sources

### Primary (HIGH confidence)

- [AWS S3 presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html) — signer permissions, bearer-token nature, expiry limits, and SigV4 signature-age policy capability.
- [AWS S3 IAM integration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security_iam_service-with-iam.html) and [S3 policy keys](https://docs.aws.amazon.com/AmazonS3/latest/userguide/amazon-s3-policy-keys.html) — bucket vs object ARN actions and prefix-restricted listing.
- [AWS S3 bucket policies/Object Ownership](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html) — BucketOwnerEnforced behavior and ACL disabling.
- [AWS Secrets Manager secret creation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/create_secret.html) and [CLI secret values](https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/put-secret-value.html) — JSON secret delivery and safe CLI handling caveat.
- [External Secrets Operator AWS Secrets Manager provider](https://external-secrets.io/latest/provider/aws-secrets-manager/) — fine-grained secret roles, JSON values, SecretStore/ExternalSecret pattern.
- [django-storages S3 backend](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html) — established project backend/configuration reference.

### Project evidence (HIGH confidence)

- `pickem/pickem_api/storage.py`, `pickem/pickem_api/models.py`, `pickem/pickem_homepage/views.py`, and logo tests — current storage, tenant mutation, compensation, and test seams.
- `charts/family-pickem/templates/external-secret-envvars.yaml`, `deployment.yaml`, `backup-cronjob.yaml`, `infra/app/values-{dev,prd}.yaml` — existing ESO path and the backup-secret exposure concern.
- Read-only AWS CLI and Kubernetes audits run 2026-07-18 — bucket controls, no existing logo IAM artifacts, `ClusterSecretStore` readiness, and existing production ExternalSecret binding.
- `.planning/phases/06-secure-logo-foundation/06-RESEARCH.md`, `06-VERIFICATION.md`, and Phase 7 context — inherited server-side image/tenant safety guarantees and phase boundary.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all services and libraries are already deployed/installed and were inspected.
- Architecture: HIGH — existing code/Helm seams align with AWS and ESO primary documentation.
- Pitfalls: HIGH — grounded in current code flow plus AWS private-delivery/IAM documentation.

**Research date:** 2026-07-18  
**Valid until:** 2026-08-17 (recheck live AWS/cluster resource state immediately before provisioning/release).
