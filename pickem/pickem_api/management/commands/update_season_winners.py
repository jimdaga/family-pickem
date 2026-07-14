"""Flag the season champion (``year_winner``) for each pool once the season ends.

Nothing previously wrote ``year_winner`` — the standings page, profile
"seasons won" stat and ``update_stats`` all read it, but it could only be set
by hand in the Django admin. This command closes that loop: once every game
of the final regular-season week is finished and scored, and the week's
winner bonus has been applied (so ``total_points`` is final), the member(s)
with the highest total in each pool are flagged as the season winner.
Ties produce co-champions.

Idempotent: pools that already have a ``year_winner`` for the season are
skipped unless ``--force`` is passed (which recomputes and reassigns).
Runs from the update pipeline after ``update_rankings``.
"""

import logging

from django.core.management.base import BaseCommand

from pickem.utils import get_season
from pickem_api.models import FamilyAuditLog, Pool, userSeasonPoints
from pickem_api.weekly_winners import week_is_complete

logger = logging.getLogger(__name__)

FINAL_WEEK = 18


class Command(BaseCommand):
    help = "Flag year_winner for each pool once the final week is complete."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, default=None)
        parser.add_argument(
            "--force", action="store_true",
            help="Re-award even if a season winner is already flagged.",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()

        awarded = 0
        for pool in Pool.objects.filter(status=Pool.Status.ACTIVE, season=season):
            if not week_is_complete(season, FINAL_WEEK, pool.competition):
                continue

            rows = list(
                userSeasonPoints.objects.filter(pool=pool, gameseason=season)
            )
            if not rows:
                continue
            if not options["force"] and any(row.year_winner for row in rows):
                continue  # already crowned

            # Totals are only final once the last week's bonus is in. The
            # weekly-winner step runs earlier in the same pipeline, so this
            # only stays False if that award failed — try again next run.
            final_week_points = [
                getattr(row, f"week_{FINAL_WEEK}_points") or 0 for row in rows
            ]
            final_week_awarded = any(
                getattr(row, f"week_{FINAL_WEEK}_winner") for row in rows
            )
            if max(final_week_points) > 0 and not final_week_awarded:
                continue

            top_total = max((row.total_points or 0) for row in rows)
            if top_total <= 0:
                continue

            changed = []
            for row in rows:
                is_winner = (row.total_points or 0) == top_total
                if row.year_winner != is_winner:
                    row.year_winner = is_winner
                    row.save(update_fields=["year_winner"])
                    changed.append(row)

            winners = sorted(
                str(row.userID)
                for row in rows
                if (row.total_points or 0) == top_total
            )
            awarded += 1
            self.stdout.write(
                f" - {pool.family.slug}/{pool.slug}: season winner(s) "
                f"{', '.join(winners)} with {top_total} points"
            )
            FamilyAuditLog.objects.create(
                family=pool.family,
                pool=pool,
                actor=None,
                action=FamilyAuditLog.Action.WEEK_WINNER_UPDATED,
                target_type='userSeasonPoints',
                target_id=f'season_{season}',
                metadata={
                    'summary': 'Automated season winner award',
                    'season': season,
                    'winners': winners,
                    'total_points': top_total,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(f"Season {season}: crowned winners in {awarded} pool(s).")
        )
