"""Recompute per-pool weekly and total points from scored picks.

ORM-based, pool-aware replacement for ``cron_update_standings.py``. The old
script keyed points by ``uid`` + season only, so a user in more than one pool
would have their standings collapsed/overwritten across pools. This command
recomputes ``week_N_points`` and ``total_points`` for every (pool, user)
independently, directly from the scored ``GamePicks`` rows.

Scoring honors each pool's ``PoolSettings``: every correct pick is worth
``win_points`` and every pick on a game that ended in a tie is worth
``tie_points`` (ties have no winner, so ``update_picks`` marks them scored
with no correct picks — the tie award happens here, where pool-specific
valuation lives). Pools without a settings row fall back to the model
defaults (1 point per win, 0 per tie).

It is idempotent and self-healing: each run recomputes all 18 weeks from the
current pick state, so re-running (or backfilling) always converges to the
correct totals. Existing ``week_N_bonus`` values are preserved and folded into
``total_points`` (matching the previous behaviour).

Run after ``update_picks`` (which flags correct picks) and before
``update_rankings`` (which ranks on ``total_points``).
"""

import logging
from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

from pickem.utils import get_season
from pickem_api.live_events import publish_event, standings_channel, standings_event_payload
from pickem_api.models import (
    Family,
    FamilyMembership,
    GamePicks,
    GamesAndScores,
    GameWeeks,
    Pool,
    PoolSettings,
    userSeasonPoints,
)

logger = logging.getLogger(__name__)

WEEKS = range(1, 19)


def maybe_publish_standings_change(old_total, old_week_points, row, week, season):
    """Publish a live standings event if points changed (or new row).

    ``old_total`` is ``row.total_points`` captured before the recompute, or
    ``None`` if the row was just created. ``old_week_points`` is the
    pre-recompute ``week_{week}_points`` (or ``None`` if unknown/new row).
    The lobby displays the current week's points, so a cross-week scoring
    correction that changes ``week_{week}_points`` without moving
    ``total_points`` still needs to publish. Best-effort via
    ``publish_event`` (which never raises) — a publish failure must never
    break the recompute.
    """
    if old_total is not None:
        total_unchanged = old_total == row.total_points
        week_unchanged = old_week_points == getattr(row, f"week_{week}_points", None)
        if total_unchanged and week_unchanged:
            return
    publish_event(
        standings_channel(row.pool_id, season), standings_event_payload(row, week)
    )


class Command(BaseCommand):
    help = "Recompute per-pool weekly/total points from scored picks."

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
            help="Limit the recompute to a single pool id (defaults to every pool).",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        pool_id_filter = options.get("pool")
        self.stdout.write(f"Recomputing standings for season {season}")
        current_week = self._current_week(season)

        pick_filter = {"gameseason": season}
        if pool_id_filter:
            pick_filter["pool_id"] = pool_id_filter

        picks_qs = GamePicks.objects.filter(**pick_filter)
        if not pool_id_filter:
            # Deactivated (soft-deleted) families keep their data but stop
            # being recomputed; exclude() (not filter) so legacy null-pool
            # picks are unaffected. An explicit --pool skips this so
            # operators can still repair an inactive family's pool.
            picks_qs = picks_qs.exclude(pool__family__status=Family.Status.INACTIVE)
        pick_combos = (
            picks_qs
            # order_by() clears Meta.ordering (gameWeek), which would leak
            # into the SELECT and break DISTINCT on (pool_id, userID).
            .order_by()
            .values_list("pool_id", "userID")
            .distinct()
        )

        # Every active member of this season's pools gets a standings row even
        # before their first pick, so rosters render complete (with zeros) on
        # the lobby, scores, and standings pages.
        member_combos = set()
        season_pools = Pool.objects.filter(status=Pool.Status.ACTIVE, season=season)
        if pool_id_filter:
            season_pools = season_pools.filter(id=pool_id_filter)
        else:
            season_pools = season_pools.filter(family__status=Family.Status.ACTIVE)
        for pool in season_pools:
            member_ids = FamilyMembership.objects.filter(
                family=pool.family,
                status=FamilyMembership.Status.ACTIVE,
                user__is_active=True,
            ).values_list("user_id", flat=True)
            member_combos.update((pool.id, str(uid)) for uid in member_ids)

        combos = member_combos | {
            (pool_id, user_id) for pool_id, user_id in pick_combos if user_id
        }

        # Games that ended in a tie: scored with equal, populated scores.
        # Picks on these games earn the pool's tie_points.
        tied_game_ids = set(
            GamesAndScores.objects.filter(
                gameseason=season,
                gameScored=True,
                statusType="finished",
                homeTeamScore__isnull=False,
                awayTeamScore=F("homeTeamScore"),
            ).values_list("id", flat=True)
        )

        # Per-pool scoring weights, fetched once.
        pool_weights = {}
        for settings in PoolSettings.objects.filter(
            pool_id__in={pool_id for pool_id, _ in combos}
        ):
            pool_weights[settings.pool_id] = (settings.win_points, settings.tie_points)

        updated = 0
        for pool_id, user_id in sorted(combos):
            if not user_id:
                continue
            win_points, tie_points = pool_weights.get(pool_id, (1, 0))
            row, created = userSeasonPoints.objects.get_or_create(
                pool_id=pool_id,
                userID=user_id,
                gameseason=season,
                defaults={
                    "userEmail": self._email_for(season, pool_id, user_id),
                },
            )
            old_total = None if created else row.total_points
            old_week_points = (
                None
                if created or current_week is None
                else getattr(row, f"week_{current_week}_points", None)
            )

            correct_by_week = Counter()
            tied_by_week = Counter()
            picks = GamePicks.objects.filter(
                pool_id=pool_id,
                userID=user_id,
                gameseason=season,
            ).values_list("gameWeek", "pick_correct", "pick_game_id")
            for game_week, pick_correct, pick_game_id in picks:
                if pick_correct:
                    correct_by_week[game_week] += 1
                elif pick_game_id in tied_game_ids:
                    tied_by_week[game_week] += 1

            total = 0
            for week in WEEKS:
                points = (
                    correct_by_week[str(week)] * win_points
                    + tied_by_week[str(week)] * tie_points
                )
                setattr(row, f"week_{week}_points", points)
                bonus = getattr(row, f"week_{week}_bonus") or 0
                total += points + bonus

            row.total_points = total
            row.save()
            maybe_publish_standings_change(
                old_total, old_week_points, row, current_week, season
            )
            updated += 1
            self.stdout.write(f" - pool {pool_id} user {user_id}: {total} points")

        self.stdout.write(
            self.style.SUCCESS(f"Recomputed standings for {updated} pool members.")
        )

    @staticmethod
    def _current_week(season):
        """Best-effort current week number for ``season`` today, or None.

        Only used to enrich the live-standings publish payload, so any
        lookup failure (e.g. no GameWeeks row for today) simply falls back
        to ``None`` rather than raising — the payload handles week=None.

        Scoped to ``season`` so a same-date GameWeeks row from another season
        can't leak the wrong week into this season's payload — notably the
        dev-only demo season 9999 seeded by ``seed_demo_weekend``, which shares
        today's date. Falls back to a season-less legacy row (some historical
        GameWeeks rows predate the season column and have season=NULL).
        """
        try:
            today = timezone.localdate()
            row = (
                GameWeeks.objects.filter(date=today, season=season).first()
                or GameWeeks.objects.filter(date=today, season__isnull=True).first()
            )
            return row.weekNumber if row else None
        except Exception:
            logger.warning("current week lookup failed", exc_info=True)
            return None

    @staticmethod
    def _email_for(season, pool_id, user_id):
        pick = (
            GamePicks.objects.filter(
                gameseason=season, pool_id=pool_id, userID=user_id
            )
            .exclude(userEmail="")
            .values_list("userEmail", flat=True)
            .first()
        )
        return pick or ""
