# Live Updates — Phase 3c: Live Points + Lobby (+ complete live game state) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live points on the lobby + standings (patched in place; rank/order on reload), via downstream-on-final recompute + a pool-membership-scoped SSE stream; plus complete the live game state on `/scores/` (clock/quarter + per-quarter line scores). Folds in the deferred 3b minors.

**Architecture:** When a game finals, the fast `live_scores_tick` runs the scoped downstream recompute; `update_standings` publishes changed points to a pool-scoped `standings:{pool}:{season}` Redis channel. A new async `/events/standings/` endpoint verifies pool membership (via `sync_to_async`) and streams it. The client patches points by `data-user-id`. Separately, the scores payload/client gain the clock/quarter + per-quarter scores.

**Tech Stack:** Django 5.2 async views + `sync_to_async`, redis-py / `redis.asyncio`, uvicorn/ASGI, APScheduler, vanilla JS `EventSource`.

## Global Constraints

- Python `>=3.12`, Django `5.2.16`; deps already present (`redis`, `django-redis`, `uvicorn`). Tests: `--settings=pickem.test_settings`, unittest discovery, `TestCase`/`SimpleTestCase` classes only.
- **No sync ORM in any async view/generator** (the 3a lesson that crashed prod): the SSE membership check and season lookup MUST go through `asgiref.sync.sync_to_async`; use `redis.asyncio` for the subscription. Reviewers must grep the async module for `.objects`/`models.`.
- Standings are **pool-scoped and not public**: the SSE endpoint must stream `standings:{pool}:{season}` ONLY to members of that pool (`FamilyMembership` user→family→pool). Non-members → 403. Cover both directions with tests.
- `update_standings` is **season-scoped** (`userSeasonPoints.total_points`); channel is `standings:{pool}:{season}` (no week). Publish is best-effort (never breaks the pipeline), like 3b.
- Reuse 3b machinery: generalize `live_events` to `publish_event(channel, payload)`; reuse the `_event_stream(channel)` async generator (keepalive, graceful Redis-error end, guarded cleanup) for the standings endpoint.
- Client: no row reordering, no live rank number (reload only). No `?v=` cache-buster on `{% static %}`. Rebuild `tailwind.css` only if utility classes are added (they won't be).
- GitOps: dev auto-tracks `-latest` again (fixed 2026-08-03). Verify dev is actually on the new image (image tag + a runtime signal) before the prd release — do NOT merge+release back-to-back for this runtime-heavy change.

---

### Task 1: Generalize live_events + standings/scores payloads

**Files:**
- Modify: `pickem/pickem_api/live_events.py`
- Modify: `pickem/pickem_api/tests/test_live_events.py`

**Interfaces:**
- Produces: `publish_event(channel, payload)` (generalized best-effort publisher); `standings_channel(pool_id, season)` → `f"standings:{pool_id}:{season}"`; `standings_event_payload(row, week)` → `{user_id, total_points, week, week_points, current_rank}`; `SCORE_TRIGGER_FIELDS` (extends `LIVE_SCORE_FIELDS` with the per-quarter period fields); `score_event_payload` extended with period arrays. `publish_score_event` stays as a thin wrapper over `publish_event` for back-compat with 3b callers.

- [ ] **Step 1: Write failing tests**

Add to `pickem/pickem_api/tests/test_live_events.py`:

```python
class StandingsEventTests(SimpleTestCase):
    def test_standings_channel(self):
        self.assertEqual(live_events.standings_channel(7, 2627), "standings:7:2627")

    def test_standings_payload(self):
        from unittest import mock
        row = mock.Mock(userID="u1", total_points=42, current_rank=2)
        setattr(row, "week_3_points", 5)
        p = live_events.standings_event_payload(row, 3)
        self.assertEqual(p["user_id"], "u1")
        self.assertEqual(p["total_points"], 42)
        self.assertEqual(p["week"], 3)
        self.assertEqual(p["week_points"], 5)


class ScorePayloadPeriodsTests(SimpleTestCase):
    def test_score_payload_includes_periods_and_status_title(self):
        from unittest import mock
        g = mock.Mock(id=1, homeTeamScore=7, awayTeamScore=0, statusType="inprogress",
                      statusTitle="5:00 - 2nd Quarter", gameWinner="",
                      homeTeamPeriod1=7, homeTeamPeriod2=0, homeTeamPeriod3=0,
                      homeTeamPeriod4=0, homeTeamPeriodOT=0,
                      awayTeamPeriod1=0, awayTeamPeriod2=0, awayTeamPeriod3=0,
                      awayTeamPeriod4=0, awayTeamPeriodOT=0)
        p = live_events.score_event_payload(g)
        self.assertEqual(p["status_title"], "5:00 - 2nd Quarter")
        self.assertEqual(p["home_periods"], [7, 0, 0, 0, 0])
        self.assertEqual(p["away_periods"], [0, 0, 0, 0, 0])
```

- [ ] **Step 2: Run — verify fail**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_live_events --settings=pickem.test_settings -v 2
```
Expected: FAIL (missing `standings_channel`/`standings_event_payload`/period keys).

- [ ] **Step 3: Implement in `live_events.py`**

Generalize the publisher and add the standings helpers + period fields:

```python
def publish_event(channel, payload):
    """Best-effort publish of one event to a Redis channel. Never raises."""
    try:
        client = _redis_client()
        if client is None:
            return
        client.publish(channel, json.dumps(payload))
    except Exception:
        logger.warning("live event publish failed", exc_info=True)


def publish_score_event(season, week, payload):
    publish_event(scores_channel(season, week), payload)


# Period fields also trigger a scores publish (clock/quarter live updates).
_PERIOD_FIELDS = (
    "homeTeamPeriod1", "homeTeamPeriod2", "homeTeamPeriod3", "homeTeamPeriod4",
    "homeTeamPeriodOT", "awayTeamPeriod1", "awayTeamPeriod2", "awayTeamPeriod3",
    "awayTeamPeriod4", "awayTeamPeriodOT",
)
SCORE_TRIGGER_FIELDS = LIVE_SCORE_FIELDS + _PERIOD_FIELDS


def standings_channel(pool_id, season):
    return f"standings:{pool_id}:{season}"


def standings_event_payload(row, week):
    return {
        "user_id": row.userID,
        "total_points": row.total_points,
        "week": week,
        "week_points": getattr(row, f"week_{week}_points", None),
        "current_rank": getattr(row, "current_rank", None),
    }
```

Extend `score_event_payload` to add:

```python
        "home_periods": [game.homeTeamPeriod1, game.homeTeamPeriod2,
                         game.homeTeamPeriod3, game.homeTeamPeriod4,
                         game.homeTeamPeriodOT],
        "away_periods": [game.awayTeamPeriod1, game.awayTeamPeriod2,
                         game.awayTeamPeriod3, game.awayTeamPeriod4,
                         game.awayTeamPeriodOT],
```

- [ ] **Step 4: Run — verify pass** (all `test_live_events` tests).
- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/live_events.py pickem/pickem_api/tests/test_live_events.py
git commit -m "feat(live): generalize publisher; standings channel/payload; score periods (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: update_games publishes clock/quarter changes

Extend the scores change-detection to fire on `statusTitle`/period changes (not just totals) so the clock/quarter ticks live.

**Files:**
- Modify: `pickem/pickem_api/management/commands/update_games.py`
- Modify: `pickem/pickem_api/tests/test_update_games_publish.py`

- [ ] **Step 1:** In `update_games.py`, change the imported/used trigger set from `LIVE_SCORE_FIELDS` to `SCORE_TRIGGER_FIELDS` in `maybe_publish_game_change` and in the `previous_by_id` `.values(...)` pre-fetch (so a clock/quarter change is detected). Keep the payload = `score_event_payload` (now with periods).
- [ ] **Step 2:** Add a test: a game whose only change is `statusTitle` (clock tick) publishes; a fully-unchanged game does not. Run the `test_update_games_publish` module.
- [ ] **Step 3:** Full suite green.
- [ ] **Step 4: Commit**

```bash
git commit -am "feat(live): publish clock/quarter (statusTitle+period) changes from update_games (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: update_standings publish-on-write

**Files:**
- Modify: `pickem/pickem_api/management/commands/update_standings.py`
- Test: `pickem/pickem_api/tests/test_update_standings_publish.py`

- [ ] **Step 1:** Write a failing test: a member whose `total_points` changed publishes to `standings:{pool}:{season}`; unchanged does not. (Test a helper `maybe_publish_standings_change(before_total, row, week)` mirroring `maybe_publish_game_change`, mocking `publish_event`.)
- [ ] **Step 2:** Run — verify fail.
- [ ] **Step 3:** Implement: at the `get_or_create` in `handle()`, capture the pre-save `total_points` (the row is fetched/created before recompute; capture `row.total_points` before mutation). After `row.save()`, call `maybe_publish_standings_change(old_total, row, current_week)` which publishes `standings_event_payload(row, current_week)` to `standings_channel(row.pool_id, season)` when `total_points` changed. Compute `current_week` once (from `get_season`-adjacent week lookup or `GameWeeks` for today; if unavailable, publish with the season-total only and `week=None`). Best-effort (never breaks the recompute).
- [ ] **Step 4:** Run — verify pass; full suite green.
- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/management/commands/update_standings.py pickem/pickem_api/tests/test_update_standings_publish.py
git commit -m "feat(live): publish changed standings points from update_standings (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Downstream-on-final in the fast tick

**Files:**
- Modify: `pickem/pickem_api/scheduler.py`
- Modify: `pickem/pickem_api/tests/test_live_window.py`

**Interfaces:**
- Produces: `scheduler.finished_unscored_exists()` (any current-season game `finished` with `gameScored=False`); `run_live_scores_tick` also runs the scoped downstream when that's true.

- [ ] **Step 1:** Write failing tests: `finished_unscored_exists()` true iff a finished+unscored game exists; `run_live_scores_tick`, after `update_games`, runs the downstream chain (mock `run_job_once`) exactly once when `finished_unscored_exists()` and skips it otherwise. (Keep the existing update_games overlap guard behavior.)
- [ ] **Step 2:** Run — verify fail.
- [ ] **Step 3:** Implement in `scheduler.py`:

```python
def finished_unscored_exists():
    from pickem.utils import get_season
    from pickem_api.models import GamesAndScores
    return GamesAndScores.objects.filter(
        gameseason=get_season(), statusType="finished", gameScored=False
    ).exists()
```

In `run_live_scores_tick`, after the `update_games` run, add:

```python
    if finished_unscored_exists():
        for job in ("update_picks", "update_standings", "update_rankings", "update_stats"):
            if _update_games_running():  # never overlap update_games step (n/a here) — keep guard pattern
                pass
            run_job_once(job)
```

(Confirm `gameScored` is the field `update_picks` flips once a finished game is scored — verify in `update_picks`/models before relying on it; adjust the flag name if different.)

- [ ] **Step 4:** Run — verify pass; full suite green.
- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/scheduler.py pickem/pickem_api/tests/test_live_window.py
git commit -m "feat(live): downstream-on-final recompute in the fast tick (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Pool-membership auth helper + /events/standings/ endpoint

**Files:**
- Modify: `pickem/pickem_homepage/live_views.py`
- Modify: `pickem/pickem_homepage/urls.py`
- Modify: `pickem/pickem_homepage/tests.py` (SSE tests live here — module, not package)

**Interfaces:**
- Produces: route `live_standings_events` at `/events/standings/`; sync helper `_resolve_pool_for_member(user, family_slug, pool_slug)` → `(pool_id, season)` or `None`.

- [ ] **Step 1:** Write failing tests in `tests.py`: `/events/standings/` reverses; a non-member (authenticated, not in the pool's family) gets 403; anonymous is redirected (middleware). Use existing test factories/fixtures for a family+pool+membership if present.
- [ ] **Step 2:** Run — verify fail.
- [ ] **Step 3:** Implement. Add a sync helper (called via `sync_to_async`):

```python
def _resolve_pool_for_member(user, family_slug, pool_slug):
    """(pool_id, season) if `user` is a member of the pool, else None. Sync — call
    via sync_to_async from the async view."""
    from pickem_api.models import FamilyMembership, Pool
    pool = (
        Pool.objects.filter(family__slug=family_slug, slug=pool_slug)
        .values("id", "season", "family_id")
        .first()
    )
    if not pool:
        return None
    if not FamilyMembership.objects.filter(
        user=user, family_id=pool["family_id"]
    ).exists():
        return None
    return pool["id"], pool["season"]
```

Async view:

```python
async def live_standings_events(request):
    family_slug = request.GET.get("family", "").strip()
    pool_slug = request.GET.get("pool", "").strip()
    if not family_slug or not pool_slug:
        return HttpResponseBadRequest("family and pool required")
    resolved = await sync_to_async(_resolve_pool_for_member)(
        request.user, family_slug, pool_slug
    )
    if resolved is None:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("not a member of this pool")
    pool_id, season = resolved
    from pickem_api.live_events import standings_channel
    resp = StreamingHttpResponse(
        _event_stream(standings_channel(pool_id, season)),
        content_type="text/event-stream",
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
```

Add the route to `urls.py`:

```python
    path("events/standings/", live_views.live_standings_events, name="live_standings_events"),
```

- [ ] **Step 4:** Run — verify pass (member/non-member/anon). Confirm no sync ORM in the async view (grep `live_views.py` for `.objects` outside the sync helper).
- [ ] **Step 5:** Local smoke (optional, if DB available): boot uvicorn, hit `/events/standings/` as a member/non-member.
- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_homepage/live_views.py pickem/pickem_homepage/urls.py pickem/pickem_homepage/tests.py
git commit -m "feat(live): pool-membership-scoped /events/standings/ SSE endpoint (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Client — live points + complete live game state + fold-in 3b minors

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/family_pool_home.html` (lobby week-points-summary rows + "Your rank" tile area)
- Modify: `pickem/pickem_homepage/templates/pickem/standings.html` (standings rows)
- Modify: `pickem/pickem_homepage/templates/pickem/scores.html` (extend `applyScoreEvent`; fold-in minors)

- [ ] **Step 1: Standings data attributes.** On the lobby `week_points_summary` rows add `data-user-id="{{ row.points.userID }}"` and `data-user-week-points` on the `{{ row.week_points }}` element. On `standings.html` rows add `data-user-id` + `data-user-total-points` on the points cell. (Read the actual templates for the exact variables — `row.points.userID`, `row.week_points`, etc.)

- [ ] **Step 2: Standings EventSource.** On both templates, add an `EventSource('/events/standings/?family=<fslug>&pool=<pslug>&week=<n>')` (expose slugs+week via `data-*`), with a handler that patches `[data-user-id="..."] [data-user-week-points]` / `[data-user-total-points]` textContent from `{user_id, total_points, week_points}`. Reuse the 3b client pattern: feature-check, `sseErrorCount`-based poll fallback (or just silent no-op if no poll exists on that page), close on give-up. Do NOT reorder rows / touch rank.

- [ ] **Step 3: Complete live game state in `scores.html` `applyScoreEvent`.** For non-status-change events, in addition to totals, patch: the status/clock text (add `data-status-title` to the `{{ game.statusTitle }}` header span) from `d.status_title`, and the per-quarter `.quarter-score` cells (add `data-home-period="1..4/OT"` / `data-away-period` markers) from `d.home_periods`/`d.away_periods`.

- [ ] **Step 4: Fold in the deferred 3b minors** (in `scores.html`): (a) guard `filterGames` so it doesn't `startLiveUpdates()` when an SSE stream is healthy (`sseSource` non-null); (b) the rare `notstarted→finished` direct-jump — in the status-change branch, if `d.status !== 'inprogress'` and no other live game exists, still refresh (e.g. temporarily force the gate). Keep it minimal.

- [ ] **Step 5:** `cd pickem && uv run python manage.py check --settings=pickem.test_settings`; full suite green; no `?v=` cache-buster; no Tailwind rebuild.

- [ ] **Step 6:** Manual (local, if feasible): with uvicorn+Redis, publish a `standings:{pool}:{season}` event and confirm a lobby row's points patch; publish a scores event with a new `status_title`/periods and confirm the clock + quarter cells update.

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/family_pool_home.html pickem/pickem_homepage/templates/pickem/standings.html pickem/pickem_homepage/templates/pickem/scores.html
git commit -m "feat(live): live points on lobby/standings + live clock/quarter; fold in 3b minors (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Add the missing SSE Redis-error-branch test (deferred 3b minor)

**Files:**
- Modify: `pickem/pickem_homepage/tests.py`

- [ ] **Step 1:** Add a test that drives `_event_stream` with a fake pubsub whose `subscribe`/`get_message` raises a redis error, asserting the generator ends gracefully (no exception propagates; the `except Exception` branch runs) — mirroring the existing `SseStreamShapeTests` fake-pubsub approach.
- [ ] **Step 2:** Run — verify pass; full suite green.
- [ ] **Step 3: Commit**

```bash
git commit -am "test(live): cover SSE _event_stream graceful end on Redis error (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Deploy verification (dev → prd)

- [ ] **Step 1 (dev, post-merge):** After dev rolls to the new `-latest` (confirm the image tag advanced + `reverse('live_standings_events')` resolves), verify: `/events/standings/` requires membership (403 for a non-member; stream for a member), a `standings:{pool}:{season}` pub/sub round-trip works on the authed Redis, and the scheduler stays healthy (recent `JobRun`, 0 restarts). Confirm dev is genuinely on the new image before proceeding (3a lesson).
- [ ] **Step 2 (prd, post-release):** Repeat against `pickem-prd`; confirm scheduler healthy (no crashloop), `/events/standings/` membership-scoped, live points patch a lobby row and the clock/quarter tick on `/scores/` in a browser during (or via a published test event) a live game.

---

## Self-Review

**Spec coverage:** downstream-on-final (Task 4); standings publish-on-write (Tasks 1+3); pool-scoped SSE auth (Task 5); client live points (Task 6); complete live game state clock/quarter+periods (Tasks 1,2,6); fold-in 3b minors (Tasks 6,7); dev→prd verify (Task 8). ✓

**Placeholder scan:** Task 4's `gameScored` field name and Task 3's `current_week` derivation are flagged to verify against the code during implementation (not left vague — the verification step is explicit). All other steps carry concrete code/commands.

**Type/name consistency:** `publish_event`/`standings_channel`/`standings_event_payload`/`SCORE_TRIGGER_FIELDS` defined in Task 1 and consumed in Tasks 2,3,5; channel `standings:{pool}:{season}` identical in publisher (Task 3) and subscriber (Task 5); route name `live_standings_events` matches the test and client URL; payload keys (`user_id`/`total_points`/`week_points`; `status_title`/`home_periods`/`away_periods`) consistent between payload producers (Task 1) and the client (Task 6).

**Async-safety (3a lesson):** Task 5's membership check + season lookup go through `sync_to_async`; the async view uses `redis.asyncio` via the reused `_event_stream`. Reviewer must confirm no sync ORM leaks into `live_views.py`'s async paths.

**Risk:** pool-scoped auth correctness — Task 5 tests both member (stream) and non-member (403) directions.
