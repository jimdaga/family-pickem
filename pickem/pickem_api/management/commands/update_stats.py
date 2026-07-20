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

Auto picks (rows created by a pool's missed-pick policy, ``auto_pick=True``)
count toward standings but not toward these stats: the game still counts as
missed, and auto picks are excluded from accuracy, perfect weeks and the
most/least-picked teams — they reflect the pool's policy, not the user.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
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
        parser.add_argument(
            "--pool",
            type=int,
            default=None,
            help=(
                "Limit the recompute to a single pool id (defaults to every pool). "
                "Writes a per-pool userStats row instead of touching the global "
                "(pool-null) row."
            ),
        )

    def handle(self, *args, **options):
        season = options.get("season") or get_season()
        season = int(season)
        pool_id = options.get("pool")

        User = get_user_model()
        emails = {
            str(uid): email
            for uid, email in User.objects.values_list("id", "email")
        }

        # Shared reference data, fetched once. Games aren't pool-scoped, so this
        # is unaffected by --pool. Keyed by game id, never slug: matchup slugs
        # ("eagles-chiefs") recur every season, so a slug match would grade a
        # current pick against a previous season's finished game.
        finished_ids = set(
            GamesAndScores.objects.filter(statusType="finished").values_list(
                "id", flat=True
            )
        )
        # Scored games as (season, week, id), for missed picks + perfect weeks.
        scored_games = list(
            GamesAndScores.objects.filter(
                gameScored=True, gameseason__isnull=False
            ).values("id", "gameseason", "gameWeek")
        )
        scored_season_by_id = {g["id"]: g["gameseason"] for g in scored_games}
        scored_ids_season = {
            g["id"] for g in scored_games if g["gameseason"] == season
        }
        # Count of scored games per (season, week), for perfect-week detection.
        scored_by_week = {}
        for g in scored_games:
            key = (g["gameseason"], g["gameWeek"])
            scored_by_week[key] = scored_by_week.get(key, 0) + 1

        if pool_id is not None:
            # Pool-scoped: identify users by their (string) userID within this
            # pool's picks, and write a per-pool row for each — the global
            # (pool-null) row from a season-wide run is left untouched.
            identities = list(
                GamePicks.objects.filter(gameseason__isnull=False, pool_id=pool_id)
                .exclude(userID="")
                .order_by("userID")
                .values_list("userID", flat=True)
                .distinct()
            )
            written = 0
            for user_id in identities:
                if not user_id:
                    continue
                identity_filter = {"userID": user_id, "pool_id": pool_id}
                stats = self._compute_for_user(
                    identity_filter,
                    user_id,
                    season,
                    finished_ids,
                    scored_season_by_id,
                    scored_ids_season,
                    scored_by_week,
                    pool_id=pool_id,
                )
                stats["userEmail"] = emails.get(
                    user_id, f"user-{user_id}@placeholder.local"
                )
                self._upsert(user_id, stats, pool_id=pool_id)
                written += 1
        else:
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
                identity_filter = {"uid": uid}
                stats = self._compute_for_user(
                    identity_filter,
                    user_id,
                    season,
                    finished_ids,
                    scored_season_by_id,
                    scored_ids_season,
                    scored_by_week,
                    pool_id=None,
                )
                stats["userEmail"] = emails.get(user_id, f"user-{user_id}@placeholder.local")
                self._upsert(user_id, stats, pool_id=None)
                written += 1

        self.stdout.write(
            self.style.SUCCESS(f"update_stats: wrote {written} userStats row(s).")
        )

    def _compute_for_user(
        self,
        identity_filter,
        user_id,
        season,
        finished_ids,
        scored_season_by_id,
        scored_ids_season,
        scored_by_week,
        pool_id=None,
    ):
        # --- Pick accuracy (real picks whose game is finished) ---
        finished_picks = GamePicks.objects.filter(
            **identity_filter, gameseason__isnull=False,
            pick_game_id__in=finished_ids, auto_pick=False,
        )
        # Distinct games, not raw pick rows: the global (pool-null) run sees
        # one pick per pool per game for multi-pool users, which would double
        # every count (and make perfect weeks unreachable).
        totals = finished_picks.aggregate(
            total=Count("pick_game_id", distinct=True),
            correct=Count("pick_game_id", filter=Q(pick_correct=True), distinct=True),
        )
        season_totals = finished_picks.filter(gameseason=season).aggregate(
            total=Count("pick_game_id", distinct=True),
            correct=Count("pick_game_id", filter=Q(pick_correct=True), distinct=True),
        )
        correct_total = totals["correct"] or 0
        total_total = totals["total"] or 0
        correct_season = season_totals["correct"] or 0
        total_season = season_totals["total"] or 0

        # --- Weeks won / seasons won (from userSeasonPoints) ---
        usp = userSeasonPoints.objects.filter(userID=user_id)
        if pool_id is not None:
            usp = usp.filter(pool_id=pool_id)
        weeks_won_total = self._sum_weeks_won(usp.filter(gameseason__isnull=False))
        weeks_won_season = self._sum_weeks_won(usp.filter(gameseason=season))
        seasons_won = usp.filter(
            year_winner=True, gameseason__isnull=False
        ).count()

        # --- Missed picks: scored games the user never picked themselves ---
        # One query for both picked_game_ids (real picks only) and
        # played_seasons (any pick, auto or not, bounds the all-time
        # "missed" universe to seasons the user actually played) instead of
        # two separate queries over the same identity/gameseason filter.
        own_picks = list(
            GamePicks.objects.filter(**identity_filter, gameseason__isnull=False)
            .order_by()
            .values_list("pick_game_id", "gameseason", "auto_pick")
        )
        picked_game_ids = {
            game_id for game_id, _season, auto in own_picks if not auto
        }
        played_seasons = {season for _game_id, season, _auto in own_picks}
        scored_ids_played = {
            g_id
            for g_id, g_season in scored_season_by_id.items()
            if g_season in played_seasons
        }
        missed_total = len(scored_ids_played - picked_game_ids)
        missed_season = len(scored_ids_season - picked_game_ids)

        # --- Perfect weeks ---
        perfect_total = self._perfect_weeks(identity_filter, scored_by_week, None)
        perfect_season = self._perfect_weeks(identity_filter, scored_by_week, season)

        # --- Most / least picked team(s) ---
        most_total, least_total = self._extreme_picked(identity_filter, None)
        most_season, least_season = self._extreme_picked(identity_filter, season)

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
    def _perfect_weeks(identity_filter, scored_by_week, season):
        """Count weeks where the user picked every scored game, all correct.

        A week is perfect when the number of scored games in it equals both
        the user's correct-pick count and total-pick count for that week (so
        missing a game or getting one wrong disqualifies it). Counts are per
        distinct game so a multi-pool user's duplicate per-pool picks don't
        inflate the totals and make perfection unreachable.
        """
        pick_filter = dict(identity_filter, auto_pick=False)
        if season is not None:
            pick_filter["gameseason"] = season
        else:
            pick_filter["gameseason__isnull"] = False

        # User's total and correct picks grouped by (season, week).
        per_week = {}
        rows = (
            GamePicks.objects.filter(**pick_filter)
            .values("gameseason", "gameWeek")
            .annotate(
                total=Count("pick_game_id", distinct=True),
                correct=Count(
                    "pick_game_id", filter=Q(pick_correct=True), distinct=True
                ),
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
    def _extreme_picked(identity_filter, season):
        """Return (most_picked, least_picked) team display strings or None.

        Ties are joined by ", ". Counts every pick by the user (optionally in a
        single season), matching pickemctl.
        """
        qs = GamePicks.objects.filter(
            **identity_filter, gameseason__isnull=False, auto_pick=False
        )
        if season is not None:
            qs = qs.filter(gameseason=season)
        counts = list(
            qs.values("pick").annotate(c=Count("pick_game_id", distinct=True)).order_by()
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
    def _upsert(user_id, fields, pool_id=None):
        """Write the userStats row for a user: the single global (pool-null) row
        for a season-wide run, or a per-pool row when scoped with --pool.

        The duplicate-collapse delete and the save run in one transaction so a
        save failure can't leave the user with no stats row.
        """
        with transaction.atomic():
            # Lock the matching rows: two concurrent runs for the same
            # (userID, pool_id) — e.g. a superadmin "Recompute" overlapping the
            # scheduled global run — could otherwise both see no row and both
            # insert, leaving divergent duplicates ((pool, userID) is indexed
            # but not unique).
            existing = list(
                userStats.objects.select_for_update()
                .filter(userID=user_id, pool_id=pool_id)
                .order_by("id")
            )
            if existing:
                obj = existing[0]
                # Collapse any accidental duplicates into one row.
                for extra in existing[1:]:
                    extra.delete()
            else:
                obj = userStats(userID=user_id, pool_id=pool_id)

            obj.userEmail = fields.pop("userEmail", obj.userEmail)
            for key, value in fields.items():
                setattr(obj, key, value)
            obj.save()
