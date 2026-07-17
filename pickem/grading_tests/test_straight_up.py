"""Scenario 1 — straight-up pools.

Clear winners, multiple users, exact point totals and rankings, plus the
straight-up edge cases the pipeline must survive: a real NFL tie, a missed
pick under the default policy, and re-running the pipeline (the scheduler
runs it every minute in production, so idempotency is a hard requirement).
"""

from pickem_api.models import GamePicks, GamesAndScores

from .factories import create_game, create_league, finish_game, make_pick
from .harness import GradingTestCase


class StraightUpPoolTest(GradingTestCase):

    def test_clear_winner_single_week(self):
        league = create_league("alice", "bob", "carol")
        g1 = create_game(1)
        g2 = create_game(1)
        g3 = create_game(1)
        mnf = create_game(1, mnf=True)

        # alice 4 correct, bob 2, carol 1 (picks made before results exist).
        for game, alice_side, bob_side, carol_side in [
            (g1, "home", "home", "away"),
            (g2, "away", "home", "home"),
            (g3, "home", "away", "home"),
            (mnf, "home", "home", "away"),
        ]:
            make_pick(league.pool, league["alice"], game, alice_side)
            make_pick(league.pool, league["bob"], game, bob_side)
            make_pick(league.pool, league["carol"], game, carol_side)

        finish_game(g1, 27, 10)   # home wins
        finish_game(g2, 14, 31)   # away wins
        finish_game(g3, 21, 17)   # home wins
        finish_game(mnf, 24, 21)  # home wins

        self.run_pipeline()

        self.assertWeek(league.pool, league["alice"], 1, points=4, bonus=2, winner=True)
        self.assertWeek(league.pool, league["bob"], 1, points=2, winner=False)
        self.assertWeek(league.pool, league["carol"], 1, points=1, winner=False)
        self.assertStandings(league.pool, [
            (league["alice"], 6, 1),   # 4 wins + 2 weekly-winner bonus
            (league["bob"], 2, 2),
            (league["carol"], 1, 3),
        ])

    def test_two_week_season_accumulates_totals_and_ranks(self):
        league = create_league("alice", "bob", "carol")

        # Week 1: alice dominates (see test above for the shape).
        w1 = [create_game(1), create_game(1), create_game(1, mnf=True)]
        sides_w1 = {
            "alice": ["home", "home", "home"],   # 3 correct
            "bob": ["home", "away", "away"],     # 1 correct
            "carol": ["away", "home", "away"],   # 1 correct
        }
        for username, sides in sides_w1.items():
            for game, side in zip(w1, sides):
                make_pick(league.pool, league[username], game, side)
        for game in w1:
            finish_game(game, 24, 17)  # home wins all three
        self.run_pipeline()

        # Week 2: bob dominates. The scheduler runs between weeks, so the
        # pipeline runs once per completed week — same as production.
        w2 = [create_game(2), create_game(2), create_game(2, mnf=True)]
        sides_w2 = {
            "alice": ["away", "away", "home"],   # 1 correct
            "bob": ["home", "home", "home"],     # 3 correct
            "carol": ["home", "away", "away"],   # 1 correct
        }
        for username, sides in sides_w2.items():
            for game, side in zip(w2, sides):
                make_pick(league.pool, league[username], game, side)
        for game in w2:
            finish_game(game, 30, 20)  # home wins all three
        self.run_pipeline()

        self.assertWeek(league.pool, league["alice"], 1, points=3, bonus=2, winner=True)
        self.assertWeek(league.pool, league["bob"], 2, points=3, bonus=2, winner=True)
        # alice: (3+2) + 1 = 6; bob: 1 + (3+2) = 6 — tied for first.
        self.assertStandings(league.pool, [
            (league["alice"], 6, 1),
            (league["bob"], 6, 1),
            (league["carol"], 2, 3),
        ])

    def test_real_nfl_tie_completes_week_and_scores_no_pick(self):
        league = create_league("alice", "bob")
        tie_game = create_game(1)
        g2 = create_game(1)
        mnf = create_game(1, mnf=True)

        for game in (tie_game, g2, mnf):
            make_pick(league.pool, league["alice"], game, "home")
            make_pick(league.pool, league["bob"], game, "away")

        finish_game(tie_game, 20, 20)  # ends in a real NFL tie
        finish_game(g2, 24, 17)
        finish_game(mnf, 31, 28)

        self.run_pipeline()

        # Nobody's tie-game pick is correct (default tie_points=0), but the
        # tie must not wedge the week: it gets marked scored and the weekly
        # winner is still awarded on the remaining games.
        tie_game.refresh_from_db()
        self.assertTrue(tie_game.gameScored)
        self.assertFalse(
            GamePicks.objects.filter(pick_game_id=tie_game.id, pick_correct=True).exists()
        )
        self.assertWeek(league.pool, league["alice"], 1, points=2, bonus=2, winner=True)
        self.assertStandings(league.pool, [
            (league["alice"], 4, 1),
            (league["bob"], 0, 2),
        ])

    def test_missed_pick_scores_zero_under_default_policy(self):
        league = create_league("alice", "bob")
        g1 = create_game(1)
        mnf = create_game(1, mnf=True)

        make_pick(league.pool, league["alice"], g1, "home")
        make_pick(league.pool, league["alice"], mnf, "home")
        make_pick(league.pool, league["bob"], mnf, "home")  # bob skipped g1

        finish_game(g1, 28, 7)
        finish_game(mnf, 24, 21)

        self.run_pipeline()

        # zero_points is the default policy: no auto pick is generated.
        self.assertFalse(GamePicks.objects.filter(auto_pick=True).exists())
        self.assertStandings(league.pool, [
            (league["alice"], 4, 1),  # 2 wins + 2 bonus
            (league["bob"], 1, 2),
        ])

    def test_pipeline_rerun_is_idempotent(self):
        league = create_league("alice", "bob")
        g1 = create_game(1)
        mnf = create_game(1, mnf=True)
        for game in (g1, mnf):
            make_pick(league.pool, league["alice"], game, "home")
            make_pick(league.pool, league["bob"], game, "away")
        finish_game(g1, 21, 14)
        finish_game(mnf, 27, 24)

        self.run_pipeline()
        self.run_pipeline()  # scheduler fires again a minute later

        expected = [
            (league["alice"], 4, 1),  # bonus applied exactly once
            (league["bob"], 0, 2),
        ]
        self.assertStandings(league.pool, expected)
        self.assertWeek(league.pool, league["alice"], 1, points=2, bonus=2, winner=True)


class WeekCompletionGateTest(GradingTestCase):
    """The weekly bonus must never be awarded while games are still live."""

    def test_no_award_until_last_game_of_week_finishes(self):
        league = create_league("alice", "bob")
        g1 = create_game(1)
        mnf = create_game(1, mnf=True)
        for game in (g1, mnf):
            make_pick(league.pool, league["alice"], game, "home")
            make_pick(league.pool, league["bob"], game, "away")

        finish_game(g1, 21, 14)  # MNF still to be played

        self.run_pipeline()
        self.assertWeek(league.pool, league["alice"], 1, points=1, winner=False)
        self.assertFalse(
            GamesAndScores.objects.get(pk=mnf.pk).gameScored
        )

        finish_game(mnf, 27, 24)
        self.run_pipeline()
        self.assertWeek(league.pool, league["alice"], 1, points=2, bonus=2, winner=True)
