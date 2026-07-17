"""Scenario 5 — tenant (family) isolation.

One schema fact shapes these tests: NFL games are global per season —
families share the slate (there is no per-family game table). Isolation
lives one level down, in ``GamePicks.pool``, ``userSeasonPoints.pool`` and
per-pool ``PoolSettings``. So the assertions here are:

* one pipeline run grades every family, but each family's results are
  computed only from its own picks and rules;
* standings are exhaustive per pool — a user from another family showing
  up in a pool's standings fails the test;
* the same person in two families is two independent competitors;
* pool-scoped recompute (``update_standings --pool``) touches nothing else.
"""

from django.core.management import call_command
from io import StringIO

from pickem_api.models import userSeasonPoints

from .factories import create_game, create_league, create_user, finish_game, join_family, make_pick
from .harness import GradingTestCase


def _shared_slate():
    """The league-independent NFL week both families play against."""
    return [create_game(1), create_game(1), create_game(1, mnf=True)]


class TenantIsolationTest(GradingTestCase):

    def test_one_pipeline_run_grades_each_family_independently(self):
        games = _shared_slate()
        smith = create_league("alice", "bob", family_name="Smith")
        jones = create_league("cara", "dan", family_name="Jones")

        # Same slate, opposite convictions.
        picks = {
            (smith, "alice"): ["home", "home", "home"],  # 3 correct
            (smith, "bob"): ["away", "home", "away"],    # 1 correct
            (jones, "cara"): ["away", "away", "home"],   # 1 correct
            (jones, "dan"): ["home", "away", "home"],    # 2 correct
        }
        for (league, username), sides in picks.items():
            for game, side in zip(games, sides):
                make_pick(league.pool, league[username], game, side)
        for game in games:
            finish_game(game, 24, 17)  # home sweeps

        self.run_pipeline()  # a single run — production grades all tenants

        # Exhaustive per pool: correct numbers AND nobody leaked across.
        self.assertStandings(smith.pool, [
            (smith["alice"], 5, 1),  # 3 + 2 bonus
            (smith["bob"], 1, 2),
        ])
        self.assertStandings(jones.pool, [
            (jones["dan"], 4, 1),    # 2 + 2 bonus
            (jones["cara"], 1, 2),
        ])

    def test_same_person_in_two_families_is_two_independent_competitors(self):
        games = _shared_slate()
        smith = create_league("alice", family_name="Smith")
        jones = create_league("cara", family_name="Jones")
        sam = create_user("sam")
        join_family(smith.family, sam)
        join_family(jones.family, sam)

        # sam sweeps in Smith, goes 0-for-3 in Jones.
        for game in games:
            make_pick(smith.pool, sam, game, "home")
            make_pick(jones.pool, sam, game, "away")
            make_pick(smith.pool, smith["alice"], game, "away")
            make_pick(jones.pool, jones["cara"], game, "home")
        for game in games:
            finish_game(game, 21, 14)

        self.run_pipeline()

        self.assertStandings(smith.pool, [
            (sam, 5, 1),             # 3 + 2 bonus
            (smith["alice"], 0, 2),
        ])
        self.assertStandings(jones.pool, [
            (jones["cara"], 5, 1),
            (sam, 0, 2),
        ])

    def test_rule_configuration_is_isolated_per_family(self):
        games = _shared_slate()
        smith = create_league("alice", "bob", family_name="Smith")  # defaults
        jones = create_league(
            "cara", "dan", family_name="Jones",
            win_points=3, weekly_winner_points=10,
        )

        # Identical pick patterns in both pools.
        for league, top, other in ((smith, "alice", "bob"), (jones, "cara", "dan")):
            for game in games:
                make_pick(league.pool, league[top], game, "home")
                make_pick(league.pool, league[other], game, "away")
        for game in games:
            finish_game(game, 28, 3)

        self.run_pipeline()

        # Same performance, different rules, different numbers — and neither
        # pool's configuration bled into the other.
        self.assertStandings(smith.pool, [
            (smith["alice"], 5, 1),   # 3×1 + 2
            (smith["bob"], 0, 2),
        ])
        self.assertStandings(jones.pool, [
            (jones["cara"], 19, 1),   # 3×3 + 10
            (jones["dan"], 0, 2),
        ])

    def test_pool_scoped_recompute_leaves_other_pools_untouched(self):
        games = _shared_slate()
        smith = create_league("alice", family_name="Smith")
        jones = create_league("cara", family_name="Jones")
        for game in games:
            make_pick(smith.pool, smith["alice"], game, "home")
            make_pick(jones.pool, jones["cara"], game, "home")
        for game in games:
            finish_game(game, 17, 10)

        # Grade picks globally (as production does), then recompute standings
        # for the Smith pool only.
        out = StringIO()
        call_command("update_picks", season=smith.pool.season, stdout=out)
        call_command(
            "update_standings",
            season=smith.pool.season, pool=smith.pool.id, stdout=out,
        )

        self.assertEqual(
            self.standings_row(smith.pool, smith["alice"]).total_points, 3
        )
        self.assertFalse(
            userSeasonPoints.objects.filter(pool=jones.pool).exists(),
            "pool-scoped recompute must not create rows for other pools",
        )

        # The regular full pipeline then brings Jones up to date too.
        self.run_pipeline()
        self.assertStandings(jones.pool, [(jones["cara"], 5, 1)])
