"""Weekly winner engine: per-pool winner calculation with pluggable tiebreakers.

Rules live on ``PoolSettings`` (per family/pool): the bonus value
(``weekly_winner_points``), the tiebreaker chain (``primary_tiebreaker``,
``secondary_tiebreaker``) and whether tiebreakers apply at all
(``allow_tiebreaker``). Strategies are registered against those choice
values, so adding a rule type is: add a ``TextChoices`` entry, register a
``Tiebreaker`` subclass — nothing else changes.

The engine is condition-triggered rather than cron-scheduled: it only acts
once every game of an (season, week) is finished *and* scored, which in
practice means Monday Night Football has gone final and ``update_picks``
has flagged the correct picks. It is idempotent — pools that already have
a winner for the week are skipped — so it is safe to run every minute from
the existing update pipeline.
"""

import logging
import random

import requests

from pickem_api.models import (
    FamilyAuditLog,
    GamePicks,
    GamesAndScores,
    PoolSettings,
    userSeasonPoints,
)

logger = logging.getLogger(__name__)

ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
)
REQUEST_TIMEOUT = 30


# --------------------------------------------------------------------------
# Game stats (ESPN) — injected so tests never touch the network
# --------------------------------------------------------------------------

class GameStatsProvider:
    """Interface for real-game stats used by tiebreakers."""

    def combined_yards(self, game_id):  # pragma: no cover - interface
        raise NotImplementedError


class EspnGameStatsProvider(GameStatsProvider):
    """Fetches team stats from ESPN's game summary endpoint."""

    def combined_yards(self, game_id):
        response = requests.get(
            ESPN_SUMMARY_URL,
            params={"event": game_id},
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        total = 0
        found = False
        for team in payload.get("boxscore", {}).get("teams", []):
            for stat in team.get("statistics", []):
                if stat.get("name") == "totalYards":
                    total += int(float(stat.get("displayValue", 0)))
                    found = True
        if not found:
            raise ValueError(f"No totalYards in ESPN summary for game {game_id}")
        return total


# --------------------------------------------------------------------------
# Week context
# --------------------------------------------------------------------------

class WeekContext:
    """Everything a tiebreaker may need, fetched lazily and at most once."""

    def __init__(self, *, pool, season, week, stats_provider):
        self.pool = pool
        self.season = season
        self.week = week
        self.stats_provider = stats_provider
        self._tiebreaker_game = None
        self._tiebreaker_game_loaded = False
        self._actual_yards = None
        self._actual_yards_loaded = False
        self.missing_tiebreaker_actual = False

    @property
    def tiebreaker_game(self):
        """The flagged tiebreaker game, else the last game of the week (MNF)."""
        if not self._tiebreaker_game_loaded:
            games = GamesAndScores.objects.filter(
                gameseason=self.season,
                gameWeek=str(self.week),
                competition=self.pool.competition,
            )
            self._tiebreaker_game = (
                games.filter(tieBreakerGame=True).order_by('-startTimestamp').first()
                or games.order_by('-startTimestamp').first()
            )
            self._tiebreaker_game_loaded = True
        return self._tiebreaker_game

    @property
    def actual_total_score(self):
        game = self.tiebreaker_game
        if game is None or game.homeTeamScore is None or game.awayTeamScore is None:
            return None
        return game.homeTeamScore + game.awayTeamScore

    @property
    def actual_combined_yards(self):
        if not self._actual_yards_loaded:
            self._actual_yards_loaded = True
            game = self.tiebreaker_game
            if game is not None:
                try:
                    self._actual_yards = self.stats_provider.combined_yards(game.id)
                except Exception:
                    logger.exception(
                        "Could not fetch combined yards for game %s", game and game.id
                    )
                    self._actual_yards = None
        return self._actual_yards

    def prediction(self, user_id, field):
        """A candidate's tiebreaker prediction for the tiebreaker game."""
        game = self.tiebreaker_game
        if game is None:
            return None
        return (
            GamePicks.objects.filter(
                pool=self.pool,
                userID=str(user_id),
                pick_game_id=game.id,
            )
            .values_list(field, flat=True)
            .first()
        )


# --------------------------------------------------------------------------
# Tiebreaker strategies
# --------------------------------------------------------------------------

TIEBREAKERS = {}


def register_tiebreaker(key):
    def decorator(cls):
        TIEBREAKERS[key] = cls()
        return cls

    return decorator


class Tiebreaker:
    """A strategy narrows the candidate list; returning it unchanged means
    "could not resolve" and the chain moves on (or ends in co-winners)."""

    #: Terminal strategies always end the chain (split/coin-flip).
    terminal = False

    def resolve(self, candidates, ctx):  # pragma: no cover - interface
        raise NotImplementedError


class _ClosestPrediction(Tiebreaker):
    """Shared: keep the candidates whose prediction is closest to an actual."""

    prediction_field = None  # GamePicks field holding the guess

    def actual(self, ctx):  # pragma: no cover - interface
        raise NotImplementedError

    def eligible(self, prediction, actual):
        return prediction is not None

    def resolve(self, candidates, ctx):
        actual = self.actual(ctx)
        if actual is None:
            if any(
                ctx.prediction(entry.userID, self.prediction_field) is not None
                for entry in candidates
            ):
                ctx.missing_tiebreaker_actual = True
            return candidates
        scored = []
        for entry in candidates:
            prediction = ctx.prediction(entry.userID, self.prediction_field)
            if self.eligible(prediction, actual):
                scored.append((abs(actual - prediction), entry))
        if not scored:
            return candidates
        best = min(distance for distance, _ in scored)
        return [entry for distance, entry in scored if distance == best]


@register_tiebreaker(PoolSettings.PrimaryTiebreaker.TOTAL_SCORE)
class ClosestTotalScore(_ClosestPrediction):
    prediction_field = 'tieBreakerScore'

    def actual(self, ctx):
        return ctx.actual_total_score


@register_tiebreaker(PoolSettings.PrimaryTiebreaker.TOTAL_SCORE_NO_OVER)
class ClosestTotalScoreWithoutGoingOver(ClosestTotalScore):
    def eligible(self, prediction, actual):
        return prediction is not None and prediction <= actual


@register_tiebreaker(PoolSettings.PrimaryTiebreaker.COMBINED_YARDS)
class ClosestCombinedYards(_ClosestPrediction):
    prediction_field = 'tieBreakerYards'

    def actual(self, ctx):
        return ctx.actual_combined_yards


@register_tiebreaker(PoolSettings.SecondaryTiebreaker.SPLIT_POINTS)
class SplitPoints(Tiebreaker):
    """Terminal: everyone still tied is a winner; the bonus is divided."""

    terminal = True
    split = True

    def resolve(self, candidates, ctx):
        return candidates


@register_tiebreaker(PoolSettings.SecondaryTiebreaker.COIN_FLIP)
class CoinFlip(Tiebreaker):
    """Terminal: one deterministic winner. Seeded from (pool, season, week)
    so re-runs — including --force re-awards — pick the same person."""

    terminal = True

    def resolve(self, candidates, ctx):
        rng = random.Random(f"{ctx.pool.id}-{ctx.season}-{ctx.week}")
        ordered = sorted(candidates, key=lambda entry: str(entry.userID))
        return [rng.choice(ordered)]


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

def week_is_complete(season, week, competition='nfl'):
    """True once every game of the week has finished and been scored —
    i.e. Monday Night Football is final and picks have been graded."""
    games = GamesAndScores.objects.filter(
        gameseason=season, gameWeek=str(week), competition=competition
    )
    if not games.exists():
        return False
    return not games.exclude(statusType='finished', gameScored=True).exists()


def complete_weeks(season, competition='nfl'):
    """All fully complete weeks of the season, ascending. The award loop
    walks every one (awarding is idempotent per pool/week) so a scheduler
    outage across a week boundary can't permanently skip a week's bonus."""
    weeks = (
        GamesAndScores.objects.filter(gameseason=season, competition=competition)
        .order_by()  # clear Meta.ordering so DISTINCT applies to gameWeek only
        .values_list('gameWeek', flat=True)
        .distinct()
    )
    numeric = sorted(int(w) for w in weeks if str(w).isdigit())
    return [
        week for week in numeric if week_is_complete(season, week, competition)
    ]


def latest_complete_week(season, competition='nfl'):
    weeks = complete_weeks(season, competition)
    return weeks[-1] if weeks else None


def _recompute_total(row):
    total = 0
    for week in range(1, 19):
        total += (getattr(row, f'week_{week}_points') or 0)
        total += (getattr(row, f'week_{week}_bonus') or 0)
    row.total_points = total


def award_weekly_winners(pool, season, week, *, stats_provider=None, force=False):
    """Calculate and persist the weekly winner(s) for one pool.

    Returns a result dict (for logging/reporting) or None when there is
    nothing to do (week already awarded, no scores yet, ...).
    """
    stats_provider = stats_provider or EspnGameStatsProvider()
    points_field = f'week_{week}_points'
    winner_field = f'week_{week}_winner'
    bonus_field = f'week_{week}_bonus'

    rows = list(
        userSeasonPoints.objects.filter(pool=pool, gameseason=season)
    )
    if not rows:
        return None
    if not force and any(getattr(row, winner_field) for row in rows):
        return None  # already awarded (engine or commissioner) — idempotent

    top_score = max((getattr(row, points_field) or 0) for row in rows)
    if top_score <= 0:
        return None  # nobody scored this week
    candidates = [row for row in rows if (getattr(row, points_field) or 0) == top_score]

    settings = PoolSettings.objects.filter(pool=pool).first() or PoolSettings(pool=pool)
    bonus = settings.weekly_winner_points
    ctx = WeekContext(pool=pool, season=season, week=week, stats_provider=stats_provider)

    method = 'top_score'
    split = False
    if len(candidates) > 1 and settings.allow_tiebreaker:
        chain = [settings.primary_tiebreaker, settings.secondary_tiebreaker]
        for key in chain:
            strategy = TIEBREAKERS.get(key)
            if strategy is None:
                logger.warning("Unknown tiebreaker %r configured on pool %s", key, pool)
                continue
            narrowed = strategy.resolve(candidates, ctx)
            if strategy.terminal:
                candidates = narrowed
                method = key
                split = getattr(strategy, 'split', False)
                break
            if len(narrowed) < len(candidates):
                candidates = narrowed
                method = key
            if len(candidates) == 1:
                break
    elif len(candidates) > 1:
        method = 'co_winners'

    if len(candidates) > 1 and not split and method not in ('co_winners',):
        # Chain exhausted without a unique winner: co-winners, full bonus each.
        method = f'{method}+co_winners' if method != 'top_score' else 'co_winners'

    if len(candidates) > 1 and ctx.missing_tiebreaker_actual:
        return None

    per_winner_bonus = bonus // len(candidates) if split else bonus
    winner_ids = {row.pk for row in candidates}
    winner_bonus_map = {}
    if split:
        ordered_winners = sorted(candidates, key=lambda row: str(row.userID))
        remainder = bonus % len(ordered_winners)
        for index, row in enumerate(ordered_winners):
            winner_bonus_map[row.pk] = per_winner_bonus + (1 if index < remainder else 0)

    for row in rows:
        is_winner = row.pk in winner_ids
        setattr(row, winner_field, is_winner)
        if is_winner:
            applied_bonus = winner_bonus_map.get(row.pk, per_winner_bonus)
        else:
            applied_bonus = getattr(row, bonus_field) if not force else 0
        setattr(row, bonus_field, applied_bonus)
        _recompute_total(row)
        row.save(update_fields=[winner_field, bonus_field, 'total_points'])

    result = {
        'week': week,
        'winners': sorted(str(row.userID) for row in candidates),
        'bonus_each': per_winner_bonus,
        'method': method,
        'tied_at': top_score,
    }
    FamilyAuditLog.objects.create(
        family=pool.family,
        pool=pool,
        actor=None,
        action=FamilyAuditLog.Action.WEEK_WINNER_UPDATED,
        target_type='userSeasonPoints',
        target_id=f'week_{week}',
        metadata={'summary': 'Automated weekly winner award', **result},
    )
    return result
