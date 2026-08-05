"""Walk a compressed clock over the demo weekend, driving live score changes.

DEBUG-only, season-9999-only. Mutates GamesAndScores rows tick-by-tick per the
scripted geometry in demo_weekend.py and republishes via the SAME production
path update_games uses, so the /scores SSE stream sees byte-identical events.
Finalized games are scored through the real pipeline (see _finalize)."""
import time

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError

from pickem_api.demo_weekend import DEMO_SEASON, DEMO_WEEK, GAMES, game_state_at
from pickem_api.live_events import SCORE_TRIGGER_FIELDS
from pickem_api.management.commands.update_games import maybe_publish_game_change
from pickem_api.models import GamesAndScores


class Command(BaseCommand):
    help = "Replay the demo weekend live (dev-only, season 9999)."

    def add_arguments(self, parser):
        parser.add_argument("--duration", type=float, default=300.0,
                            help="Total wall-clock seconds (default 300).")
        parser.add_argument("--tick", type=float, default=1.5,
                            help="Real seconds between ticks (default 1.5).")
        parser.add_argument("--season", type=int, default=DEMO_SEASON)

    def handle(self, *args, **options):
        if not django_settings.DEBUG:
            raise CommandError("simulate_weekend is a dev tool; DEBUG must be on.")
        if options["season"] != DEMO_SEASON:
            raise CommandError(
                f"simulate_weekend only runs on season {DEMO_SEASON}.")

        duration = max(0.0, options["duration"])
        tick = max(0.0, options["tick"])
        defs_by_id = {g["id"]: g for g in GAMES}
        finalized = set()

        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            frac = 1.0 if duration == 0 else min(1.0, elapsed / duration)

            rows = list(GamesAndScores.objects.filter(gameseason=DEMO_SEASON))
            for row in rows:
                g = defs_by_id.get(row.id)
                if g is None:
                    continue
                state = game_state_at(g, frac)
                before = {f: getattr(row, f) for f in SCORE_TRIGGER_FIELDS}
                changed = any(before[f] != state[f] for f in SCORE_TRIGGER_FIELDS)
                if not changed:
                    continue
                for f, v in state.items():
                    setattr(row, f, v)
                row.save()
                maybe_publish_game_change(before, row)
                if state["statusType"] == "finished" and row.id not in finalized:
                    finalized.add(row.id)
                    self._finalize(row)  # Task 4 fills this in.
                self.stdout.write(
                    f"[frac={frac:.2f}] {row.slug}: {state['statusTitle']} "
                    f"{state['homeTeamScore']}-{state['awayTeamScore']}")

            if frac >= 1.0 and len(finalized) >= len(GAMES):
                break
            time.sleep(tick)

        self.stdout.write(self.style.SUCCESS("Weekend simulation complete."))

    def _finalize(self, row):
        """Hook: run the scoring pipeline when a game goes final. Filled in
        Task 4; a no-op here keeps Task 3 independently testable."""
        return
