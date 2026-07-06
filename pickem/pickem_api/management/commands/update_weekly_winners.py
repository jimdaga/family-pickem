"""Award weekly winners for every active pool once the week is complete.

Runs from the update pipeline every minute, but only acts when all of the
week's games are finished and scored (i.e. after Monday Night Football),
and skips pools whose week is already awarded — so the award happens
exactly once, shortly after MNF goes final.
"""

import logging

from django.core.management.base import BaseCommand

from pickem.utils import get_season
from pickem_api.models import Pool
from pickem_api.weekly_winners import (
    EspnGameStatsProvider,
    award_weekly_winners,
    latest_complete_week,
    week_is_complete,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Award weekly winners for pools whose week has fully completed."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, default=None)
        parser.add_argument(
            "--week", type=int, default=None,
            help="Week to award (defaults to the latest fully completed week).",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="Re-award even if a winner is already flagged for the week.",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        week = options["week"]
        if week is None:
            week = latest_complete_week(season)
            if week is None:
                self.stdout.write("No completed week yet; nothing to award.")
                return
        elif not week_is_complete(season, week):
            self.stdout.write(
                f"Week {week} still has unfinished/unscored games; skipping."
            )
            return

        stats_provider = EspnGameStatsProvider()
        awarded = 0
        for pool in Pool.objects.filter(status=Pool.Status.ACTIVE):
            try:
                result = award_weekly_winners(
                    pool, season, week,
                    stats_provider=stats_provider,
                    force=options["force"],
                )
            except Exception:
                logger.exception("Weekly winner award failed for pool %s", pool)
                self.stderr.write(f" - {pool}: award failed (see logs)")
                continue
            if result:
                awarded += 1
                self.stdout.write(
                    f" - {pool}: week {week} -> {', '.join(result['winners'])} "
                    f"(+{result['bonus_each']} each, via {result['method']})"
                )

        self.stdout.write(
            self.style.SUCCESS(f"Week {week}: awarded winners in {awarded} pool(s).")
        )
