# ArgoCD Migration State - February 7, 2026

## STATUS: COMPLETE

All phases of the ArgoCD GitOps migration have been completed successfully.

## Completed

### Phase 1: Prerequisites
- [x] Helm CLI (was already installed)
- [x] ArgoCD installed via Helm (v9.4.1 / ArgoCD v3.3.0) in `argocd` namespace
- [x] External Secrets Operator v0.19.2 installed via ArgoCD (pinned for K8s 1.28 compat)
- [x] SSH deploy key generated and added to GitHub repo
- [x] ArgoCD repo secrets created (Git SSH + Helm repo)
- [x] IAM user `external-secrets-operator` created with SecretsManager read-only (scoped to `family-pickem/*`)
- [x] K8s secret `aws-secret-manager-credentials` created in `external-secrets` namespace
- [x] ClusterSecretStore `aws-secrets-manager` created and validated (Status: Valid, Ready: True)

### Phase 2: Helm Chart Updates (committed + pushed)
- [x] pickemctl-deployment.yaml template
- [x] pickemctl-secret.yaml template (conditional on ESO)
- [x] external-secret-envvars.yaml template (v1 API)
- [x] external-secret-pickemctl.yaml template (v1 API)
- [x] backup-cronjob.yaml template
- [x] secret.yaml made conditional (skip when ESO enabled)
- [x] values.yaml updated with pickemctl, externalSecrets, backup sections

### Phase 3: Environment Values (committed + pushed)
- [x] values-prd.yaml created
- [x] values-dev.yaml updated

### Phase 4: ArgoCD Applications
- [x] ArgoCD self-management Application → Synced, Healthy
- [x] External Secrets Application → Synced, Healthy
- [x] ingress-nginx Application → Synced, Healthy
- [x] pickem-dev Application → Synced, Healthy
- [x] pickem-prd Application → Synced, Healthy

### Phase 5: GitHub Actions
- [x] publish-artifacts.yaml updated with `update_argocd` job
- [x] sed pattern uses `[0-9][^\"]*` to only match version numbers (not `main`)

### Phase 6: Production Cutover
- [x] pickem-prd ArgoCD Application applied
- [x] ArgoCD took ownership of existing pickem-prd resources
- [x] StatefulSet immutable field issue resolved (existingClaim for PostgreSQL PVC)
- [x] ignoreDifferences added for ExternalSecret defaults and PostgreSQL secret
- [x] All pods healthy (Django, pickemctl, PostgreSQL)
- [x] CronJobs running (update-data every minute, backup at 2am)
- [x] ExternalSecrets synced from AWS Secrets Manager
- [x] Orphaned pre-migration resources cleaned up

### AWS Secrets Manager
- [x] `family-pickem/prd/envvars` - production env vars
- [x] `family-pickem/prd/pickemctl` - production pickemctl config
- [x] `family-pickem/dev/envvars` - dev env vars (DATABASE_HOST: `pickem-dev-postgresql`)
- [x] `family-pickem/dev/pickemctl` - dev pickemctl config (host: `pickem-dev-postgresql`)

### Infrastructure
- [x] PV `postgres-dev-pv` created (10Gi, /opt/postgres-dev, storageClass: manual)
- [x] /opt/postgres-dev permissions fixed on dagabuntu.home (chown 1001:1001, chmod 777)
- [x] Dev database seeded from production via pg_dump/psql pipe
- [x] Production PostgreSQL uses existingClaim: postgres-prd-pvc

### Cleanup
- [x] Old `postgres-backup` CronJob deleted (replaced by `family-pickem-prd-backup`)
- [x] Old `postgres-backup-script` ConfigMap deleted (replaced by `family-pickem-prd-backup-script`)
- [x] Old `pickemctl-config` Secret deleted (replaced by ESO-managed `family-pickem-prd-pickemctl`)
- [x] Old Helm release secrets (v1-v6) deleted (ArgoCD manages releases now)

## Known Issues / Notes
- K8s 1.28 on dagabuntu.home — ESO pinned to v0.19.2 (v1.x+ needs K8s 1.30+ for selectableFields CRD)
- No cert-manager on cluster — TLS terminated at Cloudflare edge
- StorageClass is `manual` with no dynamic provisioner — PVs must be pre-created
- This machine (fedora) is NOT the K8s node — use `ssh jim@192.168.1.222` for node ops
- Bitnami PostgreSQL subchart names services as `{release}-postgresql`, NOT `{fullnameOverride}-postgresql`
- ArgoCD ignoreDifferences configured for ExternalSecret CRD server-defaults and PostgreSQL secret random password

## Remaining: Test End-to-End Pipeline
- [ ] Create a GitHub Release → verify GitHub Actions updates `pickem-prd.yaml` targetRevision → ArgoCD syncs production

## Useful Commands
```bash
# Check overall status
kubectl get applications -n argocd

# Check ExternalSecrets
kubectl get externalsecrets -A

# Force ESO re-sync
kubectl annotate externalsecret <name> -n <ns> force-sync=$(date +%s) --overwrite

# Check pod status
kubectl get pods -n pickem-prd
kubectl get pods -n pickem-dev
```
