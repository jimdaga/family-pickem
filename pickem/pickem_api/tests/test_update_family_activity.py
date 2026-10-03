from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from grading_tests.factories import (
    SEASON,
    create_game,
    create_league,
    finish_game,
    make_pick,
)
from pickem_api.models import Family, FamilyAuditLog, GamesAndScores


class UpdateFamilyActivityTests(TestCase):
    def setUp(self):
        # Weeks 1-3 complete, week 4 upcoming.
        self.games = {}
        for week in (1, 2, 3, 4):
            game = create_game(week)
            if week < 4:
                finish_game(game, 21, 14)
                GamesAndScores.objects.filter(pk=game.pk).update(gameScored=True)
            self.games[week] = game
        self.family, self.pool, self.user = self._league("idle")
        self._age(self.family)

    def _league(self, name):
        league = create_league(f"{name}-player", family_name=f"{name} fam")
        (user,) = league.users.values()
        return league.family, league.pool, user

    def _age(self, family, days=30):
        Family.objects.filter(pk=family.pk).update(
            created_at=timezone.now() - timedelta(days=days)
        )

    def _run(self, **kwargs):
        call_command("update_family_activity", season=SEASON, stdout=StringIO(), **kwargs)

    def test_family_with_no_picks_in_last_two_completed_weeks_goes_idle(self):
        make_pick(self.pool, self.user, self.games[1], "home")  # week 1 only
        self._run()
        self.family.refresh_from_db()
        self.assertTrue(self.family.is_idle)
        self.assertIsNotNone(self.family.idle_since)
        log = FamilyAuditLog.objects.get(family=self.family)
        self.assertEqual(log.metadata['source'], 'update_family_activity')
        self.assertTrue(log.metadata['is_idle'])

    def test_pick_in_either_recent_week_keeps_family_active(self):
        make_pick(self.pool, self.user, self.games[2], "home")
        self._run()
        self.family.refresh_from_db()
        self.assertFalse(self.family.is_idle)

    def test_auto_picks_do_not_count_as_activity(self):
        pick = make_pick(self.pool, self.user, self.games[3], "home")
        pick.auto_pick = True
        pick.save()
        self._run()
        self.family.refresh_from_db()
        self.assertTrue(self.family.is_idle)

    def test_idle_family_comes_back_by_picking_the_upcoming_week(self):
        Family.objects.filter(pk=self.family.pk).update(
            is_idle=True, idle_since=timezone.now()
        )
        make_pick(self.pool, self.user, self.games[4], "home")
        self._run()
        self.family.refresh_from_db()
        self.assertFalse(self.family.is_idle)
        self.assertIsNone(self.family.idle_since)

    def test_new_family_gets_a_grace_period(self):
        family, _pool, _user = self._league("fresh")
        self._run()
        family.refresh_from_db()
        self.assertFalse(family.is_idle)

    def test_soft_deleted_family_is_not_evaluated(self):
        Family.objects.filter(pk=self.family.pk).update(status=Family.Status.INACTIVE)
        self._run()
        self.family.refresh_from_db()
        self.assertFalse(self.family.is_idle)

    def test_dry_run_saves_nothing(self):
        self._run(dry_run=True)
        self.family.refresh_from_db()
        self.assertFalse(self.family.is_idle)
        self.assertFalse(FamilyAuditLog.objects.filter(family=self.family).exists())

    def test_no_new_idle_flags_before_two_completed_weeks_but_flags_persist(self):
        # Simulate a new season: no completed weeks yet.
        GamesAndScores.objects.all().delete()
        quiet, _pool, _user = self._league("quiet")
        self._age(quiet)
        Family.objects.filter(pk=self.family.pk).update(is_idle=True)
        self._run()
        quiet.refresh_from_db()
        self.family.refresh_from_db()
        self.assertFalse(quiet.is_idle)       # not newly flagged
        self.assertTrue(self.family.is_idle)  # existing flag carries over

    def test_activity_is_judged_per_family(self):
        busy, busy_pool, busy_user = self._league("busy")
        self._age(busy)
        make_pick(busy_pool, busy_user, self.games[3], "home")
        self._run()
        busy.refresh_from_db()
        self.family.refresh_from_db()
        self.assertFalse(busy.is_idle)
        self.assertTrue(self.family.is_idle)

    def test_idle_family_comes_back_early_in_a_new_season(self):
        GamesAndScores.objects.all().delete()
        week_one = create_game(1)  # nothing complete yet
        Family.objects.filter(pk=self.family.pk).update(
            is_idle=True, idle_since=timezone.now()
        )
        make_pick(self.pool, self.user, week_one, "home")
        self._run()
        self.family.refresh_from_db()
        self.assertFalse(self.family.is_idle)
        self.assertIsNone(self.family.idle_since)
