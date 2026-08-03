# Live Updates — Phase 3a: ASGI/uvicorn Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the web tier with uvicorn (ASGI) instead of `manage.py runserver`, and re-gate the scheduler start so it runs under uvicorn — no user-visible change.

**Architecture:** Add `uvicorn[standard]`, point it at the existing `pickem.asgi:application`, and switch the container entrypoint's server line to uvicorn (both web and scheduler pods). Re-gate `PickemApiConfig.ready()` on `RUN_SCHEDULER` + `RUN_WEB_SERVER` (dropping the runserver/`RUN_MAIN` reloader checks); the scheduler pod stays `replicas:1` + `--workers 1` so the scheduler starts exactly once.

**Tech Stack:** Django 5.2, uvicorn, Helm/ArgoCD, uv.

## Global Constraints

- Python `>=3.12`, Django `5.2.16`; deps pinned exactly in `pyproject.toml`/`uv.lock`, added via `uv add` (never hand-edit the lock).
- Tests run from `pickem/` with `--settings=pickem.test_settings` (SQLite), unittest discovery (`manage.py test`) — new tests must be `TestCase`/`SimpleTestCase` classes, NOT bare pytest functions (bare functions collect 0 tests here).
- Container: deps install via `uv sync --frozen --no-dev`; the venv `/code/.venv/bin` is on `PATH`, so `uvicorn` resolves. WORKDIR is `/code`; `pickem.asgi:application` is importable there.
- The scheduler pod MUST run uvicorn with exactly one worker (`--workers 1`) and stay `replicas:1` (single scheduler). Web pods carry `RUN_SCHEDULER=false` so they never start a scheduler regardless of workers.
- Task 1 and Task 2 must ship together (same branch/release): the entrypoint switch needs the re-gated `ready()` for the scheduler to start under uvicorn. They will, being one branch.
- GitOps: dev tracks main; prd tracks releases. Enable/verify dev before prd.

---

### Task 1: Migrate the server to uvicorn

Add uvicorn, declare the ASGI app, and switch the entrypoint's server line.

**Files:**
- Modify: `pyproject.toml` (add `uvicorn[standard]` via `uv add`)
- Modify: `pickem/pickem/settings.py` (add `ASGI_APPLICATION`)
- Modify: `docker/app/docker-entrypoint.sh` (server line → uvicorn)

- [ ] **Step 1: Add uvicorn**

From repo root:

```bash
uv add "uvicorn[standard]==0.34.0"
```

Confirm `pyproject.toml` lists `uvicorn[standard]==0.34.0` and `uv.lock` updated.

- [ ] **Step 2: Declare the ASGI application**

In `pickem/pickem/settings.py`, immediately after the existing `WSGI_APPLICATION = 'pickem.wsgi.application'` line, add:

```python
# Served by uvicorn in deployed environments (see docker-entrypoint.sh); the
# streaming SSE endpoints in a later sub-phase require ASGI. WSGI is kept for
# tooling/back-compat.
ASGI_APPLICATION = 'pickem.asgi.application'
```

- [ ] **Step 3: Switch the entrypoint server line to uvicorn**

In `docker/app/docker-entrypoint.sh`, replace the final two lines:

```sh
# Start Server
export RUN_WEB_SERVER=true
python manage.py runserver 0.0.0.0:8000
```

with:

```sh
# Start Server (ASGI). exec so uvicorn is PID 1 for clean signal handling.
# RUN_WEB_SERVER marks the server process (never set for the migrate init or
# management commands) — apps.py uses it to gate scheduler startup.
export RUN_WEB_SERVER=true
exec uvicorn pickem.asgi:application --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-1}"
```

- [ ] **Step 4: Local uvicorn smoke test**

From `pickem/`:

```bash
uv run uvicorn pickem.asgi:application --host 127.0.0.1 --port 8123 &
UVPID=$!
sleep 3
curl -fsS -o /dev/null -w "livez=%{http_code}\n" http://127.0.0.1:8123/livez/
curl -fsS -o /dev/null -w "healthz=%{http_code}\n" http://127.0.0.1:8123/healthz/
kill $UVPID
```

Expected: `livez=200`; `healthz=200` (a DB must be reachable for `/healthz`; if none locally, `livez=200` alone is sufficient proof uvicorn serves the ASGI app). No import errors on startup.

- [ ] **Step 5: Full test suite still green**

```bash
cd pickem && uv run python manage.py test --settings=pickem.test_settings
```

Expected: passes as before.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock pickem/pickem/settings.py docker/app/docker-entrypoint.sh
git commit -m "feat(server): serve via uvicorn (ASGI) instead of runserver

Add uvicorn[standard], declare ASGI_APPLICATION, and switch the container
entrypoint to uvicorn. Foundation for the SSE push feature. (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Re-gate the scheduler startup

Make the scheduler start under uvicorn (no runserver/reloader), via a testable helper.

**Files:**
- Modify: `pickem/pickem_api/apps.py`
- Test: `pickem/pickem_api/tests/test_scheduler_gate.py`

**Interfaces:**
- Produces: `pickem_api.apps._should_start_scheduler(environ)` → `bool` — True iff `environ['RUN_SCHEDULER'] == 'true'` AND `environ['RUN_WEB_SERVER'] == 'true'`.

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_api/tests/test_scheduler_gate.py`:

```python
from django.test import SimpleTestCase

from pickem_api.apps import _should_start_scheduler


class ShouldStartSchedulerTests(SimpleTestCase):
    def test_both_true_starts(self):
        self.assertTrue(
            _should_start_scheduler(
                {"RUN_SCHEDULER": "true", "RUN_WEB_SERVER": "true"}
            )
        )

    def test_scheduler_only_does_not_start(self):
        self.assertFalse(_should_start_scheduler({"RUN_SCHEDULER": "true"}))

    def test_web_only_does_not_start(self):
        self.assertFalse(_should_start_scheduler({"RUN_WEB_SERVER": "true"}))

    def test_neither_does_not_start(self):
        self.assertFalse(_should_start_scheduler({}))

    def test_requires_literal_true(self):
        self.assertFalse(
            _should_start_scheduler(
                {"RUN_SCHEDULER": "1", "RUN_WEB_SERVER": "true"}
            )
        )
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_scheduler_gate --settings=pickem.test_settings -v 2
```

Expected: FAIL — `ImportError: cannot import name '_should_start_scheduler'`.

- [ ] **Step 3: Implement the helper and re-gate `ready()`**

In `pickem/pickem_api/apps.py`, add the module-level helper (above the class or after the imports):

```python
def _should_start_scheduler(environ):
    """Start the scheduler only in the dedicated server process of the scheduler
    pod: both RUN_SCHEDULER and RUN_WEB_SERVER are the string "true".

    RUN_WEB_SERVER is exported by the container entrypoint only for the server
    process (never for the migrate init or `manage.py` commands), so a
    RUN_SCHEDULER=true pod's migrate/shell/check processes never start a
    scheduler. Under uvicorn --workers 1 (the scheduler pod), ready() runs once.
    """
    return (
        environ.get("RUN_SCHEDULER") == "true"
        and environ.get("RUN_WEB_SERVER") == "true"
    )
```

Then replace the four-check guard in `ready()` (currently):

```python
        if os.environ.get("RUN_SCHEDULER") != "true":
            return
        if os.environ.get("RUN_WEB_SERVER") != "true":
            return
        if len(sys.argv) < 2 or sys.argv[1] != "runserver":
            return
        if os.environ.get("RUN_MAIN") != "true":
            return

        from . import scheduler

        scheduler.start()
```

with:

```python
        if not _should_start_scheduler(os.environ):
            return

        from . import scheduler

        scheduler.start()
```

Remove the now-unused `import sys` at the top of `apps.py` if nothing else uses it (check first — `grep -n "sys\." pickem/pickem_api/apps.py`; only remove the import if there are no other `sys.` uses).

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_scheduler_gate --settings=pickem.test_settings -v 2
```

Expected: PASS (5 tests).

- [ ] **Step 5: Full suite green (scheduler stays OFF in tests)**

```bash
cd pickem && uv run python manage.py test --settings=pickem.test_settings
```

Expected: passes; no scheduler starts during tests (neither env var is set).

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_api/apps.py pickem/pickem_api/tests/test_scheduler_gate.py
git commit -m "feat(scheduler): gate start on RUN_SCHEDULER+RUN_WEB_SERVER (uvicorn-ready)

Drop the runserver/RUN_MAIN reloader dependency so the scheduler starts under
uvicorn; extract the decision into a unit-tested helper. Scheduler pod runs
uvicorn --workers 1 (replicas:1) so ready() fires once. (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Deploy verification (dev → prd)

No values changes are needed — the entrypoint switch applies to both deployments automatically. This task is the gated rollout verification.

- [ ] **Step 1: (dev, post-merge) web serves under uvicorn**

After the branch merges to main and ArgoCD syncs dev:

```bash
kubectl config use-context kubernetes-admin@kubernetes
kubectl get pods -n pickem-dev | grep -E "family-pickem-dev(-scheduler)?-"
WPOD=$(kubectl get pods -n pickem-dev -l app.kubernetes.io/name=family-pickem --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n pickem-dev "$WPOD" -c family-pickem -- sh -c 'ps -o args= -p 1 | head -1'
```

Expected: pods `Running`/`Ready`; PID 1 is the `uvicorn pickem.asgi:application ...` process (not `manage.py runserver`).

- [ ] **Step 2: (dev) scheduler still runs the pipeline**

```bash
SPOD=$(kubectl get pods -n pickem-dev -l app.kubernetes.io/component=scheduler -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n pickem-dev "$SPOD" -- python /code/manage.py shell -c "from pickem_api.models import JobRun; from django.utils import timezone; j=JobRun.objects.order_by('-started_at').first(); print('LATEST_JOBRUN:', j.job_id, j.status, int((timezone.now()-j.started_at).total_seconds()),'s ago') if j else print('none')"
```

Expected: a recent `JobRun` (≤ a few minutes) — proves the re-gated scheduler starts under uvicorn. Also confirm the superadmin overview shows the scheduler healthy.

- [ ] **Step 3: (prd, post-release) repeat the checks**

After the release syncs to prd, repeat Steps 1–2 against `pickem-prd` (namespace `pickem-prd`, pods `family-pickem-prd*`). Confirm web PID 1 is uvicorn, and the scheduler pod has a recent `JobRun`.

Expected: prd web on uvicorn, scheduler pipeline healthy — no user-visible change, dev server retired.

---

## Self-Review

**Spec coverage (Phase 3a design):**
- uvicorn dep + ASGI_APPLICATION + entrypoint → Task 1. ✓
- Re-gate scheduler on RUN_SCHEDULER+RUN_WEB_SERVER, drop runserver/RUN_MAIN → Task 2. ✓
- Single scheduler under uvicorn --workers 1 → Global Constraints + Task 2 helper docstring; entrypoint uses `${UVICORN_WORKERS:-1}` default 1. ✓
- Testable `_should_start_scheduler` helper with the env matrix → Task 2 tests. ✓
- Verify web on uvicorn + scheduler JobRun (dev→prd) → Task 3. ✓
- Static via S3 / local dev unaffected / sync middleware works → design doc; no code needed (nothing to change). ✓

**Placeholder scan:** none — all code/commands concrete. ✓

**Type/name consistency:** `_should_start_scheduler(environ)` defined and consumed in Task 2; entrypoint `RUN_WEB_SERVER` export matches the env var the helper reads; `UVICORN_WORKERS` default 1 matches the single-scheduler requirement. ✓

**Ordering:** Task 1 and Task 2 both land on the branch before any deploy (Task 3), so the scheduler is never broken in a shipped state — noted in Global Constraints. ✓
