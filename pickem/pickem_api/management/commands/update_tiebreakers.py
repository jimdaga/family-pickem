"""Flag the last game of each week as that week's tiebreaker game.

``GamesAndScores.tieBreakerGame`` marks the one game per week on which
``/picks/`` collects score/yards predictions -- the inputs are gated on it in
``pickem_homepage/templates/pickem/picks.html`` and the submit path in
``pickem_homepage/views.py`` stores NULL for both values when it is off.

Grading reads the same flag (``WeekContext.tiebreaker_game`` in
``pickem_api/weekly_winners.py``) but falls back to the week's last game when
nothing is flagged, so a forgotten flag never broke the weekly-winner chain
outright -- it silently collected no predictions to break the tie with. The
flag is load-bearing for COLLECTION, not for grading. It used to be set by hand
every week and was easy to forget.

The rule: within a ``(gameseason, gameWeek, competition)`` group, the game with
the latest kickoff is the tiebreaker -- normally Monday night. When a
doubleheader puts two games in that last slot, the lower game id wins, so the
choice is stable across runs.

If two or more games make up the group and *all* of them share one kickoff, the
group is skipped entirely and left exactly as it was. A lone game in a group is
trivially "all tied" but is unambiguously that week's last game, so it is
flagged rather than skipped -- that is what the ``> 1`` in the predicate below
is for. That is the week-18 guard: until the schedule firms
up, ESPN returns every week-18 game at one shared placeholder kickoff, so there
is no identifiable last game. Expressing it that way rather than as a week-18
special case means it also covers any other unfinalized week, and it releases
itself on the next run that covers that week. In practice the placeholder state
is only reachable via ``--all-weeks`` or an early ``update_games --week N``:
the default current-week path does not fetch a week until it is current, by
which point ESPN's times are real. A kickoff-hour check would be wrong
here -- the placeholder is midnight *Eastern*, not midnight UTC.

The selection is authoritative: every run clears stray flags, so a
flex-scheduled game that stops being last corrects itself. There is deliberately
no kickoff freeze; see
``docs/superpowers/specs/2026-09-07-auto-tiebreaker-game-design.md`` for the
accepted trade-off.

Runs from the update pipeline immediately after ``update_games``, which is what
supplies the kickoff times this reads.
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pickem.utils import get_season
from pickem_api.models import GamesAndScores
from pickem_api.management.commands.update_games import current_week_for_today

logger = logging.getLogger(__name__)


def _week_games(season, week, competition):
    """One group's games, latest kickoff first. One query, values only."""
    return list(
        GamesAndScores.objects.filter(
            gameseason=int(season),
            gameWeek=str(week),
            competition=competition,
        )
        .order_by("-startTimestamp")
        .values("id", "startTimestamp", "tieBreakerGame")
    )


def _last_game(games, season, week, competition):
    """The week's last game, or None when the schedule isn't published yet.

    A tie for the latest kickoff means one of two very different things, and
    whether the tie covers the entire slate tells them apart:

    * *Every* game shares one kickoff -- the unpublished-schedule placeholder.
      There is no last game to find, so the week is skipped.
    * *Some* games share the latest kickoff -- a Monday-night doubleheader.
      There genuinely is a last slot, it just holds two games; the lower ESPN
      game id (``GamesAndScores.id`` is ESPN's id, not a surrogate key) wins,
      so the choice is stable across runs and across re-imports. Season 2324
      week 14 is the real precedent; see the design doc for the backtest
      against the production snapshot.
    """
    if not games:
        return None
    latest = games[0]["startTimestamp"]
    tied = [game for game in games if game["startTimestamp"] == latest]
    if len(tied) == len(games) > 1:
        logger.info(
            "Skipping tiebreaker for season %s week %s (%s): all %d games share "
            "kickoff %s -- schedule not published yet",
            season, week, competition, len(games), latest,
        )
        return None
    if len(tied) > 1:
        logger.info(
            "Season %s week %s (%s): %d games tie for the last kickoff %s "
            "(doubleheader); taking the lowest game id",
            season, week, competition, len(tied), latest,
        )
    return min(tied, key=lambda game: game["id"])


def set_week_tiebreaker(season, week, competition):
    """Flag the last game of one (season, week, competition) group.

    Returns the flagged game's id, or None when the group is empty or every
    game in it shares one kickoff -- in which case nothing is written. A
    doubleheader has no strictly-latest game but IS written (lowest ESPN id).
    """
    games = _week_games(season, week, competition)
    target = _last_game(games, season, week, competition)
    if target is None:
        return None

    stale_ids = [
        game["id"]
        for game in games
        if game["tieBreakerGame"] and game["id"] != target["id"]
    ]
    if not stale_ids and target["tieBreakerGame"]:
        return target["id"]

    # One transaction: the clear and the set must never be separately visible.
    # Management commands run in autocommit, so without this a pick submitted
    # in the gap would see no flagged game, skip the "tiebreaker required"
    # guard in pickem_homepage/views.py, and silently store
    # tiebreaker_score/yards as NULL -- losing exactly the data this flag
    # exists to collect. A crash between the two writes would leave the week
    # flagless until the next run for the same reason.
    # (update_games.py wraps its own multi-row flag reset the same way.)
    with transaction.atomic():
        if stale_ids:
            GamesAndScores.objects.filter(id__in=stale_ids).update(tieBreakerGame=False)
        if not target["tieBreakerGame"]:
            GamesAndScores.objects.filter(id=target["id"]).update(tieBreakerGame=True)
    return target["id"]


def preview_week_tiebreaker(season, week, competition):
    """The id the tiebreaker would be set to, writing nothing. None if skipped."""
    games = _week_games(season, week, competition)
    target = _last_game(games, season, week, competition)
    return target["id"] if target else None


def weeks_for_season(season):
    """Distinct gameWeek values for a season, ordered numerically.

    gameWeek is a CharField, so a database sort would put "10" before "2".
    Non-numeric weeks sort last rather than raising -- a junk row must not take
    down a pipeline step.
    """
    weeks = set(
        GamesAndScores.objects.filter(gameseason=int(season))
        .values_list("gameWeek", flat=True)
        .distinct()
    )
    return sorted(
        weeks,
        key=lambda w: (
            not str(w).isdigit(),
            int(w) if str(w).isdigit() else 0,
            str(w),
        ),
    )


def competitions_for_week(season, week):
    """Distinct competitions present in one (season, week)."""
    return sorted(
        GamesAndScores.objects.filter(gameseason=int(season), gameWeek=str(week))
        .values_list("competition", flat=True)
        .distinct()
    )


class Command(BaseCommand):
    help = "Flag the last game of each week as that week's tiebreaker game."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, default=None)
        parser.add_argument(
            "--week", default=None, help="Week number (defaults to today's week)."
        )
        parser.add_argument(
            "--all-weeks",
            action="store_true",
            help="Process every week present for the season (use for backfills).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        dry_run = options["dry_run"]

        if options["all_weeks"] and options["week"] is not None:
            raise CommandError("--week and --all-weeks are mutually exclusive.")

        if options["all_weeks"]:
            weeks = weeks_for_season(season)
        else:
            weeks = [str(options["week"] or current_week_for_today(season))]

        # Render blanks visibly rather than letting a junk "" week make the
        # joined string falsy -- the header used to say "(none)" while the body
        # went on to process that week.
        listed = ", ".join(repr(week) if not week.strip() else week for week in weeks)
        self.stdout.write(
            f"Setting tiebreaker games for season {season} "
            f"week(s) {listed if weeks else '(none)'}"
        )

        flagged = 0
        for week in weeks:
            for competition in competitions_for_week(season, week):
                if dry_run:
                    game_id = preview_week_tiebreaker(season, week, competition)
                else:
                    game_id = set_week_tiebreaker(season, week, competition)

                if game_id is None:
                    self.stdout.write(
                        f" - week {week} ({competition}): skipped, no single last game"
                    )
                    continue

                flagged += 1
                verb = "would flag" if dry_run else "tiebreaker ="
                self.stdout.write(
                    f" - week {week} ({competition}): {verb} game {game_id}"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run -- nothing written."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Set tiebreaker for {flagged} week/competition group(s)."
                )
            )
