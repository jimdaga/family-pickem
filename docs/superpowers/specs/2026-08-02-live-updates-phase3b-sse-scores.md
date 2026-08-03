# Live Updates — Phase 3b: Live Scores via SSE — Design

**Date:** 2026-08-02
**Status:** Approved (design); pending spec review
**Related issues:** #138
**Parent:** `docs/superpowers/specs/2026-08-02-live-updates-design.md` (Phase 3)
**Depends on:** 3a (ASGI/uvicorn, shipped 0.0.197), Redis w/ auth (0.0.195), scheduler split (0.0.194)

## Goal

Make game scores on `/scores/` update **live** (<2s from when our system learns
of a change) via Server-Sent Events, replacing the 30s full-HTML poll. Scope is
**scores only** — live points/ranks/W-L and the lobby are Phase 3c.

## Design

### A. Backend cadence (faster freshness during games)
- Add a **fast live-window cadence** for `update_games`: when any game in the
  current week has `statusType == "inprogress"`, run it every **~12s**;
  otherwise idle back to the normal 60s. (ESPN's scoreboard refreshes roughly
  every 15–20s, so ~12s is the practical floor.)
- The heavy downstream (`update_picks → update_standings → …`) stays on its
  normal cadence — 3b is scores-only; live points/ranks are 3c.
- Implementation fits the existing `ScheduledJobConfig`/tick model
  (`pickem_api/scheduler.py`): the fast cadence is a live-window-aware interval
  for the `update_games` step, not a new pipeline.

### B. Publish-on-write (scheduler pod → Redis)
- In `update_games`, after each game's `update_or_create`, if the score, status,
  quarter/clock, or winner **changed**, publish a compact JSON event to Redis
  channel `scores:{season}:{week}`:
  `{game_id, home_score, away_score, status, quarter, clock, winner}`.
- Only changed games publish (no spam). Runs in the scheduler pod's sync context
  via plain redis-py `publish` (reuse the `REDIS_URL` the app already has).
- If Redis is unavailable, the publish is best-effort and logged — never fails
  the pipeline (mirrors the cache's `IGNORE_EXCEPTIONS` posture).

### C. SSE endpoint
- `GET /events/scores/?week=<n>` — an **async** Django view (served by uvicorn):
  - Session-authenticated (must be logged in).
  - Subscribes to `scores:{season}:{week}` via `redis.asyncio` pubsub —
    **one subscription per connection** (simple; adequate for ~30–150 clients).
  - Streams `text/event-stream`; emits each published change as an SSE `data:`
    event; sends a keepalive comment (`: ping`) every ~20s.
  - Sets `X-Accel-Buffering: no` and `Cache-Control: no-cache` for Cloudflare/
    proxy friendliness.
  - Cleans up the Redis subscription on disconnect.

### D. Client
- Replace the 30s full-HTML re-fetch/`DOMParser` diff in `scores.html` with an
  `EventSource('/events/scores/?week=<n>')`.
- The page already renders fresh scores on load; the stream patches only changed
  games by `data-game-id`, reusing the existing score-update animation and the
  `inprogress → finished` completion handling.
- **Graceful fallback:** keep the existing 30s poll as a safety net — start it
  only if `EventSource` is unavailable or errors repeatedly. EventSource's
  built-in auto-reconnect handles transient drops.

### E. Async-safety & Cloudflare
- The custom sync middlewares (`pickem_homepage/middleware.py`) only inspect the
  request / short-circuit; they don't read or wrap the response body, so they
  won't buffer a streaming response. Verify during implementation; if any
  middleware buffers `/events/`, exempt that path.
- Keepalive + `X-Accel-Buffering: no` handle Cloudflare's idle timeout on the
  long-lived stream.

## Testing / verification
- Unit: change-detection + published-payload shape in `update_games` (a game
  whose score changed publishes; an unchanged game does not).
- Unit: live-window cadence selection (inprogress → fast; none → normal).
- Async: the SSE view requires auth (401/redirect when anonymous) and emits an
  event that was published to its channel (async test client + a fake/loopback
  publish).
- Client: fallback-to-poll when `EventSource` construction fails.
- Manual (dev): open `/scores/` during a simulated live game, publish a test
  event, confirm the card updates in <2s without reload; kill Redis → client
  falls back to polling, page still works.

## Risks
- **Long-lived connections under uvicorn/Cloudflare** — the most likely area to
  need real-environment tuning (keepalive interval, proxy timeouts). Verify on
  dev with a real browser before prd.
- **Startup async-context** (learned in 3a): the SSE view uses `redis.asyncio`
  (async-native) inside the async view, so no `SynchronousOnlyOperation`; any
  sync ORM reads it needs (e.g. resolving the current season) must be wrapped in
  `sync_to_async` or done via `aget`/async ORM.
- **ESPN rate** — ~12s polling during live windows only; negligible off-window.

## Out of scope (3c)
- Live points / ranks / W-L, `standings:{pool}:{season}:{week}` channels,
  downstream-on-final fast recompute, and the lobby widgets.
- Per-replica broadcaster (deferred optimization; per-connection is fine now).
