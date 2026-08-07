# Live Weekend Simulation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dev-only harness that stands up Redis + uvicorn locally and replays a dramatized ~13-game NFL weekend (isolated season 9999) in ~5 minutes, so the SSE-driven live surfaces (`/scores`, lobby Week Points, `/standings`) can be watched updating in real time.

**Architecture:** A shared data/geometry module (`demo_weekend.py`) defines the slate, players, scripted picks, and a pure `game_state_at(game, fraction)` function. A `seed_demo_weekend` command seeds the league pre-kickoff; a `simulate_weekend` command walks a compressed clock, mutates `GamesAndScores` rows, and reuses the **existing production publish + scoring paths** (`maybe_publish_game_change`, `update_picks`, `update_standings`) so every SSE event is byte-identical to production. A `scripts/live-sim.sh` orchestrator brings up Redis + uvicorn, points `currentSeason` at 9999, runs the sim, and tears everything down via a `trap`.

**Tech Stack:** Django 5.2 management commands, redis-py (existing `pickem_api.live_events` helpers), uvicorn/ASGI (existing), Docker (throwaway Redis), bash.

## Global Constraints

- **DEBUG-only:** every new command refuses unless `django.conf.settings.DEBUG` is truthy (matches `seed_demo_week`). Raise `CommandError`.
- **Season 9999 only:** `simulate_weekend` refuses any season other than `DEMO_SEASON` (9999). Never operate on real seasons.
- **Reuse production paths, never reimplement events:** score events go through `pickem_api.live_events.publish_score_event` / `score_event_payload` (via `update_games.maybe_publish_game_change`); standings events go through running `update_standings` — do not hand-build event payloads in the simulator.
- **Isolation:** all data keyed to `DEMO_SLUG` + `DEMO_SEASON`. The only shared row touched is the `currentSeason` singleton, which is captured and restored.
- **statusType vocabulary (closed set):** `notstarted` (pre-kickoff) → `inprogress` (live) → `finished` (final). `statusTitle` is the freeform label ("Scheduled", "Q3", "Final").
- **Python style:** follow the existing command modules — module-level constants in `UPPER_SNAKE`, `snake_case` functions, 4-space indent, no type annotations required (match surrounding code).
- **Tests run from `pickem/`:** `cd pickem && python manage.py test pickem_api.tests.<module>`. Tests must set `DEBUG` via `override_settings(DEBUG=True)` since test settings default DEBUG off.

---

### Task 1: Shared demo-weekend data + geometry module

**Files:**
- Create: `pickem/pickem_api/demo_weekend.py`
- Test: `pickem/pickem_api/tests/test_demo_weekend.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - Constants: `DEMO_SLUG: str`, `DEMO_SEASON: int` (9999), `DEMO_WEEK: str` ("1"), `DEMO_POOL_SLUG: str`, `PLAYERS: list[str]`, `TEAMS: list[tuple]` (id, slug, name, color), `GAMES: list[dict]`, `PICKS: dict[str, dict]`, `EXPECTED_WEEK_WINNER: str`.
  - `GAMES` dict keys per game: `id:int`, `home:str` (slug), `home_name:str`, `away:str`, `away_name:str`, `home_line:list[int]` (4 quarter scores), `away_line:list[int]`, `kickoff_frac:float`, `final_frac:float`, `tiebreaker:bool`.
  - `game_winner(game) -> str`: home slug if `sum(home_line) > sum(away_line)`, else away slug (ties not used in this slate).
  - `game_state_at(game, frac) -> dict` returning the mutable `GamesAndScores` fields: `statusType, statusTitle, homeTeamScore, awayTeamScore, gameWinner, homeTeamPeriod1..4, homeTeamPeriodOT, awayTeamPeriod1..4, awayTeamPeriodOT`.

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_api/tests/test_demo_weekend.py`:

```python
from django.test import TestCase

from pickem_api import demo_weekend as dw


class DemoWeekendGeometryTests(TestCase):
    def test_slate_shape(self):
        self.assertEqual(dw.DEMO_SEASON, 9999)
        self.assertGreaterEqual(len(dw.GAMES), 13)
        self.assertGreaterEqual(len(dw.PLAYERS), 8)
        # Exactly one Monday-night tiebreaker game.
        self.assertEqual(sum(1 for g in dw.GAMES if g["tiebreaker"]), 1)

    def test_before_kickoff_is_scheduled_scoreless(self):
        g = dw.GAMES[0]
        st = dw.game_state_at(g, g["kickoff_frac"] - 0.001)
        self.assertEqual(st["statusType"], "notstarted")
        self.assertEqual(st["homeTeamScore"], 0)
        self.assertEqual(st["awayTeamScore"], 0)
        self.assertEqual(st["gameWinner"], "")

    def test_after_final_matches_line_totals(self):
        for g in dw.GAMES:
            st = dw.game_state_at(g, 1.0)
            self.assertEqual(st["statusType"], "finished")
            self.assertEqual(st["statusTitle"], "Final")
            self.assertEqual(st["homeTeamScore"], sum(g["home_line"]))
            self.assertEqual(st["awayTeamScore"], sum(g["away_line"]))
            self.assertEqual(st["gameWinner"], dw.game_winner(g))

    def test_live_scores_are_monotonic_nondecreasing(self):
        g = dw.GAMES[0]
        prev_h = prev_a = 0
        f = g["kickoff_frac"]
        while f <= g["final_frac"]:
            st = dw.game_state_at(g, f)
            self.assertGreaterEqual(st["homeTeamScore"], prev_h)
            self.assertGreaterEqual(st["awayTeamScore"], prev_a)
            prev_h, prev_a = st["homeTeamScore"], st["awayTeamScore"]
            f += 0.01

    def test_every_pick_targets_a_real_game_and_team(self):
        ids = {g["id"] for g in dw.GAMES}
        slugs = {g["home"] for g in dw.GAMES} | {g["away"] for g in dw.GAMES}
        for player, cfg in dw.PICKS.items():
            for gid, pick in cfg["picks"].items():
                self.assertIn(gid, ids)
                self.assertIn(pick, slugs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_api.tests.test_demo_weekend -v2`
Expected: FAIL — `ModuleNotFoundError: No module named 'pickem_api.demo_weekend'`.

- [ ] **Step 3: Write minimal implementation**

Create `pickem/pickem_api/demo_weekend.py`. Fill `GAMES`/`PICKS` with the concrete slate below (13 games, 8 players; alice & bob identical except the tiebreaker so the MNF game decides the winner):

```python
"""Static slate + pure geometry for the live-weekend simulation harness.

Shared by the seed_demo_weekend and simulate_weekend management commands so the
seeded picks and the scripted score progression stay in one place. Pure data +
functions only — no Django imports, no DB access — so it is trivially testable.
"""

DEMO_SLUG = "demo-live-sim"
DEMO_POOL_SLUG = "demo-pool"
DEMO_SEASON = 9999
DEMO_WEEK = "1"

# 8 synthetic players. alice & bob are the tiebreaker duel (see PICKS).
PLAYERS = [
    "demo-alice", "demo-bob", "demo-carol", "demo-dave",
    "demo-erin", "demo-frank", "demo-gina", "demo-hank",
]

# (team_id, slug, name, hex color) — fake teams, isolated ids.
TEAMS = [
    (999801, "demo-sharks", "Demo Sharks", "0ea5e9"),
    (999802, "demo-eagles", "Demo Eagles", "16a34a"),
    (999803, "demo-colts", "Demo Colts", "2563eb"),
    (999804, "demo-bears", "Demo Bears", "ea580c"),
    (999805, "demo-lions", "Demo Lions", "ca8a04"),
    (999806, "demo-tigers", "Demo Tigers", "dc2626"),
    (999807, "demo-wolves", "Demo Wolves", "7c3aed"),
    (999808, "demo-hawks", "Demo Hawks", "0d9488"),
    (999809, "demo-rams", "Demo Rams", "db2777"),
    (999810, "demo-jets", "Demo Jets", "4b5563"),
    (999811, "demo-ducks", "Demo Ducks", "0891b2"),
    (999812, "demo-bulls", "Demo Bulls", "b91c1c"),
    (999813, "demo-owls", "Demo Owls", "6d28d9"),
    (999814, "demo-crabs", "Demo Crabs", "c2410c"),
    (999815, "demo-mules", "Demo Mules", "334155"),
    (999816, "demo-goats", "Demo Goats", "15803d"),
    (999817, "demo-pumas", "Demo Pumas", "9333ea"),
    (999818, "demo-seals", "Demo Seals", "0369a1"),
    (999819, "demo-moose", "Demo Moose", "a16207"),
    (999820, "demo-orcas", "Demo Orcas", "1e293b"),
    (999821, "demo-lynx", "Demo Lynx", "be123c"),
    (999822, "demo-storm", "Demo Storm", "1d4ed8"),
    (999823, "demo-frost", "Demo Frost", "0e7490"),
    (999824, "demo-flames", "Demo Flames", "dc2626"),
    (999825, "demo-comet", "Demo Comet", "7e22ce"),
    (999826, "demo-vipers", "Demo Vipers", "166534"),
]

_TEAM_SLUGS = {slug for _id, slug, _n, _c in TEAMS}


def _game(gid, home, away, home_line, away_line, kickoff_frac, final_frac,
          tiebreaker=False):
    names = {slug: name for _id, slug, name, _c in TEAMS}
    return {
        "id": gid,
        "home": home, "home_name": names[home], "home_line": home_line,
        "away": away, "away_name": names[away], "away_line": away_line,
        "kickoff_frac": kickoff_frac, "final_frac": final_frac,
        "tiebreaker": tiebreaker,
    }


# Waves: Thu (~0.02-0.15), Sun-early (~0.20-0.55), Sun-late (~0.45-0.75),
# SNF (~0.65-0.85), MNF tiebreaker (~0.82-1.0). final_frac staggered so the
# standings reorder in waves rather than all at once.
GAMES = [
    # Thursday night
    _game(9998001, "demo-sharks", "demo-eagles", [7, 7, 3, 7], [0, 3, 7, 3], 0.02, 0.15),
    # Sunday early wave (8 games)
    _game(9998002, "demo-colts", "demo-bears", [3, 0, 7, 0], [7, 7, 7, 3], 0.20, 0.40),
    _game(9998003, "demo-lions", "demo-tigers", [7, 10, 0, 7], [0, 0, 3, 7], 0.20, 0.42),
    _game(9998004, "demo-wolves", "demo-hawks", [0, 7, 7, 0], [3, 7, 0, 7], 0.21, 0.44),
    _game(9998005, "demo-rams", "demo-jets", [10, 7, 7, 3], [0, 0, 3, 0], 0.21, 0.46),
    _game(9998006, "demo-ducks", "demo-bulls", [0, 3, 0, 7], [7, 7, 7, 7], 0.22, 0.48),
    _game(9998007, "demo-owls", "demo-crabs", [7, 7, 7, 7], [3, 0, 3, 0], 0.22, 0.50),
    _game(9998008, "demo-mules", "demo-goats", [3, 3, 3, 0], [0, 7, 0, 7], 0.23, 0.52),
    _game(9998009, "demo-pumas", "demo-seals", [7, 0, 10, 7], [0, 3, 0, 3], 0.23, 0.54),
    # Sunday late wave (2 games)
    _game(9998010, "demo-moose", "demo-orcas", [0, 7, 0, 7], [7, 0, 7, 3], 0.45, 0.70),
    _game(9998011, "demo-lynx", "demo-storm", [7, 7, 7, 0], [0, 3, 0, 7], 0.46, 0.72),
    # Sunday night
    _game(9998012, "demo-frost", "demo-flames", [3, 7, 3, 7], [0, 0, 7, 3], 0.65, 0.85),
    # Monday night — the tiebreaker. Close final (final total = 44) so the
    # tiebreaker guesses decide it. sharks win 24-20.
    _game(9998013, "demo-comet", "demo-vipers", [7, 3, 7, 7], [0, 7, 3, 10], 0.82, 1.0,
          tiebreaker=True),
]

# Favorites (the pick most players make) per game id — the "chalk".
_FAVORITE = {g["id"]: (g["home"] if sum(g["home_line"]) > sum(g["away_line"])
                       else g["away"]) for g in GAMES}
# A couple of upsets: games where chalk LOSES, used to spread the pack.
# (colts lose to bears; ducks lose to bulls; mules lose to goats.)

# Each player picks the favorite except for a scripted handful of contrarian
# picks that separate them across the waves. alice and bob are identical on all
# 13 games (both pick every favorite) so only the tiebreaker separates them.
_CONTRARIAN = {
    "demo-carol": {9998002: "demo-colts", 9998006: "demo-ducks"},   # 2 wrong upsets
    "demo-dave": {9998004: "demo-wolves", 9998008: "demo-mules"},   # 2 wrong
    "demo-erin": {9998003: "demo-tigers"},                          # 1 wrong
    "demo-frank": {9998005: "demo-jets", 9998007: "demo-crabs", 9998009: "demo-seals"},
    "demo-gina": {9998010: "demo-orcas"},                           # 1 wrong (late wave)
    "demo-hank": {9998011: "demo-storm", 9998012: "demo-flames"},   # 2 wrong (late/SNF)
}


def _picks_for(player):
    picks = {g["id"]: _FAVORITE[g["id"]] for g in GAMES}
    picks.update(_CONTRARIAN.get(player, {}))
    return picks


# alice's tiebreaker guess (44) is exact; bob's (50) is off — alice wins.
PICKS = {p: {"picks": _picks_for(p), "tb_score": None, "tb_yards": None}
         for p in PLAYERS}
PICKS["demo-alice"].update(tb_score=44, tb_yards=700)
PICKS["demo-bob"].update(tb_score=50, tb_yards=780)
PICKS["demo-carol"].update(tb_score=38, tb_yards=640)
PICKS["demo-dave"].update(tb_score=52, tb_yards=800)
PICKS["demo-erin"].update(tb_score=41, tb_yards=690)
PICKS["demo-frank"].update(tb_score=47, tb_yards=720)
PICKS["demo-gina"].update(tb_score=35, tb_yards=610)
PICKS["demo-hank"].update(tb_score=55, tb_yards=830)

# alice & bob both go a perfect 13/13 (identical favorite picks); alice's exact
# tiebreaker guess wins the week. Enforced by the simulate integration test.
EXPECTED_WEEK_WINNER = "demo-alice"

_QUARTER_TITLES = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
_PERIOD_FIELDS = ("Period1", "Period2", "Period3", "Period4")


def game_winner(game):
    """Home slug if home outscores away, else away slug (no ties in slate)."""
    return (game["home"] if sum(game["home_line"]) > sum(game["away_line"])
            else game["away"])


def _period_fields(home_line, away_line, completed_quarters):
    """Per-quarter line-score fields, revealed only through completed quarters."""
    out = {}
    for i, name in enumerate(_PERIOD_FIELDS):
        shown = i < completed_quarters
        out[f"homeTeam{name}"] = home_line[i] if shown else None
        out[f"awayTeam{name}"] = away_line[i] if shown else None
    out["homeTeamPeriodOT"] = None
    out["awayTeamPeriodOT"] = None
    return out


def _scheduled(game):
    return {
        "statusType": "notstarted", "statusTitle": "Scheduled",
        "homeTeamScore": 0, "awayTeamScore": 0, "gameWinner": "",
        **_period_fields(game["home_line"], game["away_line"], 0),
    }


def _final(game):
    return {
        "statusType": "finished", "statusTitle": "Final",
        "homeTeamScore": sum(game["home_line"]),
        "awayTeamScore": sum(game["away_line"]),
        "gameWinner": game_winner(game),
        **_period_fields(game["home_line"], game["away_line"], 4),
    }


def game_state_at(game, frac):
    """Mutable GamesAndScores fields for `game` at overall window fraction `frac`."""
    ko, fin = game["kickoff_frac"], game["final_frac"]
    if frac < ko:
        return _scheduled(game)
    if frac >= fin:
        return _final(game)
    # Live: p is 0..1 across this game's own window; q_float 0..4.
    p = (frac - ko) / (fin - ko)
    q_float = p * 4.0
    completed = int(q_float)                      # 0..3 fully-played quarters
    current = min(4, completed + 1)               # 1..4 quarter on the clock
    frac_in_q = q_float - completed               # 0..1 through current quarter
    home = sum(game["home_line"][:completed]) + int(
        game["home_line"][min(completed, 3)] * frac_in_q)
    away = sum(game["away_line"][:completed]) + int(
        game["away_line"][min(completed, 3)] * frac_in_q)
    return {
        "statusType": "inprogress",
        "statusTitle": _QUARTER_TITLES[current],
        "homeTeamScore": home, "awayTeamScore": away, "gameWinner": "",
        **_period_fields(game["home_line"], game["away_line"], completed),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_api.tests.test_demo_weekend -v2`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/demo_weekend.py pickem/pickem_api/tests/test_demo_weekend.py
git commit -m "feat(sim): demo-weekend slate + pure score geometry module"
```

---

### Task 2: `seed_demo_weekend` management command

**Files:**
- Create: `pickem/pickem_api/management/commands/seed_demo_weekend.py`
- Test: `pickem/pickem_api/tests/test_seed_demo_weekend.py`

**Interfaces:**
- Consumes: `pickem_api.demo_weekend` (all constants + `game_winner`).
- Produces: a management command `seed_demo_weekend` with options `--wipe`, `--owner <username>`, `--make-current`, `--print-current-season`. Seeds the demo family/pool/players/teams and **pre-kickoff** games (`statusType='notstarted'`, scoreless, `gameScored=False`) plus all picks.

**Notes for the implementer:**
- Model the family/pool/membership/teams/picks creation on `seed_demo_week.py` (same module, same `GamePicks` id format `f'{pool.id}-{user.id}-{game_id}'`, same `UserProfile` handling if that command sets it — check and mirror).
- `--make-current`: set the `currentSeason` singleton's `season` to `DEMO_SEASON`. `--print-current-season`: print the current `currentSeason.season` integer (nothing else) and exit — the orchestrator captures it for restore. Both still require DEBUG.
- Create a `UserProfile` per demo player with a `favorite_team` and `tagline` so the lobby avatar/rank rendering is exercised. Inspect `UserProfile` fields first; only set fields that exist.

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_api/tests/test_seed_demo_weekend.py`:

```python
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from io import StringIO

from pickem_api import demo_weekend as dw
from pickem_api.models import (
    Family, GamePicks, GamesAndScores, Pool, currentSeason,
)


@override_settings(DEBUG=True)
class SeedDemoWeekendTests(TestCase):
    def test_seeds_expected_shape_pre_kickoff(self):
        call_command("seed_demo_weekend", stdout=StringIO())
        self.assertTrue(Family.objects.filter(slug=dw.DEMO_SLUG).exists())
        self.assertTrue(
            Pool.objects.filter(family__slug=dw.DEMO_SLUG,
                                slug=dw.DEMO_POOL_SLUG).exists())
        games = GamesAndScores.objects.filter(gameseason=dw.DEMO_SEASON)
        self.assertEqual(games.count(), len(dw.GAMES))
        # Every game seeded pre-kickoff: not started, scoreless, ungraded.
        for g in games:
            self.assertEqual(g.statusType, "notstarted")
            self.assertEqual(g.homeTeamScore, 0)
            self.assertFalse(g.gameScored)
        expected_picks = sum(len(cfg["picks"]) for cfg in dw.PICKS.values())
        self.assertEqual(
            GamePicks.objects.filter(gameseason=dw.DEMO_SEASON).count(),
            expected_picks)

    def test_wipe_removes_everything(self):
        call_command("seed_demo_weekend", stdout=StringIO())
        call_command("seed_demo_weekend", "--wipe", stdout=StringIO())
        self.assertFalse(Family.objects.filter(slug=dw.DEMO_SLUG).exists())
        self.assertEqual(
            GamesAndScores.objects.filter(gameseason=dw.DEMO_SEASON).count(), 0)

    def test_make_current_and_print(self):
        currentSeason.objects.create(season=2627)
        call_command("seed_demo_weekend", "--make-current", stdout=StringIO())
        self.assertEqual(currentSeason.objects.first().season, dw.DEMO_SEASON)
        out = StringIO()
        call_command("seed_demo_weekend", "--print-current-season", stdout=out)
        self.assertEqual(out.getvalue().strip(), str(dw.DEMO_SEASON))

    def test_refuses_without_debug(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command("seed_demo_weekend", stdout=StringIO())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_api.tests.test_seed_demo_weekend -v2`
Expected: FAIL — unknown command `seed_demo_weekend`.

- [ ] **Step 3: Write minimal implementation**

First read `pickem/pickem_api/management/commands/seed_demo_week.py` and `UserProfile` in `pickem_homepage/models.py` for exact field names. Then create `pickem/pickem_api/management/commands/seed_demo_weekend.py`:

```python
"""Seed the isolated live-sim demo league PRE-kickoff (see demo_weekend.py).

Unlike seed_demo_week (which seeds finished games), this seeds a full ~13-game
weekend with games not-yet-started, ready for simulate_weekend to drive. All
data is keyed to DEMO_SLUG + DEMO_SEASON (9999); --wipe removes it. Dev-only.
"""
from datetime import timedelta

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pickem_api.demo_weekend import (
    DEMO_POOL_SLUG, DEMO_SEASON, DEMO_SLUG, DEMO_WEEK, GAMES, PICKS,
    PLAYERS, TEAMS,
)
from pickem_api.models import (
    Family, FamilyAuditLog, FamilyMembership, GamePicks, GamesAndScores,
    Pool, PoolSettings, Teams, currentSeason, userPoints, userSeasonPoints,
    userStats,
)


class Command(BaseCommand):
    help = "Seed (or --wipe) the isolated live-sim demo weekend. Dev-only."

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true")
        parser.add_argument("--owner", default=None,
                            help="Real username to add as OWNER so it's browsable.")
        parser.add_argument("--make-current", action="store_true",
                            help="Point the currentSeason singleton at 9999.")
        parser.add_argument("--print-current-season", action="store_true",
                            help="Print the current season int and exit.")

    def handle(self, *args, **options):
        if not django_settings.DEBUG:
            raise CommandError("seed_demo_weekend is a dev tool; DEBUG must be on.")

        if options["print_current_season"]:
            row = currentSeason.objects.first()
            self.stdout.write(str(row.season if row else ""))
            return
        if options["make_current"]:
            row = currentSeason.objects.first()
            if row is None:
                row = currentSeason.objects.create(season=DEMO_SEASON)
            else:
                row.season = DEMO_SEASON
                row.save(update_fields=["season"])
            self.stdout.write(self.style.SUCCESS(
                f"currentSeason set to {DEMO_SEASON}."))
            return
        if options["wipe"]:
            self._wipe()
            return

        family, _ = Family.objects.get_or_create(
            slug=DEMO_SLUG,
            defaults={"name": "Demo Live Sim", "status": Family.Status.ACTIVE})
        pool, _ = Pool.objects.get_or_create(
            family=family, slug=DEMO_POOL_SLUG,
            defaults={"name": "Demo Pool", "season": DEMO_SEASON,
                      "competition": "nfl", "status": Pool.Status.ACTIVE,
                      "is_default": True})
        PoolSettings.objects.get_or_create(pool=pool)

        users = {}
        for username in PLAYERS:
            user, _ = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"})
            users[username] = user
            FamilyMembership.objects.get_or_create(
                family=family, user=user,
                defaults={"role": FamilyMembership.Role.MEMBER,
                          "status": FamilyMembership.Status.ACTIVE})
            # UserProfile: only set fields confirmed to exist (see note above).
            self._ensure_profile(user)

        owner_username = options.get("owner")
        if owner_username:
            owner = User.objects.filter(username=owner_username).first()
            if owner is None:
                raise CommandError(f"--owner user '{owner_username}' not found.")
            FamilyMembership.objects.get_or_create(
                family=family, user=owner,
                defaults={"role": FamilyMembership.Role.OWNER,
                          "status": FamilyMembership.Status.ACTIVE})

        for team_id, slug, name, color in TEAMS:
            Teams.objects.update_or_create(id=team_id, defaults=dict(
                gameseason=DEMO_SEASON, teamNameSlug=slug, teamNameName=name,
                teamLogo="/static/images/nfl.svg", teamWins=0, teamLosses=0,
                teamTies=0, color=color, alternateColor="334155"))

        base = timezone.now()
        for g in GAMES:
            # Kickoff timestamps spread so the scores page ordering looks real.
            kickoff = base + timedelta(hours=g["kickoff_frac"] * 72)
            GamesAndScores.objects.update_or_create(id=g["id"], defaults={
                "slug": f'{g["home"]}-{g["away"]}', "competition": "nfl",
                "gameWeek": DEMO_WEEK, "gameyear": "2099",
                "gameseason": DEMO_SEASON, "startTimestamp": kickoff,
                "statusType": "notstarted", "statusTitle": "Scheduled",
                "gameWinner": "", "gameScored": False,
                "tieBreakerGame": g["tiebreaker"],
                "homeTeamId": g["id"] * 10 + 1, "homeTeamSlug": g["home"],
                "homeTeamName": g["home_name"], "homeTeamScore": 0,
                "awayTeamId": g["id"] * 10 + 2, "awayTeamSlug": g["away"],
                "awayTeamName": g["away_name"], "awayTeamScore": 0})

        games_by_id = {g["id"]: g for g in GAMES}
        pick_count = 0
        for username, cfg in PICKS.items():
            user = users[username]
            for game_id, pick in cfg["picks"].items():
                g = games_by_id[game_id]
                GamePicks.objects.update_or_create(
                    id=f"{pool.id}-{user.id}-{game_id}", defaults={
                        "pool": pool, "pick_game_id": game_id,
                        "slug": f'{g["home"]}-{g["away"]}', "userID": str(user.id),
                        "uid": user.id, "userEmail": user.email,
                        "gameWeek": DEMO_WEEK, "gameyear": "2099",
                        "gameseason": DEMO_SEASON, "competition": "nfl",
                        "pick": pick, "pick_correct": False,
                        "tieBreakerScore": cfg["tb_score"] if g["tiebreaker"] else None,
                        "tieBreakerYards": cfg["tb_yards"] if g["tiebreaker"] else None})
                pick_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded '{family.name}' (season {DEMO_SEASON}): {len(users)} players, "
            f"{len(GAMES)} pre-kickoff games, {pick_count} picks. "
            f"Run simulate_weekend to drive it."))

    def _ensure_profile(self, user):
        """Best-effort UserProfile with a favorite team + tagline if the model
        supports them. Kept defensive so a schema drift can't break seeding."""
        try:
            from pickem_homepage.models import UserProfile
        except Exception:
            return
        UserProfile.objects.get_or_create(
            user=user, defaults={"tagline": "Demo player"})

    def _wipe(self):
        family = Family.objects.filter(slug=DEMO_SLUG).first()
        GamePicks.objects.filter(gameseason=DEMO_SEASON).delete()
        userSeasonPoints.objects.filter(gameseason=DEMO_SEASON).delete()
        GamesAndScores.objects.filter(gameseason=DEMO_SEASON).delete()
        Teams.objects.filter(gameseason=DEMO_SEASON).delete()
        if family:
            FamilyAuditLog.objects.filter(family=family).delete()
            FamilyMembership.objects.filter(family=family).delete()
            for pool in family.pools.all():
                GamePicks.objects.filter(pool=pool).delete()
                userSeasonPoints.objects.filter(pool=pool).delete()
                userPoints.objects.filter(pool=pool).delete()
                userStats.objects.filter(pool=pool).delete()
                PoolSettings.objects.filter(pool=pool).delete()
                pool.delete()
            family.delete()
        User.objects.filter(username__in=PLAYERS).delete()
        self.stdout.write(self.style.SUCCESS("Demo live-sim data wiped."))
```

> If `UserProfile` requires a `favorite_team` FK or the `tagline` field is named differently, adjust `_ensure_profile` to the real fields (or drop it). The test does not assert profile fields, so keep it minimal and non-fatal.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_api.tests.test_seed_demo_weekend -v2`
Expected: PASS (4 tests). If a model field name differs (e.g. `userSeasonPoints` has no `gameseason`), fix per the real model and re-run.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/management/commands/seed_demo_weekend.py \
        pickem/pickem_api/tests/test_seed_demo_weekend.py
git commit -m "feat(sim): seed_demo_weekend command (pre-kickoff slate + season pointer)"
```

---

### Task 3: `simulate_weekend` — tick engine + live score publishing

**Files:**
- Create: `pickem/pickem_api/management/commands/simulate_weekend.py`
- Test: `pickem/pickem_api/tests/test_simulate_weekend.py`

**Interfaces:**
- Consumes: `pickem_api.demo_weekend` (`GAMES`, `game_state_at`, `DEMO_SEASON`, `DEMO_WEEK`); `pickem_api.management.commands.update_games.maybe_publish_game_change`; `pickem_api.live_events.SCORE_TRIGGER_FIELDS`.
- Produces: management command `simulate_weekend` with options `--duration <sec>` (default 300), `--tick <sec>` (default 1.5), `--season <int>` (default `DEMO_SEASON`). This task delivers the clock + per-tick game mutation + score publishing; Task 4 adds finalize→pipeline scoring.

**Design of one tick:**
1. `frac = min(1.0, elapsed / duration)`.
2. For each game row (fetch once, keep in memory), compute `game_state_at(game_def, frac)`. If any `SCORE_TRIGGER_FIELDS` differ from the row, capture `before` (dict of those fields), apply the state to the row, `save()`, then `maybe_publish_game_change(before, after=row)`.
3. Sleep `--tick`.
4. Loop until `frac >= 1.0` and all games finished.

**Testability:** accept an injectable `sleep`/`now` is overkill; instead the test uses a tiny `--duration 0` (everything already `frac>=1.0` on the first tick → all games jump to final in one pass) and patches `time.sleep`. Assert publishes fired and rows reached `finished`.

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_api/tests/test_simulate_weekend.py`:

```python
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from pickem_api import demo_weekend as dw
from pickem_api.management.commands import simulate_weekend as sw
from pickem_api.models import GamesAndScores


@override_settings(DEBUG=True)
class SimulateWeekendScoreTests(TestCase):
    def setUp(self):
        call_command("seed_demo_weekend", stdout=StringIO())

    def test_refuses_non_demo_season(self):
        with self.assertRaises(CommandError):
            call_command("simulate_weekend", "--season", "2627",
                        stdout=StringIO())

    def test_duration_zero_finalizes_all_games_and_publishes(self):
        with mock.patch("time.sleep"), \
             mock.patch.object(sw, "maybe_publish_game_change") as pub:
            call_command("simulate_weekend", "--duration", "0", "--tick", "0",
                        stdout=StringIO())
        # Every game is now final with its scripted totals.
        for g in dw.GAMES:
            row = GamesAndScores.objects.get(id=g["id"])
            self.assertEqual(row.statusType, "finished")
            self.assertEqual(row.homeTeamScore, sum(g["home_line"]))
            self.assertEqual(row.gameWinner, dw.game_winner(g))
        # A score publish fired for each game that changed (all of them).
        self.assertGreaterEqual(pub.call_count, len(dw.GAMES))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_api.tests.test_simulate_weekend -v2`
Expected: FAIL — unknown command `simulate_weekend`.

- [ ] **Step 3: Write minimal implementation**

Create `pickem/pickem_api/management/commands/simulate_weekend.py` (Task 4 will extend `handle`'s finalize branch — leave the marked hook):

```python
"""Walk a compressed clock over the demo weekend, driving live score changes.

DEBUG-only, season-9999-only. Mutates GamesAndScores rows tick-by-tick per the
scripted geometry in demo_weekend.py and republishes via the SAME production
path update_games uses, so the /scores SSE stream sees byte-identical events.
Finalized games are scored through the real pipeline (see _finalize)."""
import time

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError

from pickem_api.demo_weekend import DEMO_SEASON, DEMO_WEEK, GAMES, game_state_at
from pickem_api.live_events import SCORE_TRIGGER_FIELDS
from pickem_api.management.commands.update_games import maybe_publish_game_change
from pickem_api.models import GamesAndScores


class Command(BaseCommand):
    help = "Replay the demo weekend live (dev-only, season 9999)."

    def add_arguments(self, parser):
        parser.add_argument("--duration", type=float, default=300.0,
                            help="Total wall-clock seconds (default 300).")
        parser.add_argument("--tick", type=float, default=1.5,
                            help="Real seconds between ticks (default 1.5).")
        parser.add_argument("--season", type=int, default=DEMO_SEASON)

    def handle(self, *args, **options):
        if not django_settings.DEBUG:
            raise CommandError("simulate_weekend is a dev tool; DEBUG must be on.")
        if options["season"] != DEMO_SEASON:
            raise CommandError(
                f"simulate_weekend only runs on season {DEMO_SEASON}.")

        duration = max(0.0, options["duration"])
        tick = max(0.0, options["tick"])
        defs_by_id = {g["id"]: g for g in GAMES}
        finalized = set()

        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            frac = 1.0 if duration == 0 else min(1.0, elapsed / duration)

            rows = list(GamesAndScores.objects.filter(gameseason=DEMO_SEASON))
            for row in rows:
                g = defs_by_id.get(row.id)
                if g is None:
                    continue
                state = game_state_at(g, frac)
                before = {f: getattr(row, f) for f in SCORE_TRIGGER_FIELDS}
                changed = any(before[f] != state[f] for f in SCORE_TRIGGER_FIELDS)
                if not changed:
                    continue
                for f, v in state.items():
                    setattr(row, f, v)
                row.save()
                maybe_publish_game_change(before, row)
                if state["statusType"] == "finished" and row.id not in finalized:
                    finalized.add(row.id)
                    self._finalize(row)  # Task 4 fills this in.
                self.stdout.write(
                    f"[frac={frac:.2f}] {row.slug}: {state['statusTitle']} "
                    f"{state['homeTeamScore']}-{state['awayTeamScore']}")

            if frac >= 1.0 and len(finalized) >= len(GAMES):
                break
            time.sleep(tick)

        self.stdout.write(self.style.SUCCESS("Weekend simulation complete."))

    def _finalize(self, row):
        """Hook: run the scoring pipeline when a game goes final. Filled in
        Task 4; a no-op here keeps Task 3 independently testable."""
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_api.tests.test_simulate_weekend -v2`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/management/commands/simulate_weekend.py \
        pickem/pickem_api/tests/test_simulate_weekend.py
git commit -m "feat(sim): simulate_weekend tick engine + live score publishing"
```

---

### Task 4: `simulate_weekend` finalize → scoring pipeline (standings drama)

**Files:**
- Modify: `pickem/pickem_api/management/commands/simulate_weekend.py` (fill `_finalize`, add end-of-week bonus/ranking)
- Test: `pickem/pickem_api/tests/test_simulate_weekend.py` (add integration test)

**Interfaces:**
- Consumes: `django.core.management.call_command`; existing commands `update_picks`, `update_standings`, `update_weekly_winners`, `update_rankings` (all accept `--season`; `update_weekly_winners` also `--week`).
- Produces: after a full run, `userSeasonPoints` for the demo pool reflects graded picks + weekly winner, and `EXPECTED_WEEK_WINNER` is the week's winner.

- [ ] **Step 1: Write the failing test**

Add to `pickem/pickem_api/tests/test_simulate_weekend.py`:

```python
    def test_full_run_grades_and_flips_to_expected_week_winner(self):
        from pickem_api.models import userSeasonPoints
        with mock.patch("time.sleep"):
            call_command("simulate_weekend", "--duration", "0", "--tick", "0",
                        stdout=StringIO())
        # The scripted tiebreaker resolves to EXPECTED_WEEK_WINNER. The winner
        # flag lives on userSeasonPoints for the demo week; find who has it.
        winners = userSeasonPoints.objects.filter(
            gameseason=dw.DEMO_SEASON, **{f"week{dw.DEMO_WEEK}Winner": True})
        winner_ids = {int(w.userID) for w in winners}
        from django.contrib.auth.models import User
        expected = User.objects.get(username=dw.EXPECTED_WEEK_WINNER)
        self.assertIn(expected.id, winner_ids)
```

> **Before writing the implementation**, confirm the real weekly-winner field name and the `userSeasonPoints` week-points/winner columns by reading `update_weekly_winners.py` and the `userSeasonPoints` model. The `week{N}Winner` / `week_{N}_points` names above are the plan's best guess from `standings_event_payload` (`week_{week}_points`) — **use the actual names** and adjust the test's `**{...}` filter accordingly.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_api.tests.test_simulate_weekend.SimulateWeekendScoreTests.test_full_run_grades_and_flips_to_expected_week_winner -v2`
Expected: FAIL — `_finalize` is a no-op, so no picks are graded and no winner is set.

- [ ] **Step 3: Write minimal implementation**

Replace the `_finalize` no-op and add a week-completion step. Edit `simulate_weekend.py`:

```python
from django.core.management import call_command
```

Replace `_finalize` and the post-loop success line:

```python
    def _finalize(self, row):
        """Score a just-finalized game through the real pipeline so the
        standings SSE fires. update_picks grades the game's picks;
        update_standings republishes the pool's live standings."""
        call_command("update_picks", season=DEMO_SEASON, verbosity=0)
        call_command("update_standings", season=DEMO_SEASON, verbosity=0)

    def _complete_week(self):
        """Once every game is final, award the weekly winner + ranks (bonus
        can flip the leaderboard) and republish standings a final time."""
        call_command("update_weekly_winners", season=DEMO_SEASON,
                     week=int(DEMO_WEEK), verbosity=0)
        call_command("update_rankings", season=DEMO_SEASON, verbosity=0)
        call_command("update_standings", season=DEMO_SEASON, verbosity=0)
```

Then call `self._complete_week()` right before the `break`:

```python
            if frac >= 1.0 and len(finalized) >= len(GAMES):
                self._complete_week()
                break
```

> If `update_weekly_winners` requires the week to be fully complete via a `--force` flag or a different signature, read its `add_arguments`/`handle` and pass what it needs. The goal: after this, the demo week has a winner set.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_api.tests.test_simulate_weekend -v2`
Expected: PASS (3 tests). If the winner isn't `EXPECTED_WEEK_WINNER`, the scripted `PICKS`/tiebreaker in `demo_weekend.py` need adjusting (the drama didn't resolve as designed) — tune `tb_score` guesses / contrarian picks until alice wins, then update `EXPECTED_WEEK_WINNER` if you deliberately change the intended winner.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/management/commands/simulate_weekend.py \
        pickem/pickem_api/tests/test_simulate_weekend.py
git commit -m "feat(sim): finalize games through real scoring pipeline (live standings)"
```

---

### Task 5: `scripts/live-sim.sh` orchestrator

**Files:**
- Create: `scripts/live-sim.sh` (executable)

**Interfaces:**
- Consumes: Docker (`redis:7-alpine`), `uv`, the three commands above, `/healthz`.
- Produces: a one-command entry point. No unit test — verified manually and with `bash -n` / `shellcheck`.

**Behavior:** capture the current season → set 9999 → seed → simulate, with a `trap` that always restores season, wipes demo data, and stops uvicorn + Redis.

- [ ] **Step 1: Write the script**

Create `scripts/live-sim.sh`:

```bash
#!/usr/bin/env bash
# Live-weekend simulation harness (DEV ONLY). Brings up throwaway Redis + an
# ASGI server, points the site at the isolated demo season (9999), replays a
# dramatized ~13-game weekend in ~5 min, then restores everything.
#
# Usage: scripts/live-sim.sh <your-username> [duration_seconds]
set -euo pipefail

OWNER="${1:?Usage: scripts/live-sim.sh <your-username> [duration_seconds]}"
DURATION="${2:-300}"
REDIS_NAME="pickem-live-sim-redis"
PORT=8000
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/pickem"

export DEBUG=True
export REDIS_URL="redis://localhost:6379/0"

UVICORN_PID=""
OLD_SEASON=""

cleanup() {
  echo "== teardown =="
  if [[ -n "$OLD_SEASON" ]]; then
    uv run python manage.py seed_demo_weekend --make-current >/dev/null 2>&1 || true
    # Restore the captured real season via a tiny shell one-liner.
    uv run python manage.py shell -c \
      "from pickem_api.models import currentSeason as c; r=c.objects.first();\
 r and (setattr(r,'season',$OLD_SEASON) or r.save(update_fields=['season']))" \
      >/dev/null 2>&1 || true
  fi
  uv run python manage.py seed_demo_weekend --wipe >/dev/null 2>&1 || true
  [[ -n "$UVICORN_PID" ]] && kill "$UVICORN_PID" >/dev/null 2>&1 || true
  docker rm -f "$REDIS_NAME" >/dev/null 2>&1 || true
  echo "== done =="
}
trap cleanup EXIT INT TERM

echo "== starting throwaway Redis =="
docker rm -f "$REDIS_NAME" >/dev/null 2>&1 || true
docker run -d --rm -p 6379:6379 --name "$REDIS_NAME" redis:7-alpine >/dev/null

echo "== launching uvicorn on :$PORT =="
uv run uvicorn pickem.asgi:application --host 0.0.0.0 --port "$PORT" \
  --log-level warning &
UVICORN_PID=$!

echo "== waiting for /healthz =="
for _ in $(seq 1 60); do
  if curl -sf "http://localhost:$PORT/healthz" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -sf "http://localhost:$PORT/healthz" >/dev/null || { echo "server never came up"; exit 1; }

echo "== capturing current season =="
OLD_SEASON="$(uv run python manage.py seed_demo_weekend --print-current-season | tail -n1 | tr -dc '0-9')"
echo "captured season: ${OLD_SEASON:-<none>}"

echo "== seeding demo weekend + pointing season at 9999 =="
uv run python manage.py seed_demo_weekend --owner "$OWNER"
uv run python manage.py seed_demo_weekend --make-current

cat <<EOF

  ┌───────────────────────────────────────────────────────────┐
  │ Open http://localhost:$PORT and sign in as $OWNER
  │ Watch:  /scores  (select Week $(python -c 'import sys' 2>/dev/null; echo 1))
  │         the lobby Week Points panel  (demo family/pool)
  │         /standings
  │ Simulation runs for ${DURATION}s. Ctrl-C to stop early (auto-cleans up).
  └───────────────────────────────────────────────────────────┘

EOF

echo "== running simulation (${DURATION}s) =="
uv run python manage.py simulate_weekend --duration "$DURATION"

echo "Simulation finished; cleaning up."
```

- [ ] **Step 2: Make executable + lint**

```bash
chmod +x scripts/live-sim.sh
bash -n scripts/live-sim.sh          # syntax check
command -v shellcheck >/dev/null && shellcheck scripts/live-sim.sh || true
```
Expected: `bash -n` prints nothing (valid). Address any shellcheck errors (warnings on the `trap`/`kill` idioms are acceptable).

- [ ] **Step 3: Manual smoke (documented, not automated)**

With Docker running and the local DB up:
```bash
scripts/live-sim.sh <your-username> 60
```
Expected: Redis container starts, uvicorn serves `/healthz`, seeding prints counts, the sim logs `[frac=..]` lines, and on exit the teardown restores the season and wipes demo data. Verify afterward:
```bash
cd pickem && DEBUG=True uv run python manage.py shell -c \
 "from pickem_api.models import currentSeason,GamesAndScores as G; \
  print('season=',currentSeason.objects.first().season); \
  print('demo_games=',G.objects.filter(gameseason=9999).count())"
```
Expected: season restored to your real season, `demo_games= 0`.

- [ ] **Step 4: Commit**

```bash
git add scripts/live-sim.sh
git commit -m "feat(sim): live-sim.sh orchestrator (redis+uvicorn+season swap+teardown)"
```

---

### Task 6: Documentation

**Files:**
- Modify: `CLAUDE.md` (add a short "Live Weekend Simulation" subsection under Data Pipeline or Common Development Commands)

- [ ] **Step 1: Add docs**

Add to `CLAUDE.md` a subsection describing the harness:

```markdown
### Live Weekend Simulation (dev-only)

`scripts/live-sim.sh <your-username> [duration]` stands up throwaway Redis +
uvicorn, points `currentSeason` at the isolated demo season (9999), seeds a
~13-game weekend, and replays it live over ~5 min so the SSE-driven surfaces
(`/scores`, lobby Week Points, `/standings`) can be watched updating. It tears
everything down (restoring your real season) on exit. Requires Docker + DEBUG.
Building blocks (all DEBUG-only, season-9999-only):
`seed_demo_weekend`, `simulate_weekend` (see `pickem_api/demo_weekend.py`).
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document the live-weekend simulation harness"
```

---

## Self-Review

**Spec coverage:**
- Redis + uvicorn + REDIS_URL brought up automatically → Task 5. ✓
- Isolated demo league season 9999, browsable via `--owner` → Task 2. ✓
- ~13 games, ~8 players, waves, scripted MNF tiebreaker flip → Task 1 (data) + Task 4 (verified by test). ✓
- `/scores` live via SSE (current-season = 9999) → Task 3 (publish) + Task 5 (`--make-current`). ✓
- Lobby Week Points + `/standings` live reorder → Task 4 (`update_standings` per finalize). ✓
- Teardown restores `currentSeason`, wipes demo, stops uvicorn/Redis, idempotent → Task 5 `trap`. ✓
- DEBUG-guard + season-9999-guard → Tasks 2, 3 (tested). ✓
- Reuse production publish/scoring paths, no reimplemented events → Tasks 3, 4. ✓
- Tests mirroring `test_update_*_publish` → Tasks 1–4. ✓
- statusType enum follow-up explicitly out of scope → not a task (correct). ✓

**Placeholder scan:** `_finalize` is an intentional, tested no-op in Task 3, filled in Task 4 (not a placeholder — each task is independently testable). Model-field-name confirmations (Task 2 `UserProfile`, Task 4 weekly-winner column) are called out as read-first steps with the real fallback named, not left as "TODO". No "TBD"/"handle edge cases"/bare "write tests" remain.

**Type consistency:** `game_state_at`/`game_winner`/`DEMO_*`/`GAMES`/`PICKS` names are used identically across Tasks 1–4. `maybe_publish_game_change(before, after)` signature matches `update_games.py`. `SCORE_TRIGGER_FIELDS` imported from `live_events` (its real home). Command option names (`--duration`/`--tick`/`--season`/`--make-current`/`--print-current-season`/`--wipe`/`--owner`) are consistent between the commands and the orchestrator.

**Known read-first risks (flagged in-task, not blockers):** exact `userSeasonPoints` weekly-winner column name (Task 4), `UserProfile` field names (Task 2), and `update_weekly_winners` completion semantics (Task 4) must be confirmed against the models/commands during implementation — each task names the fallback and the file to read.
