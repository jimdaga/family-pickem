"""Update NFL team win/loss/tie records from ESPN.

ORM-based replacement for the standalone ``cron_update_records.py`` script.
Fetches the team list and per-team season record directly from ESPN and
upserts the global ``Teams`` rows with the ORM (no self-API round-trip).

Teams are global (not pool-scoped), so this command has no tenant awareness.
"""

import logging

import requests
from django.core.management.base import BaseCommand, CommandError

from pickem.utils import get_season
from pickem_api.models import Teams

logger = logging.getLogger(__name__)

ESPN_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
)
ESPN_RECORD_URL = (
    "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
    "seasons/{year}/types/2/teams/{team_id}/record"
)
REQUEST_TIMEOUT = 30


def season_start_year(season):
    """Convert a YYZZ season (e.g. 2526) into the ESPN start year (2025)."""
    return 2000 + int(season) // 100


def fetch_team_list():
    """Return the list of ESPN team dicts (id, slug, displayName, colors, logos)."""
    response = requests.get(
        ESPN_TEAMS_URL,
        headers={"Content-Type": "application/json"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return [
        entry["team"]
        for league in data["sports"][0]["leagues"]
        for entry in league["teams"]
    ]


def fetch_team_record(team_id, year):
    """Return (wins, losses, ties) for a team's regular-season record."""
    response = requests.get(
        ESPN_RECORD_URL.format(year=year, team_id=team_id),
        headers={"Content-Type": "application/json"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    wins = losses = ties = 0
    try:
        stats = response.json()["items"][0]["stats"]
    except (KeyError, IndexError):
        return wins, losses, ties
    for stat in stats:
        if stat["name"] == "wins":
            wins = int(float(stat["value"]))
        elif stat["name"] == "losses":
            losses = int(float(stat["value"]))
        elif stat["name"] == "ties":
            ties = int(float(stat["value"]))
    return wins, losses, ties


class Command(BaseCommand):
    help = "Update NFL team records (wins/losses/ties) from ESPN."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Season in YYZZ format (defaults to the current season).",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        year = season_start_year(season)
        self.stdout.write(f"Updating team records for season {season} (year {year})")

        try:
            teams = fetch_team_list()
        except requests.exceptions.RequestException as exc:
            raise CommandError(f"Failed to fetch team list from ESPN: {exc}")

        updated = 0
        for team in teams:
            slug = team.get("slug", "")
            try:
                wins, losses, ties = fetch_team_record(team["id"], year)
            except requests.exceptions.RequestException as exc:
                logger.warning("Skipping %s: record fetch failed: %s", slug, exc)
                self.stderr.write(f" - {slug}: record fetch failed ({exc})")
                continue

            logo = ""
            logos = team.get("logos") or []
            if logos:
                logo = logos[0].get("href", "")

            Teams.objects.update_or_create(
                id=int(team["id"]),
                defaults={
                    "gameseason": int(season),
                    "teamNameSlug": slug,
                    "teamNameName": team.get("displayName", slug),
                    "teamLogo": logo,
                    "teamWins": wins,
                    "teamLosses": losses,
                    "teamTies": ties,
                    "color": team.get("color", "") or "",
                    "alternateColor": team.get("alternateColor", "") or "",
                },
            )
            updated += 1
            self.stdout.write(f" - {slug}: {wins}-{losses}-{ties}")

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} team records."))
