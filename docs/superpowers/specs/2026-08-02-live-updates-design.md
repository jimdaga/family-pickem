# Live Updates (SSE push) — Design

**Date:** 2026-08-02
**Status:** Approved (design); pending spec review
**Related issues:** #138 (async views for /scores/), #93 (shared cache / Redis), #95 (scheduler extraction + web autoscaling)

## Goal

Make Family Pickem *feel live*. During games, viewers should see — without reloading —
game scores/status, and (as picks get graded) their points, wins/losses, and
leaderboard rank, on both the dedicated scores page (`/scores/`) and the lobby
(homepage). Target latency: **< 2s** from when our system learns of a change to
when it appears on screen.

## Why the current approach is not enough

- **Frontend:** `scores.html` polls its own full URL every 30s, re-downloads the
  entire rendered HTML page, parses it with `DOMParser`, and diffs game cards.
  Heavy per client, and caps freshness at ~30s.
- **Backend:** the in-process APScheduler runs `update_games` every 60s, so the
  DB is up to ~60s stale. Combined worst case ~90s.
- **Infra ceiling:** WSGI served by `manage.py runserver`, a single web replica,
  file-based cache (`/tmp/django_cache`, no Redis), no ASGI/Channels. None of
  this can hold many long-lived push connections or coordinate across processes.

## Chosen approach

**Server-Sent Events (SSE) push, on a scaled-out stack.** SSE is the right fit:
the data flow is purely server→browser (no client→server messaging), SSE is
lighter than WebSockets/Channels, runs over plain HTTP, and auto-reconnects.

The push layer can only be as fresh as the database, so faster `update_games`
during live windows is a required companion, and a shared broker (Redis) is
required so the scheduler process can notify browser connections held by any web
replica.

## Decomposition & build order

Three sequential sub-projects, each with its own spec → plan → implementation:

### Phase 1 — Redis (#93)
- Add Redis as a **self-managed** Deployment + Service in the Helm chart (dev +
  prd), using the official `redis` image. Deliberately *not* the Bitnami subchart:
  Bitnami deprecated its free catalog (Aug 2025), moving versioned image tags to
  the frozen `bitnamilegacy` repo. In-cluster Redis runs without auth (network-
  internal); add auth from AWS SM/ESO before ever exposing it.
- Repoint `CACHES['default']` from `FileBasedCache` to `django-redis`.
- Redis serves two roles henceforth: shared Django cache **and** pub/sub broker
  for live events.
- **Done when:** cache works cross-request/cross-pod and Redis is reachable from
  pods.

### Phase 2 — Scheduler split + web autoscaling (#95)
- New single-replica `scheduler` Deployment: `RUN_SCHEDULER=true`, `replicas: 1`,
  no HPA. Only this pod writes the APScheduler `DjangoJobStore`.
- Web Deployment: `RUN_SCHEDULER=false`, `autoscaling.enabled=true` + HPA.
- Remove the Helm `fail` guard forbidding `scheduler.enabled && autoscaling.enabled`
  (now safe because they are separate deployments).
- **Done when:** the HPA scales web pods while exactly one scheduler runs the
  pipeline.

### Phase 3 — Live push feature
The main event. Depends on Phases 1 & 2 (and on the Django 5.2 upgrade for async
views/streaming). Detailed below.

## Phase 3 detail

### A. Backend cadence — faster freshness

Split work by what actually changes when:

- **During live play, only scores/status change.** A dedicated **fast scores job**
  on the scheduler runs `update_games` every **~10s** while any game in the
  current week is `inprogress`; when no game is live it idles back to the normal
  60s cadence. Self-adjusting — no fast polling outside game windows.
- **Points / ranks / W-L change only when a game goes final.** The heavy
  downstream (`update_picks → update_standings → update_rankings → update_stats`)
  does **not** run every 10s. It fires when the fast job detects a game flipping
  to `finished`, scoped to the affected pool/week.
- **ESPN reality:** the source feed refreshes roughly every 15–20s, so ~10s is
  the practical floor; faster just re-fetches unchanged data.

### B. Publish-on-write

After the scheduler writes fresh data, it `PUBLISH`es a compact JSON event to
Redis. Two channel families:

- `scores:{season}:{week}` — score/status deltas (not pool-specific).
- `standings:{pool}:{season}:{week}` — points / ranks / W-L deltas (pool-scoped).

Events carry only changed fields, e.g.
`{game_id, home, away, status, quarter, clock}` — **not** rendered HTML.

### C. Transport — ASGI + SSE

- Switch the web process from `manage.py runserver` (WSGI) to **uvicorn (ASGI)**.
  Required for scale regardless; lets one replica hold many live connections
  cheaply via async.
- One async view, `GET /events/`, that:
  - Authenticates via the existing session, then subscribes the browser **only**
    to channels it is allowed: the user's pools + the public scores channel.
    Enforces pool membership so nobody streams another family's standings.
  - Uses a **per-replica broadcaster**: one Redis subscription per replica fans
    out to all local connections, instead of one Redis connection per browser.
  - Sends a keepalive comment every ~20s so Cloudflare/proxies don't drop idle
    streams; sets `X-Accel-Buffering: no` to defeat buffering.
  - Relies on EventSource's built-in auto-reconnect for dropped connections.

### D. Client

- Replace the 30s full-HTML re-fetch in `scores.html` with a single
  `EventSource('/events/')`.
- On (re)connect, do **one** snapshot fetch of current state, then apply streamed
  deltas by patching elements keyed on `data-game-id` / `data-user-id`.
- The same handler set powers the lobby tiles (scores preview + standings
  preview). Retire the `DOMParser` diffing path.

### E. Error handling & testing

- **Graceful degradation:** if Redis/SSE is unavailable, the client falls back to
  a slow (~30s) poll of the snapshot endpoint. The page degrades, never breaks.
- **Async-safety:** the `/events/` path must be async-safe. Audit the two sync
  custom middlewares (`pickem_homepage/middleware.py`) and either make them
  async-compatible or exempt the streaming path.
- **Tests:**
  - Unit: live-window detection and fast/slow cadence switching; event payload
    shape.
  - Async: `/events/` auth scoping — a user must never receive another pool's
    channel.
  - Client: fallback-to-poll when the stream is unavailable.

## Notable risks

- **Cloudflare + SSE:** Cloudflare proxies SSE, but long-lived streams need the
  keepalive + no-buffering handling above to stay reliable. Most likely area to
  need real-environment tuning.
- **Middleware async-safety:** sync-only middleware around an async streaming view
  can force buffering/blocking; must be handled explicitly.
- **Connection budget:** at ~30–150 concurrent viewers, one uvicorn replica per
  the per-replica-broadcaster model is comfortable, but load-test before launch.

## Out of scope

- Bidirectional features (live chat/reactions) — would argue for WebSockets;
  not needed now.
- Against-the-spread / confidence pick types and other unrelated scoring work.
