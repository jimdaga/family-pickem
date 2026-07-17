"""Synthetic-data factories for the grading integration suite.

Hand-rolled on purpose: ``requirements.txt`` is also the production image's
dependency set, and these factories are thin enough that Factory Boy would
add a dependency without removing meaningful code. The API mimics Factory
Boy's shape — every field has a sensible default and each test overrides
only what its scenario is about.

The one rule that matters everywhere: factories write **production-shaped
rows**. ``finish_game`` sets exactly the fields ``update_games`` would set
from ESPN (scores, winner *slug*, ``statusType='finished'``) and nothing
more — scoring/flagging is left to the real pipeline commands.
"""

import itertools
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from pickem_api.models import (
    Family,
    FamilyMembership,
    GamePicks,
    GamesAndScores,
    Pool,
    PoolSettings,
)

#: Fixed synthetic season (YYZZ). Every factory and pipeline call pins this so
#: ``get_season()`` (which hits the /api/currentseason endpoint) is never used.
SEASON = 2526
GAMEYEAR = "2025"

_family_seq = itertools.count(1)
_user_seq = itertools.count(1)
_game_seq = itertools.count(1)

#: Synthetic game ids start high above any real ESPN event id in fixtures.
_GAME_ID_BASE = 900_000


def create_family(name=None):
    n = next(_family_seq)
    name = name or f"Family {n}"
    return Family.objects.create(name=name, slug=f"family-{n}")


def create_user(username=None):
    n = next(_user_seq)
    username = username or f"user{n}"
    return User.objects.create_user(
        username=f"{username}-{n}",
        email=f"{username}-{n}@example.test",
        password="pw",
        first_name=username.capitalize(),
    )


def join_family(family, user, role=FamilyMembership.Role.MEMBER):
    return FamilyMembership.objects.create(family=family, user=user, role=role)


def create_pool(family, season=SEASON, **settings_overrides):
    """An active pool plus its PoolSettings row (overrides go to settings)."""
    pool = Pool.objects.create(
        family=family,
        name=f"{family.name} Pool",
        slug="main",
        season=season,
        competition="nfl",
        status=Pool.Status.ACTIVE,
        is_default=True,
    )
    PoolSettings.objects.create(pool=pool, **settings_overrides)
    return pool


class League:
    """A family + active pool + users with active memberships.

    ``league.users`` maps the requested username to its ``User``; games and
    picks are created through module functions so tests read top-to-bottom.
    """

    def __init__(self, family, pool, users):
        self.family = family
        self.pool = pool
        self.users = users

    @property
    def settings(self):
        return self.pool.settings

    def __getitem__(self, username):
        return self.users[username]


def create_league(*usernames, family_name=None, season=SEASON, **settings_overrides):
    family = create_family(name=family_name)
    pool = create_pool(family, season=season, **settings_overrides)
    users = {}
    for username in usernames:
        user = create_user(username)
        join_family(family, user)
        users[username] = user
    return League(family, pool, users)


def create_game(
    week,
    *,
    season=SEASON,
    home=None,
    away=None,
    kickoff=None,
    mnf=False,
    tiebreaker_game=None,
    home_win_probability=None,
    away_win_probability=None,
    spread=None,
):
    """A scheduled (not yet played) NFL game.

    Kickoffs are placed in the past — ``week`` days after a base a month ago,
    each game an hour after the previous — so picks are already locked and
    ``update_missed_picks`` treats the game as started. ``mnf=True`` marks the
    week's tiebreaker game and pushes it to the end of the week's slate.
    """
    n = next(_game_seq)
    home = home or f"home{n}"
    away = away or f"away{n}"
    if kickoff is None:
        base = timezone.now() - timedelta(days=30)
        kickoff = base + timedelta(days=week, hours=n % 24)
        if mnf:
            kickoff += timedelta(days=1)
    if tiebreaker_game is None:
        tiebreaker_game = mnf
    return GamesAndScores.objects.create(
        id=_GAME_ID_BASE + n,
        slug=f"{away}-{home}",
        competition="nfl",
        gameWeek=str(week),
        gameyear=GAMEYEAR,
        gameseason=season,
        startTimestamp=kickoff,
        statusType="scheduled",
        statusTitle="Scheduled",
        gameWinner="",
        homeTeamId=n * 2,
        homeTeamSlug=home,
        homeTeamName=home.replace("-", " ").title(),
        awayTeamId=n * 2 + 1,
        awayTeamSlug=away,
        awayTeamName=away.replace("-", " ").title(),
        tieBreakerGame=tiebreaker_game,
        homeTeamWinProbability=home_win_probability,
        awayTeamWinProbability=away_win_probability,
        spread=spread,
    )


def finish_game(game, home_score, away_score):
    """Record a final score exactly the way ``update_games`` would.

    Scores, the winner's **slug** (empty on a tie), and finished status —
    nothing else. ``gameScored``/``pick_correct`` are the real pipeline's job.
    """
    game.homeTeamScore = home_score
    game.awayTeamScore = away_score
    if home_score > away_score:
        game.gameWinner = game.homeTeamSlug
    elif away_score > home_score:
        game.gameWinner = game.awayTeamSlug
    else:
        game.gameWinner = ""
    game.statusType = "finished"
    game.statusTitle = "Final"
    game.save()
    return game


def make_pick(pool, user, game, team, *, score=None, yards=None):
    """A user's pick, id-keyed the same way the picks page builds it.

    ``team`` is ``"home"``, ``"away"``, or a raw team slug. ``score``/``yards``
    are the tiebreaker predictions (only meaningful on the tiebreaker game).
    """
    slug = {"home": game.homeTeamSlug, "away": game.awayTeamSlug}.get(team, team)
    return GamePicks.objects.create(
        id=f"{pool.id}-{user.id}-{game.id}",
        pool=pool,
        userEmail=user.email,
        userID=str(user.id),
        uid=user.id,
        slug=game.slug,
        competition=game.competition,
        gameWeek=game.gameWeek,
        gameyear=game.gameyear,
        gameseason=game.gameseason,
        pick_game_id=game.id,
        pick=slug,
        tieBreakerScore=score,
        tieBreakerYards=yards,
    )
