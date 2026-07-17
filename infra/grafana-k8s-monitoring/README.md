# Grafana Cloud Monitoring

Ships the full observability stack from the `databuntu` cluster to Grafana
Cloud (free tier) via the pinned `k8s-monitoring` **v4.3.0** chart: cluster +
host metrics, Kubernetes events, pod logs, cost (OpenCost), plus OTLP trace and
Pyroscope profile **receivers** (which sit ready until the app is instrumented).

Deployed by ArgoCD (`infra/argocd/applications/grafana-k8s-monitoring.yaml`).
Credentials come from AWS Secrets Manager via ESO — **never** committed to git.
Collector config is GitOps in `values.yaml`; Grafana's Fleet Management
remote-config path is deliberately not used.

## Endpoints (in `values.yaml`, not secret)

| Signal | Destination | URL |
|---|---|---|
| Metrics | `grafana-cloud-metrics` (prometheus) | `prometheus-prod-56-prod-us-east-2.grafana.net/api/prom/push` |
| Logs | `grafana-cloud-logs` (loki) | `logs-prod-036.grafana.net/loki/api/v1/push` |
| Traces/OTLP | `gc-otlp-endpoint` (otlp http) | `otlp-gateway-prod-us-east-2.grafana.net/otlp` |
| Profiles | `grafana-cloud-profiles` (pyroscope) | `profiles-prod-001.grafana.net:443` |

## One-time setup

### Create the AWS Secrets Manager secret

Requires an authenticated AWS session (`aws login` if expired). ESO's IAM user is
already scoped to `family-pickem/*`, so no IAM change is needed. Fill in the
per-signal usernames (instance IDs from the portal) and the `glc_...`
access-policy token, then:

```bash
aws secretsmanager create-secret \
  --name family-pickem/monitoring/grafana-cloud \
  --region us-east-1 \
  --secret-string '{
    "prometheus-username": "<PROM_INSTANCE_ID>",
    "loki-username": "<LOKI_INSTANCE_ID>",
    "otlp-username": "<OTLP_INSTANCE_ID>",
    "profiles-username": "<PROFILES_INSTANCE_ID>",
    "access-token": "<GLC_TOKEN>"
  }'
```

The ExternalSecret (`manifests/external-secret.yaml`) extracts every JSON key
straight into the k8s Secret `grafana-cloud-credentials`, which all four
destinations authenticate with (username per signal, shared access token).

### Rotate the token later

```bash
aws secretsmanager put-secret-value \
  --secret-id family-pickem/monitoring/grafana-cloud \
  --region us-east-1 --secret-string '{...}'
kubectl annotate externalsecret grafana-cloud-credentials -n monitoring \
  force-sync=$(date +%s) --overwrite
```

No git change or redeploy needed.

## Verify

```bash
kubectl get externalsecret -n monitoring          # Ready=True / SecretSynced
kubectl get pods -n monitoring                     # alloy-* + operator Running
kubectl get secret grafana-cloud-credentials -n monitoring
```

Then in Grafana Cloud: **Infrastructure → Kubernetes** shows cluster
`databuntu`; **Explore → Loki** `{cluster="databuntu"}` returns pod logs.

## Scope

Full stack enabled: `clusterMetrics`, `hostMetrics` (linux, incl. energy via
kepler), `costMetrics` (OpenCost), `clusterEvents`, `podLogsViaLoki`,
`applicationObservability` (OTLP + zipkin receivers), `autoInstrumentation`
(Beyla), `profiling` (eBPF). `windows-exporter` is off (linux-only node).
Watch the free-tier usage page after ~1h. See the design spec:
`docs/superpowers/specs/2026-07-17-grafana-cloud-monitoring-design.md`.
