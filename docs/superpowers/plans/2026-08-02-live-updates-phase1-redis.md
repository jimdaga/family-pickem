# Live Updates — Phase 1: Redis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a shared Redis instance and repoint Django's default cache at it, so the app has a cross-request/cross-replica cache and a broker that later phases use for live-update pub/sub.

**Architecture:** Redis runs as a small self-managed Deployment + Service inside the Helm chart, using the official `redis` image (opt-in per environment). We deliberately do NOT use the Bitnami Redis subchart — Bitnami deprecated its free catalog (Aug 2025), moving versioned image tags to the frozen `bitnamilegacy` repo. The Django app selects its cache backend at startup: Redis when `REDIS_URL` is set, otherwise the existing file-based cache — so local dev and the test suite need no external services. `REDIS_URL` is derived in the deployment template from the chart fullname, matching our own `{fullname}-redis` service.

**Tech Stack:** Django 5.2, django-redis, official Redis image (self-managed Deployment), Helm, ArgoCD GitOps, uv.

## Global Constraints

- Python `>=3.12`; Django `5.2.16`. (`pyproject.toml`)
- All Python deps are pinned to exact versions in `pyproject.toml` and locked in `uv.lock`; add deps with `uv add <pkg>==<version>` (never hand-edit the lock). (`pyproject.toml`)
- Tests run against SQLite via `--settings=pickem.test_settings` from the `pickem/` directory. (`pickem/pickem/test_settings.py`)
- Postgres remains a Bitnami subchart named `{release}-postgresql` (release = `pickem-prd` / `pickem-dev`). Redis is a **self-managed** Deployment + Service named `{fullname}-redis`, where fullname = `fullnameOverride` = `family-pickem-prd` / `family-pickem-dev`. So the Redis service is `family-pickem-prd-redis` / `family-pickem-dev-redis`. (`infra/app/values-prd.yaml`; `charts/family-pickem/templates/_helpers.tpl`)
- Do NOT hardcode ArgoCD chart `targetRevision` values; the release workflow manages them.
- Never edit K8s Secrets directly; secrets flow AWS Secrets Manager → ESO → K8s. (This phase needs NO new secret — in-cluster Redis runs without auth; see Task 2.)
- GitOps: dev tracks `main` automatically; prd tracks GitHub Releases. Enabling Redis in an environment happens by merging a values change, not by `kubectl` edits.

---

### Task 1: Cache backend selection (app-side)

Add `django-redis`, extract cache-backend selection into a testable helper, and wire it into settings so Redis is used when `REDIS_URL` is present and the file-based cache otherwise.

**Files:**
- Create: `pickem/pickem/cache.py`
- Create: `pickem/pickem_api/tests/test_cache_config.py`
- Modify: `pickem/pickem/settings.py:137-146` (replace the inline `CACHES` dict)
- Modify: `pyproject.toml` (add `django-redis` via `uv add`)

**Interfaces:**
- Produces: `pickem.cache.build_caches(environ)` → `dict` — a Django `CACHES` mapping. `environ` is any mapping (typically `os.environ`). Returns the Redis backend when `environ['REDIS_URL']` is a non-blank string, else the file-based backend.

- [ ] **Step 1: Add the django-redis dependency**

Run from repo root:

```bash
uv add "django-redis==5.4.0"
```

This updates `pyproject.toml` and `uv.lock` (pulls in `redis` as a transitive dep). Confirm `pyproject.toml` now lists `django-redis==5.4.0`.

- [ ] **Step 2: Write the failing test**

Create `pickem/pickem_api/tests/test_cache_config.py`:

```python
from pickem.cache import build_caches


def test_uses_filebased_cache_when_no_redis_url():
    caches = build_caches({})
    assert caches['default']['BACKEND'] == (
        'django.core.cache.backends.filebased.FileBasedCache'
    )


def test_uses_redis_when_redis_url_set():
    caches = build_caches({'REDIS_URL': 'redis://example:6379/1'})
    default = caches['default']
    assert default['BACKEND'] == 'django_redis.cache.RedisCache'
    assert default['LOCATION'] == 'redis://example:6379/1'
    # A cache outage must degrade to "no cache", never surface as a 500.
    assert default['OPTIONS']['IGNORE_EXCEPTIONS'] is True


def test_blank_redis_url_falls_back_to_filebased():
    caches = build_caches({'REDIS_URL': '   '})
    assert caches['default']['BACKEND'] == (
        'django.core.cache.backends.filebased.FileBasedCache'
    )
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_cache_config --settings=pickem.test_settings -v 2
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pickem.cache'`.

- [ ] **Step 4: Write the minimal implementation**

Create `pickem/pickem/cache.py`:

```python
"""Cache backend selection.

Uses Redis (shared across requests and replicas) when ``REDIS_URL`` is set,
otherwise falls back to the local file-based cache so local development and the
test suite need no external services.

See docs/superpowers/specs/2026-08-02-live-updates-design.md (Phase 1) and
issue #93.
"""


def build_caches(environ):
    """Return a Django ``CACHES`` dict based on the given environment mapping.

    ``environ`` is typically ``os.environ``. When ``REDIS_URL`` is a non-blank
    string the default cache is Redis (via django-redis); otherwise it is the
    file-based cache at ``/tmp/django_cache``.
    """
    redis_url = environ.get('REDIS_URL', '').strip()
    if redis_url:
        return {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': redis_url,
                'TIMEOUT': 300,  # 5 minutes
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                    # A cache outage must degrade to "no cache", never 500s.
                    'IGNORE_EXCEPTIONS': True,
                },
            }
        }
    return {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': '/tmp/django_cache',
            'TIMEOUT': 300,  # 5 minutes
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
            },
        }
    }
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_cache_config --settings=pickem.test_settings -v 2
```

Expected: PASS (3 tests).

- [ ] **Step 6: Wire the helper into settings**

In `pickem/pickem/settings.py`, replace the inline `CACHES` block (currently lines 137-146):

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/django_cache',
        'TIMEOUT': 300,  # 5 minutes
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}
```

with:

```python
from .cache import build_caches

# Redis when REDIS_URL is set (see pickem/cache.py and issue #93); the
# file-based cache otherwise, so local dev and tests need no external services.
CACHES = build_caches(os.environ)
```

- [ ] **Step 7: Verify the full suite still passes with the file-based fallback**

Run (no `REDIS_URL` in the environment, so the fallback branch is exercised):

```bash
cd pickem && uv run python manage.py test --settings=pickem.test_settings
```

Expected: the suite passes as before (no new failures introduced).

- [ ] **Step 8: Update the dependency note in CLAUDE.md**

In `CLAUDE.md`, under "Dependencies" / "Key packages", add a line:

```markdown
- **django-redis** - Shared Redis cache backend (used when `REDIS_URL` is set; falls back to file-based cache locally)
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock pickem/pickem/cache.py pickem/pickem_api/tests/test_cache_config.py pickem/pickem/settings.py CLAUDE.md
git commit -m "feat(cache): select Redis backend when REDIS_URL is set

Extract cache-backend selection into pickem.cache.build_caches so it is
unit-testable; use django-redis when REDIS_URL is present, else keep the
file-based cache for local dev and tests. Foundation for live updates (#93).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Self-managed Redis Deployment + chart wiring (chart-side)

Add a small Redis Deployment + Service to the Helm chart using the official image, default it off, and inject `REDIS_URL` into the web deployment when it is enabled.

**Files:**
- Create: `charts/family-pickem/templates/redis.yaml`
- Modify: `charts/family-pickem/values.yaml` (add `redis:` block, default disabled)
- Modify: `charts/family-pickem/templates/deployment.yaml` (add `REDIS_URL` env in the main container)

**Interfaces:**
- Produces: when `redis.enabled=true`, a `{{ include "family-pickem.fullname" . }}-redis` Deployment + ClusterIP Service on port 6379, and the web container env `REDIS_URL=redis://{fullname}-redis:6379/1`, consumed by `pickem.cache.build_caches` from Task 1.

- [ ] **Step 1: Add the redis values block**

In `charts/family-pickem/values.yaml`, add after the `postgresql:` block:

```yaml
# Shared Redis: the Django cache now, and the pub/sub broker for live updates
# later (#93). Self-managed (NOT the Bitnami subchart — Bitnami deprecated its
# free catalog in Aug 2025). Disabled by default; enabled per environment in
# infra/app/. Ephemeral: no persistence, since it is only a cache/broker.
# Reachable only inside the cluster network, so it runs without auth; add auth
# (a password from AWS Secrets Manager via ESO) before ever exposing it.
redis:
  enabled: false
  image: "redis:7.4-alpine"
  resources: {}
```

- [ ] **Step 2: Create the Redis Deployment + Service template**

Create `charts/family-pickem/templates/redis.yaml`:

```yaml
{{- if .Values.redis.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "family-pickem.fullname" . }}-redis
  labels:
    {{- include "family-pickem.labels" . | nindent 4 }}
    app.kubernetes.io/component: redis
spec:
  replicas: 1
  # Recreate: a single ephemeral cache instance; never run two at once.
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "family-pickem.name" . }}-redis
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ include "family-pickem.name" . }}-redis
        app.kubernetes.io/instance: {{ .Release.Name }}
        app.kubernetes.io/component: redis
    spec:
      containers:
        - name: redis
          image: {{ .Values.redis.image | quote }}
          imagePullPolicy: IfNotPresent
          # Ephemeral cache/broker: disable RDB snapshots and AOF entirely.
          args: ["--save", "", "--appendonly", "no"]
          ports:
            - name: redis
              containerPort: 6379
              protocol: TCP
          livenessProbe:
            tcpSocket:
              port: redis
            initialDelaySeconds: 10
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
          resources:
            {{- toYaml .Values.redis.resources | nindent 12 }}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ include "family-pickem.fullname" . }}-redis
  labels:
    {{- include "family-pickem.labels" . | nindent 4 }}
    app.kubernetes.io/component: redis
spec:
  type: ClusterIP
  ports:
    - name: redis
      port: 6379
      targetPort: redis
      protocol: TCP
  selector:
    app.kubernetes.io/name: {{ include "family-pickem.name" . }}-redis
    app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

> Why explicit `-redis` selector labels rather than the shared `selectorLabels` helper: the web Deployment/Service select on `name`+`instance` only. If the Redis pod carried those same two labels, the web Service would route traffic to it. The distinct `{{ name }}-redis` value keeps the two selectors from overlapping.

- [ ] **Step 3: Inject REDIS_URL into the deployment**

In `charts/family-pickem/templates/deployment.yaml`, in the **main app container** (`containers:` → `name: {{ .Chart.Name }}`), add the following immediately after the `APP_RELEASE` env entry (which sits just before the `scheduler.enabled` block):

```yaml
          {{- if .Values.redis.enabled }}
          # Shared Redis cache/broker (self-managed; see templates/redis.yaml).
          # DB 1 is the Django cache; later phases use other DB indexes for pub/sub.
          - name: REDIS_URL
            value: "redis://{{ include "family-pickem.fullname" . }}-redis:6379/1"
          {{- end }}
```

- [ ] **Step 4: Lint the chart**

Run:

```bash
cd charts/family-pickem
helm lint . -f ../../infra/app/values-prd.yaml --set redis.enabled=true
```

Expected: `0 chart(s) failed`. (No `helm dependency build` needed — Redis is now a first-party template, not a subchart.)

- [ ] **Step 5: Verify the rendered output**

Run:

```bash
cd charts/family-pickem
# REDIS_URL points at our own service
helm template pickem-prd . -f ../../infra/app/values-prd.yaml --set redis.enabled=true | grep -A2 "name: REDIS_URL"
# The Redis Deployment + Service render
helm template pickem-prd . -f ../../infra/app/values-prd.yaml --set redis.enabled=true | grep -E "name: family-pickem-prd-redis"
```

Expected:
- The first command prints `value: "redis://family-pickem-prd-redis:6379/1"`.
- The second shows the `family-pickem-prd-redis` Deployment and Service names.

Also confirm the default is still off:

```bash
helm template pickem-prd . -f ../../infra/app/values-prd.yaml | grep "REDIS_URL" || echo "REDIS_URL absent by default — correct"
```

Expected: prints `REDIS_URL absent by default — correct`.

- [ ] **Step 6: Commit**

```bash
git add charts/family-pickem/values.yaml charts/family-pickem/templates/redis.yaml charts/family-pickem/templates/deployment.yaml
git commit -m "feat(chart): add self-managed Redis Deployment and REDIS_URL wiring

Small first-party Redis Deployment + Service on the official redis image,
gated on redis.enabled (default off). Avoids the deprecated Bitnami subchart.
When enabled, the web deployment gets REDIS_URL pointing at the
{fullname}-redis service. In-cluster Redis runs without auth. (#93)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Enable Redis in the dev environment

Turn Redis on for dev, let ArgoCD sync it, and verify the app actually uses it.

**Files:**
- Modify: `infra/app/values-dev.yaml` (set `redis.enabled: true`)

- [ ] **Step 1: Enable redis in dev values**

In `infra/app/values-dev.yaml`, add a top-level block (near the `postgresql:` block):

```yaml
redis:
  enabled: true
```

- [ ] **Step 2: Confirm the dev render**

Run:

```bash
cd charts/family-pickem
helm template pickem-dev . -f ../../infra/app/values-dev.yaml | grep -A2 "name: REDIS_URL"
```

Expected: `value: "redis://family-pickem-dev-redis:6379/1"`.

- [ ] **Step 3: Commit and push (dev auto-deploys from main)**

```bash
git add infra/app/values-dev.yaml
git commit -m "feat(dev): enable Redis in the dev environment (#93)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

This change deploys to dev once merged to `main` (ArgoCD `pickem-dev` tracks main).

- [ ] **Step 4: Verify in the running dev cluster (post-merge)**

After ArgoCD syncs dev, confirm Redis is up and the app is using it:

```bash
# Redis pod running
kubectl get pods -n pickem-dev | grep redis
# App is pointed at Redis and can round-trip the cache
kubectl exec -n pickem-dev deploy/family-pickem-dev -- \
  python pickem/manage.py shell -c \
  "from django.core.cache import cache; cache.set('livecheck','ok',30); print('CACHE:', cache.get('livecheck'))"
# The key is visible in Redis DB 1
kubectl exec -n pickem-dev deploy/family-pickem-dev-redis -- \
  redis-cli -n 1 keys '*livecheck*'
```

Expected: the Redis pod is `Running`; the shell prints `CACHE: ok`; `redis-cli` lists a `...livecheck` key. (The official `redis` image is upstream-maintained, so there is no image-pull deprecation risk here.)

---

### Task 4: Enable Redis in the production environment

Only after dev is verified. This is the production rollout gate.

**Files:**
- Modify: `infra/app/values-prd.yaml` (set `redis.enabled: true`)

- [ ] **Step 1: Enable redis in prd values**

In `infra/app/values-prd.yaml`, add a top-level block (near the `postgresql:` block):

```yaml
redis:
  enabled: true
```

- [ ] **Step 2: Confirm the prd render**

Run:

```bash
cd charts/family-pickem
helm template pickem-prd . -f ../../infra/app/values-prd.yaml | grep -A2 "name: REDIS_URL"
```

Expected: `value: "redis://family-pickem-prd-redis:6379/1"`.

- [ ] **Step 3: Commit**

```bash
git add infra/app/values-prd.yaml
git commit -m "feat(prd): enable Redis in production (#93)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

This deploys to prd on the next GitHub Release (ArgoCD `pickem-prd` tracks releases).

- [ ] **Step 4: Verify in the running prd cluster (post-release)**

After the release syncs, repeat the dev verification against prd:

```bash
kubectl get pods -n pickem-prd | grep redis
kubectl exec -n pickem-prd deploy/family-pickem-prd -- \
  python pickem/manage.py shell -c \
  "from django.core.cache import cache; cache.set('livecheck','ok',30); print('CACHE:', cache.get('livecheck'))"
kubectl exec -n pickem-prd deploy/family-pickem-prd-redis -- \
  redis-cli -n 1 keys '*livecheck*'
```

Expected: Redis pod `Running`; `CACHE: ok`; the key is present in Redis DB 1.

---

## Self-Review

**Spec coverage (Phase 1 of the design doc):**
- "Add a Redis subchart to the Helm chart (dev + prd)" → satisfied via a self-managed Deployment instead of the Bitnami subchart (Tasks 2, 3, 4), a deliberate deviation because Bitnami deprecated its free catalog. ✓
- "Repoint `CACHES['default']` from `FileBasedCache` to `django-redis`" → Task 1. ✓
- "Redis serves two roles: shared cache and pub/sub broker" → cache used now (Task 1); broker DBs reserved via the DB-index comment (Task 2 Step 3). ✓
- "Done when: cache works cross-request/cross-pod and Redis reachable from pods" → Task 3/4 Step 4 verification. ✓

**Placeholder scan:** No TBD/TODO; every code and command step is concrete. ✓

**Type/name consistency:** `build_caches(environ)` is defined in Task 1 and consumed by settings in the same task; `REDIS_URL` env produced in Task 2 matches the key `build_caches` reads; the service name `{fullname}-redis` (= `family-pickem-{env}-redis`) is used consistently across the template, the `REDIS_URL` value, and all verification commands. Redis selector labels (`{name}-redis`) are deliberately distinct from the web selector to avoid overlap. ✓

**Notable deviation from spec:** self-managed Redis instead of the Bitnami subchart, decided after confirming Bitnami's Aug 2025 free-catalog deprecation. This removes the previously-flagged image-pull risk entirely (official `redis` image is upstream-maintained).
