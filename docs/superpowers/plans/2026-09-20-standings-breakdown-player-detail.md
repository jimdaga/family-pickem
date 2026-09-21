# Standings Breakdown Player Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the standings "Detailed Breakdown" cards with player identity (favorite team, tagline), a trophy-case badge row (perfect weeks, weeks won, seasons won), a stat ribbon (accuracy, correct, best week), and an inline-SVG sparkline of weekly correct-pick percentage.

**Architecture:** A new pure helper module (`pickem_homepage/sparkline.py`) maps a weekly-accuracy series to an SVG polyline. `build_pool_standings_stats()` is restructured to emit that series from the per-week group-by it already runs, so the sparkline adds zero queries. A new batched `build_user_profile_map()` supplies tagline + `Teams` row in two queries, avoiding the per-row `lookuplogo` N+1. `render_standings_page` wires all of it onto the existing `player_points` entries, tenant-branch only.

**Tech Stack:** Django 5.2, Python 3.12, Tailwind CSS, inline SVG (no charting library, no JS).

## Global Constraints

- Run tests with `--settings=pickem.test_settings` to match CI.
- Django ORM only — no raw SQL.
- **Never** append `?v=...` to a `{% static %}` URL (corrupts S3 signed URLs; see CLAUDE.md).
- Personal data (tagline, favorite team, real names) must never be attached on the non-tenant branch of `render_standings_page`.
- The sparkline must not depend on GSAP or any CDN asset.
- Sparkline y-axis is fixed 0–100, never auto-scaled to the series range.
- New Tailwind utility classes require `npm run build:prod` before commit (the compiled `tailwind.css` is committed and served).

---

### Task 1: Pure sparkline geometry helper

**Files:**
- Create: `pickem/pickem_homepage/sparkline.py`
- Test: `pickem/pickem_homepage/tests.py` (append `SparklineGeometryTests`)

**Interfaces:**
- Consumes: nothing.
- Produces: `sparkline_points(series, width=120, height=28, pad=2) -> str` where `series` is a list of `{'week': int, 'accuracy': int, ...}` dicts. Returns a space-separated `"x,y x,y"` polyline points string, or `""` for an empty series. Also produces `SPARKLINE_WIDTH = 120`, `SPARKLINE_HEIGHT = 28`.

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_homepage/tests.py`:

```python
class SparklineGeometryTests(TestCase):
    """The sparkline's y-axis is deliberately pinned to 0-100 rather than
    auto-scaled to each player's own range: auto-scaling would make a member
    who ranged 61-64% look as volatile as one who ranged 20-90%, and would
    make two cards on the same page mutually incomparable."""

    def _series(self, *accuracies):
        return [
            {'week': i, 'accuracy': a, 'correct': 0, 'total': 0}
            for i, a in enumerate(accuracies, 1)
        ]

    def test_empty_series_has_no_points(self):
        self.assertEqual(sparkline_points([]), "")

    def test_single_point_is_centered_horizontally(self):
        points = sparkline_points(self._series(50), width=100, height=20, pad=2)
        self.assertEqual(len(points.split()), 1)
        x, y = points.split(',')
        self.assertAlmostEqual(float(x), 50.0, places=1)

    def test_zero_and_hundred_map_to_the_full_vertical_range(self):
        points = sparkline_points(self._series(0, 100), width=100, height=20, pad=2)
        first, last = points.split()
        # y is inverted: 0% sits at the bottom, 100% at the top.
        self.assertAlmostEqual(float(first.split(',')[1]), 18.0, places=1)
        self.assertAlmostEqual(float(last.split(',')[1]), 2.0, places=1)

    def test_flat_series_is_a_horizontal_line(self):
        points = sparkline_points(self._series(60, 60, 60), width=100, height=20, pad=2)
        ys = {p.split(',')[1] for p in points.split()}
        self.assertEqual(len(ys), 1)

    def test_axis_is_fixed_not_autoscaled(self):
        # A narrow band must NOT be stretched to fill the box. If it were
        # autoscaled, 61 and 64 would land on the extreme top and bottom.
        points = sparkline_points(self._series(61, 64), width=100, height=20, pad=2)
        ys = [float(p.split(',')[1]) for p in points.split()]
        self.assertNotAlmostEqual(ys[0], 18.0, places=1)
        self.assertNotAlmostEqual(ys[1], 2.0, places=1)

    def test_points_are_evenly_spaced_across_the_width(self):
        points = sparkline_points(self._series(10, 20, 30), width=100, height=20, pad=2)
        xs = [float(p.split(',')[0]) for p in points.split()]
        self.assertAlmostEqual(xs[0], 2.0, places=1)
        self.assertAlmostEqual(xs[-1], 98.0, places=1)
        self.assertAlmostEqual(xs[1], 50.0, places=1)
```

Add the import near the other `pickem_homepage` imports at the top of `tests.py`:

```python
from pickem_homepage.sparkline import sparkline_points
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.SparklineGeometryTests --settings=pickem.test_settings
```

Expected: `ModuleNotFoundError: No module named 'pickem_homepage.sparkline'`

- [ ] **Step 3: Write the implementation**

Create `pickem/pickem_homepage/sparkline.py`:

```python
"""Geometry for the standings breakdown sparkline.

Pure functions only — no models, no request, no ORM — so the shape of the
line can be tested directly. The sparkline is rendered as inline SVG with no
JavaScript and no charting library: the standings page pulls GSAP from a CDN
for its entrance animation, and a reader must never lose data because that
CDN failed or because they run with reduced motion on.
"""

# Matches the ribbon's slot in standings.html. Kept here so the template and
# the geometry can never disagree about the viewBox.
SPARKLINE_WIDTH = 120
SPARKLINE_HEIGHT = 28

# Correct-pick percentage is a fixed 0-100 quantity, so the axis is fixed too.
# Auto-scaling to each player's own min/max would make a 61-64% season look as
# dramatic as a 20-90% one, and would stop two cards on the same page from
# being comparable at a glance -- the opposite of what the sparkline is for.
_AXIS_MIN = 0.0
_AXIS_MAX = 100.0


def sparkline_points(series, width=SPARKLINE_WIDTH, height=SPARKLINE_HEIGHT, pad=2):
    """Map a weekly-accuracy series to an SVG polyline ``points`` string.

    ``series`` is the list of ``{'week', 'accuracy', ...}`` dicts produced by
    ``build_pool_standings_stats``, already ordered by week. Returns "" for an
    empty series (the caller omits the sparkline entirely); a single-entry
    series returns one point, which the template renders as a dot rather than
    a line, since a one-point polyline draws nothing.
    """
    if not series:
        return ""

    usable_width = max(width - 2 * pad, 1)
    usable_height = max(height - 2 * pad, 1)
    span = _AXIS_MAX - _AXIS_MIN

    def y_for(accuracy):
        # Clamp defensively: a stray out-of-range value should flatten against
        # the edge, never draw outside the viewBox.
        clamped = min(max(float(accuracy or 0), _AXIS_MIN), _AXIS_MAX)
        ratio = (clamped - _AXIS_MIN) / span
        # SVG y grows downward, so a high percentage needs a low y.
        return pad + (1 - ratio) * usable_height

    if len(series) == 1:
        return f"{pad + usable_width / 2:.1f},{y_for(series[0]['accuracy']):.1f}"

    step = usable_width / (len(series) - 1)
    return " ".join(
        f"{pad + i * step:.1f},{y_for(entry['accuracy']):.1f}"
        for i, entry in enumerate(series)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.SparklineGeometryTests --settings=pickem.test_settings
```

Expected: `OK` (6 tests)

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/sparkline.py pickem/pickem_homepage/tests.py
git commit -m "feat(standings): add pure sparkline geometry helper"
```

---

### Task 2: Weekly-accuracy series from the existing per-week query

**Files:**
- Modify: `pickem/pickem_homepage/views.py:1318-1392` (`build_pool_standings_stats`)
- Test: `pickem/pickem_api/tests/legacy.py` (append to the class at `:2171` that already covers this function)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `build_pool_standings_stats(pool, gameseason, competition)` returns `{userID(str): {'correct': int, 'accuracy': int|None, 'perfect_weeks': int, 'weekly_accuracy': [{'week': int, 'accuracy': int, 'correct': int, 'total': int}]}}`, the series ordered by week ascending. Existing keys are unchanged.

**Why this restructure:** the function already runs a `(userID, gameWeek)` group-by annotating `correct` and `total`, then uses it only to count perfect weeks. Two things block reusing it for accuracy: it is not filtered to finished games (so `total` counts picks on unplayed games), and it runs only inside `if scored_by_week:` (i.e. only when a *complete* week exists). Adding `pick_game_id__in=finished_ids` is a no-op for complete weeks — in a complete week every game is finished — so perfect-week counts are unaffected. Step 1 pins that.

- [ ] **Step 1: Write the failing tests**

Append to the existing test class in `pickem/pickem_api/tests/legacy.py` that already exercises `build_pool_standings_stats` (the one beginning at line ~2171). Match its existing fixture style for `self.pool`, `GamesAndScores` and `GamePicks`:

```python
    def test_weekly_accuracy_series_is_ordered_and_per_week(self):
        from pickem_homepage.views import build_pool_standings_stats

        stats = build_pool_standings_stats(self.pool, 2526, "nfl")
        series = stats[str(self.user.id)]["weekly_accuracy"]

        self.assertEqual([e["week"] for e in series], sorted(e["week"] for e in series))
        for entry in series:
            self.assertEqual(
                entry["accuracy"], round(entry["correct"] / entry["total"] * 100)
            )

    def test_weekly_accuracy_ignores_picks_on_unplayed_games(self):
        """A pick on a game that has not finished must not deflate that week's
        accuracy by inflating the denominator."""
        from pickem_homepage.views import build_pool_standings_stats

        before = build_pool_standings_stats(self.pool, 2526, "nfl")
        before_series = {
            e["week"]: e for e in before[str(self.user.id)]["weekly_accuracy"]
        }

        unplayed = GamesAndScores.objects.create(
            id=99901, slug="unplayed", competition="nfl", gameWeek="1",
            gameyear="2025", gameseason=2526, statusType="inprogress",
            homeTeamSlug="home", awayTeamSlug="away",
        )
        GamePicks.objects.create(
            id=f"{self.pool.id}-{self.user.id}-99901", pool=self.pool,
            pick_game_id=99901, slug="99901", userID=str(self.user.id),
            uid=self.user.id, userEmail=self.user.email, gameWeek="1",
            gameyear="2025", gameseason=2526, competition="nfl",
            pick="home", pick_correct=False, auto_pick=False,
        )

        after = build_pool_standings_stats(self.pool, 2526, "nfl")
        after_series = {
            e["week"]: e for e in after[str(self.user.id)]["weekly_accuracy"]
        }
        self.assertEqual(after_series[1]["total"], before_series[1]["total"])
        self.assertEqual(after_series[1]["accuracy"], before_series[1]["accuracy"])

    def test_weekly_accuracy_present_before_any_week_is_complete(self):
        """The series must appear as soon as any game is graded, not only once
        a whole week is complete (which is all perfect_weeks ever needed)."""
        from pickem_homepage.views import build_pool_standings_stats

        stats = build_pool_standings_stats(self.pool, 2526, "nfl")
        self.assertTrue(stats[str(self.user.id)]["weekly_accuracy"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.legacy --settings=pickem.test_settings -k weekly_accuracy
```

Expected: FAIL with `KeyError: 'weekly_accuracy'`

- [ ] **Step 3: Restructure the implementation**

In `pickem/pickem_homepage/views.py`, replace the body of `build_pool_standings_stats` from the `stats[uid] = {` initializer through the end of the perfect-weeks block.

First, add `'weekly_accuracy': []` to the per-user initializer:

```python
        stats[uid] = {
            'correct': correct,
            'accuracy': round(correct / total * 100) if total else None,
            'perfect_weeks': 0,
            'weekly_accuracy': [],
        }
```

Then replace the perfect-weeks block with a single per-week pass that feeds both results:

```python
    # One per-week pass feeds two things: the sparkline series on the standings
    # breakdown cards, and the perfect-week count.
    #
    # Perfect weeks: weeks where the user picked every game and got them all
    # right (mirrors update_stats' definition, scoped to this pool). Only
    # fully-complete weeks count -- a perfect week means every game in the week
    # was picked correctly, which cannot be judged until the whole week is
    # final. Counting games "scored so far" mid-week would let a lone 1/1 pick
    # masquerade as a perfect week.
    from pickem_api.weekly_winners import week_is_complete
    scored_by_week = {}
    for week in GamesAndScores.objects.filter(
        gameseason=gameseason, competition=competition, gameScored=True
    ).values_list('gameWeek', flat=True):
        scored_by_week[week] = scored_by_week.get(week, 0) + 1
    complete_weeks = {
        wk: n for wk, n in scored_by_week.items()
        if week_is_complete(gameseason, wk, competition)
    }

    # Restricted to finished games so an ungraded pick cannot inflate the
    # denominator. For a complete week this changes nothing (every game in it
    # is finished), so the perfect-week counts below are unaffected.
    per_week = (
        GamePicks.objects.filter(
            pool=pool, gameseason=gameseason, competition=competition,
            pick_game_id__in=finished_ids, auto_pick=False,
        )
        .values('userID', 'gameWeek')
        .annotate(
            correct=Count('pick_game_id', filter=Q(pick_correct=True), distinct=True),
            total=Count('pick_game_id', distinct=True),
        )
    )

    series_by_uid = {}
    for row in per_week:
        uid = str(row['userID'])
        entry = stats.setdefault(
            uid,
            {'correct': 0, 'accuracy': None, 'perfect_weeks': 0, 'weekly_accuracy': []},
        )
        total = row['total'] or 0
        correct = row['correct'] or 0

        if total:
            # gameWeek is stored as a string; sort and display it as a number.
            try:
                week_num = int(row['gameWeek'])
            except (TypeError, ValueError):
                week_num = None
            if week_num is not None:
                series_by_uid.setdefault(uid, []).append({
                    'week': week_num,
                    'accuracy': round(correct / total * 100),
                    'correct': correct,
                    'total': total,
                })

        scored_count = complete_weeks.get(row['gameWeek'], 0)
        if scored_count and correct == scored_count and total == scored_count:
            entry['perfect_weeks'] += 1

    for uid, series in series_by_uid.items():
        stats[uid]['weekly_accuracy'] = sorted(series, key=lambda e: e['week'])

    return stats
```

- [ ] **Step 4: Run the full existing suite for this function plus the new tests**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.legacy pickem_homepage.tests --settings=pickem.test_settings
```

Expected: `OK`. The pre-existing perfect-week tests at `legacy.py:2171` must still pass unchanged — that is the regression gate for this restructure.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/views.py pickem/pickem_api/tests/legacy.py
git commit -m "feat(standings): emit weekly accuracy series from the per-week pass"
```

---

### Task 3: Batched profile + favorite-team lookup

**Files:**
- Modify: `pickem/pickem_homepage/views.py` (add after `build_user_display_maps`, which ends at `:240`)
- Test: `pickem/pickem_homepage/tests.py` (append `BuildUserProfileMapTests`)

**Interfaces:**
- Consumes: nothing from Tasks 1–2.
- Produces: `build_user_profile_map(user_ids) -> {userID(str): {'tagline': str|None, 'team': Teams|None}}`. Every requested id gets a key; users with no `UserProfile` get `{'tagline': None, 'team': None}`.

**Why not `lookuplogo`:** that filter runs one query per call (`pickem_homepage_extras.py:171`) and this page renders it once per player — the exact N+1 that `picks.html` already carries a guard test against. `UserProfile.favorite_team` stores the full `Teams.teamNameSlug` (verified against production: `dallas-cowboys`, `philadelphia-eagles`, `new-england-patriots`), so it joins directly.

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_homepage/tests.py`:

```python
class BuildUserProfileMapTests(TestCase):
    def setUp(self):
        self.with_team = User.objects.create_user('withteam', 'wt@example.com', 'pw')
        self.no_profile = User.objects.create_user('noprofile', 'np@example.com', 'pw')
        self.bad_slug = User.objects.create_user('badslug', 'bs@example.com', 'pw')
        UserProfile.objects.update_or_create(
            user=self.with_team,
            defaults={'tagline': "Statistically, I'm due.",
                      'favorite_team': 'dallas-cowboys'},
        )
        UserProfile.objects.update_or_create(
            user=self.bad_slug,
            defaults={'tagline': None, 'favorite_team': 'not-a-real-team'},
        )
        UserProfile.objects.filter(user=self.no_profile).delete()
        Teams.objects.update_or_create(
            teamNameSlug='dallas-cowboys',
            defaults={'teamNameName': 'Dallas Cowboys', 'teamLogo': 'http://x/dal.png'},
        )

    def test_returns_tagline_and_resolved_team(self):
        result = build_user_profile_map([self.with_team.id])
        entry = result[str(self.with_team.id)]
        self.assertEqual(entry['tagline'], "Statistically, I'm due.")
        self.assertEqual(entry['team'].teamNameName, 'Dallas Cowboys')

    def test_user_without_a_profile_gets_empty_entry(self):
        result = build_user_profile_map([self.no_profile.id])
        self.assertEqual(result[str(self.no_profile.id)],
                         {'tagline': None, 'team': None})

    def test_unknown_team_slug_resolves_to_none(self):
        result = build_user_profile_map([self.bad_slug.id])
        self.assertIsNone(result[str(self.bad_slug.id)]['team'])

    def test_lookup_is_batched_regardless_of_user_count(self):
        """Two queries total (profiles, then teams) no matter how many users --
        this page renders one entry per player, so a per-row lookup would be an
        N+1."""
        ids = [self.with_team.id, self.no_profile.id, self.bad_slug.id]
        with self.assertNumQueries(2):
            build_user_profile_map(ids)

    def test_empty_input_makes_no_queries(self):
        with self.assertNumQueries(0):
            self.assertEqual(build_user_profile_map([]), {})
```

Add to the imports at the top of `tests.py` (alongside the existing view imports):

```python
from pickem_homepage.views import build_user_profile_map
```

Ensure `UserProfile` and `Teams` are imported in `tests.py`; add them to the existing `from pickem_api.models import (...)` block if absent.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.BuildUserProfileMapTests --settings=pickem.test_settings
```

Expected: `ImportError: cannot import name 'build_user_profile_map'`

- [ ] **Step 3: Write the implementation**

In `pickem/pickem_homepage/views.py`, immediately after `build_user_display_maps` ends (line ~240):

```python
def build_user_profile_map(user_ids):
    """Tagline + favorite-team row for each user, in two queries total.

    Deliberately not the ``lookuplogo`` template filter: that issues a query
    per call, and the standings breakdown renders one per player. Returns an
    entry for every requested id, so the template never has to guard a miss.
    """
    raw_ids = {str(uid) for uid in user_ids if uid}
    if not raw_ids:
        return {}
    numeric_ids = {int(uid) for uid in raw_ids if uid.isdigit()}

    profiles = {
        str(p.user_id): p
        for p in UserProfile.objects.filter(user_id__in=numeric_ids)
    }
    slugs = {
        p.favorite_team for p in profiles.values() if p.favorite_team
    }
    teams = {
        t.teamNameSlug: t
        for t in Teams.objects.filter(teamNameSlug__in=slugs)
    } if slugs else {}

    result = {}
    for key in raw_ids:
        profile = profiles.get(key)
        result[key] = {
            'tagline': (profile.tagline or None) if profile else None,
            'team': teams.get(profile.favorite_team) if profile else None,
        }
    return result
```

Confirm `UserProfile` and `Teams` are already imported in `views.py` (both are — `UserProfile` is used at `:1660`, `Teams` at `:1662`).

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.BuildUserProfileMapTests --settings=pickem.test_settings
```

Expected: `OK` (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/views.py pickem/pickem_homepage/tests.py
git commit -m "feat(standings): add batched tagline + favorite-team lookup"
```

---

### Task 4: Wire the data onto the standings view

**Files:**
- Modify: `pickem/pickem_homepage/views.py:4021-4065` (the badge block and context in `render_standings_page`)
- Test: `pickem/pickem_homepage/tests.py` (append `StandingsBreakdownContextTests`)

**Interfaces:**
- Consumes: `sparkline_points` (Task 1), `build_pool_standings_stats`'s `weekly_accuracy` (Task 2), `build_user_profile_map` (Task 3).
- Produces: each entry in `player_points` gains `accuracy` (int|None), `correct_picks` (int), `total_picks` (int), `best_week_points` (int|None), `best_week_number` (int|None), `seasons_won` (int), `tagline` (str|None), `favorite_team` (Teams|None), `sparkline` (str), `sparkline_label` (str). Context gains `sparkline_width` and `sparkline_height`.

- [ ] **Step 1: Write the failing tests**

**Fixtures:** these tests need the tenant fixtures (`self.smith_pool`, `self.smith_member`, `self._tenant_url`) that already exist on `TenantScoresStandingsRulesIsolationTests` (`tests.py:2202`). Add these as **methods on that existing class**, not as a new standalone `TestCase` — a fresh class would have none of that setup. Each test that needs a tagline or favorite team creates it inline, since the existing `setUp` does not.

Append the following methods inside `TenantScoresStandingsRulesIsolationTests`:

```python
    def _give_smith_member_a_profile(self):
        """The class setUp creates no UserProfile, so tests that assert on
        identity create one explicitly."""
        UserProfile.objects.update_or_create(
            user=self.smith_member,
            defaults={'tagline': "Statistically, I'm due.",
                      'favorite_team': 'dallas-cowboys'},
        )
        Teams.objects.update_or_create(
            teamNameSlug='dallas-cowboys',
            defaults={'teamNameName': 'Dallas Cowboys',
                      'teamLogo': 'http://example.test/dal.png'},
        )

    def test_entries_carry_identity_and_form(self):
        self._give_smith_member_a_profile()
        self.client.force_login(self.smith_member)
        response = self.client.get(self._tenant_url("family_pool_standings"))

        entry = next(
            e for e in response.context["player_points"]
            if str(e.userID) == str(self.smith_member.id)
        )
        self.assertEqual(entry.tagline, "Statistically, I'm due.")
        self.assertEqual(entry.favorite_team.teamNameName, "Dallas Cowboys")
        self.assertIsNotNone(entry.accuracy)
        self.assertIsInstance(entry.seasons_won, int)

    def test_best_week_is_the_highest_single_week(self):
        self.client.force_login(self.smith_member)
        response = self.client.get(self._tenant_url("family_pool_standings"))

        entry = next(
            e for e in response.context["player_points"]
            if str(e.userID) == str(self.smith_member.id)
        )
        weekly = [
            getattr(entry, f"week_{i}_points") for i in range(1, 19)
            if getattr(entry, f"week_{i}_points") is not None
        ]
        if weekly:
            self.assertEqual(entry.best_week_points, max(weekly))
            self.assertEqual(
                getattr(entry, f"week_{entry.best_week_number}_points"),
                max(weekly),
            )

    def test_sparkline_points_string_is_attached(self):
        self.client.force_login(self.smith_member)
        response = self.client.get(self._tenant_url("family_pool_standings"))

        entry = next(
            e for e in response.context["player_points"]
            if str(e.userID) == str(self.smith_member.id)
        )
        self.assertTrue(entry.sparkline)
        self.assertIn(",", entry.sparkline)
        self.assertIn("accuracy", entry.sparkline_label.lower())

    def test_player_with_no_graded_picks_has_no_sparkline(self):
        GamePicks.objects.filter(pool=self.smith_pool).delete()
        self.client.force_login(self.smith_member)
        response = self.client.get(self._tenant_url("family_pool_standings"))

        for entry in response.context["player_points"]:
            self.assertEqual(entry.sparkline, "")
            self.assertIsNone(entry.accuracy)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.StandingsBreakdownContextTests --settings=pickem.test_settings
```

Expected: FAIL with `AttributeError: 'userSeasonPoints' object has no attribute 'tagline'`

- [ ] **Step 3: Write the implementation**

In `render_standings_page`, the existing tenant block computes `perfect_by_uid` by calling `build_pool_standings_stats` and throwing the rest away. Capture the whole result instead:

```python
    pool_stats = {}
    perfect_by_uid = {}
    prev_champion_ids = set()
    seasons_won_by_uid = {}
    if tenant_context and str(selected_season).isdigit():
        season_int = int(selected_season)
        pool_stats = build_pool_standings_stats(
            target_pool, season_int, target_pool.competition
        )
        perfect_by_uid = {
            uid: stat.get('perfect_weeks', 0) for uid, stat in pool_stats.items()
        }
        prev_champion_ids = {
            str(uid)
            for uid in userSeasonPoints.objects.filter(
                pool__family=tenant_context.family,
                gameseason=season_int - 101,
                year_winner=True,
            ).values_list('userID', flat=True)
            if uid
        }
        # Seasons won across this family's history. Read from userSeasonPoints
        # (the same source prev_champion_ids uses) rather than
        # userStats.seasonsWon, which the scheduled pipeline does not reliably
        # write per-pool -- the reason build_pool_standings_stats exists.
        for uid in userSeasonPoints.objects.filter(
            pool__family=tenant_context.family, year_winner=True,
        ).values_list('userID', flat=True):
            if uid:
                seasons_won_by_uid[str(uid)] = seasons_won_by_uid.get(str(uid), 0) + 1
```

Then extend the existing per-entry loop:

```python
    profile_map = (
        build_user_profile_map([e.userID for e in player_points])
        if tenant_context else {}
    )
    for entry in player_points:
        uid = str(entry.userID)
        entry.weeks_won = sum(
            1 for i in range(1, 19) if getattr(entry, f'week_{i}_winner', False)
        )
        entry.perfect_weeks = perfect_by_uid.get(uid, 0)
        entry.prev_champion = uid in prev_champion_ids
        entry.seasons_won = seasons_won_by_uid.get(uid, 0)

        stat = pool_stats.get(uid, {})
        entry.accuracy = stat.get('accuracy')
        entry.correct_picks = stat.get('correct', 0)
        series = stat.get('weekly_accuracy', [])
        entry.total_picks = sum(s['total'] for s in series)
        entry.sparkline = sparkline_points(series)
        if series:
            entry.sparkline_label = (
                f"Weekly accuracy, week {series[0]['week']} to "
                f"week {series[-1]['week']}: {stat.get('accuracy')}% overall"
            )
        else:
            entry.sparkline_label = "No weekly accuracy yet"

        # Best single week, straight off the row -- no query.
        best_points, best_week = None, None
        for i in range(1, 19):
            points = getattr(entry, f'week_{i}_points', None)
            if points is not None and (best_points is None or points > best_points):
                best_points, best_week = points, i
        entry.best_week_points = best_points
        entry.best_week_number = best_week

        profile = profile_map.get(uid, {})
        entry.tagline = profile.get('tagline')
        entry.favorite_team = profile.get('team')
```

Add to the `context` dict:

```python
        'sparkline_width': SPARKLINE_WIDTH,
        'sparkline_height': SPARKLINE_HEIGHT,
```

Add the import at the top of `views.py`:

```python
from pickem_homepage.sparkline import (
    SPARKLINE_HEIGHT, SPARKLINE_WIDTH, sparkline_points,
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.StandingsBreakdownContextTests --settings=pickem.test_settings
```

Expected: `OK` (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/views.py pickem/pickem_homepage/tests.py
git commit -m "feat(standings): attach identity, form and sparkline to breakdown entries"
```

---

### Task 5: Render the enriched card

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/standings.html:239-290` (the breakdown card)
- Build: `npm run build:prod` if any new Tailwind utility is introduced

**Interfaces:**
- Consumes: every attribute produced by Task 4.
- Produces: no Python interface.

The card becomes three bands. The 18-week grid (the `<!-- Weeks Grid -->` block) is left exactly as-is.

- [ ] **Step 1: Replace the player header with the identity strip**

Inside `{% with usernames|lookup:player.userID as username %}`, replace the existing `<!-- Player Header -->` block's `<div class="flex-1">` contents with:

```html
	                    <div class="flex-1 min-w-0">
	                        <div class="flex items-center gap-2 flex-wrap">
	                            <h5 class="text-sm font-bold text-text-dark dark:text-white uppercase">
	                                <a href="{% if family and pool %}{% url 'family_pool_user_profile' family.slug pool.slug player.userID %}{% else %}{% url 'user_profile' player.userID %}{% endif %}" class="hover:text-primary transition-colors">{{ username }}</a>
	                            </h5>
	                            {% if player.favorite_team and player.favorite_team.teamLogo %}
	                            <span class="inline-flex items-center gap-1 rounded-full bg-bg-light dark:bg-surface px-1.5 py-0.5 border border-border-light dark:border-border-subtle" title="Favorite team: {{ player.favorite_team.teamNameName }}">
	                                <img src="{{ player.favorite_team.teamLogo }}" alt="{{ player.favorite_team.teamNameName }} logo" class="w-3.5 h-3.5 object-contain">
	                                <span class="text-[10px] font-bold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary">{{ player.favorite_team.teamNameName }}</span>
	                            </span>
	                            {% endif %}
	                        </div>
                        <p class="text-sm text-text-secondary-light dark:text-text-secondary">
                            Total: <strong class="text-text-dark dark:text-white">{{ player.total_points|default:0 }} points</strong>
                        </p>
                        {% if player.tagline %}
                        <p class="text-xs italic text-text-secondary-light dark:text-text-secondary truncate" title="{{ player.tagline }}">&ldquo;{{ player.tagline }}&rdquo;</p>
                        {% endif %}
                        {% if player.prev_champion or player.weeks_won or player.perfect_weeks or player.seasons_won %}
                        <!-- Badges (same meaning as the lobby standings + leaderboard rows) -->
                        <div class="mt-1 flex flex-wrap items-center gap-1">
                            {% if player.prev_champion %}<span class="inline-flex items-center gap-1 rounded-full bg-yellow-500/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-yellow-700 dark:text-yellow-300" title="Won last season"><i class="fas fa-crown"></i>Champ</span>{% endif %}
                            {% if player.seasons_won %}<span class="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-700 dark:text-amber-300" title="Season champion {{ player.seasons_won }} time{{ player.seasons_won|pluralize }}"><i class="fas fa-medal"></i>{{ player.seasons_won }} Season{{ player.seasons_won|pluralize }}</span>{% endif %}
                            {% if player.weeks_won %}<span class="inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-sky-700 dark:text-sky-300" title="Weekly winner {{ player.weeks_won }} time{{ player.weeks_won|pluralize }}"><i class="fas fa-trophy"></i>{{ player.weeks_won }}W</span>{% endif %}
                            {% if player.perfect_weeks %}<span class="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-700 dark:text-emerald-300" title="Perfect week{{ player.perfect_weeks|pluralize }}"><i class="fas fa-star"></i>{% if player.perfect_weeks > 1 %}{{ player.perfect_weeks }} {% endif %}Perfect</span>{% endif %}
                        </div>
                        {% endif %}
                    </div>
```

- [ ] **Step 2: Add the stat ribbon between the header and the weeks grid**

Immediately after the `{% endwith %}` that closes the header block and before `<!-- Weeks Grid -->`:

```html
                <!-- Stat ribbon: form and volume. Trophy counts live in the
                     badge row above and are deliberately not repeated here. -->
                <div class="flex items-center justify-between gap-4 mb-3 pb-3 border-b border-border-light dark:border-border-subtle">
                    <div class="flex items-center gap-4 sm:gap-6">
                        <div>
                            <div class="text-[10px] font-bold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary">Accuracy</div>
                            <div class="text-sm font-black text-text-dark dark:text-white">{% if player.accuracy != None %}{{ player.accuracy }}%{% else %}&mdash;{% endif %}</div>
                        </div>
                        <div>
                            <div class="text-[10px] font-bold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary">Correct</div>
                            <div class="text-sm font-black text-text-dark dark:text-white">{% if player.total_picks %}{{ player.correct_picks }}/{{ player.total_picks }}{% else %}&mdash;{% endif %}</div>
                        </div>
                        <div>
                            <div class="text-[10px] font-bold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary">Best Week</div>
                            <div class="text-sm font-black text-text-dark dark:text-white">{% if player.best_week_points != None %}{{ player.best_week_points }} <span class="text-[10px] font-semibold text-text-secondary-light dark:text-text-secondary">(W{{ player.best_week_number }})</span>{% else %}&mdash;{% endif %}</div>
                        </div>
                    </div>
                    {% if player.sparkline %}
                    <div class="flex flex-col items-end flex-shrink-0">
                        <svg viewBox="0 0 {{ sparkline_width }} {{ sparkline_height }}"
                             width="{{ sparkline_width }}" height="{{ sparkline_height }}"
                             class="overflow-visible" role="img"
                             aria-label="{{ player.sparkline_label }}"
                             preserveAspectRatio="none">
                            <title>{{ player.sparkline_label }}</title>
                            <polyline points="{{ player.sparkline }}" fill="none"
                                      stroke="currentColor" stroke-width="1.5"
                                      stroke-linecap="round" stroke-linejoin="round"
                                      class="text-primary" />
                        </svg>
                        <div class="text-[10px] font-bold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary">Weekly accuracy</div>
                    </div>
                    {% endif %}
                </div>
```

A single-point series yields a one-point `polyline`, which draws nothing. Add a companion circle so a lone graded week still shows:

```html
                            <polyline points="{{ player.sparkline }}" fill="none"
                                      stroke="currentColor" stroke-width="1.5"
                                      stroke-linecap="round" stroke-linejoin="round"
                                      class="text-primary" />
                            <polyline points="{{ player.sparkline }}" fill="none"
                                      stroke="currentColor" stroke-width="3"
                                      stroke-linecap="round" stroke-dasharray="0 1000"
                                      class="text-primary" />
```

The second `polyline` uses `stroke-dasharray="0 1000"` with `stroke-linecap="round"`, which renders a round dot at the first vertex and nothing else — so a one-point series shows a dot, and a longer series gains a subtle start marker.

- [ ] **Step 3: Verify the page renders**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests --settings=pickem.test_settings
```

Then check the live page:

```bash
curl -s http://localhost:8000/ -o /dev/null -w '%{http_code}\n'
```

Expected: existing tests `OK`.

- [ ] **Step 4: Rebuild Tailwind if any new utility class was introduced**

```bash
npm run build:prod
```

All classes used above already appear elsewhere in the project except `overflow-visible` and the `amber-*` badge tints; run the build to be certain, and commit `tailwind.css` only if it actually changed.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/standings.html
git add pickem/pickem_homepage/static/css/tailwind.css 2>/dev/null || true
git commit -m "feat(standings): identity strip, stat ribbon and sparkline on breakdown cards"
```

---

### Task 6: Privacy and query-count guards

**Files:**
- Test: `pickem/pickem_homepage/tests.py` (append `StandingsBreakdownGuardTests`)

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: no runtime interface — regression guards only.

- [ ] **Step 1: Write the guard tests**

As in Task 4, these go in as **methods on the existing `TenantScoresStandingsRulesIsolationTests`** (`tests.py:2202`), which owns the tenant fixtures and now also owns `_give_smith_member_a_profile` from Task 4:

```python
    def test_render_shows_tagline_favorite_team_and_seasons_badge(self):
        self._give_smith_member_a_profile()
        self.client.force_login(self.smith_member)
        response = self.client.get(self._tenant_url("family_pool_standings"))

        self.assertContains(response, "Statistically, I&#x27;m due.")
        self.assertContains(response, "Dallas Cowboys logo")
        self.assertContains(response, "Weekly accuracy")

    def test_non_tenant_branch_carries_no_tagline(self):
        """Mirrors the existing first_names leak guard: the non-tenant branch
        spans every pool in the install, so it must never carry personal
        details."""
        response = self.client.get(reverse("standings"))
        if response.status_code == 200:
            for entry in response.context["player_points"]:
                self.assertIsNone(entry.tagline)
                self.assertIsNone(entry.favorite_team)

    def test_breakdown_query_count_does_not_grow_with_player_count(self):
        """The profile/team lookups are batched and the sparkline reuses the
        per-week pass, so adding players must not add queries."""
        self.client.force_login(self.smith_member)
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(self._tenant_url("family_pool_standings"))

        for i in range(5):
            extra = User.objects.create_user(f"extra{i}", f"e{i}@example.com", "pw")
            FamilyMembership.objects.create(family=self.smith_family, user=extra)
            UserProfile.objects.update_or_create(
                user=extra,
                defaults={'tagline': f'tag {i}', 'favorite_team': 'dallas-cowboys'},
            )
            userSeasonPoints.objects.create(
                pool=self.smith_pool, userID=str(extra.id),
                gameseason=self.smith_pool.season, total_points=i,
            )

        with CaptureQueriesContext(connection) as grown:
            self.client.get(self._tenant_url("family_pool_standings"))

        self.assertEqual(len(grown.captured_queries), len(baseline.captured_queries))
```

Add these imports to `tests.py` if absent:

```python
from django.db import connection
from django.test.utils import CaptureQueriesContext
```

- [ ] **Step 2: Run them**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.StandingsBreakdownGuardTests --settings=pickem.test_settings
```

Expected: `OK`. If the query-count guard fails, the cause is a per-row lookup that slipped into the template — find it and move it into `build_user_profile_map`.

- [ ] **Step 3: Run the whole suite**

```bash
cd pickem && uv run python manage.py test --settings=pickem.test_settings
```

Expected: `OK`, no regressions.

- [ ] **Step 4: Commit**

```bash
git add pickem/pickem_homepage/tests.py
git commit -m "test(standings): guard breakdown privacy and query count"
```

---

## Manual verification

Start the server and open a tenant standings page:

```bash
cd pickem && uv run python manage.py runserver
```

Visit `http://localhost:8000/` → pick a family/pool → Standings. In the Detailed Breakdown, confirm:

- Favorite-team logo chip sits beside the username (for members who set one).
- Tagline renders in italics under the points total, truncating rather than wrapping.
- Badge row shows champ / seasons / weeks-won / perfect, with **no** repeat of those counts in the ribbon.
- Ribbon reads Accuracy, Correct, Best Week; the sparkline sits at the right with its caption.
- Toggle dark mode — every new element keeps contrast.
- Narrow the window to a phone width — the ribbon wraps without pushing the card sideways.
