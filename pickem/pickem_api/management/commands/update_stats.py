"""Recompute per-user statistics (``userStats``).

ORM-based replacement for the standalone ``pickemctl`` Go service, which wrote
the same table via raw SQL (and broke when Django column names changed). Stats
are global per user — aggregated across every pool a user plays in — and are
written as a single ``userStats`` row per user (``pool`` left null), matching
pickemctl's behaviour.

Computed per user:
  - correct / total picks and pick-percent (season + all-time), over picks whose
    game is finished
  - weeks won and seasons won
  - missed picks: scored games the user never picked (season + all-time)
  - perfect weeks: weeks where the user picked every scored game and got them all
    correct (season + all-time)
  - most / least picked team(s) (season + all-time; ties joined by ", ")
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from pickem.utils import get_season
from pickem_api.models import (
    GamePicks,
    GamesAndScores,
    userSeasonPoints,
    userStats,
)

logger = logging.getLogger(__name__)

# week_N_winner boolean fields on userSeasonPoints, used to sum weeks won.
WEEK_WINNER_FIELDS = [f"week_{week}_winner" for week in range(1, 19)]


def _percent(correct, total):
    """Whole-number percentage, 0 when there are no picks."""
    if not total:
        return 0
    return int(correct / total * 100)


class Command(BaseCommand):
    help = "Recompute userStats for every user (replaces the pickemctl service)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Season in YYZZ format (defaults to the current season).",
        )

    def handle(self, *args, **options):
        season = options.get("season") or get_season()
        season = int(season)

        User = get_user_model()
        emails = {
            str(uid): email
            for uid, email in User.objects.values_list("id", "email")
        }

        # Shared reference data, fetched once.
        finished_slugs = set(
            GamesAndScores.objects.filter(statusType="finished").values_list(
                "slug", flat=True
            )
        )
        # Scored games as (season, week, id), for missed picks + perfect weeks.
        scored_games = list(
            GamesAndScores.objects.filter(
                gameScored=True, gameseason__isnull=False
            ).values("id", "gameseason", "gameWeek")
        )
        scored_ids_all = {g["id"] for g in scored_games}
        scored_ids_season = {
            g["id"] for g in scored_games if g["gameseason"] == season
        }
        # Count of scored games per (season, week), for perfect-week detection.
        scored_by_week = {}
        for g in scored_games:
            key = (g["gameseason"], g["gameWeek"])
            scored_by_week[key] = scored_by_week.get(key, 0) + 1

        # order_by("uid") clears GamePicks' default Meta ordering (gameWeek);
        # otherwise it's added to the SELECT and DISTINCT returns one row per
        # (uid, week), processing each user once per week they picked.
        uids = list(
            GamePicks.objects.filter(gameseason__isnull=False)
            .order_by("uid")
            .values_list("uid", flat=True)
            .distinct()
        )

        written = 0
        for uid in uids:
            if uid is None:
                continue
            user_id = str(uid)
            stats = self._compute_for_user(
                uid,
                season,
                finished_slugs,
                scored_ids_all,
                scored_ids_season,
                scored_by_week,
            )
            stats["userEmail"] = emails.get(user_id, f"user-{user_id}@placeholder.local")
            self._upsert(user_id, stats)
            written += 1

        self.stdout.write(
            self.style.SUCCESS(f"update_stats: wrote {written} userStats row(s).")
        )

    def _compute_for_user(
        self,
        uid,
        season,
        finished_slugs,
        scored_ids_all,
        scored_ids_season,
        scored_by_week,
    ):
        user_id = str(uid)

        # --- Pick accuracy (picks whose game is finished) ---
        finished_picks = GamePicks.objects.filter(
            uid=uid, gameseason__isnull=False, slug__in=finished_slugs
        )
        totals = finished_picks.aggregate(
            total=Count("id"), correct=Count("id", filter=Q(pick_correct=True))
        )
        season_totals = finished_picks.filter(gameseason=season).aggregate(
            total=Count("id"), correct=Count("id", filter=Q(pick_correct=True))
        )
        correct_total = totals["correct"] or 0
        total_total = totals["total"] or 0
        correct_season = season_totals["correct"] or 0
        total_season = season_totals["total"] or 0

        # --- Weeks won / seasons won (from userSeasonPoints) ---
        usp = userSeasonPoints.objects.filter(userID=user_id)
        weeks_won_total = self._sum_weeks_won(usp.filter(gameseason__isnull=False))
        weeks_won_season = self._sum_weeks_won(usp.filter(gameseason=season))
        seasons_won = usp.filter(
            year_winner=True, gameseason__isnull=False
        ).count()

        # --- Missed picks: scored games the user never picked ---
        picked_game_ids = set(
            GamePicks.objects.filter(
                uid=uid, gameseason__isnull=False
            ).values_list("pick_game_id", flat=True)
        )
        missed_total = len(scored_ids_all - picked_game_ids)
        missed_season = len(scored_ids_season - picked_game_ids)

        # --- Perfect weeks ---
        perfect_total = self._perfect_weeks(uid, scored_by_week, None)
        perfect_season = self._perfect_weeks(uid, scored_by_week, season)

        # --- Most / least picked team(s) ---
        most_total, least_total = self._extreme_picked(uid, None)
        most_season, least_season = self._extreme_picked(uid, season)

        return {
            "correctPickTotalTotal": correct_total,
            "totalPicksTotal": total_total,
            "pickPercentTotal": _percent(correct_total, total_total),
            "correctPickTotalSeason": correct_season,
            "totalPicksSeason": total_season,
            "pickPercentSeason": _percent(correct_season, total_season),
            "weeksWonTotal": weeks_won_total,
            "weeksWonSeason": weeks_won_season,
            "seasonsWon": seasons_won,
            "missedPicksTotal": missed_total,
            "missedPicksSeason": missed_season,
            "perfectWeeksTotal": perfect_total,
            "perfectWeeksSeason": perfect_season,
            "mostPickedTotal": most_total,
            "leastPickedTotal": least_total,
            "mostPickedSeason": most_season,
            "leastPickedSeason": least_season,
        }

    @staticmethod
    def _sum_weeks_won(queryset):
        """Sum the 18 week_N_winner booleans across a user's season rows."""
        total = 0
        for row in queryset.values_list(*WEEK_WINNER_FIELDS):
            total += sum(1 for won in row if won)
        return total

    @staticmethod
    def _perfect_weeks(uid, scored_by_week, season):
        """Count weeks where the user picked every scored game, all correct.

        Matches pickemctl: a week is perfect when the number of scored games in
        it equals both the user's correct-pick count and total-pick count for
        that week (so missing a game, getting one wrong, or extra cross-pool
        picks all disqualify it).
        """
        pick_filter = {"uid": uid, "gameseason__isnull": False}
        if season is not None:
            pick_filter = {"uid": uid, "gameseason": season}

        # User's total and correct picks grouped by (season, week).
        per_week = {}
        rows = (
            GamePicks.objects.filter(**pick_filter)
            .values("gameseason", "gameWeek")
            .annotate(
                total=Count("id"),
                correct=Count("id", filter=Q(pick_correct=True)),
            )
        )
        for row in rows:
            per_week[(row["gameseason"], row["gameWeek"])] = (
                row["total"],
                row["correct"],
            )

        perfect = 0
        for (g_season, g_week), scored_count in scored_by_week.items():
            if season is not None and g_season != season:
                continue
            if scored_count <= 0:
                continue
            total, correct = per_week.get((g_season, g_week), (0, 0))
            if scored_count == correct and scored_count == total:
                perfect += 1
        return perfect

    @staticmethod
    def _extreme_picked(uid, season):
        """Return (most_picked, least_picked) team display strings or None.

        Ties are joined by ", ". Counts every pick by the user (optionally in a
        single season), matching pickemctl.
        """
        qs = GamePicks.objects.filter(uid=uid)
        if season is not None:
            qs = qs.filter(gameseason=season)
        counts = list(
            qs.values("pick").annotate(c=Count("id")).order_by()
        )
        counts = [row for row in counts if row["pick"]]
        if not counts:
            return None, None

        max_c = max(row["c"] for row in counts)
        min_c = min(row["c"] for row in counts)
        most = ", ".join(sorted(row["pick"] for row in counts if row["c"] == max_c))
        least = ", ".join(sorted(row["pick"] for row in counts if row["c"] == min_c))
        return most, least

    @staticmethod
    def _upsert(user_id, fields):
        """Write the single global (pool-null) userStats row for a user."""
        existing = list(
            userStats.objects.filter(userID=user_id, pool__isnull=True).order_by("id")
        )
        if existing:
            obj = existing[0]
            # Collapse any accidental duplicates into one row.
            for extra in existing[1:]:
                extra.delete()
        else:
            obj = userStats(userID=user_id, pool=None)

        obj.userEmail = fields.pop("userEmail", obj.userEmail)
        for key, value in fields.items():
            setattr(obj, key, value)
        obj.save()
