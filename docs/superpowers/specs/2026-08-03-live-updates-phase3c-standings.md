# Live Updates — Phase 3c: Live Points / W-L + Lobby — Design

**Date:** 2026-08-03
**Status:** Approved (design); pending spec review
**Related issues:** #138
**Parent:** `docs/superpowers/specs/2026-08-02-live-updates-design.md` (Phase 3)
**Depends on:** 3a (uvicorn, 0.0.196/0.0.197), 3b (SSE scores, 0.0.198), Redis w/ auth.

## Goal

Make each player's **points** (this week's `week_N_points` and season
`total_points`) update live (no reload) on the lobby and standings views as games
settle — completing the live experience for scores (3b) + points (3c). **Scope
(confirmed):** points patch in place; the leaderboard *order* and the *rank
number* update on the next natural page load, not live. (There is no W/L record
in this app — standings metrics are points + rank; pick-accuracy stats are a
separate stats page, out of scope.) Live rank/reorder is a deferred fast-follow.

## Design

### A. Downstream-on-final (scheduler)
Points/W-L change only when a game settles. Extend the fast `live_scores_tick`:
after `update_games`, if the current week has any **finished-but-unscored** game
(`GamesAndScores.statusType == "finished"` with `gameScored == False`), run the
scoped downstream once — `update_picks → update_standings → update_rankings →
update_stats` (pool-scoped where the command supports `--pool`). This catches a
final within ~12s instead of waiting for the 60s pipeline; it's idempotent
(scoring flips `gameScored`, so subsequent ticks skip) and only fires on real
transitions.

### B. Publish-on-write (standings)
Add best-effort publish to `update_standings` (mirroring 3b's `update_games`):
after recomputing a pool member's `userSeasonPoints` row, if `total_points` (or
the current week's `week_N_points`) changed, publish a compact delta to the
**pool-scoped, season-scoped** channel `standings:{pool}:{season}` —
`{user_id, total_points, week, week_points, current_rank}` for changed rows only.
(`current_rank` is included for a future fast-follow; the 3c client patches only
points.) Reuse `live_events.py` — add `standings_channel(pool, season)` +
`standings_event_payload(row, week)`, and generalize the best-effort publisher to
a `publish_event(channel, payload)` used by both scores and standings.

### C. SSE endpoint — pool-scoped auth (the key new piece)
Scores are public; standings are not. Add `GET /events/standings/?pool=<slug>&week=<n>`
(async, uvicorn). It:
- Resolves the current season and the pool from `<slug>`, and **verifies the
  requesting user is a member of that pool** via `FamilyMembership` (user → family
  → pool) — all through `sync_to_async` (no sync ORM in the async path, per the
  3a lesson). Non-members get 403; anonymous is already blocked by
  `RequireLoginForInternalPagesMiddleware`.
- Subscribes to `standings:{pool}:{season}` and streams like 3b (reuse the
  generalized `_event_stream(channel)` — keepalive, graceful Redis-error end,
  guarded cleanup).
- The page keeps its own scores `EventSource` (3b) for game scores; standings is
  a second, pool-scoped stream. Two lightweight connections per page is fine at
  this scale (per-connection subscribe, per 3b's decision).

### D. Client
On the lobby (`family_pool_home.html`) and the standings page, add an
`EventSource('/events/standings/?pool=<slug>&week=<n>')` that patches each
player's **points in place** by `data-user-id` (add `data-user-id` +
`data-user-week-points` on the week-points-summary rows, and
`data-user-total-points` on the standings-page rows). Reuse the 3b client pattern
(feature-check, patch, poll fallback after repeated errors, close on give-up). Do
NOT reorder rows or change rank numbers (those update on reload). Expose the pool
slug + week to JS via data attributes.

### E. Fold in deferred 3b minors
While in these files: (1) guard `filterGames` so it doesn't start the 30s poll
while an SSE stream is healthy; (2) add the missing unit test for the SSE
Redis-error branch (`_event_stream` ending gracefully on a subscribe/connection
error); (3) the rare `notstarted→finished` direct-jump card refresh.

## Testing / verification
- Unit: standings change-detection + payload; pool-membership auth helper
  (member → allowed, non-member → denied) via the sync helper; downstream-on-final
  trigger (finished-unscored → runs recompute; none → skips).
- Async: `/events/standings/` requires membership (403 for non-member, stream for
  member); reuses the 3b stream-shape coverage.
- Full suite green.
- Dev→prd (gated, dev verified first per the 3a/dev-autotrack lesson): standings
  route reachable + membership-scoped, `standings:` pub/sub round-trip on authed
  Redis, and a settled game's points/W-L patching a lobby row live in a browser.

## Risks
- **Pool-scoped auth correctness** — a membership-check bug could leak another
  family's standings or wrongly deny a member. Cover both directions with tests.
- **Downstream cost during dense slates** — the scoped recompute on each final is
  heavier than a score publish; it's gated on finished-unscored and idempotent,
  but confirm it doesn't pile up when several games final near-simultaneously
  (the `update_games` overlap guard from 3b plus `gameScored` idempotency should
  contain it).
- Async-safety: all DB access in the async view via `sync_to_async` (3a lesson).

## Out of scope
- Live leaderboard **row reordering** / live rank number (deferred fast-follow).
- Per-replica broadcaster (still deferred; per-connection is fine).
