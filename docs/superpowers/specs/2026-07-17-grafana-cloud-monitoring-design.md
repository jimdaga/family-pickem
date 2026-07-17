# Grafana Cloud Monitoring (Phase 1: Infra + Logs) — Design

**Date**: 2026-07-17
**Status**: Approved (pending endpoint values)

## Goal

Ship cluster metrics, Kubernetes events, and pod logs (including the Django app)
from the single-node cluster (`dagabuntu.home`) to Grafana Cloud's free tier.
Everything installed and configured via GitOps: ArgoCD + pinned Helm chart +
values in git, credentials via ESO from AWS Secrets Manager.

## Decisions Made

| Decision | Choice | Why |
|---|---|---|
| Collector | Grafana `k8s-monitoring` Helm chart **v4.3.0** (pinned) | Official chart behind Grafana Cloud's k8s UI; free-tier-friendly metric allowlists; Alloy Operator manages collectors |
| Install path | GitOps values in git — **not** the GUI's `grafana-cloud-onboarding` / Fleet Management flow | Fleet Management moves pipeline config into the Grafana Cloud UI, conflicting with the repo's GitOps-everything rule |
| Telemetry scope | Metrics + pod logs + cluster events. No traces/profiles/node logs in phase 1 | Fits free tier (10k series / 50GB logs); app OTLP tracing is a later phase |
| Credentials | One AWS SM secret `family-pickem/monitoring/grafana-cloud`, pulled by ESO | Cluster-scoped, so it gets its own path; existing ESO IAM user is already scoped to `family-pickem/*` |
| Cluster name | `dagabuntu` | Matches host/stack naming (the GUI command's `databuntu` was a typo) |

## Known Values (extracted from the GUI onboarding command)

- Org ID: `1848319`, region: `prod-us-east-0`
- Access policy `dagabuntu-dagabuntu`; its token has scopes
  `alerts:write, logs:write, metrics:write, rules:write, traces:write, profiles:write`
  — sufficient as the shared password for both Prometheus and Loki destinations.
  (Verified by API probe; the token cannot read/list stacks, which is fine.)

## Values To Fill At Implementation (from portal → stack → tile "Details")

- Prometheus remote-write URL (e.g. `https://prometheus-prod-NN-prod-us-east-0.grafana.net/api/prom/push`)
- Prometheus username / instance ID
- Loki push URL (e.g. `https://logs-prod-NNN.grafana.net/loki/api/v1/push`)
- Loki username / instance ID

URLs and usernames are not secret: URLs go in `values.yaml`; usernames go in the
AWS SM secret alongside the token so all per-stack identity lives in one place.

## Architecture

Three new git artifacts, mirroring the `external-secrets` app pattern:

### 1. `infra/argocd/applications/grafana-k8s-monitoring.yaml`

ArgoCD multi-source Application (picked up automatically by the root app):

- Source A: chart `k8s-monitoring`, repo `https://grafana.github.io/helm-charts`,
  `targetRevision: "4.3.0"` (pinned — no auto-drift), values from
  `$values/infra/grafana-k8s-monitoring/values.yaml`
- Source B: git ref `values` (same repo, `targetRevision: main`)
- Source C: git `path: infra/grafana-k8s-monitoring/manifests` — raw manifests
  (the ExternalSecret)
- Destination: namespace `monitoring`, `CreateNamespace=true`,
  automated sync + prune + selfHeal, `ServerSideApply=true`

### 2. `infra/grafana-k8s-monitoring/manifests/external-secret.yaml`

`ExternalSecret` (API `external-secrets.io/v1`, matching existing templates):

- Store: existing `ClusterSecretStore/aws-secrets-manager`
- Source: AWS SM secret `family-pickem/monitoring/grafana-cloud`, JSON keys:
  - `prometheus-username`
  - `loki-username`
  - `access-token`
- Target: k8s Secret `grafana-cloud-credentials` in `monitoring`, same key names

### 3. `infra/grafana-k8s-monitoring/values.yaml`

```yaml
cluster:
  name: dagabuntu

destinations:
  - name: grafana-cloud-metrics
    type: prometheus
    url: <PROMETHEUS_REMOTE_WRITE_URL>
    auth:
      type: basic
      usernameKey: prometheus-username
      passwordKey: access-token
    secret:
      create: false
      name: grafana-cloud-credentials
      namespace: monitoring
  - name: grafana-cloud-logs
    type: loki
    url: <LOKI_PUSH_URL>
    auth:
      type: basic
      usernameKey: loki-username
      passwordKey: access-token
    secret:
      create: false
      name: grafana-cloud-credentials
      namespace: monitoring

clusterMetrics:
  enabled: true            # chart's default cost-reducing allowlists stay on

clusterEvents:
  enabled: true

podLogs:
  enabled: true            # all namespaces incl. pickem-prd / pickem-dev

# Explicitly off in phase 1: nodeLogs, applicationObservability (OTLP/traces),
# profiling, costMetrics (OpenCost), autoInstrumentation.

alloy-metrics:
  enabled: true
alloy-singleton:
  enabled: true            # cluster events
alloy-logs:
  enabled: true            # daemonset; 1 node → 1 pod
```

(Exact v4 collector/feature key names to be confirmed against the chart's
values schema during implementation; the shape above reflects v4 docs.)

Single-node sizing: default resources are acceptable; trim requests if the node
gets tight.

## Manual Prerequisites (user, one-time)

1. Create the AWS SM secret (AWS CLI command supplied at implementation):
   `family-pickem/monitoring/grafana-cloud` =
   `{"prometheus-username": "...", "loki-username": "...", "access-token": "glc_..."}`
2. Provide the two endpoint URLs + usernames from the portal.
3. The pasted `glc_` token stays out of git and shell history; rotate later if
   desired (rotation = update AWS SM + force ESO sync, no git change).

## Ordering / Failure Notes

- First sync: Alloy pods may crash-loop briefly until ESO materializes
  `grafana-cloud-credentials`; ESO syncs in seconds and pods self-heal.
- If ArgoCD shows persistent diff noise on chart-managed CRDs/objects, add
  `ignoreDifferences` (same remedy used for ESO/PostgreSQL).
- Chart declares no `kubeVersion` floor; Alloy Operator 0.6.x supports k8s 1.28.
  The version pin protects against upstream drift (same lesson as ESO 0.19.2).

## Validation

1. `kubectl get pods -n monitoring` — operator + collectors Running.
2. `kubectl get externalsecret -n monitoring` — Ready/Synced.
3. Grafana Cloud → Infrastructure → Kubernetes: cluster `dagabuntu` appears
   with nodes/pods; Explore → Loki: `{cluster="dagabuntu"}` returns app logs.
4. Watch billing/usage page for active series after ~1h; expect well under 10k.

## Out of Scope (later phases)

- Django app traces/metrics via OTLP (`applicationObservability` feature +
  app instrumentation) — token already has `traces:write`.
- Alerting rules, custom dashboards, synthetic monitoring.
- Postgres exporter integration (chart `integrations` feature supports it).
