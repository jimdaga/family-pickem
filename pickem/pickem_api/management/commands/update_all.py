"""Run the full data-update pipeline in dependency order.

Single entry point replacing cron.sh. Each step is a management command;
a failure in one step is logged and the pipeline continues so a transient
error (e.g. ESPN hiccup) doesn't block the rest.

Order matters:
  1. update_records        - team win/loss records (independent)
  2. update_games          - fetch scores + winners from ESPN
  3. update_picks          - score picks against game winners
  4. update_standings      - recompute per-pool weekly/total points
  5. update_weekly_winners - award winner bonuses once the week completes
  6. update_rankings       - rank pool members by total points (incl. bonus)
  7. update_stats          - recompute per-user userStats (replaces pickemctl)
"""

import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

PIPELINE = [
    "update_records",
    "update_games",
    "update_picks",
    "update_standings",
    "update_weekly_winners",
    "update_rankings",
    "update_stats",
]


class Command(BaseCommand):
    help = "Run the full update pipeline (records, games, picks, standings, rankings)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Season in YYZZ format (defaults to the current season).",
        )

    def handle(self, *args, **options):
        season = options.get("season")
        step_kwargs = {"season": season} if season else {}

        failures = 0
        for command in PIPELINE:
            self.stdout.write(self.style.MIGRATE_HEADING(f"== {command} =="))
            try:
                call_command(command, **step_kwargs)
            except Exception as exc:  # noqa: BLE001 - keep the pipeline going
                failures += 1
                logger.exception("Pipeline step %s failed", command)
                self.stderr.write(self.style.ERROR(f"{command} failed: {exc}"))

        if failures:
            self.stdout.write(
                self.style.WARNING(f"Pipeline finished with {failures} failed step(s).")
            )
            raise CommandError(f"Pipeline finished with {failures} failed step(s).")
        else:
            self.stdout.write(self.style.SUCCESS("Pipeline finished cleanly."))
