# Live Updates — Phase 3b: Live Scores via SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live game scores on `/scores/` via SSE — fast live-window `update_games` cadence, publish-on-write to Redis, an async `/events/scores/` endpoint, and a client `EventSource` replacing the 30s poll (poll kept as fallback). Scores only; points/ranks/lobby are 3c.

**Architecture:** The scheduler pod refreshes scores every ~12s while games are live and `PUBLISH`es compact change events to Redis `scores:{season}:{week}`. Web pods (uvicorn/ASGI, from 3a) serve an async SSE view that `redis.asyncio`-subscribes per connection and streams events; the browser patches game cards by `data-game-id`.

**Tech Stack:** Django 5.2 async views, redis-py (sync publish) + `redis.asyncio` (async subscribe), uvicorn/ASGI, APScheduler, vanilla JS `EventSource`.

## Global Constraints

- Python `>=3.12`, Django `5.2.16`; deps pinned in `pyproject.toml`/`uv.lock` via `uv add`. `redis` is already present (django-redis dep) — includes `redis.asyncio`.
- Tests: `--settings=pickem.test_settings` (SQLite), unittest discovery — `TestCase`/`SimpleTestCase` classes only, never bare functions. Async views: use `django.test.TestCase` with `async def` tests and `await`, or `SimpleTestCase` + `asyncio`.
- **No sync ORM in an async context** (3a lesson): the async SSE view must use `redis.asyncio` and, for any DB read, `asgiref.sync.sync_to_async` or async ORM (`aget`). Never call sync ORM directly in the async view.
- Redis access uses the existing `REDIS_URL` env (already carries auth in dev/prd). Publish/subscribe failures must be best-effort/logged, never crash the pipeline or the page (mirror the cache `IGNORE_EXCEPTIONS` posture).
- Channel name is exactly `scores:{season}:{week}` where season is the int from `get_season()` and week is the numeric week string used elsewhere.
- Served by uvicorn (3a). The scheduler pod publishes; web pods subscribe. Both have `REDIS_URL`.
- GitOps: dev tracks main, prd tracks releases; enable/verify dev before prd. No values changes needed for 3b (routes + code only).

---

### Task 1: Redis score-event publisher + channel helper

A small, testable module for channel naming, the event payload, and publishing.

**Files:**
- Create: `pickem/pickem_api/live_events.py`
- Test: `pickem/pickem_api/tests/test_live_events.py`

**Interfaces:**
- Produces:
  - `scores_channel(season, week) -> str` → `f"scores:{season}:{week}"`
  - `score_event_payload(game) -> dict` → the compact live fields of a `GamesAndScores`
  - `LIVE_SCORE_FIELDS: tuple[str, ...]` → the field names whose change triggers a publish
  - `publish_score_event(season, week, payload) -> None` → best-effort redis-py publish (no-op + log on failure or when `REDIS_URL` unset)

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_api/tests/test_live_events.py`:

```python
from unittest import mock

from django.test import SimpleTestCase

from pickem_api import live_events


class ChannelAndPayloadTests(SimpleTestCase):
    def test_channel_name(self):
        self.assertEqual(live_events.scores_channel(2627, "3"), "scores:2627:3")

    def test_payload_has_compact_live_fields(self):
        game = mock.Mock(
            id=401, homeTeamScore=14, awayTeamScore=7, statusType="inprogress",
            statusTitle="Q2 5:00", gameWinner="",
        )
        payload = live_events.score_event_payload(game)
        self.assertEqual(payload["game_id"], 401)
        self.assertEqual(payload["home_score"], 14)
        self.assertEqual(payload["away_score"], 7)
        self.assertEqual(payload["status"], "inprogress")
        self.assertEqual(payload["winner"], "")


class PublishTests(SimpleTestCase):
    def test_publish_no_redis_url_is_noop(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            # Must not raise even with no REDIS_URL configured.
            live_events.publish_score_event(2627, "3", {"game_id": 1})

    def test_publish_swallows_redis_errors(self):
        boom = mock.Mock(side_effect=RuntimeError("down"))
        with mock.patch.dict("os.environ", {"REDIS_URL": "redis://x:6379/1"}), \
                mock.patch.object(live_events, "_redis_client", return_value=mock.Mock(publish=boom)):
            # Best-effort: a Redis error must be swallowed (logged), not raised.
            live_events.publish_score_event(2627, "3", {"game_id": 1})
```

- [ ] **Step 2: Run it — verify it fails**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_live_events --settings=pickem.test_settings -v 2
```

Expected: FAIL (`ModuleNotFoundError: No module named 'pickem_api.live_events'`).

- [ ] **Step 3: Implement the module**

Create `pickem/pickem_api/live_events.py`:

```python
"""Publish compact live game-score events to Redis for the SSE endpoint.

The scheduler pod calls publish_score_event() from update_games after a game's
score/status changes; web pods subscribe to the channel in the async SSE view
(see pickem_homepage/live_views.py). Redis is the same instance used for the
cache (REDIS_URL). All failures are best-effort/logged — a Redis outage must
never break the pipeline.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# Changing any of these on a GamesAndScores row triggers a publish.
LIVE_SCORE_FIELDS = (
    "homeTeamScore",
    "awayTeamScore",
    "statusType",
    "statusTitle",
    "gameWinner",
)


def scores_channel(season, week):
    """Redis pub/sub channel for a season+week's live scores."""
    return f"scores:{season}:{week}"


def score_event_payload(game):
    """Compact JSON-serializable dict of a game's live fields for the client."""
    return {
        "game_id": game.id,
        "home_score": game.homeTeamScore,
        "away_score": game.awayTeamScore,
        "status": game.statusType,
        "status_title": game.statusTitle,
        "winner": game.gameWinner,
    }


def _redis_client():
    """A sync redis-py client from REDIS_URL, or None if unset."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    import redis

    return redis.from_url(url)


def publish_score_event(season, week, payload):
    """Best-effort publish of one score change. Never raises."""
    try:
        client = _redis_client()
        if client is None:
            return
        client.publish(scores_channel(season, week), json.dumps(payload))
    except Exception:
        logger.warning("live score publish failed", exc_info=True)
```

- [ ] **Step 4: Run the tests — verify pass**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_live_events --settings=pickem.test_settings -v 2
```

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/live_events.py pickem/pickem_api/tests/test_live_events.py
git commit -m "feat(live): Redis score-event publisher + channel helper

Best-effort publish of compact live score events to scores:{season}:{week};
no-op when REDIS_URL is unset, swallows Redis errors. (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Publish-on-write in update_games

Detect per-game score/status changes and publish them.

**Files:**
- Modify: `pickem/pickem_api/management/commands/update_games.py` (around the `update_or_create` at line ~332)
- Test: `pickem/pickem_api/tests/test_update_games_publish.py`

**Interfaces:**
- Consumes: `live_events.LIVE_SCORE_FIELDS`, `score_event_payload`, `publish_score_event`, `scores_channel` (Task 1).

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_api/tests/test_update_games_publish.py`:

```python
from unittest import mock

from django.test import TestCase

from pickem_api.management.commands import update_games as ug


class PublishChangedGameTests(TestCase):
    def _game(self, **kw):
        base = dict(
            id=401, gameseason=2627, gameWeek="3",
            homeTeamScore=0, awayTeamScore=0, statusType="notstarted",
            statusTitle="", gameWinner="",
        )
        base.update(kw)
        return mock.Mock(**base)

    def test_publishes_when_live_field_changed(self):
        before = {"homeTeamScore": 0, "awayTeamScore": 0, "statusType": "notstarted",
                  "statusTitle": "", "gameWinner": ""}
        after = self._game(homeTeamScore=7, statusType="inprogress")
        with mock.patch.object(ug, "publish_score_event") as pub:
            ug.maybe_publish_game_change(before, after)
            self.assertEqual(pub.call_count, 1)
            args = pub.call_args.args
            self.assertEqual(args[0], 2627)      # season
            self.assertEqual(args[1], "3")       # week
            self.assertEqual(args[2]["home_score"], 7)

    def test_no_publish_when_unchanged(self):
        before = {"homeTeamScore": 7, "awayTeamScore": 0, "statusType": "inprogress",
                  "statusTitle": "Q1", "gameWinner": ""}
        after = self._game(homeTeamScore=7, awayTeamScore=0, statusType="inprogress",
                           statusTitle="Q1", gameWinner="")
        with mock.patch.object(ug, "publish_score_event") as pub:
            ug.maybe_publish_game_change(before, after)
            pub.assert_not_called()

    def test_publishes_new_game(self):
        after = self._game(statusType="notstarted")
        with mock.patch.object(ug, "publish_score_event") as pub:
            ug.maybe_publish_game_change(None, after)  # None = newly created
            self.assertEqual(pub.call_count, 1)
```

- [ ] **Step 2: Run it — verify it fails**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_update_games_publish --settings=pickem.test_settings -v 2
```

Expected: FAIL (`AttributeError: ... has no attribute 'maybe_publish_game_change'`).

- [ ] **Step 3: Implement**

In `pickem/pickem_api/management/commands/update_games.py`, add near the top-level imports:

```python
from pickem_api.live_events import (
    LIVE_SCORE_FIELDS,
    publish_score_event,
    score_event_payload,
)
```

Add a module-level helper (above the `Command` class):

```python
def maybe_publish_game_change(before, after):
    """Publish a live score event if any LIVE_SCORE_FIELD changed (or new game).

    ``before`` is a dict of the row's LIVE_SCORE_FIELDS prior to the upsert, or
    None if the row was just created. ``after`` is the saved GamesAndScores.
    """
    if before is not None:
        changed = any(
            before.get(f) != getattr(after, f) for f in LIVE_SCORE_FIELDS
        )
        if not changed:
            return
    publish_score_event(
        after.gameseason, str(after.gameWeek), score_event_payload(after)
    )
```

Then wrap the `update_or_create` call site (around line 332). Replace:

```python
            game, _created = GamesAndScores.objects.update_or_create(
                id=game_id, defaults=defaults
            )
```

with:

```python
            existing = (
                GamesAndScores.objects.filter(id=game_id)
                .values(*LIVE_SCORE_FIELDS)
                .first()
            )
            game, _created = GamesAndScores.objects.update_or_create(
                id=game_id, defaults=defaults
            )
            # Best-effort live push (scores-only SSE); never blocks the upsert.
            maybe_publish_game_change(None if _created else existing, game)
```

- [ ] **Step 4: Run the tests — verify pass**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_update_games_publish --settings=pickem.test_settings -v 2
```

Expected: PASS (3 tests).

- [ ] **Step 5: Full suite green**

```bash
cd pickem && uv run python manage.py test --settings=pickem.test_settings
```

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_api/management/commands/update_games.py pickem/pickem_api/tests/test_update_games_publish.py
git commit -m "feat(live): publish score changes from update_games (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Fast live-window cadence for update_games

Refresh scores every ~12s while any game is in progress; otherwise a cheap no-op.

**Files:**
- Modify: `pickem/pickem_api/scheduler.py`
- Test: `pickem/pickem_api/tests/test_live_window.py`

**Interfaces:**
- Produces: `scheduler.live_window_active() -> bool` (any current-week game `inprogress`); `scheduler.run_live_scores_tick()` (runs `update_games` only when a live window is active).

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_api/tests/test_live_window.py`:

```python
from unittest import mock

from django.test import TestCase

from pickem_api import scheduler
from pickem_api.models import GamesAndScores


class LiveWindowTests(TestCase):
    def test_inactive_when_no_inprogress_games(self):
        self.assertFalse(scheduler.live_window_active())

    def test_active_with_an_inprogress_game(self):
        GamesAndScores.objects.create(
            id=1, gameseason=2627, gameWeek="3", statusType="inprogress",
        )
        self.assertTrue(scheduler.live_window_active())

    def test_tick_runs_update_games_only_when_active(self):
        with mock.patch.object(scheduler, "live_window_active", return_value=False), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            run.assert_not_called()
        with mock.patch.object(scheduler, "live_window_active", return_value=True), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            run.assert_called_once_with("update_games")
```

- [ ] **Step 2: Run it — verify it fails**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_live_window --settings=pickem.test_settings -v 2
```

Expected: FAIL (`AttributeError: module 'pickem_api.scheduler' has no attribute 'live_window_active'`).

- [ ] **Step 3: Implement**

In `pickem/pickem_api/scheduler.py`, add:

```python
# How often to refresh scores while games are live (seconds). ESPN's scoreboard
# refreshes ~15-20s, so faster just re-fetches unchanged data.
LIVE_SCORES_INTERVAL_SECONDS = 12


def live_window_active():
    """True if any game in the current season/week is in progress."""
    from pickem.utils import get_season
    from pickem_api.models import GamesAndScores

    return GamesAndScores.objects.filter(
        gameseason=get_season(), statusType="inprogress"
    ).exists()


def run_live_scores_tick():
    """Fast score refresh: run update_games only during a live window.

    Off-window this is a single cheap EXISTS query and returns. On-window it
    runs update_games (which publishes changed games to Redis)."""
    if not live_window_active():
        return
    run_job_once("update_games")
```

Then register the fast job in `start()` — after the `pipeline_tick` job is added, add:

```python
    scheduler.add_job(
        run_live_scores_tick,
        trigger=IntervalTrigger(seconds=LIVE_SCORES_INTERVAL_SECONDS),
        id='live_scores_tick',
        name='Live scores fast refresh',
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
```

And extend the stale-job cleanup exclusion so the new job isn't deleted — change the `DjangoJob.objects.exclude(id__in=(...))` line to include `'live_scores_tick'`:

```python
    DjangoJob.objects.exclude(
        id__in=('pipeline_tick', 'prune_superadmin_logs', 'live_scores_tick')
    ).delete()
```

- [ ] **Step 4: Run the tests — verify pass**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_live_window --settings=pickem.test_settings -v 2
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/scheduler.py pickem/pickem_api/tests/test_live_window.py
git commit -m "feat(live): fast ~12s update_games cadence during live windows (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Async SSE endpoint /events/scores/

Stream published score events to authenticated browsers.

**Files:**
- Create: `pickem/pickem_homepage/live_views.py`
- Modify: `pickem/pickem_homepage/urls.py` (add the route)
- Test: `pickem/pickem_homepage/tests/test_sse_scores.py` (create `tests/` package if absent — mirror existing test layout)

**Interfaces:**
- Consumes: `live_events.scores_channel` (Task 1). Produces route name `live_scores_events` at `/events/scores/`.

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_homepage/tests/test_sse_scores.py`:

```python
from django.test import TestCase
from django.urls import reverse


class SseScoresAuthTests(TestCase):
    def test_requires_login(self):
        # RequireLoginForInternalPagesMiddleware should block anonymous access.
        resp = self.client.get("/events/scores/?week=3")
        self.assertIn(resp.status_code, (302, 401))

    def test_url_reverses(self):
        self.assertEqual(reverse("live_scores_events"), "/events/scores/")
```

(If `pickem_homepage/tests/` doesn't exist, create it as a package with `__init__.py`; if `pickem_homepage/tests.py` exists as a module, add this class there instead and skip the package.)

- [ ] **Step 2: Run it — verify it fails**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.test_sse_scores --settings=pickem.test_settings -v 2
```

Expected: FAIL (`NoReverseMatch` / 404).

- [ ] **Step 3: Implement the async view**

Create `pickem/pickem_homepage/live_views.py`:

```python
"""Server-Sent Events endpoint for live game scores (Phase 3b).

Served by uvicorn (ASGI). Each connection subscribes to the season/week's Redis
channel via redis.asyncio and streams change events published by update_games.
Auth is enforced by RequireLoginForInternalPagesMiddleware (the path is not in
its public allowlist). Uses only async-safe I/O — no sync ORM in this view.
"""
import asyncio
import os

from asgiref.sync import sync_to_async
from django.http import HttpResponseBadRequest, StreamingHttpResponse

from pickem_api.live_events import scores_channel

KEEPALIVE_SECONDS = 20


async def _event_stream(channel):
    import redis.asyncio as aioredis

    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        # No broker: end the stream immediately; the client falls back to poll.
        return
    client = aioredis.from_url(url)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)
    try:
        # Prime the connection so proxies flush headers immediately.
        yield ": connected\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=KEEPALIVE_SECONDS,
                )
            except asyncio.TimeoutError:
                yield ": ping\n\n"  # keepalive comment
                continue
            if msg and msg.get("type") == "message":
                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield f"data: {data}\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await client.aclose()


async def live_scores_events(request):
    """SSE stream of live score changes for ?week=<n> in the current season."""
    week = request.GET.get("week", "").strip()
    if not week.isdigit():
        return HttpResponseBadRequest("week required")

    from pickem.utils import get_season

    season = await sync_to_async(get_season)()
    channel = scores_channel(season, week)

    resp = StreamingHttpResponse(
        _event_stream(channel), content_type="text/event-stream"
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"  # defeat proxy/Cloudflare buffering
    return resp
```

In `pickem/pickem_homepage/urls.py`, import the module and add the route to `urlpatterns`:

```python
from . import live_views
```
```python
    path("events/scores/", live_views.live_scores_events, name="live_scores_events"),
```

- [ ] **Step 4: Run the auth/reverse tests — verify pass**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.test_sse_scores --settings=pickem.test_settings -v 2
```

Expected: PASS (2 tests).

- [ ] **Step 5: Add an async streaming test**

Append to `pickem/pickem_homepage/tests/test_sse_scores.py`:

```python
from unittest import mock


class SseStreamShapeTests(TestCase):
    async def test_stream_emits_published_event(self):
        # Drive the async generator directly with a fake pubsub so no real
        # Redis is needed: first a message, then stop.
        from pickem_homepage import live_views

        class FakePubSub:
            def __init__(self):
                self._msgs = [{"type": "message", "data": b'{"game_id": 1}'}]

            async def subscribe(self, ch):
                return None

            async def get_message(self, ignore_subscribe_messages=True):
                if self._msgs:
                    return self._msgs.pop(0)
                raise asyncio_stop()

            async def unsubscribe(self, ch):
                return None

            async def aclose(self):
                return None

        class FakeClient:
            def pubsub(self):
                return FakePubSub()

            async def aclose(self):
                return None

        import asyncio as _asyncio

        def asyncio_stop():
            return _asyncio.CancelledError()

        with mock.patch.dict("os.environ", {"REDIS_URL": "redis://x:6379/1"}), \
                mock.patch("redis.asyncio.from_url", return_value=FakeClient()):
            gen = live_views._event_stream("scores:2627:3")
            first = await gen.__anext__()
            self.assertIn("connected", first)
            second = await gen.__anext__()
            self.assertIn('data: {"game_id": 1}', second)
            await gen.aclose()
```

Run:

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.test_sse_scores --settings=pickem.test_settings -v 2
```

Expected: PASS (3 tests). If the async test needs it, ensure the class is `TestCase` (Django supports `async def test_*`).

- [ ] **Step 6: Verify sync middleware doesn't buffer the stream**

Boot uvicorn locally, log in via a quick shell-created session (or use `DEBUG=true` and an authed browser), and confirm `curl -N` on `/events/scores/?week=3` receives `: connected` immediately (headers not buffered). If a middleware buffers it, add the `/events/` prefix to an exemption. Document the result in the report.

```bash
cd pickem && DEBUG=true uv run uvicorn pickem.asgi:application --port 8123 &
# (authenticated curl -N http://127.0.0.1:8123/events/scores/?week=3 shows ": connected" then ": ping" ~20s later)
```

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_homepage/live_views.py pickem/pickem_homepage/urls.py pickem/pickem_homepage/tests/test_sse_scores.py
git commit -m "feat(live): async SSE endpoint /events/scores/ (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Client EventSource on the scores page

Replace the 30s full-HTML poll with SSE; keep the poll as a fallback.

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/scores.html` (the live-update JS block around lines 1346–1660)

**Interfaces:**
- Consumes: `/events/scores/?week=<n>` (Task 4). The page must expose the current week to JS — add `data-live-week="{{ game_week }}"` to a stable element (e.g. the scores container) if not already present.

- [ ] **Step 1: Expose the week to JS**

In `scores.html`, ensure the scores container (or `<body>`/a wrapper) carries the current week, e.g. add `data-live-week="{{ game_week }}"` to the element that already has `data-scores-card`'s parent container. (Confirm `game_week` is in the template context from `render_scores_page`; it is.)

- [ ] **Step 2: Add the EventSource client, guarded, with poll fallback**

In the `scores.html` script block, alongside the existing `startLiveUpdates()`/`updateInterval` poll logic, add:

```javascript
    function applyScoreEvent(ev) {
        let d;
        try { d = JSON.parse(ev.data); } catch (e) { return; }
        const card = document.querySelector(`.game-score-card[data-game-id="${d.game_id}"]`);
        if (!card) return;
        const home = card.querySelector('[data-home-score]');
        const away = card.querySelector('[data-away-score]');
        if (home) home.textContent = d.home_score;
        if (away) away.textContent = d.away_score;
        card.setAttribute('data-game-status', d.status);
        // reuse existing update animation + completion handling
        card.style.animation = 'none'; card.offsetHeight; card.style.animation = 'fadeIn 0.5s ease-in';
        if (window.scoresLivePulse) window.scoresLivePulse();
    }

    let sseSource = null;
    function startSse() {
        if (!window.EventSource) return false;
        const wk = (document.querySelector('[data-live-week]') || {}).dataset
            ? document.querySelector('[data-live-week]').dataset.liveWeek : null;
        if (!wk) return false;
        try {
            sseSource = new EventSource(`/events/scores/?week=${encodeURIComponent(wk)}`);
        } catch (e) { return false; }
        sseSource.onmessage = applyScoreEvent;
        sseSource.onerror = function () {
            // EventSource auto-reconnects; if it never opens, fall back to poll.
            if (sseSource.readyState === EventSource.CLOSED) {
                sseSource = null;
                startLiveUpdates(); // existing 30s poll
            }
        };
        return true;
    }
```

Then change the page-load trigger so SSE is preferred and the poll is the fallback. Replace the existing initial trigger:

```javascript
    if (hasLiveGames()) {
        setTimeout(startLiveUpdates, 2000);
    }
```

with:

```javascript
    // Prefer SSE for live updates; the 30s poll remains the fallback.
    if (!startSse()) {
        if (hasLiveGames()) {
            setTimeout(startLiveUpdates, 2000);
        }
    }
```

The game cards must expose `data-game-id`, `data-home-score`, `data-away-score`. Add these attributes to the card template markup if missing (the card already has `data-game-status`); wire `data-game-id="{{ game.id }}"` on `.game-score-card` and `data-home-score`/`data-away-score` on the score spans.

- [ ] **Step 3: Rebuild Tailwind only if classes changed**

No new utility classes are expected (behavioral JS + data attributes only). Do NOT rebuild/commit `tailwind.css` unless you added classes.

- [ ] **Step 4: Manual verification (local, browser)**

With uvicorn running and Redis up locally, open `/scores/` on a week with an `inprogress` game, publish a test event (`python manage.py shell` → `from pickem_api.live_events import publish_score_event; publish_score_event(<season>, "<week>", {...})`), and confirm the card updates within ~2s without reload. Kill Redis → confirm the page still works and the poll fallback engages.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/scores.html
git commit -m "feat(live): EventSource live scores on /scores/ with poll fallback (#138)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Deploy verification (dev → prd)

No values changes; routes+code ship with the image. Gated rollout verification.

- [ ] **Step 1: (dev, post-merge)** After ArgoCD syncs dev, confirm the endpoint and stream:

```bash
kubectl config use-context kubernetes-admin@kubernetes
# endpoint requires auth (401/redirect for anon):
kubectl exec -n pickem-dev deploy/family-pickem-dev -c family-pickem -- \
  sh -c 'curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/events/scores/?week=1'
# scheduler still healthy + live job registered:
kubectl exec -n pickem-dev deploy/family-pickem-dev-scheduler -- \
  python /code/manage.py shell -c "from django_apscheduler.models import DjangoJob; print(sorted(j.id for j in DjangoJob.objects.all()))"
```

Expected: the curl returns 302/401 (auth), and the DjangoJob list includes `live_scores_tick`. Then, in a browser on dev, open `/scores/` and confirm (during a live game, or by publishing a test event) a card updates live.

- [ ] **Step 2: (prd, post-release)** Repeat against `pickem-prd`. Confirm `live_scores_tick` is registered on the prd scheduler, `/events/scores/` requires auth, and a real/simulated live game updates the page in <2s. Watch the prd scheduler pod stays healthy (no restarts) and web pods hold SSE connections without error spikes (Sentry).

---

## Self-Review

**Spec coverage:**
- Fast live-window cadence → Task 3. ✓
- Publish-on-write → Tasks 1 (publisher) + 2 (hook in update_games). ✓
- Async SSE endpoint (auth, redis.asyncio, keepalive, no-buffering) → Task 4. ✓
- Client EventSource + poll fallback → Task 5. ✓
- Async-safety (no sync ORM in async view; `get_season` via `sync_to_async`) → Task 4 view + Global Constraints. ✓
- Best-effort Redis (no crash on outage) → Task 1 publisher + Task 4 empty-URL guard. ✓
- Deploy verify dev→prd → Task 6. ✓

**Placeholder scan:** none — all steps carry concrete code/commands.

**Type/name consistency:** `scores_channel`/`score_event_payload`/`publish_score_event`/`LIVE_SCORE_FIELDS` defined in Task 1 and consumed with matching signatures in Tasks 2 & 4; channel `scores:{season}:{week}` identical in publisher (Task 1), the fast tick's update_games (Task 3 → Task 2 publish), and the SSE subscribe (Task 4); route name `live_scores_events` matches the test and the client URL `/events/scores/`.

**Ordering:** Task 1 (publisher) precedes its consumers (2, 4); Task 3 (cadence) depends on Task 2's publishing update_games; Task 5 (client) depends on Task 4 (endpoint); Task 6 verifies after merge. All code lands before the deploy task.

**Risk carried from 3a:** the async view strictly avoids sync ORM (only `get_season` via `sync_to_async`); reviewers should confirm no other sync ORM/`.objects` call sneaks into `live_views.py`.
