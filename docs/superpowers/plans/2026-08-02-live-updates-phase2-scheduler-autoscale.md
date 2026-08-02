# Live Updates — Phase 2: Scheduler Extraction + Web Autoscaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the update pipeline in its own single-replica scheduler Deployment, make the web tier `RUN_SCHEDULER=false`, fix the removed `autoscaling/v2beta1` HPA API, remove the scheduler/autoscaling mutual-exclusion, and enable web autoscaling in dev + prd.

**Architecture:** A new Helm template renders a dedicated scheduler Deployment (same image/secret, `RUN_SCHEDULER=true`, `replicas: 1`, `Recreate`, no Service/HPA). The web Deployment stops running the scheduler and gains CPU/memory requests so the HPA can compute utilization. The HPA template moves to `autoscaling/v2`. All coordination (queued jobs, health) already flows through the shared Postgres `DjangoJobStore`, so no application code changes.

**Tech Stack:** Helm, Kubernetes 1.28 (`autoscaling/v2`), ArgoCD GitOps, django-apscheduler.

## Global Constraints

- Chart resources for Bitnami subcharts are `{release}-<subchart>`; first-party resources use `{{ include "family-pickem.fullname" . }}` (= `family-pickem-prd` / `family-pickem-dev`). Release names: `pickem-prd` / `pickem-dev`. (`infra/app/values-*.yaml`)
- Kubernetes is **1.28**: use `autoscaling/v2` (NOT `v2beta1`, removed in 1.26).
- `scheduler.enabled` now means "render the dedicated scheduler Deployment"; the web Deployment is **always** `RUN_SCHEDULER=false`.
- Exactly one scheduler executor: scheduler Deployment is `replicas: 1` + `strategy.type: Recreate`.
- Do NOT hardcode ArgoCD `targetRevision`; enabling per env is a values change merged via GitOps (dev tracks main; prd tracks releases).
- No application (Python) code changes are required or expected in this phase — it is chart + values only. `pickem_superadmin/jobs.py` already handles the web-vs-scheduler split via the shared DjangoJobStore.
- Verify chart changes with `helm lint` + `helm template` (no live cluster needed at desk). If `helm template` errors with "missing … postgresql", run `helm dependency build .` once (the postgres subchart vendor dir may be empty in a fresh worktree); never commit vendored `charts/*.tgz`.

---

### Task 1: Migrate the HPA to autoscaling/v2

Fix the removed API version so the HPA can be created on k8s 1.28.

**Files:**
- Modify: `charts/family-pickem/templates/hpa.yaml`

- [ ] **Step 1: Rewrite hpa.yaml to the v2 schema**

Replace the entire file `charts/family-pickem/templates/hpa.yaml` with:

```yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "family-pickem.fullname" . }}
  labels:
    {{- include "family-pickem.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "family-pickem.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    {{- if .Values.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
    {{- end }}
    {{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
    {{- end }}
{{- end }}
```

- [ ] **Step 2: Verify it renders as autoscaling/v2**

Run:

```bash
cd charts/family-pickem
helm template pickem-prd . -f ../../infra/app/values-prd.yaml --set autoscaling.enabled=true | grep -A3 "kind: HorizontalPodAutoscaler"
helm template pickem-prd . -f ../../infra/app/values-prd.yaml --set autoscaling.enabled=true | grep -E "apiVersion: autoscaling/v2$|averageUtilization|type: Utilization"
```

Expected: HPA renders with `apiVersion: autoscaling/v2`, and the CPU metric uses `type: Utilization` + `averageUtilization`. No `v2beta1`, no `targetAverageUtilization`.

- [ ] **Step 3: Lint**

Run:

```bash
cd charts/family-pickem && helm lint . -f ../../infra/app/values-prd.yaml --set autoscaling.enabled=true
```

Expected: `0 chart(s) failed`.

- [ ] **Step 4: Commit**

```bash
git add charts/family-pickem/templates/hpa.yaml
git commit -m "fix(chart): migrate HPA to autoscaling/v2 (v2beta1 removed in k8s 1.26)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add web resource requests + HPA defaults to chart values

The CPU-target HPA needs a CPU request on the web container; without it the HPA reports `<unknown>` and never scales.

**Files:**
- Modify: `charts/family-pickem/values.yaml` (`resources`, `autoscaling`, add `scheduler.resources`)

**Interfaces:**
- Produces: `.Values.resources` (web container requests/limits), `.Values.scheduler.resources`, and `.Values.autoscaling` defaults consumed by Tasks 1, 3, 4.

- [ ] **Step 1: Set web `resources` default**

In `charts/family-pickem/values.yaml`, replace the existing `resources: {}` block (with its explanatory comment) with:

```yaml
# Web container resources. requests.cpu is REQUIRED for the CPU-target HPA to
# compute utilization. No CPU limit so pods can burst.
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    memory: 512Mi
```

- [ ] **Step 2: Set `autoscaling` defaults**

In `charts/family-pickem/values.yaml`, replace the existing `autoscaling:` block with:

```yaml
autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 4
  targetCPUUtilizationPercentage: 75
  # targetMemoryUtilizationPercentage: 80
```

- [ ] **Step 3: Add `scheduler.resources`**

In `charts/family-pickem/values.yaml`, replace the existing `scheduler:` block with:

```yaml
# Dedicated scheduler Deployment (see templates/scheduler-deployment.yaml).
# When enabled, runs the update pipeline in its own single-replica pod
# (RUN_SCHEDULER=true); the web tier always runs RUN_SCHEDULER=false and can
# therefore autoscale.
scheduler:
  enabled: false
  resources:
    requests:
      cpu: 50m
      memory: 256Mi
    limits:
      memory: 512Mi
```

- [ ] **Step 4: Verify web requests render**

Run:

```bash
cd charts/family-pickem
helm template pickem-prd . -f ../../infra/app/values-prd.yaml | sed -n '/kind: Deployment/,/kind: /p' | grep -A6 "resources:" | grep -E "cpu: 100m|memory: 256Mi|memory: 512Mi" | head
```

Expected: the web container shows `cpu: 100m`, `memory: 256Mi` requests and `memory: 512Mi` limit.

- [ ] **Step 5: Commit**

```bash
git add charts/family-pickem/values.yaml
git commit -m "feat(chart): web resource requests + HPA/scheduler resource defaults

CPU request is required for the CPU-target HPA. Add scheduler.resources for the
upcoming dedicated scheduler Deployment. (#95)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Web Deployment — RUN_SCHEDULER=false always, remove fail guard

The web tier stops running the pipeline; the scheduler/autoscaling mutual-exclusion goes away.

**Files:**
- Modify: `charts/family-pickem/templates/deployment.yaml`

- [ ] **Step 1: Remove the fail guard and the in-web scheduler env**

In `charts/family-pickem/templates/deployment.yaml`, in the main app container, delete this block (currently around lines 77-85):

```yaml
          {{- if and .Values.scheduler.enabled .Values.autoscaling.enabled }}
          {{ fail "scheduler.enabled requires autoscaling.enabled=false" }}
          {{- end }}
          {{- if .Values.scheduler.enabled }}
          # In-process APScheduler runs the update pipeline. Safe only because
          # the web Deployment is single-replica; do not enable with replicaCount > 1.
          - name: RUN_SCHEDULER
            value: "true"
          {{- end }}
```

Replace it with:

```yaml
          # The web tier never runs the pipeline — the dedicated scheduler
          # Deployment does (templates/scheduler-deployment.yaml). Explicit
          # RUN_SCHEDULER=false so the web pods stay stateless and can autoscale.
          - name: RUN_SCHEDULER
            value: "false"
```

- [ ] **Step 2: Verify web no longer sets RUN_SCHEDULER=true and no fail**

Run:

```bash
cd charts/family-pickem
# scheduler.enabled + autoscaling.enabled together must NOT fail now
helm template pickem-prd . -f ../../infra/app/values-prd.yaml --set scheduler.enabled=true --set autoscaling.enabled=true >/dev/null && echo "renders OK (no fail guard)"
# web container has RUN_SCHEDULER=false
helm template pickem-prd . -f ../../infra/app/values-prd.yaml --set scheduler.enabled=true --set autoscaling.enabled=true | sed -n '/name: family-pickem$/,/kind: /p' | grep -A1 "RUN_SCHEDULER" | head
```

Expected: prints `renders OK (no fail guard)`, and the web container's `RUN_SCHEDULER` value is `"false"`.

- [ ] **Step 3: Commit**

```bash
git add charts/family-pickem/templates/deployment.yaml
git commit -m "feat(chart): web tier always RUN_SCHEDULER=false; drop autoscaling fail guard

The scheduler now runs in its own Deployment, so the web tier never runs the
pipeline and scheduler+autoscaling are no longer mutually exclusive. (#95)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Dedicated scheduler Deployment template

Render the single-replica pipeline runner, with a migrations-wait init so it never races web on migrate.

**Files:**
- Create: `charts/family-pickem/templates/scheduler-deployment.yaml`

**Interfaces:**
- Consumes: `.Values.scheduler.enabled`, `.Values.scheduler.resources`, `.Values.image`, the `-envvars` secret, and `.Values.redis.enabled` for `REDIS_URL` (the scheduler needs Redis too, for Phase 3 pub/sub and cache).

- [ ] **Step 1: Create the scheduler Deployment template**

Create `charts/family-pickem/templates/scheduler-deployment.yaml`:

```yaml
{{- if .Values.scheduler.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "family-pickem.fullname" . }}-scheduler
  labels:
    {{- include "family-pickem.labels" . | nindent 4 }}
    app.kubernetes.io/component: scheduler
spec:
  # Exactly one scheduler ever: single replica + Recreate guarantees a single
  # writer to the APScheduler DjangoJobStore (preserves max_instances=1).
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "family-pickem.name" . }}-scheduler
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ include "family-pickem.name" . }}-scheduler
        app.kubernetes.io/instance: {{ .Release.Name }}
        app.kubernetes.io/component: scheduler
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "family-pickem.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      initContainers:
        # The web Deployment owns migrations. The scheduler waits for them so
        # the two Deployments never race to migrate on a deploy.
        - name: {{ .Chart.Name }}-wait-migrations
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          command:
            - sh
            - -c
            - 'until python manage.py migrate --check; do echo "waiting for migrations"; sleep 2; done'
          envFrom:
          - secretRef:
              name: {{ include "family-pickem.fullname" . }}-envvars
          {{- if and .Values.externalSecrets.enabled .Values.externalSecrets.logoStorageKey }}
          - secretRef:
              name: {{ include "family-pickem.fullname" . }}-logo-storage
          {{- end }}
          env:
          - name: THIS_POD_IP
            valueFrom:
              fieldRef:
                fieldPath: status.podIP
          {{- if .Values.redis.enabled }}
          - name: REDIS_URL
            value: "redis://{{ include "family-pickem.fullname" . }}-redis:6379/1"
          {{- end }}
          resources:
            {{- toYaml .Values.scheduler.resources | nindent 12 }}
      containers:
        - name: {{ .Chart.Name }}-scheduler
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          envFrom:
          - secretRef:
              name: {{ include "family-pickem.fullname" . }}-envvars
          {{- if and .Values.externalSecrets.enabled .Values.externalSecrets.logoStorageKey }}
          - secretRef:
              name: {{ include "family-pickem.fullname" . }}-logo-storage
          {{- end }}
          env:
          - name: THIS_POD_IP
            valueFrom:
              fieldRef:
                fieldPath: status.podIP
          - name: APP_RELEASE
            value: "{{ .Values.image.tag | default .Chart.AppVersion }}"
          # This pod IS the scheduler: it runs the in-process APScheduler pipeline.
          - name: RUN_SCHEDULER
            value: "true"
          {{- if .Values.redis.enabled }}
          - name: REDIS_URL
            value: "redis://{{ include "family-pickem.fullname" . }}-redis:6379/1"
          {{- end }}
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          {{- if .Values.healthchecks.enabled }}
          livenessProbe:
            httpGet:
              path: /livez/
              port: http
            initialDelaySeconds: 25
          readinessProbe:
            httpGet:
              path: /healthz/
              port: http
            initialDelaySeconds: 25
          {{- end }}
          resources:
            {{- toYaml .Values.scheduler.resources | nindent 12 }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end }}
```

- [ ] **Step 2: Verify the scheduler Deployment renders correctly**

Run:

```bash
cd charts/family-pickem
helm template pickem-prd . -f ../../infra/app/values-prd.yaml --set scheduler.enabled=true --set redis.enabled=true | sed -n '/name: family-pickem-prd-scheduler$/,/^---/p' > /tmp/sched.yaml
grep -E "name: family-pickem-prd-scheduler|replicas: 1|type: Recreate|RUN_SCHEDULER|value: .true.|wait-migrations|component: scheduler" /tmp/sched.yaml | head -20
echo "--- confirm NO Service/HPA named -scheduler ---"
helm template pickem-prd . -f ../../infra/app/values-prd.yaml --set scheduler.enabled=true | grep -E "kind: Service|kind: HorizontalPodAutoscaler" -A2 | grep "scheduler" && echo "UNEXPECTED scheduler Service/HPA" || echo "OK: no scheduler Service/HPA"
```

Expected: the scheduler Deployment renders with `replicas: 1`, `Recreate`, `RUN_SCHEDULER` = `"true"`, the wait-migrations init, and the `component: scheduler` label; and there is NO Service or HPA targeting the scheduler.

- [ ] **Step 3: Lint the full chart with scheduler + autoscaling + redis all on**

Run:

```bash
cd charts/family-pickem
helm lint . -f ../../infra/app/values-prd.yaml --set scheduler.enabled=true --set autoscaling.enabled=true --set redis.enabled=true
```

Expected: `0 chart(s) failed`.

- [ ] **Step 4: Commit**

```bash
git add charts/family-pickem/templates/scheduler-deployment.yaml
git commit -m "feat(chart): dedicated single-replica scheduler Deployment

Runs the update pipeline (RUN_SCHEDULER=true) in its own pod, replicas:1 +
Recreate for a single DjangoJobStore writer, with a migrations-wait init so it
never races the web deploy. No Service/HPA. (#95)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Enable in dev (scheduler split + autoscaling)

**Files:**
- Modify: `infra/app/values-dev.yaml`

- [ ] **Step 1: Turn on autoscaling in dev**

`infra/app/values-dev.yaml` already has `scheduler.enabled: true`. Under the existing `autoscaling`-less config, add a top-level block:

```yaml
autoscaling:
  enabled: true
```

(Leave `scheduler.enabled: true` as-is — its meaning is now "dedicated scheduler Deployment".)

- [ ] **Step 2: Verify dev render**

Run:

```bash
cd charts/family-pickem
helm template pickem-dev . -f ../../infra/app/values-dev.yaml > /tmp/dev.yaml
grep -c "family-pickem-dev-scheduler" /tmp/dev.yaml    # scheduler Deployment present
grep "apiVersion: autoscaling/v2" /tmp/dev.yaml        # HPA present, v2
grep -A1 "RUN_SCHEDULER" /tmp/dev.yaml | grep -E "true|false"  # web=false, scheduler=true
```

Expected: scheduler Deployment present, HPA `autoscaling/v2` present, and both `RUN_SCHEDULER` values appear (web `"false"`, scheduler `"true"`).

- [ ] **Step 3: Commit**

```bash
git add infra/app/values-dev.yaml
git commit -m "feat(dev): enable web autoscaling; scheduler runs in its own pod (#95)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: Verify in the running dev cluster (post-merge)**

After ArgoCD syncs dev:

```bash
kubectl config use-context kubernetes-admin@kubernetes
# one scheduler pod, web pod(s), and an HPA
kubectl get deploy,hpa -n pickem-dev | grep -E "family-pickem-dev|scheduler"
kubectl get hpa -n pickem-dev family-pickem-dev -o wide   # TARGETS must show a % , not <unknown>
# scheduler is the only RUN_SCHEDULER=true
kubectl get pods -n pickem-dev -l app.kubernetes.io/component=scheduler
# pipeline still ticking (recent JobRun) + queued job hand-off works:
#   from /superadmin/jobs/ queue "update_records" and confirm the scheduler pod
#   runs it within ~60s (check /superadmin/jobs/ history or JobRun rows).
```

Expected: exactly one scheduler pod; HPA `TARGETS` shows a CPU percentage (not `<unknown>` — if `<unknown>`, metrics-server is missing/unhealthy, see spec Risks); a manually-queued job executes within ~60s.

---

### Task 6: Enable in production

Only after dev is verified — this is the prd rollout gate.

**Files:**
- Modify: `infra/app/values-prd.yaml`

- [ ] **Step 1: Turn on autoscaling in prd**

`infra/app/values-prd.yaml` already has `scheduler.enabled: true`. Add a top-level block:

```yaml
autoscaling:
  enabled: true
```

- [ ] **Step 2: Verify prd render**

Run:

```bash
cd charts/family-pickem
helm template pickem-prd . -f ../../infra/app/values-prd.yaml > /tmp/prd.yaml
grep -c "family-pickem-prd-scheduler" /tmp/prd.yaml
grep "apiVersion: autoscaling/v2" /tmp/prd.yaml
grep -A1 "RUN_SCHEDULER" /tmp/prd.yaml | grep -E "true|false"
```

Expected: scheduler Deployment present, HPA `autoscaling/v2` present, web `RUN_SCHEDULER="false"` + scheduler `"true"`.

- [ ] **Step 3: Commit**

```bash
git add infra/app/values-prd.yaml
git commit -m "feat(prd): enable web autoscaling; scheduler in its own pod (#95)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: Verify in prd (post-release)**

After the release syncs, repeat the dev checks against `pickem-prd`:

```bash
kubectl get deploy,hpa -n pickem-prd | grep -E "family-pickem-prd|scheduler"
kubectl get hpa -n pickem-prd family-pickem-prd -o wide          # TARGETS shows % not <unknown>
kubectl get pods -n pickem-prd -l app.kubernetes.io/component=scheduler   # exactly one
# pipeline ticking + queue a job from /superadmin/jobs/ -> runs within ~60s
```

Expected: exactly one scheduler pod; HPA reports a real CPU target; `update_all` still runs on tick; a console-queued job executes within ~60s; overview shows scheduler healthy.

---

## Self-Review

**Spec coverage (Phase 2 design doc):**
- Dedicated scheduler Deployment (RUN_SCHEDULER=true, replicas 1, Recreate, no Service/HPA, migrations-wait init) → Task 4. ✓
- Web always RUN_SCHEDULER=false; remove fail guard → Task 3. ✓
- Web CPU/memory requests (HPA needs them) → Task 2. ✓
- HPA autoscaling/v2beta1 → v2 → Task 1. ✓
- values: autoscaling defaults, scheduler.resources, enable dev+prd → Tasks 2, 5, 6. ✓
- Migrations: web owns migrate, scheduler waits → Task 4 (wait-migrations init). ✓
- Superadmin: no code changes (verified via queued-job post-deploy check) → Tasks 5/6 Step 4. ✓
- Single-writer guarantee (replicas 1 + Recreate) → Task 4. ✓

**Placeholder scan:** No TBD/TODO; all YAML and commands are concrete. ✓

**Type/name consistency:** scheduler resources use `{{ include "family-pickem.name" . }}-scheduler` selector labels (distinct from web and from `-redis`, so no Service selector overlap); `RUN_SCHEDULER` values are strings (`"true"`/`"false"`); HPA v2 metric schema matches Task 1; `REDIS_URL` matches Phase 1's `{fullname}-redis:6379/1`. ✓

**Ordering:** Tasks 1-4 are chart changes (default-off, no behavior change on render until enabled); Task 5 enables dev; Task 6 gates prd behind dev verification. A reviewer can accept dev (Task 5) while holding prd (Task 6). ✓
