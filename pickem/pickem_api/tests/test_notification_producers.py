from django.contrib.auth.models import User
from django.test import TestCase

from pickem_api.models import Family, Notification, Pool, userSeasonPoints
from pickem_api.notifications import publish_week_winner_digest


class WeekWinnerDigestTests(TestCase):
    """One digest per participant naming every pool of theirs that was awarded."""

    def setUp(self):
        self.season = 2526
        self.week = 5

        self.smith = Family.objects.create(name="Smith Family", slug="smith")
        self.jones = Family.objects.create(name="Jones Family", slug="jones")
        self.smith_pool = Pool.objects.create(
            family=self.smith, name="Smith Pool", slug="smith-pool",
            season=self.season, status=Pool.Status.ACTIVE,
        )
        self.jones_pool = Pool.objects.create(
            family=self.jones, name="Jones Pool", slug="jones-pool",
            season=self.season, status=Pool.Status.ACTIVE,
        )

        self.ana = User.objects.create_user(username="ana", email="ana@example.com")
        self.bo = User.objects.create_user(username="bo", email="bo@example.com")
        self.cy = User.objects.create_user(username="cy", email="cy@example.com")

    def _row(self, user, pool, points, winner=False):
        return userSeasonPoints.objects.create(
            pool=pool,
            userEmail=user.email,
            userID=str(user.id),
            gameseason=self.season,
            gameyear="2025",
            **{
                f"week_{self.week}_points": points,
                f"week_{self.week}_winner": winner,
            },
        )

    def _pools(self):
        return [self.smith_pool, self.jones_pool]

    def test_winner_sees_their_own_win_in_the_title(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.bo, self.smith_pool, 11)

        created = publish_week_winner_digest(self.season, self.week, self._pools())

        self.assertEqual(created, 2)
        ana_note = Notification.objects.get(recipient=self.ana)
        self.assertEqual(ana_note.title, "You won Week 5!")
        # Exact format: "<family>: <winner> (<pts> pts)". A colon, not an em
        # dash -- the dash read badly in the panel.
        self.assertEqual(ana_note.body, "Smith Family: you (14 pts)")
        self.assertIn("Smith Family", ana_note.body)
        self.assertIn("you", ana_note.body)
        self.assertIn("14 pts", ana_note.body)

    def test_non_winner_sees_the_neutral_title_and_the_winners_name(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.bo, self.smith_pool, 11)

        publish_week_winner_digest(self.season, self.week, self._pools())

        bo_note = Notification.objects.get(recipient=self.bo)
        self.assertEqual(bo_note.title, "Week 5 winners")
        self.assertIn("Ana", bo_note.body)
        self.assertNotIn("you", bo_note.body)

    def test_multi_pool_member_gets_one_digest_listing_every_pool(self):
        # Ana plays in both families and wins one of them.
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.ana, self.jones_pool, 9)
        self._row(self.bo, self.jones_pool, 12, winner=True)

        publish_week_winner_digest(self.season, self.week, self._pools())

        notes = Notification.objects.filter(recipient=self.ana)
        self.assertEqual(notes.count(), 1, "one digest, not one per pool")
        body = notes.first().body
        self.assertIn("Smith Family", body)
        self.assertIn("Jones Family", body)
        self.assertIn("you", body)
        self.assertIn("Bo", body)
        # Won one of two, so the title names which -- see WeekWinnerTitleTests.
        self.assertEqual(notes.first().title, "You won Week 5 in Smith Family")

    def test_digest_links_to_a_pool_the_user_won(self):
        self._row(self.ana, self.jones_pool, 9)
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.bo, self.jones_pool, 12, winner=True)

        publish_week_winner_digest(self.season, self.week, self._pools())

        note = Notification.objects.get(recipient=self.ana)
        self.assertEqual(note.pool, self.smith_pool)
        self.assertIn("/smith/pools/smith-pool/standings/", note.url)

    def test_running_twice_creates_nothing_new(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.bo, self.smith_pool, 11)

        first = publish_week_winner_digest(self.season, self.week, self._pools())
        second = publish_week_winner_digest(self.season, self.week, self._pools())

        self.assertEqual(first, 2)
        self.assertEqual(second, 0, "pipeline re-runs must not duplicate")
        self.assertEqual(Notification.objects.count(), 2)

    def test_a_later_week_is_a_separate_digest(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        publish_week_winner_digest(self.season, self.week, self._pools())

        userSeasonPoints.objects.filter(pool=self.smith_pool).update(
            week_6_points=10, week_6_winner=True,
        )
        publish_week_winner_digest(self.season, 6, self._pools())

        self.assertEqual(Notification.objects.filter(recipient=self.ana).count(), 2)

    def test_pool_with_no_awarded_winner_is_skipped_entirely(self):
        self._row(self.ana, self.smith_pool, 14)  # no winner flag
        self._row(self.bo, self.jones_pool, 12, winner=True)

        publish_week_winner_digest(self.season, self.week, self._pools())

        # Ana is only in the unawarded pool, so she gets nothing.
        self.assertFalse(Notification.objects.filter(recipient=self.ana).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.bo).exists())

    def test_tied_winners_are_named_together(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.bo, self.smith_pool, 14, winner=True)
        self._row(self.cy, self.smith_pool, 9)

        publish_week_winner_digest(self.season, self.week, self._pools())

        cy_body = Notification.objects.get(recipient=self.cy).body
        self.assertIn("Ana", cy_body)
        self.assertIn("Bo", cy_body)
        # A tied winner sees themselves first, then the co-winner.
        ana_body = Notification.objects.get(recipient=self.ana).body
        self.assertIn("you & Bo", ana_body)

    def test_inactive_user_is_not_notified(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.bo, self.smith_pool, 11)
        self.bo.is_active = False
        self.bo.save(update_fields=["is_active"])

        created = publish_week_winner_digest(self.season, self.week, self._pools())

        self.assertEqual(created, 1)
        self.assertFalse(Notification.objects.filter(recipient=self.bo).exists())

    def test_body_stays_within_the_field_limit_for_many_pools(self):
        # A member of many families must not blow past body's 500 chars.
        pools = []
        for i in range(12):
            fam = Family.objects.create(
                name=f"A Very Long Family Name Number {i}", slug=f"fam-{i}",
            )
            pool = Pool.objects.create(
                family=fam, name=f"Pool {i}", slug=f"pool-{i}",
                season=self.season, status=Pool.Status.ACTIVE,
            )
            pools.append(pool)
            self._row(self.ana, pool, 10 + i, winner=True)

        publish_week_winner_digest(self.season, self.week, pools)

        body = Notification.objects.get(recipient=self.ana).body
        self.assertLessEqual(len(body), 500)
        self.assertIn("and 6 more", body)

    def test_returns_zero_when_no_pools_given(self):
        self.assertEqual(publish_week_winner_digest(self.season, self.week, []), 0)


class WeekWinnerCommandWiringTests(TestCase):
    """The producer must actually run from ``update_weekly_winners``.

    The unit tests above call publish_week_winner_digest directly; this one
    drives the real management command, so a broken import or a hook in the
    wrong place fails here rather than silently shipping a producer nothing
    ever calls.
    """

    class StubStats:
        def combined_yards(self, game_id):
            return 700

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from pickem_api.models import GamesAndScores, PoolSettings

        self.family = Family.objects.create(name="Smith Family", slug="smith")
        self.pool = Pool.objects.create(
            family=self.family, name="Pool", slug="main", season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )
        PoolSettings.objects.create(pool=self.pool)
        GamesAndScores.objects.create(
            id=900, slug="a-b", competition="nfl", gameWeek="1", gameyear="2025",
            gameseason=2526, startTimestamp=timezone.now(), statusType="finished",
            statusTitle="Final", gameScored=True,
            homeTeamId=1, homeTeamSlug="a", homeTeamName="A",
            awayTeamId=2, awayTeamSlug="b", awayTeamName="B",
        )
        GamesAndScores.objects.create(
            id=901, slug="c-d", competition="nfl", gameWeek="1", gameyear="2025",
            gameseason=2526, startTimestamp=timezone.now() + timedelta(days=1),
            statusType="finished", statusTitle="Final", gameScored=True,
            tieBreakerGame=True, homeTeamScore=24, awayTeamScore=20,
            homeTeamId=3, homeTeamSlug="c", homeTeamName="C",
            awayTeamId=4, awayTeamSlug="d", awayTeamName="D",
        )

        # Real Users, because the producer resolves userID back to a User.
        self.ana = User.objects.create_user(username="ana", email="ana@example.com")
        self.bo = User.objects.create_user(username="bo", email="bo@example.com")
        for user, points in ((self.ana, 12), (self.bo, 8)):
            userSeasonPoints.objects.create(
                pool=self.pool, gameseason=2526, userID=str(user.id),
                userEmail=user.email, week_1_points=points,
            )

    def _run(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        out = StringIO()
        with patch(
            "pickem_api.management.commands.update_weekly_winners.EspnGameStatsProvider"
        ) as provider:
            provider.return_value = self.StubStats()
            call_command("update_weekly_winners", season=2526, stdout=out, stderr=out)
        return out.getvalue()

    def test_command_awards_and_notifies(self):
        output = self._run()

        self.assertIn("awarded winners in 1 pool(s)", output)
        self.assertIn("sent 2 winner notification(s)", output)

        ana_note = Notification.objects.get(recipient=self.ana)
        self.assertEqual(ana_note.title, "You won Week 1!")
        self.assertEqual(ana_note.kind, Notification.Kind.WEEK_WINNER)
        self.assertEqual(
            Notification.objects.get(recipient=self.bo).title, "Week 1 winners",
        )

    def test_rerunning_the_command_does_not_duplicate(self):
        self._run()
        self._run()
        self.assertEqual(Notification.objects.count(), 2)

    def test_notification_failure_does_not_break_the_award(self):
        from unittest.mock import patch

        # The bonus points are the real work and are already committed by the
        # time we notify; a notification bug must not take the award down.
        # assertLogs both captures the traceback (keeping test output pristine)
        # and pins that the failure is actually logged rather than swallowed.
        with patch(
            "pickem_api.management.commands.update_weekly_winners."
            "publish_week_winner_digest",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertLogs(
                "pickem_api.management.commands.update_weekly_winners", level="ERROR",
            ) as logs:
                output = self._run()

        self.assertTrue(
            any("notifications failed" in m for m in logs.output),
            f"expected a logged failure, got {logs.output}",
        )
        self.assertIn("awarded winners in 1 pool(s)", output)
        self.assertIn("winner notifications failed", output)
        self.assertTrue(
            userSeasonPoints.objects.get(pool=self.pool, userID=str(self.ana.id))
            .week_1_winner
        )


class WeekWinnerTitleTests(TestCase):
    """The title has to distinguish winning one pool from sweeping them all.

    The body always carries the per-pool truth, but the title is what a reader
    sees at a glance in the bell without opening anything.
    """

    def setUp(self):
        self.season = 2526
        self.week = 5
        self.ana = User.objects.create_user(username="ana", email="ana@example.com")
        self.rival = User.objects.create_user(username="rival", email="r@example.com")

    def _pools(self, count):
        pools = []
        for i in range(count):
            family = Family.objects.create(name=f"Family {i}", slug=f"fam-{i}")
            pools.append(Pool.objects.create(
                family=family, name=f"Pool {i}", slug=f"pool-{i}",
                season=self.season, status=Pool.Status.ACTIVE,
            ))
        return pools

    def _seed(self, pools, ana_wins):
        for pool, ana_won in zip(pools, ana_wins):
            for user, points, won in (
                (self.ana, 14, ana_won), (self.rival, 9, not ana_won),
            ):
                userSeasonPoints.objects.create(
                    pool=pool, userEmail=user.email, userID=str(user.id),
                    gameseason=self.season, gameyear="2025",
                    **{
                        f"week_{self.week}_points": points,
                        f"week_{self.week}_winner": won,
                    },
                )

    def _title_for(self, ana_wins):
        pools = self._pools(len(ana_wins))
        self._seed(pools, ana_wins)
        publish_week_winner_digest(self.season, self.week, pools)
        return Notification.objects.get(recipient=self.ana).title

    def test_single_pool_win_stays_simple(self):
        self.assertEqual(self._title_for([True]), "You won Week 5!")

    def test_winning_one_of_several_names_the_pool(self):
        self.assertEqual(
            self._title_for([True, False, False]), "You won Week 5 in Family 0",
        )

    def test_winning_some_of_several_gives_the_ratio(self):
        self.assertEqual(
            self._title_for([True, True, False]), "You won Week 5 in 2 of 3 pools",
        )

    def test_sweeping_every_pool_is_called_out(self):
        self.assertEqual(
            self._title_for([True, True, True]), "You swept Week 5: all 3 pools!",
        )

    def test_winning_nothing_is_neutral(self):
        self.assertEqual(self._title_for([False, False, False]), "Week 5 winners")

    def test_title_never_exceeds_the_field_limit(self):
        # A long family name in the "won one of several" branch is the only
        # variant that interpolates unbounded text into the title.
        family = Family.objects.create(name="F" * 400, slug="long")
        long_pool = Pool.objects.create(
            family=family, name="Pool", slug="long-pool",
            season=self.season, status=Pool.Status.ACTIVE,
        )
        others = self._pools(2)
        self._seed([long_pool] + others, [True, False, False])

        publish_week_winner_digest(self.season, self.week, [long_pool] + others)

        self.assertLessEqual(
            len(Notification.objects.get(recipient=self.ana).title), 200,
        )
