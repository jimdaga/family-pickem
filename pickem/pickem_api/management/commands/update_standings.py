"""Recompute per-pool weekly and total points from scored picks.

ORM-based, pool-aware replacement for ``cron_update_standings.py``. The old
script keyed points by ``uid`` + season only, so a user in more than one pool
would have their standings collapsed/overwritten across pools. This command
recomputes ``week_N_points`` and ``total_points`` for every (pool, user)
independently, directly from the scored ``GamePicks`` rows.

It is idempotent and self-healing: each run recomputes all 18 weeks from the
current pick state, so re-running (or backfilling) always converges to the
correct totals. Existing ``week_N_bonus`` values are preserved and folded into
``total_points`` (matching the previous behaviour).

Run after ``update_picks`` (which flags correct picks) and before
``update_rankings`` (which ranks on ``total_points``).
"""

import logging

from django.core.management.base import BaseCommand

from pickem.utils import get_season
from pickem_api.models import GamePicks, userSeasonPoints

logger = logging.getLogger(__name__)

WEEKS = range(1, 19)


class Command(BaseCommand):
    help = "Recompute per-pool weekly/total points from scored picks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Season in YYZZ format (defaults to the current season).",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        self.stdout.write(f"Recomputing standings for season {season}")

        combos = (
            GamePicks.objects.filter(gameseason=season)
            .values_list("pool_id", "userID")
            .distinct()
        )

        updated = 0
        for pool_id, user_id in combos:
            if not user_id:
                continue
            row, _ = userSeasonPoints.objects.get_or_create(
                pool_id=pool_id,
                userID=user_id,
                gameseason=season,
                defaults={
                    "userEmail": self._email_for(season, pool_id, user_id),
                },
            )

            total = 0
            for week in WEEKS:
                correct = GamePicks.objects.filter(
                    pool_id=pool_id,
                    userID=user_id,
                    gameseason=season,
                    gameWeek=str(week),
                    pick_correct=True,
                ).count()
                setattr(row, f"week_{week}_points", correct)
                bonus = getattr(row, f"week_{week}_bonus") or 0
                total += correct + bonus

            row.total_points = total
            row.save()
            updated += 1
            self.stdout.write(f" - pool {pool_id} user {user_id}: {total} points")

        self.stdout.write(
            self.style.SUCCESS(f"Recomputed standings for {updated} pool members.")
        )

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
