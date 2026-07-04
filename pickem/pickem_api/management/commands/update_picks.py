"""Score user picks for finished, not-yet-scored games.

ORM-based replacement for ``cron_update_picks.py`` (which drove the scoring
through /api/unscored, /api/picks and PATCH round-trips). For each finished
game that has a winner and hasn't been scored yet, every matching pick — in
any pool — is compared against the winner: correct picks are flagged and the
game is marked scored. Scoring is intentionally pool-agnostic (a pick is
correct or not based purely on the winner), so this stays correct across all
tenant pools.
"""

import logging

from django.core.management.base import BaseCommand

from pickem.utils import get_season
from pickem_api.models import GamePicks, GamesAndScores

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Score picks for finished, unscored games and mark those games scored."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Season in YYZZ format (defaults to the current season).",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        games = GamesAndScores.objects.filter(
            gameseason=season, gameScored=False, statusType="finished"
        )

        scored_games = 0
        correct_total = 0
        for game in games:
            if not game.gameWinner:
                logger.warning(
                    "Game %s finished without a winner; leaving unscored.", game.slug
                )
                self.stderr.write(f" - {game.slug}: finished but no winner yet")
                continue

            correct = GamePicks.objects.filter(
                pick_game_id=game.id, pick=game.gameWinner
            ).update(pick_correct=True)

            game.gameScored = True
            game.save(update_fields=["gameScored"])

            scored_games += 1
            correct_total += correct
            self.stdout.write(
                f" - {game.slug}: winner {game.gameWinner}, {correct} correct picks"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Scored {scored_games} games, marked {correct_total} picks correct."
            )
        )
