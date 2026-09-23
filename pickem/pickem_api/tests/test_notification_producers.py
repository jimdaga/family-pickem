from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from pickem_api.models import (
    Family, FamilyMembership, Notification, Pool, userSeasonPoints,
)
from pickem_api.notifications import publish_week_winner_digest


def _member(user, pool):
    """Digests only reach current family members, so fixtures need one."""
    FamilyMembership.objects.get_or_create(family=pool.family, user=user)


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
        _member(user, pool)
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


class _WeekWinnerCommandFixture:
    """Week-1 games plus two real players, and a way to run the real command.

    A mixin rather than a TestCase so the classes that share it don't also
    inherit -- and re-run against a different fixture -- each other's tests.
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
            _member(user, self.pool)
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


class WeekWinnerCommandWiringTests(_WeekWinnerCommandFixture, TestCase):
    """The producer must actually run from ``update_weekly_winners``.

    The unit tests above call publish_week_winner_digest directly; these drive
    the real management command, so a broken import or a hook in the wrong
    place fails here rather than silently shipping a producer nothing calls.
    """

    def test_command_awards_and_notifies(self):
        output = self._run()

        self.assertIn("awarded winners in 1 pool(s)", output)
        self.assertIn("sent or updated 2 winner notification(s)", output)

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
                _member(user, pool)
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


class WeekWinnerLaunchTests(_WeekWinnerCommandFixture, TestCase):
    """Deploying mid-season must be silent; the first digest is the next award.

    Mirrors production at ship time: Weeks 1 and 2 were awarded before this
    producer existed. Those must never be announced -- only a week the command
    itself awards from here on.
    """

    def setUp(self):
        super().setUp()
        # Weeks 1 and 2 already awarded, as in prd on deploy day.
        self._add_week(2, game_id=902)
        userSeasonPoints.objects.filter(userID=str(self.ana.id)).update(
            week_1_winner=True, week_2_points=11, week_2_winner=True,
        )
        userSeasonPoints.objects.filter(userID=str(self.bo.id)).update(
            week_2_points=6,
        )

    def _add_week(self, week, game_id):
        from datetime import timedelta

        from django.utils import timezone

        from pickem_api.models import GamesAndScores

        GamesAndScores.objects.create(
            id=game_id, slug=f"wk{week}", competition="nfl", gameWeek=str(week),
            gameyear="2025", gameseason=2526,
            startTimestamp=timezone.now() + timedelta(days=7 * week),
            statusType="finished", statusTitle="Final", gameScored=True,
            tieBreakerGame=True, homeTeamScore=17, awayTeamScore=10,
            homeTeamId=5, homeTeamSlug="e", homeTeamName="E",
            awayTeamId=6, awayTeamSlug="f", awayTeamName="F",
        )

    def test_deploy_with_weeks_already_awarded_sends_nothing(self):
        output = self._run()

        self.assertEqual(Notification.objects.count(), 0)
        self.assertNotIn("winner notification", output)

    def test_next_awarded_week_is_announced(self):
        self._run()  # deploy tick: silent

        # Week 3 finishes after deploy; the command awards it and announces it.
        self._add_week(3, game_id=903)
        userSeasonPoints.objects.filter(userID=str(self.ana.id)).update(week_3_points=5)
        userSeasonPoints.objects.filter(userID=str(self.bo.id)).update(week_3_points=9)
        output = self._run()

        self.assertEqual(
            sorted(Notification.objects.values_list("title", flat=True)),
            ["Week 3 winners", "You won Week 3!"],
        )
        self.assertIn("Week 3: sent or updated 2 winner notification(s)", output)

    def test_outage_backfill_announces_only_the_newest_week(self):
        # Weeks 3 and 4 both finish while the scheduler is down; one pass then
        # awards both. Only Week 4 should reach anyone's bell.
        for week, gid in ((3, 903), (4, 904)):
            self._add_week(week, game_id=gid)
            userSeasonPoints.objects.filter(userID=str(self.ana.id)).update(
                **{f"week_{week}_points": 5})
            userSeasonPoints.objects.filter(userID=str(self.bo.id)).update(
                **{f"week_{week}_points": 9})

        self._run()

        titles = set(Notification.objects.values_list("title", flat=True))
        self.assertEqual(titles, {"Week 4 winners", "You won Week 4!"})
        # ...while Week 3's award itself still lands.
        self.assertTrue(
            userSeasonPoints.objects.get(userID=str(self.bo.id)).week_3_winner
        )


class WeekWinnerReviewFixTests(WeekWinnerDigestTests):
    """Regressions for the pre-merge code review of the digest producer.

    Subclasses WeekWinnerDigestTests only for its fixture helpers; the parent's
    tests are excluded below so they don't run twice.
    """

    def test_former_family_member_is_not_notified(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.bo, self.smith_pool, 11)
        FamilyMembership.objects.filter(user=self.bo, family=self.smith).update(
            status=FamilyMembership.Status.INACTIVE,
        )

        publish_week_winner_digest(self.season, self.week, self._pools())

        self.assertFalse(Notification.objects.filter(recipient=self.bo).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.ana).exists())

    def test_pool_awarded_on_a_later_tick_updates_the_digest(self):
        # Tick 1: only Jones is awarded (Smith's award is still pending).
        self._row(self.ana, self.jones_pool, 9)
        self._row(self.bo, self.jones_pool, 12, winner=True)
        smith_row = self._row(self.ana, self.smith_pool, 14)  # not yet awarded
        publish_week_winner_digest(self.season, self.week, self._pools())

        note = Notification.objects.get(recipient=self.ana)
        self.assertEqual(note.title, "Week 5 winners")
        note.read_at = timezone.now()
        note.save(update_fields=["read_at"])

        # Tick 2: Smith is awarded -- and Ana won it.
        setattr(smith_row, f"week_{self.week}_winner", True)
        smith_row.save()
        changed = publish_week_winner_digest(self.season, self.week, self._pools())

        note.refresh_from_db()
        self.assertEqual(changed, 1)
        self.assertEqual(note.title, "You won Week 5 in Smith Family")
        self.assertIn("Smith Family: you", note.body)
        self.assertIsNone(note.read_at, "new information must resurface as unread")
        self.assertEqual(Notification.objects.filter(recipient=self.ana).count(), 1)

    def test_changed_winner_rewrites_the_old_digest(self):
        # A --force re-award flips the winner from Ana to Bo.
        ana_row = self._row(self.ana, self.smith_pool, 14, winner=True)
        bo_row = self._row(self.bo, self.smith_pool, 14)
        publish_week_winner_digest(self.season, self.week, self._pools())

        setattr(ana_row, f"week_{self.week}_winner", False)
        ana_row.save()
        setattr(bo_row, f"week_{self.week}_winner", True)
        bo_row.save()
        publish_week_winner_digest(
            self.season, self.week, self._pools(), create_missing=False,
        )

        self.assertEqual(Notification.objects.get(recipient=self.ana).title, "Week 5 winners")
        self.assertEqual(Notification.objects.get(recipient=self.bo).title, "You won Week 5!")

    def test_create_missing_false_never_announces_a_new_week(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.bo, self.smith_pool, 11)

        changed = publish_week_winner_digest(
            self.season, self.week, self._pools(), create_missing=False,
        )

        self.assertEqual(changed, 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_two_pools_in_one_family_are_told_apart(self):
        second = Pool.objects.create(
            family=self.smith, name="Survivor", slug="survivor",
            season=self.season, status=Pool.Status.ACTIVE,
        )
        self._row(self.ana, self.smith_pool, 14, winner=True)
        self._row(self.ana, second, 9)
        self._row(self.bo, second, 12, winner=True)

        publish_week_winner_digest(
            self.season, self.week, [self.smith_pool, second],
        )

        note = Notification.objects.get(recipient=self.ana)
        self.assertIn("Smith Family (Smith Pool): you", note.body)
        self.assertIn("Smith Family (Survivor): Bo", note.body)
        self.assertEqual(note.title, "You won Week 5 in Smith Family (Smith Pool)")


# Keep only the new tests on the subclass; the inherited ones already run on
# WeekWinnerDigestTests.
for _name in [n for n in vars(WeekWinnerDigestTests) if n.startswith("test_")]:
    setattr(WeekWinnerReviewFixTests, _name, None)


class WeekWinnerPostponedWeekTests(_WeekWinnerCommandFixture, TestCase):
    """A week whose award lands late is still announced when it lands."""

    def test_postponed_week_is_announced_after_a_later_week(self):
        from datetime import timedelta

        from django.utils import timezone as tz

        from pickem_api.models import GamesAndScores

        # Week 1 has a postponed game; Week 2 completes first.
        GamesAndScores.objects.filter(id=900).update(
            statusType="postponed", gameScored=False,
        )
        GamesAndScores.objects.create(
            id=902, slug="wk2", competition="nfl", gameWeek="2", gameyear="2025",
            gameseason=2526, startTimestamp=tz.now() + timedelta(days=7),
            statusType="finished", statusTitle="Final", gameScored=True,
            tieBreakerGame=True, homeTeamScore=17, awayTeamScore=10,
            homeTeamId=5, homeTeamSlug="e", homeTeamName="E",
            awayTeamId=6, awayTeamSlug="f", awayTeamName="F",
        )
        userSeasonPoints.objects.filter(userID=str(self.bo.id)).update(week_2_points=9)
        userSeasonPoints.objects.filter(userID=str(self.ana.id)).update(week_2_points=4)

        self._run()
        self.assertEqual(
            set(Notification.objects.values_list("title", flat=True)),
            {"Week 2 winners", "You won Week 2!"},
        )

        # The postponed game is played; Week 1 is awarded on a later tick.
        GamesAndScores.objects.filter(id=900).update(
            statusType="finished", gameScored=True,
        )
        output = self._run()

        self.assertIn("Week 1: sent or updated 2 winner notification(s)", output)
        self.assertTrue(
            Notification.objects.filter(title="You won Week 1!").exists(),
            "a week awarded late must still be announced",
        )


class WeekWinnerOutboxTests(_WeekWinnerCommandFixture, TestCase):
    """A failed publish is retried on the next tick, not lost (CodeRabbit #198)."""

    def test_failed_publish_is_retried_next_run(self):
        from unittest.mock import patch

        from pickem_api.models import WeekWinnerAnnouncement

        with patch(
            "pickem_api.management.commands.update_weekly_winners."
            "publish_week_winner_digest",
            side_effect=RuntimeError("db blip"),
        ), self.assertLogs(
            "pickem_api.management.commands.update_weekly_winners", level="ERROR",
        ):
            self._run()

        # The award committed; the announcement is still pending.
        self.assertEqual(Notification.objects.count(), 0)
        self.assertIsNone(WeekWinnerAnnouncement.objects.get(week=1).published_at)

        # Next tick: nothing new is awarded, but the pending week goes out.
        output = self._run()
        self.assertIn("Week 1: sent or updated 2 winner notification(s)", output)
        self.assertIsNotNone(WeekWinnerAnnouncement.objects.get(week=1).published_at)

    def test_published_week_is_not_republished(self):
        from pickem_api.models import WeekWinnerAnnouncement

        self._run()
        self._run()
        self.assertEqual(WeekWinnerAnnouncement.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_force_on_an_unannounced_week_stays_silent(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        from pickem_api.models import WeekWinnerAnnouncement

        # Week 1 awarded before the producer existed (as in prd).
        userSeasonPoints.objects.filter(userID=str(self.ana.id)).update(week_1_winner=True)
        with patch(
            "pickem_api.management.commands.update_weekly_winners.EspnGameStatsProvider"
        ) as provider:
            provider.return_value = self.StubStats()
            call_command(
                "update_weekly_winners", season=2526, week=1, force=True,
                stdout=StringIO(), stderr=StringIO(),
            )

        self.assertEqual(Notification.objects.count(), 0)
        self.assertFalse(WeekWinnerAnnouncement.objects.exists())


class WeekWinnerInsertRaceTests(WeekWinnerDigestTests):
    """Losing an insert race must still leave the digest current (CodeRabbit #198)."""

    def _lose_the_race_to(self, stale_title):
        """Make the first existence check miss a row that a concurrent call
        created, so our insert hits the unique key."""
        from unittest.mock import patch

        from django.db.models.query import QuerySet

        real_first = QuerySet.first
        state = {"hidden": False}

        def first(qs):
            row = real_first(qs)
            if row is not None and not state["hidden"] and row.title == stale_title:
                state["hidden"] = True
                return None
            return row

        return patch.object(QuerySet, "first", first)

    def test_stale_winner_of_the_race_is_brought_up_to_date(self):
        self._row(self.ana, self.smith_pool, 14, winner=True)
        # A concurrent call wrote a narrower digest first.
        Notification.objects.create(
            recipient=self.ana, kind=Notification.Kind.WEEK_WINNER,
            title="Week 5 winners", body="stale",
            dedupe_key=f"week_winners:{self.season}:{self.week}:{self.ana.id}",
        )

        with self._lose_the_race_to("Week 5 winners"):
            publish_week_winner_digest(self.season, self.week, self._pools())

        note = Notification.objects.get(recipient=self.ana)
        self.assertEqual(note.title, "You won Week 5!")
        self.assertEqual(note.body, "Smith Family: you (14 pts)")

    def test_integrity_error_that_is_not_a_race_is_logged(self):
        from unittest.mock import patch

        from django.db import IntegrityError

        self._row(self.ana, self.smith_pool, 14, winner=True)
        with patch.object(
            Notification.objects, "create", side_effect=IntegrityError("fk"),
        ), self.assertLogs("pickem_api.notifications", level="ERROR") as logs:
            publish_week_winner_digest(self.season, self.week, self._pools())

        self.assertTrue(any("Could not create" in m for m in logs.output))


for _name in [n for n in vars(WeekWinnerDigestTests) if n.startswith("test_")]:
    setattr(WeekWinnerInsertRaceTests, _name, None)
