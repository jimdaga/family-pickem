# Live Updates — Phase 3a: ASGI/uvicorn Migration — Design

**Date:** 2026-08-02
**Status:** Approved (design); pending spec review
**Related issues:** #138 (async /scores/), part of the live-updates initiative Phase 3
**Parent:** `docs/superpowers/specs/2026-08-02-live-updates-design.md` (Phase 3)

## Goal

Serve the web tier with a production ASGI server (uvicorn) instead of
`manage.py runserver`, and adapt the scheduler's startup to the new model.
**No user-visible change.** This de-risks the prod server swap on its own and is
the foundation the SSE push feature (3b) requires (async streaming views).

## Motivation

- The app runs `manage.py runserver` — the Django dev server — in every
  deployed environment (`docker/app/docker-entrypoint.sh`), which even Django
  warns against in prod and cannot hold the long-lived async connections SSE
  needs.
- `pickem/pickem/asgi.py` already exposes `application`, but nothing serves it
  and `ASGI_APPLICATION` is unset.
- The scheduler currently starts in `PickemApiConfig.ready()` gated on
  `runserver` + `RUN_MAIN` (the runserver reloader child). Moving off runserver
  requires re-gating that startup — and doing so removes the brittle
  reloader dependency flagged during Phase 2 review.

## Design

### Server: uvicorn
- Add dependency `uvicorn[standard]`.
- Set `ASGI_APPLICATION = 'pickem.asgi.application'` in `settings.py` (keep
  `WSGI_APPLICATION` for tooling/back-compat).
- Entrypoint server line becomes:
  `exec uvicorn pickem.asgi:application --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}`
  (`exec` so uvicorn is PID 1 for clean signal handling). Both web and scheduler
  pods use this same entrypoint.
- One uvicorn worker per pod by default. Async plus the Phase 2 HPA handle
  concurrency and scale; Django's sync views run in ASGI's threadpool.

### Scheduler-start adaptation
Re-gate `PickemApiConfig.ready()`:

```python
# start the scheduler in the dedicated server process of the scheduler pod only
if os.environ.get("RUN_SCHEDULER") != "true":
    return
if os.environ.get("RUN_WEB_SERVER") != "true":
    return
from . import scheduler
scheduler.start()
```

- Drops the `sys.argv[1] == "runserver"` and `RUN_MAIN == "true"` checks.
- `RUN_WEB_SERVER=true` is exported by the entrypoint **only** for the server
  process — the migrate init and management commands (migrate/shell/check) never
  set it — so a `RUN_SCHEDULER=true` pod's migrate-check init still will not
  start a scheduler.
- Single-instance guarantee: the scheduler pod stays `replicas: 1` (Phase 2) and
  runs uvicorn `--workers 1`, so `ready()` runs exactly once → one scheduler.
  `scheduler.start()` is already idempotent within a process.

### Unaffected / safe
- **Static files** are served from S3 (`STORAGES`/django-storages) in dev and
  prd, so uvicorn need not serve them.
- **Local dev** is untouched: developers run `uv run python manage.py runserver`
  directly (CLAUDE.md), not the container entrypoint. `RUN_SCHEDULER`/
  `RUN_WEB_SERVER` are unset locally, so the scheduler stays off locally (and in
  tests) exactly as today.
- **Sync middleware** (`pickem_homepage/middleware.py`) works under ASGI —
  Django auto-wraps sync middleware. Async-safety of the *streaming* SSE path is
  a 3b concern; this phase has no streaming endpoint.

## Testing / verification

- Unit: the re-gated `ready()` logic — a small helper `_should_start_scheduler(environ)`
  returning True only when both env vars are `"true"`, unit-tested for the
  matrix (neither/one/both set). Keeps the decision testable without launching a
  server.
- Full existing suite stays green (server model doesn't affect tests).
- Local smoke: run `uvicorn pickem.asgi:application` and curl `/livez/`,
  `/healthz/`, `/` — pages render.
- Post-deploy (dev then prd): web pods serve under uvicorn (Ready), and the
  **scheduler pod still runs the pipeline** (recent `JobRun`) and the superadmin
  overview shows it healthy — the key confirmation that the re-gated startup
  works under uvicorn.

## Risks

- **Prod server swap** is the real risk, but it's isolated here with no other
  change, and gated dev → prd. If uvicorn misbehaves, roll back the release.
- **Scheduler doesn't start under uvicorn** if the re-gating is wrong — caught by
  the post-deploy `JobRun` check in dev before prd.
- **Long-request behavior differs** slightly (uvicorn vs runserver); no
  long-lived endpoints exist yet (SSE is 3b), so low exposure.

## Out of scope (later sub-phases)
- 3b: backend live cadence, Redis publish-on-write, async `/events/` SSE
  endpoint, live scores on `/scores/`.
- 3c: points/ranks/W-L live + lobby widgets.
- Async-rewriting the custom middleware (only needed for the streaming path, 3b).
