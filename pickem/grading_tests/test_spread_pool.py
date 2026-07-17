"""Scenario 4 — against-the-spread pools.

There is no spread grading backend yet: ``pick_type=against_spread`` exists
as a locked settings value (disabled in every form, rejected server-side)
and ``update_picks`` grades every pool straight-up regardless.

This file therefore has two jobs:

1. A live **canary** that pins today's behavior: an against_spread pool is
   still graded straight-up. The moment a spread backend changes grading,
   the canary fails — that failure is the signal to delete the canary and
   enable the scaffolded scenarios below.
2. Skipped **scaffolds** for the four spread scenarios (favorite covers,
   favorite wins without covering, underdog wins outright, push), written
   against the documented spread convention (``GamesAndScores.spread`` is
   positive when it favors the home team) with full expected standings.
"""

from unittest import skip

from pickem_api.models import PoolSettings

from .factories import create_game, create_league, finish_game, make_pick
from .harness import GradingTestCase

SPREAD_NOT_IMPLEMENTED = (
    "against_spread grading is not implemented (locked in PoolSettings forms); "
    "enable when the spread backend lands and the canary test fails"
)


def spread_league():
    return create_league(
        "alice", "bob",
        pick_type=PoolSettings.PickType.AGAINST_SPREAD,
    )


class SpreadPoolCanaryTest(GradingTestCase):
    """Fails the day spread grading lands — then flip the scaffolds on."""

    def test_against_spread_pool_currently_grades_straight_up(self):
        league = spread_league()
        # Home favored by 7; home wins 20-17 → wins outright, does NOT cover.
        game = create_game(1, spread=7.0, mnf=True)
        make_pick(league.pool, league["alice"], game, "home")
        make_pick(league.pool, league["bob"], game, "away")
        finish_game(game, 20, 17)

        self.run_pipeline()

        # Straight-up grading: alice (outright winner) scores even though the
        # favorite failed to cover. If this assertion starts failing, spread
        # grading has landed: delete this test and un-skip the class below.
        self.assertStandings(league.pool, [
            (league["alice"], 3, 1),  # 1 win + 2 weekly-winner bonus
            (league["bob"], 0, 2),
        ])


@skip(SPREAD_NOT_IMPLEMENTED)
class SpreadPoolTest(GradingTestCase):
    """Expected against-the-spread behavior, ready to enable."""

    def test_favorite_covers(self):
        league = spread_league()
        game = create_game(1, spread=7.0, mnf=True)  # home favored by 7
        make_pick(league.pool, league["alice"], game, "home")
        make_pick(league.pool, league["bob"], game, "away")
        finish_game(game, 27, 10)  # home wins by 17: covers

        self.run_pipeline()

        self.assertStandings(league.pool, [
            (league["alice"], 3, 1),
            (league["bob"], 0, 2),
        ])

    def test_favorite_wins_but_does_not_cover(self):
        league = spread_league()
        game = create_game(1, spread=7.0, mnf=True)
        make_pick(league.pool, league["alice"], game, "home")
        make_pick(league.pool, league["bob"], game, "away")
        finish_game(game, 20, 17)  # home wins by 3: fails to cover

        self.run_pipeline()

        # Against the spread the underdog side is the winning ticket.
        self.assertStandings(league.pool, [
            (league["bob"], 3, 1),
            (league["alice"], 0, 2),
        ])

    def test_underdog_wins_outright(self):
        league = spread_league()
        game = create_game(1, spread=7.0, mnf=True)
        make_pick(league.pool, league["alice"], game, "home")
        make_pick(league.pool, league["bob"], game, "away")
        finish_game(game, 13, 24)  # underdog wins outright

        self.run_pipeline()

        self.assertStandings(league.pool, [
            (league["bob"], 3, 1),
            (league["alice"], 0, 2),
        ])

    def test_push_awards_tie_points_to_both_sides(self):
        league = spread_league()
        league.settings.tie_points = 1
        league.settings.save()
        game = create_game(1, spread=7.0, mnf=True)
        make_pick(league.pool, league["alice"], game, "home")
        make_pick(league.pool, league["bob"], game, "away")
        finish_game(game, 24, 17)  # home wins by exactly 7: push

        self.run_pipeline()

        # A push is a spread-world tie: both sides get the pool's tie_points
        # and there is no weekly winner (nobody "scored" a win).
        self.assertWeek(league.pool, league["alice"], 1, points=1, winner=False)
        self.assertWeek(league.pool, league["bob"], 1, points=1, winner=False)
