"""Fetch NFL game data from ESPN and upsert GamesAndScores rows.

ORM-based replacement for ``cron_update_games_v2.py`` (scores, quarter line
scores, betting odds, weather, venue, broadcast). Games are global (not
pool-scoped). Replaces the self-API POST/PUT round-trip with a direct
``update_or_create`` and derives the ESPN season year from the current
season instead of the old hardcoded ``game_year = "2025"``.
"""

import logging
from datetime import date

import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from pickem.utils import get_season
from pickem_api.models import GameWeeks, GamesAndScores, Teams
from pickem_api.management.commands.update_records import season_start_year

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)
REQUEST_TIMEOUT = 30

STATUS_MAP = {
    "STATUS_SCHEDULED": "notstarted",
    "STATUS_IN_PROGRESS": "inprogress",
    "STATUS_END_PERIOD": "inprogress",
    "STATUS_HALFTIME": "inprogress",
    "STATUS_FINAL": "finished",
    "STATUS_FINAL_OVERTIME": "finished",
}

WEATHER_CONDITION_MAP = {
    "1": "Clear", "2": "Partly Cloudy", "3": "Mostly Cloudy", "4": "Overcast",
    "5": "Hazy", "6": "Mostly Sunny", "7": "Cloudy", "8": "Dreary", "11": "Fog",
    "12": "Showers", "13": "Mostly Cloudy with Showers",
    "14": "Partly Sunny with Showers", "15": "Thunderstorms",
    "16": "Mostly Cloudy with Thunderstorms",
    "17": "Partly Sunny with Thunderstorms", "18": "Rain", "19": "Flurries",
    "20": "Mostly Cloudy with Flurries", "21": "Partly Sunny with Flurries",
    "22": "Snow", "23": "Mostly Cloudy with Snow", "24": "Ice", "25": "Sleet",
    "26": "Freezing Rain", "29": "Rain and Snow", "30": "Hot", "31": "Cold",
    "32": "Windy",
}


def team_slug(team_id):
    return (
        Teams.objects.filter(id=team_id)
        .values_list("teamNameSlug", flat=True)
        .first()
        or ""
    )


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _linescores(competitor):
    """Return (p1, p2, p3, p4, ot) integer scores, None where missing."""
    scores = [None, None, None, None, None]
    for idx, entry in enumerate(competitor.get("linescores", [])[:5]):
        scores[idx] = _int(entry.get("value"))
    return scores


def _win_probabilities(competition):
    spread = over_under = home_prob = away_prob = None
    odds = competition.get("odds") or []
    if odds:
        data = odds[0]
        spread = data.get("spread")
        over_under = data.get("overUnder")
        home_fav = data.get("homeTeamOdds", {}).get("favorite", False)
        away_fav = data.get("awayTeamOdds", {}).get("favorite", False)
        if spread is not None:
            factor = min(abs(spread) * 2, 25)
            if home_fav:
                home_prob = min(52 + factor, 85)
                away_prob = 100 - home_prob
            elif away_fav:
                away_prob = min(52 + factor, 85)
                home_prob = 100 - away_prob
            else:
                home_prob = away_prob = 50
        else:
            home_prob = away_prob = 50
    return spread, over_under, home_prob, away_prob


def _weather(event, game_id):
    temperature = condition = None
    weather = event.get("weather")
    if weather:
        temperature = weather.get("temperature")
        condition = weather.get("displayValue")
        if not condition:
            condition = weather.get("condition", weather.get("conditionId"))
        if condition and str(condition).isdigit():
            condition = WEATHER_CONDITION_MAP.get(str(condition))
    return temperature, condition


def _broadcast(competition):
    for entry in competition.get("broadcasts") or []:
        names = entry.get("names") or []
        if names:
            return names[0]
    for geo in competition.get("geoBroadcasts") or []:
        media = geo.get("media") or {}
        if media.get("shortName"):
            return media["shortName"]
    return None


def _gamecast_url(event):
    for link in event.get("links", []):
        if link.get("text") == "Gamecast" or link.get("shortText") == "Gamecast":
            return link.get("href")
    return None


def parse_scoreboard(payload, season, game_year, slug_lookup=team_slug):
    """Yield (game_id, defaults) tuples parsed from an ESPN scoreboard payload."""
    game_week = ((payload or {}).get("week") or {}).get("number")
    if game_week is None:
        logger.warning("Skipping ESPN scoreboard payload missing week.number")
        return

    for event in payload.get("events", []):
        for competition in event.get("competitions", []):
            try:
                game_id = _int(competition["id"])
                status_detail = competition["status"]["type"]
                status_name = status_detail["name"]
                status_type = STATUS_MAP.get(status_name, status_name)
                status_title = (
                    status_detail["detail"]
                    if status_type == "inprogress"
                    else status_detail["description"]
                )

                teams = {"home": {}, "away": {}}
                for competitor in competition["competitors"]:
                    side = competitor["homeAway"]
                    p1, p2, p3, p4, ot = _linescores(competitor)
                    teams[side] = {
                        "id": _int(competitor["id"]),
                        "slug": slug_lookup(competitor["id"]),
                        "name": competitor["team"]["displayName"],
                        "winner": competitor.get("winner", False),
                        "score": _int(competitor.get("score")),
                        "p": (p1, p2, p3, p4, ot),
                    }

                home, away = teams["home"], teams["away"]
                if home.get("winner"):
                    winner = home["slug"]
                elif away.get("winner"):
                    winner = away["slug"]
                else:
                    winner = ""

                spread, over_under, home_prob, away_prob = _win_probabilities(competition)
                temperature, condition = _weather(event, game_id)

                defaults = {
                    "slug": "{}-{}".format(home["slug"], away["slug"]),
                    "competition": "nfl",
                    "gameWeek": str(game_week),
                    "gameyear": str(game_year),
                    "gameseason": int(season),
                    "startTimestamp": parse_datetime(competition["date"]),
                    "gameWinner": winner,
                    "statusType": status_type,
                    "statusTitle": status_title,
                    "homeTeamId": home["id"],
                    "homeTeamSlug": home["slug"],
                    "homeTeamName": home["name"],
                    "homeTeamScore": home["score"],
                    "homeTeamPeriod1": home["p"][0],
                    "homeTeamPeriod2": home["p"][1],
                    "homeTeamPeriod3": home["p"][2],
                    "homeTeamPeriod4": home["p"][3],
                    "homeTeamPeriodOT": home["p"][4],
                    "awayTeamId": away["id"],
                    "awayTeamSlug": away["slug"],
                    "awayTeamName": away["name"],
                    "awayTeamScore": away["score"],
                    "awayTeamPeriod1": away["p"][0],
                    "awayTeamPeriod2": away["p"][1],
                    "awayTeamPeriod3": away["p"][2],
                    "awayTeamPeriod4": away["p"][3],
                    "awayTeamPeriodOT": away["p"][4],
                    "homeTeamWinProbability": home_prob,
                    "awayTeamWinProbability": away_prob,
                    "spread": spread,
                    "overUnder": over_under,
                    "temperature": temperature,
                    "weatherCondition": condition,
                    "venueIndoor": (competition.get("venue") or {}).get("indoor", False),
                    "broadcast": _broadcast(competition),
                    "gamecastUrl": _gamecast_url(event),
                }
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "Skipping malformed ESPN competition payload for event=%s competition=%s: %s",
                    event.get("id"),
                    competition.get("id"),
                    exc,
                )
                continue

            # A flapping ESPN poll can report a game "finished" while briefly
            # dropping the scores. Writing that would null out a good final, so
            # skip it and let a later, complete poll persist the result.
            if status_type == "finished" and (
                home["score"] is None or away["score"] is None
            ):
                logger.warning(
                    "Skipping finished game %s with missing score (home=%s away=%s)",
                    game_id, home["score"], away["score"],
                )
                continue

            yield game_id, defaults


def current_week_for_today(season=None):
    today = date.today().strftime("%Y-%m-%d")
    weeks = GameWeeks.objects.all()
    if season is not None:
        weeks = weeks.filter(season=season)
    week = weeks.filter(date=today).values_list("weekNumber", flat=True).first()
    if week is not None:
        return str(week)
    # No row for today (off-day/schedule gap): fall back to the most recent
    # week that has already started rather than hardcoding "1", which would
    # churn week-1 rows with stale ESPN data on every off-season run. Scoped to
    # the season so a prior season's rows can't bleed in.
    recent = (
        weeks.filter(date__lte=today)
        .order_by("-date")
        .values_list("weekNumber", flat=True)
        .first()
    )
    return str(recent) if recent is not None else "1"


def fetch_scoreboard(week, game_year):
    response = requests.get(
        ESPN_SCOREBOARD_URL,
        headers={"Content-Type": "application/json"},
        params={"week": week, "dates": game_year},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


class Command(BaseCommand):
    help = "Fetch NFL games from ESPN and upsert GamesAndScores rows."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, default=None)
        parser.add_argument(
            "--week", default=None, help="Week number (defaults to today's week)."
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        year = season_start_year(season)
        week = options["week"] or current_week_for_today(season)
        self.stdout.write(f"Updating games for season {season} week {week}")

        payload = fetch_scoreboard(week, year)
        count = 0
        for game_id, defaults in parse_scoreboard(payload, season, year):
            GamesAndScores.objects.update_or_create(id=game_id, defaults=defaults)
            count += 1
            self.stdout.write(f" - {defaults['slug']} ({defaults['statusType']})")

        self.stdout.write(self.style.SUCCESS(f"Upserted {count} games."))
