# Live Updates — Phase 2: Scheduler Extraction + Web Autoscaling — Design

**Date:** 2026-08-02
**Status:** Approved (design); pending spec review
**Related issues:** #95 (extract scheduler so web can autoscale), #138 (async /scores/ — later), #93 (Redis — shipped 0.0.193)
**Parent:** `docs/superpowers/specs/2026-08-02-live-updates-design.md` (Phase 2)

## Goal

Move the update pipeline off the web pod into its own single-replica Deployment,
and enable the web tier's HorizontalPodAutoscaler in dev and prd — so the web
tier can scale horizontally (needed by the Phase 3 SSE push feature) while the
pipeline still runs exactly once.

## Motivation

- The pipeline runs as an in-process APScheduler on the web pod
  (`RUN_SCHEDULER=true`), and the Helm chart hard-fails if you enable both the
  scheduler and autoscaling (`deployment.yaml:77` — "Safe only because the web
  Deployment is single-replica"). So the web tier cannot scale today.
- **Discovered defect:** the HPA template uses `autoscaling/v2beta1`
  (`hpa.yaml:2`), an API **removed in Kubernetes 1.26**. This cluster is 1.28,
  so the HPA cannot even be created as written. Phase 2 must fix this regardless.

## Design

### 1. Dedicated scheduler Deployment (new template)
- New `charts/family-pickem/templates/scheduler-deployment.yaml`, gated on
  `scheduler.enabled`. Same image and `-envvars` secret as web, but:
  - `RUN_SCHEDULER=true`, `replicas: 1`, `strategy.type: Recreate`.
  - **No** Service, Ingress, or HPA.
  - Liveness/readiness on `/livez` / `/healthz` (it still runs `runserver`
    in-process alongside the scheduler — simplest, matches today's behavior;
    just not exposed).
  - Its own `scheduler.resources`.
- `Recreate` + `replicas: 1` is the single-writer guarantee for the APScheduler
  `DjangoJobStore` and preserves `max_instances=1` (never two schedulers).

### 2. Web Deployment changes (`deployment.yaml`)
- Web is **always** `RUN_SCHEDULER=false` (never runs the pipeline). Remove the
  `{{- if .Values.scheduler.enabled }} RUN_SCHEDULER=true` block.
- Remove the `fail "scheduler.enabled requires autoscaling.enabled=false"`
  guard — the two are compatible now that the scheduler is a separate Deployment.
- **Add CPU + memory resource *requests*** to the web container. A CPU-target
  HPA cannot compute utilization without a CPU request. (Chart default
  `resources: {}` must become concrete values.)

### 3. Fix the HPA (`hpa.yaml`)
- `autoscaling/v2beta1` → `autoscaling/v2`.
- Metric schema to v2 shape:
  ```yaml
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
  ```
  (and the same shape for the optional memory metric).

### 4. Values semantics
- `scheduler.enabled` now means **"run the dedicated scheduler Deployment"** — no
  longer "run the scheduler inside the web pod". Web is always `RUN_SCHEDULER=false`.
- `autoscaling.enabled: true` in **both** `values-dev.yaml` and `values-prd.yaml`.
- HPA defaults: `minReplicas: 1`, `maxReplicas: 4`,
  `targetCPUUtilizationPercentage: 75`.
- Web resources: `requests: {cpu: 100m, memory: 256Mi}`, `limits: {memory: 512Mi}`
  (no CPU limit, so pods can burst). Scheduler resources: `requests: {cpu: 50m,
  memory: 256Mi}`, `limits: {memory: 512Mi}`.

### 5. Migrations
- Keep the migrate init container on the **web** Deployment only.
- Give the scheduler pod an init container that **waits** for migrations rather
  than running them, so the two Deployments never race to migrate on deploy:
  `until python manage.py migrate --check; do echo "waiting for migrations"; sleep 2; done`
  (`migrate --check` exits non-zero while migrations are pending).

## Superadmin console: no code changes required

The Jobs/overview subsystem was already built for a cross-process scheduler; it
coordinates entirely through the shared Postgres DB:
- **Queueing** (`pickem_superadmin/jobs.py::queue_command`): on a web pod
  (`RUN_SCHEDULER=false`) `get_scheduler()` returns `None`, so it uses
  `_add_job_via_fallback_scheduler` — a throwaway **paused** `BackgroundScheduler`
  that persists the job into the `DjangoJobStore` (Postgres) and shuts down. The
  dedicated scheduler pod executes it on its next tick.
- **Health/status** (`scheduler_health()`, `current_running_jobs()`): read
  `DjangoJob.next_run_time`, `JobRun`, and `RunningJobMarker` from Postgres, so
  the console — rendered on any web replica — reflects the *separate* scheduler
  pod's liveness. The "Queueing is disabled — ensure `RUN_SCHEDULER=true`"
  warning already keys off this.

**Behavioral nuance (not a bug):** today web==scheduler, so a manually-queued job
fires almost immediately (live path). After the split, web takes the fallback
path, so the job waits for the scheduler pod's next tick — **≤60s**. This is the
already-documented "enqueued, not instant" tradeoff. With multiple web replicas
each can queue independently (distinct timestamped job IDs; `replace_existing`),
and there is still exactly one executor (the single scheduler pod).

## Multi-replica safety (verified)

- Sessions are database-backed (Django default, no `SESSION_ENGINE` override) →
  shared via Postgres across replicas.
- Cache is shared Redis (Phase 1).
- The only `RUN_SCHEDULER`-gated in-process singleton is the scheduler itself
  (`pickem_api/apps.py:29`); with `RUN_SCHEDULER=false` the web pods carry no
  pipeline state.

## Rollout & verification

- Enable in **dev** first (auto-deploys from main), verify, then it ships to prd
  on the next release.
- Post-deploy checks (both envs):
  1. Exactly one scheduler pod (`replicas: 1`) running; web Deployment scalable
     by the HPA (HPA object exists and reports metrics, not `<unknown>`).
  2. `update_all` still runs on its tick (recent `JobRun` rows).
  3. **From `/superadmin/jobs/`, queue a run and confirm the scheduler pod
     executes it within ~60s** — proves the cross-pod DjangoJobStore hand-off.
  4. Overview still shows the scheduler healthy once it's in its own pod.

## Risks

- **HPA needs metrics-server.** The v2 HPA reads CPU utilization from
  metrics-server; if the cluster lacks it (or it's unhealthy), the HPA reports
  `<unknown>` and won't scale. Confirm metrics-server is present before relying
  on autoscaling (does not break the app; scaling just won't happen).
- **Two Deployments now share one image/secret** — a bad env var affects both;
  acceptable and intended (single source of truth).
- **maxReplicas × resource requests** must fit the single node's capacity;
  `maxReplicas: 4` at 100m CPU / 256Mi each is comfortable.

## Out of scope

- The Phase 3 SSE push feature (async `/events/`, publish-on-write, client) —
  separate spec/plan.
- Redis auth / NetworkPolicy (tracked as the Phase 1 prd-enable gate).
