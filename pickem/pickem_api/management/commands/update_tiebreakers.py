"""Flag the last game of each week as that week's tiebreaker game.

``GamesAndScores.tieBreakerGame`` marks the one game per week on which players
enter score/yards tiebreaker predictions (see ``pickem_api/weekly_winners.py``).
It used to be set by hand every week and was easy to forget, leaving a week with
no tiebreaker inputs at all.

The rule: within a ``(gameseason, gameWeek, competition)`` group, the game with
the strictly latest kickoff is the tiebreaker -- normally Monday night.

If two or more games tie for the latest kickoff, the group is skipped entirely
and left exactly as it was. That is the week-18 guard: until the schedule firms
up, ESPN returns every week-18 game at one shared placeholder kickoff, so there
is no identifiable last game. Expressing it as a tie test rather than a week-18
special case means it also covers any other unfinalized week, and it releases
itself the moment real kickoff times land. A kickoff-hour check would be wrong
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

from django.core.management.base import BaseCommand

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
    """The single latest-kickoff game, or None when there is no unique one."""
    if not games:
        return None
    latest = games[0]["startTimestamp"]
    tied = sum(1 for game in games if game["startTimestamp"] == latest)
    if tied > 1:
        logger.info(
            "Skipping tiebreaker for season %s week %s (%s): %d games tie for "
            "the latest kickoff %s -- schedule not published yet",
            season, week, competition, tied, latest,
        )
        return None
    return games[0]


def set_week_tiebreaker(season, week, competition):
    """Flag the last game of one (season, week, competition) group.

    Returns the flagged game's id, or None when the group is empty or has no
    strictly-latest game -- in which case nothing is written.
    """
    games = _week_games(season, week, competition)
    target = _last_game(games, season, week, competition)
    if target is None:
        return None

    stale_ids = [game["id"] for game in games[1:] if game["tieBreakerGame"]]
    if stale_ids:
        GamesAndScores.objects.filter(id__in=stale_ids).update(tieBreakerGame=False)
    if not target["tieBreakerGame"]:
        GamesAndScores.objects.filter(id=target["id"]).update(tieBreakerGame=True)
    return target["id"]
