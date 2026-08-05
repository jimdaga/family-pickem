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
