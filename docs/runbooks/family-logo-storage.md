# Family logo storage operations

Family logos are private WebP objects under `family-pickem/family-logos/*`. Each
environment uses its own IAM user and Secrets Manager entry:

| Environment | IAM user | Secrets Manager key |
| --- | --- | --- |
| dev | `family-pickem-dev-logo-storage` | `family-pickem/dev/family-logo-storage` |
| prd | `family-pickem-prd-logo-storage` | `family-pickem/prd/family-logo-storage` |

The stored JSON contains only the `FAMILY_LOGO_*` configuration consumed by the
application: bucket, region, short signed-URL expiry, and the dedicated IAM
credential. It is reconciled by the existing `aws-secrets-manager`
ClusterSecretStore into `<release>-logo-storage`. Helm injects that target only
into the web Deployment and its migration init container. The backup CronJob
continues to use only its existing general-purpose secret.

## Provision or rotate

Use an authenticated, audited AWS CLI identity and the appropriate Kubernetes
context. Never paste a credential into a terminal, chart value, manual
Kubernetes Secret, ticket, or chat.

```bash
LOGO_STORAGE_NAMESPACE=family-pickem ./infra/family-logo-storage/provision.sh dev
LOGO_STORAGE_NAMESPACE=family-pickem ./infra/family-logo-storage/provision.sh prd
```

The script is idempotent. It aborts before changing credentials unless the
bucket is in `us-east-1`, all four Block Public Access switches are enabled,
Object Ownership is `BucketOwnerEnforced`, default encryption is present, and
the bucket policy is not public. It updates the exact three-action object-prefix
policy, then proves both expected allows and root/different-prefix/ACL/listing/
bucket-policy denials with IAM simulation.

It first reads only the existing secret metadata/current key identifier and IAM
key metadata. A matching active key is reused. Otherwise it creates one
replacement, keeps the secret only in process memory, updates the complete
Secrets Manager JSON, forces the ExternalSecret refresh, waits for Ready, and
waits for the Deployment rollout (which includes the migration init container).
Only after those checks does it deactivate and delete the superseded key.

If Secret Manager, ESO, or rollout validation fails, the script restores the
prior secret value when one existed, retains/reactivates the prior key, and
deactivates/deletes the unadopted replacement. Output includes only redacted
identity, key, and secret-version identifiers; it never emits credential values.

## Release evidence

Record the command exit status and redacted evidence in the release ticket:

```bash
kubectl -n family-pickem get externalsecret family-pickem-prd-logo-storage
kubectl -n family-pickem rollout status deployment/family-pickem-prd --timeout=5m
kubectl -n family-pickem get secret family-pickem-prd-logo-storage -o jsonpath='{.metadata.ownerReferences[0].kind}{"\n"}'
```

Expected results: the ExternalSecret is `Ready`, the Deployment completed its
rollout, and the resulting Secret is owner-managed by an ExternalSecret. Do not
render, print, decode, or copy Secret data as evidence.

Then conduct the staging upload, replacement, removal, and signed-delivery
smoke tests defined in the Phase 8 release checklist before production. If the
script reports an unsafe bucket control or an IAM simulation mismatch, stop the
release and correct the cloud configuration; do not broaden the policy or add
ACL permissions as a workaround.
