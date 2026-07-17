# Grafana Cloud Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship cluster metrics, Kubernetes events, and pod logs (incl. the Django app) from the single-node `dagabuntu` cluster to Grafana Cloud's free tier, installed and configured entirely via ArgoCD + a pinned Helm chart, with credentials pulled by ESO from AWS Secrets Manager.

**Architecture:** A new ArgoCD multi-source `Application` deploys the pinned Grafana `k8s-monitoring` v4.3.0 chart into a `monitoring` namespace, taking its values from a git `values.yaml` and rendering a raw `ExternalSecret` from a git `path` source. The `ExternalSecret` uses the existing `aws-secrets-manager` `ClusterSecretStore` to materialize a `grafana-cloud-credentials` secret that the chart's Prometheus + Loki destinations authenticate with. The app-of-apps root picks the new Application up automatically.

**Tech Stack:** ArgoCD (app-of-apps), Helm (`grafana/k8s-monitoring` 4.3.0, Alloy Operator + Grafana Alloy collectors), External Secrets Operator v0.19.2, AWS Secrets Manager.

> **Scope note (post-portal, 2026-07-17):** the user supplied the portal-generated
> spec and chose the **full observability stack**. Tasks 1–3 are implemented and
> committed; the authoritative config lives in `infra/grafana-k8s-monitoring/`
> (four destinations — prometheus/loki/otlp/pyroscope; features clusterMetrics,
> hostMetrics, costMetrics, clusterEvents, podLogsViaLoki, applicationObservability,
> autoInstrumentation, profiling; five collectors; OpenCost + kepler on,
> windows-exporter off; cluster name `databuntu`). The lean per-task snippets
> below were the original draft — the committed files supersede them. The AWS SM
> secret (Task 4) now carries five keys: `prometheus-username`, `loki-username`,
> `otlp-username`, `profiles-username`, `access-token`. Render verified with
> `helm template … --version 4.3.0`: no token leaks into rendered output, no
> fleet-management, all five collectors present.

## Global Constraints

- **Chart version pinned** to `4.3.0` — never `main`/`latest`/`>=`. Upstream drift is a known hazard (cf. ESO 0.19.2 pin for k8s 1.28 compat).
- **k8s 1.28 single node** (`dagabuntu.home` / `192.168.1.222`). Collectors sized for one node: 1× `alloy-metrics`, 1× `alloy-singleton`, `alloy-logs` daemonset (= 1 pod).
- **GitOps only** — no `kubectl apply`/`helm install` of app resources by hand; every change lands via git → ArgoCD. Manual steps are limited to the AWS SM secret and live verification.
- **No secrets in git** — only endpoint URLs and usernames-as-secret-keys live in git. The `glc_` token and the instance-ID usernames live in AWS Secrets Manager only.
- **ESO IAM scope** is `family-pickem/*`; the secret path `family-pickem/monitoring/grafana-cloud` is already covered — no IAM change needed.
- **ESO API version** `external-secrets.io/v1`, `ClusterSecretStore` named `aws-secrets-manager` (match existing `external-secret-envvars.yaml`).
- **Cluster name** in all config: `dagabuntu`.
- **Free-tier budget** — enable only clusterMetrics, clusterEvents, podLogsViaLoki, hostMetrics(linux). Explicitly disable costMetrics/opencost, kepler, windows-exporter, profiling, traces, nodeLogs, autoInstrumentation.

## Files

- Create: `infra/grafana-k8s-monitoring/values.yaml` — chart configuration (destinations, features, collectors).
- Create: `infra/grafana-k8s-monitoring/manifests/external-secret.yaml` — ESO ExternalSecret → `grafana-cloud-credentials`.
- Create: `infra/grafana-k8s-monitoring/README.md` — one-time setup (AWS SM secret shape, portal values, verification).
- Create: `infra/argocd/applications/grafana-k8s-monitoring.yaml` — ArgoCD multi-source Application.
- Reference only (do not edit): `infra/argocd/applications/root-app.yaml` (globs `*.yaml`, picks up the new app), `infra/external-secrets/cluster-secret-store.yaml`, `charts/family-pickem/templates/external-secret-envvars.yaml` (ESO shape reference).

## Values To Obtain Before Task 2 (from Grafana Cloud portal → your stack → "Details"/"Connections")

- `PROM_URL` — Prometheus remote-write URL, e.g. `https://prometheus-prod-NN-prod-us-east-0.grafana.net/api/prom/push`
- `PROM_USERNAME` — Prometheus instance ID (numeric)
- `LOKI_URL` — Loki push URL, e.g. `https://logs-prod-NNN.grafana.net/loki/api/v1/push`
- `LOKI_USERNAME` — Loki instance ID (numeric)
- `ACCESS_TOKEN` — the `glc_...` access-policy token (already have one from onboarding; scopes include `metrics:write`+`logs:write`)

URLs go in git (`values.yaml`); the three credential values go in AWS SM only.

---

### Task 1: ExternalSecret manifest + directory scaffold

**Files:**
- Create: `infra/grafana-k8s-monitoring/manifests/external-secret.yaml`

**Interfaces:**
- Consumes: existing `ClusterSecretStore/aws-secrets-manager`; AWS SM secret `family-pickem/monitoring/grafana-cloud` (created in Task 4) whose JSON keys are `prometheus-username`, `loki-username`, `access-token`.
- Produces: k8s `Secret/grafana-cloud-credentials` in namespace `monitoring` with keys `prometheus-username`, `loki-username`, `access-token` — consumed by Task 2's destinations.

- [ ] **Step 1: Write the manifest**

Create `infra/grafana-k8s-monitoring/manifests/external-secret.yaml`. The `dataFrom.extract` form (matching the repo's `external-secret-envvars.yaml`) maps every JSON key in the AWS SM secret straight through to k8s secret keys, so no per-key mapping is needed. The sync-wave annotation makes ArgoCD apply this before the chart's collectors.

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: grafana-cloud-credentials
  namespace: monitoring
  annotations:
    # Materialize the credential secret before the Alloy collectors that mount it.
    argocd.argoproj.io/sync-wave: "-1"
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: grafana-cloud-credentials
    creationPolicy: Owner
    deletionPolicy: Retain
  dataFrom:
    - extract:
        key: family-pickem/monitoring/grafana-cloud
        conversionStrategy: Default
        decodingStrategy: None
        metadataPolicy: None
```

- [ ] **Step 2: Verify the YAML parses and has the expected shape**

Run:
```bash
python3 -c "import yaml,sys; d=yaml.safe_load(open('infra/grafana-k8s-monitoring/manifests/external-secret.yaml')); \
assert d['apiVersion']=='external-secrets.io/v1'; assert d['kind']=='ExternalSecret'; \
assert d['spec']['secretStoreRef']=={'name':'aws-secrets-manager','kind':'ClusterSecretStore'}; \
assert d['spec']['target']['name']=='grafana-cloud-credentials'; \
assert d['spec']['dataFrom'][0]['extract']['key']=='family-pickem/monitoring/grafana-cloud'; \
print('OK')"
```
Expected: prints `OK` (non-zero exit / AssertionError means a field is wrong).

- [ ] **Step 3: Commit**

```bash
git add infra/grafana-k8s-monitoring/manifests/external-secret.yaml
git commit -m "feat(monitoring): ESO ExternalSecret for Grafana Cloud credentials"
```

---

### Task 2: Chart values.yaml

**Files:**
- Create: `infra/grafana-k8s-monitoring/values.yaml`

**Interfaces:**
- Consumes: `Secret/grafana-cloud-credentials` (keys `prometheus-username`, `loki-username`, `access-token`) from Task 1; the five portal values from the "Values To Obtain" section.
- Produces: a values file referenced by Task 3's Application as `$values/infra/grafana-k8s-monitoring/values.yaml`.

- [ ] **Step 1: Write the values file**

Create `infra/grafana-k8s-monitoring/values.yaml`. Replace `<PROM_URL>` and `<LOKI_URL>` with the real portal URLs (usernames/token are NOT here — they come from the secret). Collector-to-feature bindings and presets are copied verbatim from Grafana's official v4.3.0 ArgoCD external-secrets example.

```yaml
# Grafana Cloud monitoring — k8s-monitoring chart v4.3.0 values.
# Credentials come from the ESO-managed Secret 'grafana-cloud-credentials'
# (keys: prometheus-username, loki-username, access-token). Only non-secret
# endpoint URLs live here.
cluster:
  name: dagabuntu

destinations:
  grafana-cloud-metrics:
    type: prometheus
    url: <PROM_URL>
    auth:
      type: basic
      usernameKey: prometheus-username
      passwordKey: access-token
    secret:
      create: false
      name: grafana-cloud-credentials
      namespace: monitoring
  grafana-cloud-logs:
    type: loki
    url: <LOKI_URL>
    auth:
      type: basic
      usernameKey: loki-username
      passwordKey: access-token
    secret:
      create: false
      name: grafana-cloud-credentials
      namespace: monitoring

# --- Features (phase 1: infra metrics + events + pod logs) ---
clusterMetrics:
  enabled: true
  collector: alloy-metrics

clusterEvents:
  enabled: true
  collector: alloy-singleton

podLogsViaLoki:
  enabled: true
  collector: alloy-logs
  structuredMetadata:
    pod: ""

hostMetrics:
  enabled: true
  collector: alloy-metrics
  linuxHosts:
    enabled: true
  windowsHosts:
    enabled: false
  energyMetrics:
    enabled: false

# --- Explicitly disabled in phase 1 (free-tier budget / not needed) ---
costMetrics:
  enabled: false
nodeLogs:
  enabled: false
applicationObservability:
  enabled: false
autoInstrumentation:
  enabled: false
profiling:
  enabled: false

# --- Collectors: single-node sizing ---
collectors:
  alloy-metrics:
    presets: [clustered, statefulset]
  alloy-logs:
    presets: [filesystem-log-reader, daemonset]
  alloy-singleton:
    presets: [singleton]

# --- Telemetry backends: keep KSM + node-exporter, drop the rest ---
telemetryServices:
  kube-state-metrics:
    deploy: true
  node-exporter:
    deploy: true
  windows-exporter:
    deploy: false
  kepler:
    deploy: false
  opencost:
    deploy: false
```

- [ ] **Step 2: Add the pinned chart repo locally (for render verification only)**

Run:
```bash
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1; helm repo update grafana >/dev/null
```
Expected: exit 0 (repo already added is fine).

- [ ] **Step 3: Render the chart with these values against a throwaway secret**

The chart validates that referenced secrets/config are coherent at template time. Render into the scratchpad with placeholder URLs swapped in so no real endpoint is needed for the test.

Run:
```bash
sed -e 's#<PROM_URL>#https://prometheus-prod-01-prod-us-east-0.grafana.net/api/prom/push#' \
    -e 's#<LOKI_URL>#https://logs-prod-001.grafana.net/loki/api/v1/push#' \
    infra/grafana-k8s-monitoring/values.yaml > /tmp/gc-values-test.yaml
helm template k8smon grafana/k8s-monitoring --version 4.3.0 \
  --namespace monitoring \
  -f /tmp/gc-values-test.yaml > /tmp/gc-render.yaml && echo "RENDER-OK"
```
Expected: prints `RENDER-OK`. If Helm errors on an unknown/renamed key, reconcile the key name against `helm show values grafana/k8s-monitoring --version 4.3.0` and fix `values.yaml`.

- [ ] **Step 4: Assert the render wired up the destinations, collectors, and features we want**

Run:
```bash
grep -q "grafana-cloud-credentials" /tmp/gc-render.yaml && echo "secret-ref OK"
grep -Eq "alloy-metrics|alloy-singleton|alloy-logs" /tmp/gc-render.yaml && echo "collectors OK"
grep -q 'name: dagabuntu' /tmp/gc-render.yaml && echo "cluster OK"
```
Expected: `secret-ref OK`, `collectors OK`, `cluster OK` all print. (`grep -c windows-exporter` should be 0 or only-disabled; not required to assert.)

- [ ] **Step 5: Commit**

```bash
git add infra/grafana-k8s-monitoring/values.yaml
git commit -m "feat(monitoring): k8s-monitoring v4.3.0 chart values for Grafana Cloud"
```

---

### Task 3: ArgoCD Application

**Files:**
- Create: `infra/argocd/applications/grafana-k8s-monitoring.yaml`

**Interfaces:**
- Consumes: `values.yaml` (Task 2) and `manifests/external-secret.yaml` (Task 1) from git.
- Produces: an ArgoCD `Application` named `grafana-k8s-monitoring` that the root app-of-apps reconciles automatically.

- [ ] **Step 1: Write the Application manifest**

Create `infra/argocd/applications/grafana-k8s-monitoring.yaml`. Three sources: the pinned chart (values from the `$values` git ref), the same git repo as the `values` ref, and a `path` source that renders the raw ExternalSecret. Mirrors the `external-secrets.yaml` multi-source pattern already in this directory.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: grafana-k8s-monitoring
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  sources:
    # Grafana k8s-monitoring chart (pinned)
    - repoURL: https://grafana.github.io/helm-charts
      chart: k8s-monitoring
      targetRevision: "4.3.0"
      helm:
        valueFiles:
          - $values/infra/grafana-k8s-monitoring/values.yaml
    # Git repo: provides $values AND the raw ExternalSecret manifest
    - repoURL: git@github.com:jimdaga/family-pickem.git
      targetRevision: main
      ref: values
    - repoURL: git@github.com:jimdaga/family-pickem.git
      targetRevision: main
      path: infra/grafana-k8s-monitoring/manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

- [ ] **Step 2: Verify the manifest parses and has the three-source shape**

Run:
```bash
python3 -c "import yaml; d=yaml.safe_load(open('infra/argocd/applications/grafana-k8s-monitoring.yaml')); \
s=d['spec']['sources']; \
assert d['metadata']['name']=='grafana-k8s-monitoring'; \
assert any(x.get('chart')=='k8s-monitoring' and x.get('targetRevision')=='4.3.0' for x in s), 'chart source'; \
assert any(x.get('ref')=='values' for x in s), 'values ref'; \
assert any(x.get('path')=='infra/grafana-k8s-monitoring/manifests' for x in s), 'manifest path'; \
assert d['spec']['destination']['namespace']=='monitoring'; \
print('OK')"
```
Expected: prints `OK`.

- [ ] **Step 3: Confirm the root app-of-apps will pick it up**

The root globs `*.yaml` in this directory non-recursively. Confirm the file is a top-level `*.yaml` and matches the pattern that already includes the sibling apps.

Run:
```bash
ls infra/argocd/applications/grafana-k8s-monitoring.yaml && \
grep -q "include: '\*.yaml'" infra/argocd/applications/root-app.yaml && echo "will-be-reconciled"
```
Expected: path lists + prints `will-be-reconciled`.

- [ ] **Step 4: Commit**

```bash
git add infra/argocd/applications/grafana-k8s-monitoring.yaml
git commit -m "feat(monitoring): ArgoCD Application for Grafana Cloud k8s-monitoring"
```

---

### Task 4: One-time setup docs + AWS Secrets Manager secret

**Files:**
- Create: `infra/grafana-k8s-monitoring/README.md`

**Interfaces:**
- Produces: AWS SM secret `family-pickem/monitoring/grafana-cloud` consumed by Task 1's ExternalSecret; documentation the operator follows.

> This task's secret creation runs against AWS and is performed by the user (needs an authenticated AWS session — `aws login` if expired, per CLAUDE.md). The README is committed to git; the secret is not.

- [ ] **Step 1: Write the README**

Create `infra/grafana-k8s-monitoring/README.md`:

````markdown
# Grafana Cloud Monitoring (infra + logs)

Ships cluster metrics, Kubernetes events, and pod logs from the `dagabuntu`
cluster to Grafana Cloud's free tier via the pinned `k8s-monitoring` v4.3.0
chart. Deployed by ArgoCD (`infra/argocd/applications/grafana-k8s-monitoring.yaml`);
credentials via ESO from AWS Secrets Manager.

## One-time setup

### 1. Gather values from the Grafana Cloud portal
Stack → **Connections / Details**:
- Prometheus remote-write URL + username (instance ID) → `PROM_URL`, `PROM_USERNAME`
- Loki push URL + username (instance ID) → `LOKI_URL`, `LOKI_USERNAME`
- An access-policy token (`glc_...`) with `metrics:write` + `logs:write` → `ACCESS_TOKEN`

Put the two URLs into `values.yaml` (`<PROM_URL>` / `<LOKI_URL>`). The usernames
and token go into AWS Secrets Manager (below), never into git.

### 2. Create the AWS Secrets Manager secret
Requires an authenticated AWS session (`aws login` if expired). ESO's IAM user is
already scoped to `family-pickem/*`, so no IAM change is needed.

```bash
aws secretsmanager create-secret \
  --name family-pickem/monitoring/grafana-cloud \
  --region us-east-1 \
  --secret-string '{
    "prometheus-username": "<PROM_USERNAME>",
    "loki-username": "<LOKI_USERNAME>",
    "access-token": "<ACCESS_TOKEN>"
  }'
```

To rotate later: `aws secretsmanager put-secret-value --secret-id family-pickem/monitoring/grafana-cloud --secret-string '{...}'`
then force an ESO resync:
`kubectl annotate externalsecret grafana-cloud-credentials -n monitoring force-sync=$(date +%s) --overwrite`
(no git change, no redeploy needed).

## Verify
```bash
kubectl get externalsecret -n monitoring          # SecretSynced / Ready=True
kubectl get pods -n monitoring                     # alloy-* + operator Running
kubectl get secret grafana-cloud-credentials -n monitoring
```
Then in Grafana Cloud: **Infrastructure → Kubernetes** shows cluster `dagabuntu`;
**Explore → Loki** `{cluster="dagabuntu"}` returns pod logs.

## Scope
Phase 1 = metrics + events + pod logs + host metrics. Disabled: traces/OTLP,
profiling, cost metrics, node/journal logs. See the design spec in
`docs/superpowers/specs/2026-07-17-grafana-cloud-monitoring-design.md`.
````

- [ ] **Step 2: Commit the README**

```bash
git add infra/grafana-k8s-monitoring/README.md
git commit -m "docs(monitoring): one-time setup for Grafana Cloud secret + values"
```

- [ ] **Step 3: (User, live) Create the AWS SM secret**

Fill the placeholders and run the `aws secretsmanager create-secret` command from the README. Verify:
```bash
aws secretsmanager describe-secret --secret-id family-pickem/monitoring/grafana-cloud --region us-east-1 --query Name --output text
```
Expected: prints `family-pickem/monitoring/grafana-cloud`.

---

### Task 5: Deploy via ArgoCD and validate end-to-end

**Files:** none (git push + live cluster validation).

> Deployment is GitOps: merging to `main` makes the root app reconcile the new Application. All commands here are read-only validation except the merge itself.

- [ ] **Step 1: Push the branch and open a PR**

```bash
git push -u origin feat/grafana-cloud-monitoring
gh pr create --title "feat: Grafana Cloud monitoring via ArgoCD" \
  --body "Deploys pinned k8s-monitoring v4.3.0 to the monitoring namespace; creds via ESO. See docs/superpowers/plans/2026-07-17-grafana-cloud-monitoring.md"
```
Expected: PR URL printed.

- [ ] **Step 2: Confirm the AWS SM secret exists (gate before merge)**

Task 4 Step 3 must be done, or the first sync will crash-loop waiting for the secret.
```bash
aws secretsmanager describe-secret --secret-id family-pickem/monitoring/grafana-cloud --region us-east-1 --query Name --output text
```
Expected: prints the secret name. If it errors, complete Task 4 Step 3 first.

- [ ] **Step 3: Merge (GitOps deploy)**

```bash
gh pr merge --squash --admin
```
Expected: merged. The root app-of-apps reconciles `grafana-k8s-monitoring` within a couple minutes.

- [ ] **Step 4: Watch the Application sync**

Requires the kubectl tunnel context (see memory `k8s-api-access-tunnel`).
```bash
kubectl --context tunnel -n argocd get application grafana-k8s-monitoring
kubectl --context tunnel -n monitoring get externalsecret,pods
```
Expected: Application `Synced`/`Healthy`; ExternalSecret `Ready=True`; `alloy-metrics-*`, `alloy-singleton-*`, `alloy-logs-*` (daemonset) and the alloy-operator pod `Running`. Alloy pods may restart once or twice before the secret lands — self-heals.

- [ ] **Step 5: Confirm data lands in Grafana Cloud**

- Grafana Cloud → **Infrastructure → Kubernetes**: cluster `dagabuntu` appears with nodes/pods (allow a few minutes for first scrape).
- **Explore → Loki**: `{cluster="dagabuntu", namespace="pickem-prd"}` returns Django app logs.
- **Billing/Usage**: active series well under the 10k free-tier limit after ~1h.

- [ ] **Step 6: Update infra state notes**

Add a line to `infra/MIGRATION_STATE.md` recording Grafana Cloud monitoring as deployed (chart 4.3.0, namespace `monitoring`, secret `family-pickem/monitoring/grafana-cloud`), then commit directly to `main` (docs-only) or fold into the PR before merge.

---

## Self-Review Notes

- **Spec coverage:** ExternalSecret (Task 1) ✓, values/destinations/features (Task 2) ✓, ArgoCD Application (Task 3) ✓, AWS SM secret + docs (Task 4) ✓, deploy + validation (Task 5) ✓. Cluster name `dagabuntu` ✓. Free-tier disables ✓. Chart pin ✓.
- **Deviation from spec:** spec sketched `destinations` as a list and top-level `alloy-*` keys; corrected to v4.3.0's **map** destinations, feature `collector:` bindings, `podLogsViaLoki`, and a `collectors` map — verified against Grafana's tagged v4.3.0 ArgoCD external-secrets example. Added `hostMetrics` (linux, single node) as low-cost infra value; still within free-tier intent.
- **Type/name consistency:** secret name `grafana-cloud-credentials`, keys `prometheus-username`/`loki-username`/`access-token`, and AWS SM path `family-pickem/monitoring/grafana-cloud` are identical across Tasks 1, 2, and 4.
- **No placeholders** except the intentional `<PROM_URL>`/`<LOKI_URL>`/`<*_USERNAME>`/`<ACCESS_TOKEN>` operator-supplied values, each documented in the README and the "Values To Obtain" section.
