# Structural Live Updates (#159) — Design

**Status:** Approved 2026-08-03. Follow-on to the SSE live-updates initiative
(Phases 1–3c shipped through `family-pickem-0.0.199`; see
`docs/superpowers/specs/2026-08-02-live-updates-design.md`).

## Problem

SSE currently only **patches existing DOM text** — a game card's score, a
leaderboard row's week-points cell. It cannot create, remove, or reorder
elements. So three structural changes still require a manual page reload:

1. **Scores card status swap** — a game going `notstarted → inprogress`
   (kickoff) or `inprogress → finished` changes the card's *layout*, not just
   its numbers. SSE flips `data-game-status` and patches score text, but the
   card keeps its old structure until reload.
2. **Lobby / standings section first-appearance** — a leaderboard row (or a
   whole section) that isn't yet in the DOM when its first event arrives.
3. **Rank reorder** — when week-points/points change enough to change row
   order, the values update in place but the rows never move.

This is the reload friction observed during the 0.0.199 / 0.0.202 live demos.

## Current state (verified 2026-08-03)

| Surface | Has now | Structural gap |
|---|---|---|
| `/scores/` | Score-text patch via SSE (`applyScoreEvent`); full-page card refetch (`updateLiveScores`) **gated on `hasLiveGames()`** | Kickoff & finish don't swap card layout (gate is false pre-kickoff) |
| Lobby (`family_pool_home.html`) | Week-points value patch by `data-user-id` (`applyStandingsEvent`) | Section first-appearance, new member rows, rank reorder |
| `/standings/` | Points value patch by `data-user-id` (`applyStandingsEvent`) | Rank reorder |

Relevant existing code:
- `pickem/pickem_homepage/templates/pickem/scores.html` — `applyScoreEvent`
  (~L1613), `updateLiveScores` (~L1369, does card-by-card `innerHTML` swap),
  `hasLiveGames` (~L1365), EventSource wiring (~L1677).
- `pickem/pickem_homepage/templates/pickem/family_pool_home.html` and
  `standings.html` — `applyStandingsEvent` patches `[data-user-week-points]` /
  points cell by `[data-user-id]`.
- `pickem/pickem_api/scheduler.py` — `live_window_active()` (L217) is true
  **only when a game is already `inprogress`**, so the fast 12s
  `run_live_scores_tick` does not run before kickoff; the kickoff status write
  comes from the 60s `run_pipeline_tick` instead.

## Chosen approach: SSE-signaled structural refetch (Approach A)

SSE remains the "something changed" signal. The existing **value-patch** path
stays the untouched fast path. We add **one** new path: when an event implies a
change the client can't express by editing text, the client triggers a
**debounced refetch** of just the affected page region and swaps its
`innerHTML`. The server stays the single source of layout truth — no template
duplication, no rendering in the async/SSE path.

Rejected alternatives:
- **B — dedicated fragment endpoints:** lighter payloads but new views/routes +
  partial extraction + tests; deferred to #160 as an optimization if payload
  size ever matters.
- **C — push rendered HTML over SSE:** requires async template rendering
  (`sync_to_async`), fatter Redis messages, awkward per-user styling. Rejected.

## Components

### 1. Shared refetch coordinator (new vanilla-JS helper)

A small helper, reused by scores + lobby + standings clients:

- `scheduleStructuralRefetch(regionKey)` — trailing-debounced (~1.5s). A burst
  of events coalesces into a single refetch. Multiple distinct `regionKey`s
  requested within the window are all swapped by the one fetch.
- On fire: `fetch(window.location.href, { headers: XHR + no-store,
  credentials: 'same-origin' })`, parse with `DOMParser`, and for each
  registered region swap the container's `innerHTML` from the fresh document,
  then re-run that region's layout hooks.
- This generalizes the swap logic already in `updateLiveScores`; extract the
  fetch-parse-swap core so both the interval poll and SSE call the same code.
- Vanilla JS only — no new dependency; matches existing style.

**Region registry** (per page, declared where the client is wired):
- `scores` → swap each `.game-score-card` by index (as `updateLiveScores` does
  today) + the weekly-performance and week-points-leaderboard blocks; re-init
  the week-points pager/layout manager.
- `leaderboard` → swap the lobby podium+list container / standings table body;
  re-init pagination + `weekPointsLayoutManager`.

### 2. Scores — kickoff / finish swap

> **Implementation note (found during planning):** this is **already
> implemented and working**. `statusType` is in `SCORE_TRIGGER_FIELDS`
> (`live_events.py`), so a kickoff/finish publishes an SSE event; `applyScoreEvent`
> (`scores.html` ~L1618) already detects the status change, forces `hasLiveGames()`
> true, and calls `updateLiveScores()` for a full card refetch. The 0.0.199/0.0.202
> demo "didn't swap" only because the DB was edited directly, bypassing
> `update_games`/publish. **No change needed here** beyond the §4 fallback.


In `applyScoreEvent`: when the event's `status` ≠ the card's current
`data-game-status`, call `scheduleStructuralRefetch('scores')` (in addition to
flipping `data-game-status` so `hasLiveGames()` stays correct for the interval
poll). The refetch renders the correct layout for the new status.

- The common in-progress score tick (no status change) keeps the current
  in-place value patch — no refetch.
- The SSE-triggered refetch path is **ungated from `hasLiveGames()`** so kickoff
  works when nothing is live yet. (The 30s interval poll stays gated as-is.)

### 3. Lobby / standings — section appearance + reorder

In `applyStandingsEvent`, after locating the row by `data-user-id`:

- **No row exists** for that `user_id` → structural (new member / section
  first-appearance) → `scheduleStructuralRefetch('leaderboard')`.
- Row exists but the new `week_points`/`points` would **change its order**
  relative to its immediate neighbors → `scheduleStructuralRefetch('leaderboard')`.
- Otherwise → in-place value patch (unchanged current behavior).

Order-change detection: compare the incoming value against the adjacent visible
rows' values (read from their `data-*` value attributes); if the new value
crosses a neighbor, it's a reorder.

### 4. Trigger reliability (fallback)

Because `live_window_active()` is false pre-kickoff, the kickoff status event
comes from the 60s pipeline tick, and the existing 30s interval poll is also
gated on `hasLiveGames()`. SSE is therefore the sole prompt kickoff trigger. To
guarantee the swap even if an SSE event is dropped or missed, add a
**lightweight client heartbeat**: when the page has `notstarted` cards whose
kickoff time is at/past `now`, run a low-frequency (~60s)
`scheduleStructuralRefetch('scores')` until they flip. Cheap, self-limiting, and
the debounce ensures heartbeat + SSE never double-fetch.

### 5. Week Points block polish (lobby — final step)

Bundled cosmetic/rank improvements to the lobby Week Points block
(`family_pool_home.html`, the podium grid from 0.0.202). These share the block
and the "has a completed game" condition, so they land as the last step:

- **Rank only after a completed game.** `build_week_points_summary` currently
  assigns `rank = 1..N` unconditionally. Change it to assign a numeric rank
  **only when the current week has ≥1 completed game**; otherwise `rank = None`.
  The template renders `#N` when `row.rank` is set and `–` (em/en-dash, matching
  the existing standings-preview treatment at ~L348) when it is `None`. Before
  any game completes, everyone is equal, so every row shows `–`.
  - Detection: a boolean `week_has_completed_game` (any `GamesAndScores` row for
    the season+week with `statusType='finished'`), computed in the view and
    passed into the helper so the helper stays pure and unit-testable.
- **User avatars (like the scores page).** Each Week Points row renders the
  member's avatar via `{% with row.points.userID|lookupavatar as avatar %}` →
  `<img class="w-8 h-8 rounded-full border …" src="{{ avatar|default:'https://www.gravatar.com/avatar/?d=identicon&s=64' }}">`,
  matching the scores-page styling. The numeric rank (`#N`, when present) shows as
  a small label beside the avatar; when unranked, the `–` shows in its place.
  `lookupavatar` is already loaded (`pickem_homepage_extras`) in the template.
- **Paginate at 12, not 10.** The grid is 3 columns × 4 rows, so
  `data-week-points-page-size="10"` → `"12"` fills a clean page.

Interaction with §3: pre-completion all rows are equal and unranked, so no
reorder occurs; post-completion ranks are numeric and the §3 reorder-refetch
applies normally.

### 6. Testing

The behavior is client-side JS, which Django can't unit-test directly. Scope:

- **Django tests (contract lock):** assert each page renders the container
  hooks and `data-*` attributes the client depends on — `data-game-status` and
  `data-game-id` on cards, `data-user-id` (+ the value attributes used for
  reorder detection) on leaderboard rows, and the region container ids — so a
  template change can't silently break the client contract.
- **Server-side rank rule (§5):** extend the existing
  `BuildWeekPointsSummaryTests` — assert every row has `rank is None` when the
  week has no completed game, and `rank = 1..N` once a completed game exists.
- **No other server behavior changes**, so the existing suite covers regressions.
- **Behavioral verification:** scripted live demo on dev (as done for 0.0.199 /
  0.0.202): drive a `notstarted → inprogress → finished` transition and a
  point change that reorders rows, confirm swaps with no reload, then restore.

## Out of scope (→ epic #160)

- Fragment endpoints (Approach B) as a payload optimization.
- Live **total-points / rank value** updates beyond week-points.
- Stats, team-records, message-board, and season-winner live surfaces.

## Global constraints

- Vanilla JS only; no new frontend dependency.
- No `?v=` cache-buster on `{% static %}` URLs (see CLAUDE.md).
- No server behavior changes to the SSE publish path or views; this is a
  client + template-contract change only.
- Any real utility-class additions require `npm run build:prod`; discard
  version-only `tailwind.css` churn.
