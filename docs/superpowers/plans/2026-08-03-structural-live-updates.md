# Structural Live Updates (#159) Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the lobby & standings leaderboards self-update their *structure*
(new rows, reordering) live, add a scores pre-kickoff fallback, and polish the
lobby Week Points block (rank-after-first-game, avatars, paginate-at-12).

**Architecture:** SSE stays the change-signal. Value patches remain the instant
fast path; on top of them, a **debounced, coalesced leaderboard refetch** re-renders
the leaderboard container from the server (correct order + any new rows). Server
stays the single source of layout truth. See spec
`docs/superpowers/specs/2026-08-03-structural-live-updates-design.md`.

**Tech Stack:** Django 5.2 templates, vanilla JS (no new deps), Redis SSE (unchanged).

## Global Constraints

- Vanilla JS only; no new frontend dependency.
- No `?v=` cache-buster on `{% static %}` URLs.
- No changes to the SSE publish path or async views — client + template + one
  view helper only.
- Rebuild `tailwind.css` via `npm run build:prod` only if real utility classes
  are added; else discard version-only churn.
- §2 (scores kickoff/finish swap) is **already implemented** — do not rebuild it.

---

### Task 1: Week Points rank rule — rank only after a completed game (§5a)

**Files:**
- Modify: `pickem/pickem_homepage/views.py` — `build_week_points_summary` (~L462)
  and its caller in `family_pool_home` (~L1108).
- Test: `pickem/pickem_homepage/tests.py` — `BuildWeekPointsSummaryTests`.

**Interfaces:**
- Produces: `build_week_points_summary(pool, gameseason, current_week,
  week_has_completed_game)` — same return list of dicts, but each `row['rank']`
  is `None` when `week_has_completed_game` is False, else `1..N`.

- [ ] **Step 1: Write failing tests.** Add to `BuildWeekPointsSummaryTests`:

```python
def test_rank_is_none_when_no_completed_game(self):
    rows = build_week_points_summary(self.pool, 2526, "1", week_has_completed_game=False)
    self.assertTrue(len(rows) >= 1)
    self.assertTrue(all(r["rank"] is None for r in rows))

def test_rank_is_numeric_when_a_game_completed(self):
    rows = build_week_points_summary(self.pool, 2526, "1", week_has_completed_game=True)
    self.assertEqual([r["rank"] for r in rows], list(range(1, len(rows) + 1)))
```

(Existing tests call the helper with 3 args — update them to pass
`week_has_completed_game=True` so they keep asserting numeric ranks.)

- [ ] **Step 2: Run tests, verify they fail** (TypeError: unexpected kwarg / rank not None).

Run: `cd pickem && uv run python manage.py test pickem_homepage.tests.BuildWeekPointsSummaryTests --settings=pickem.test_settings -v2`

- [ ] **Step 3: Implement.** Add the parameter and gate the rank:

```python
def build_week_points_summary(pool, gameseason, current_week, week_has_completed_game):
    # ... unchanged filtering + sort ...
    return [
        {
            'rank': (rank if week_has_completed_game else None),
            'points': points,
            'week_points': getattr(points, week_points_field) or 0,
            'user': week_points_users.get(int(points.userID)) if str(points.userID).isdigit() else None,
        }
        for rank, points in enumerate(week_points_rows, 1)
    ]
```

In `family_pool_home`, compute the flag and pass it:

```python
from pickem_api.models import GamesAndScores
week_has_completed_game = GamesAndScores.objects.filter(
    gameseason=gameseason, gameWeek=current_week, statusType="finished"
).exists()
week_points_summary = build_week_points_summary(
    pool, gameseason, current_week, week_has_completed_game
)
```

- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** (`feat(lobby): Week Points rank only after first completed game`).

---

### Task 2: Week Points template — avatars, rank display, paginate at 12 (§5b, §5c)

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/family_pool_home.html`
  (grid ~L198, row ~L200-208).

**Interfaces:**
- Consumes: `row.rank` (None or int), `row.points.userID`, `row.user`.

- [ ] **Step 1: Paginate at 12.** Change `data-week-points-page-size="10"` → `"12"`.

- [ ] **Step 2: Add avatar + rank label to the row.** Replace the rank-only badge
  (`<span …>#{{ row.rank }}</span>`) with an avatar image plus a rank/dash label:

```django
<span class="flex-shrink-0 w-6 text-center text-sm font-black {% if row.rank %}text-primary{% else %}text-text-secondary-light dark:text-text-secondary{% endif %}">{% if row.rank %}{{ row.rank }}{% else %}<span title="Ranking begins after the first completed game">&ndash;</span>{% endif %}</span>
{% with row.points.userID|lookupavatar as avatar %}
<img src="{{ avatar|default:'https://www.gravatar.com/avatar/?d=identicon&s=64' }}" alt="" class="h-8 w-8 flex-shrink-0 rounded-full border border-border-light dark:border-border-subtle object-cover" onerror="this.src='https://www.gravatar.com/avatar/?d=identicon&s=64'">
{% endwith %}
```

- [ ] **Step 3: Add reorder value attribute** to the row for Task 3's refetch
  trigger: on the `[data-week-points-row]` element add
  `data-week-points-value="{{ row.week_points }}"`.

- [ ] **Step 4: Verify render.** With the dev server running:
  `curl -s http://localhost:8000/... | grep -c 'data-week-points-value'` (sanity),
  and visually confirm avatars + `–` before any game, numeric rank after.

- [ ] **Step 5: Commit** (`feat(lobby): avatars + rank label in Week Points block`).

---

### Task 3: Lobby leaderboard structural refetch — new rows + reorder (§3)

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/family_pool_home.html` — the
  live-standings SSE `<script>` (~L662-719) and the pagination script (~L725) to
  expose a re-init hook.

**Interfaces:**
- Consumes: pagination script must expose `window.__weekPointsPaginate =
  function () { … }` (or similar) so the refetch can re-init after swapping.

- [ ] **Step 1: Expose a pagination re-init hook.** Wrap the pagination IIFE body
  in a named `function initWeekPointsPager()` and assign it to
  `window.__weekPointsPaginate`; call it once on load. (Idempotent: it re-reads
  rows + page size from the DOM each call.)

- [ ] **Step 2: Add a debounced leaderboard refetch** to the SSE script:

```javascript
var refetchTimer = null;
function scheduleLeaderboardRefetch() {
    if (refetchTimer) { clearTimeout(refetchTimer); }
    refetchTimer = setTimeout(function () {
        refetchTimer = null;
        fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Cache-Control': 'no-store' },
            cache: 'no-store', credentials: 'same-origin'
        }).then(function (r) { return r.ok ? r.text() : null; })
          .then(function (html) {
              if (!html) { return; }
              var doc = new DOMParser().parseFromString(html, 'text/html');
              var fresh = doc.querySelector('[data-week-points-grid]');
              var current = document.querySelector('[data-week-points-grid]');
              if (fresh && current) {
                  current.innerHTML = fresh.innerHTML;
                  if (typeof window.__weekPointsPaginate === 'function') {
                      window.__weekPointsPaginate();
                  }
              }
          }).catch(function () {});
    }, 1500);
}
```

- [ ] **Step 3: Trigger it from `applyStandingsEvent`.** After the existing
  in-place value patch, add: if the row is missing (`!row`) **or** the incoming
  `week_points` differs from the row's `data-week-points-value`, call
  `scheduleLeaderboardRefetch()`. (Value patch stays for instant feedback; the
  debounced refetch settles order + brings in new rows.)

- [ ] **Step 4: Verify** with a scripted dev change: bump a member's week points
  so ranks reorder → row moves without reload; add a member → row appears.

- [ ] **Step 5: Commit** (`feat(lobby): live reorder + new-row refetch for Week Points`).

---

### Task 4: Standings page structural refetch — reorder (§3)

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/standings.html` — row (~L137)
  and the SSE `<script>` (~L354-402).

- [ ] **Step 1: Add a reorder value attribute** to each `.standings-row`:
  `data-total-points="{{ player.totalPoints }}"` (use the field the leaderboard
  is ordered by — confirm the exact ordering field in the view before wiring).

- [ ] **Step 2: Add the same debounced refetch** as Task 3, swapping the
  leaderboard container (the `.space-y-1.5` list wrapper — give it a stable
  `data-standings-list` hook). No pagination on this page, so no re-init hook.

- [ ] **Step 3: Trigger from `applyStandingsEvent`** on missing row or changed value.

- [ ] **Step 4: Verify** reorder on `/standings/` via a scripted dev change.

- [ ] **Step 5: Commit** (`feat(standings): live row reorder refetch`).

---

### Task 5: Scores pre-kickoff heartbeat fallback (§4)

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/scores.html` — near the SSE
  wiring (~L1708).

**Rationale:** §2 works when the SSE kickoff event arrives. If SSE is down (fell
back to the 30s poll, which is gated on `hasLiveGames()`), a kickoff won't swap.
This adds a cheap safety net.

- [ ] **Step 1: Add a heartbeat** that, every 60s, if any card is `notstarted`
  with a kickoff time at/before now, calls `updateLiveScores()` (force the gate as
  `applyScoreEvent` does). Self-limits: stops when no such card remains.
  (Reuse the existing kickoff-time data attribute if present; otherwise read the
  card's start time — confirm which attribute holds it before wiring.)

- [ ] **Step 2: Verify** it no-ops when nothing is imminent and fires once a
  notstarted card's kickoff passes.

- [ ] **Step 3: Commit** (`feat(scores): pre-kickoff heartbeat fallback`).

---

### Task 6: Contract-lock tests + full suite (§6)

**Files:**
- Test: `pickem/pickem_homepage/tests.py`.

- [ ] **Step 1: Add render-contract tests** asserting the lobby renders
  `data-week-points-value` on rows and `data-week-points-grid` on the container,
  and standings renders `data-user-id` + `data-total-points` + `data-standings-list`.
  (A GET as an authenticated pool member; reuse existing test fixtures/patterns.)

- [ ] **Step 2: Run the full suite** (mirrors CI):

```bash
cd pickem
uv run python manage.py check --settings=pickem.test_settings
uv run python manage.py makemigrations --check --dry-run --settings=pickem.test_settings
uv run python manage.py test --settings=pickem.test_settings -v2
```

- [ ] **Step 3: Commit** (`test: lock live-update DOM contract`).

---

## Ship

After all tasks green: run `pr-review-toolkit:review-pr`, fix Critical/Important,
then ship-it (PR → checks → CodeRabbit → merge → release → prd verify). One
release covering: Message Board reorder + Week Points polish + live structural
updates.

## Self-Review

- **Spec coverage:** §2 (already done — Task 5 covers only the fallback), §3
  (Tasks 3, 4), §5a (Task 1), §5b/c (Task 2), §6 (Task 6). ✓
- **Type consistency:** helper signature `build_week_points_summary(pool,
  gameseason, current_week, week_has_completed_game)` used identically in view,
  helper, and tests. ✓
- **Open confirmations for the implementer:** exact standings ordering field
  (Task 4 Step 1), the scores card kickoff-time attribute (Task 5 Step 1). Both
  flagged inline to verify before wiring.
