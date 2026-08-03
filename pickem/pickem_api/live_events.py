"""Publish compact live game-score events to Redis for the SSE endpoint.

The scheduler pod calls publish_score_event() from update_games after a game's
score/status changes; web pods subscribe to the channel in the async SSE view
(see pickem_homepage/live_views.py). Redis is the same instance used for the
cache (REDIS_URL). All failures are best-effort/logged — a Redis outage must
never break the pipeline.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# Changing any of these on a GamesAndScores row triggers a publish.
LIVE_SCORE_FIELDS = (
    "homeTeamScore",
    "awayTeamScore",
    "statusType",
    "statusTitle",
    "gameWinner",
)


def scores_channel(season, week):
    """Redis pub/sub channel for a season+week's live scores."""
    return f"scores:{season}:{week}"


def score_event_payload(game):
    """Compact JSON-serializable dict of a game's live fields for the client."""
    return {
        "game_id": game.id,
        "home_score": game.homeTeamScore,
        "away_score": game.awayTeamScore,
        "status": game.statusType,
        "status_title": game.statusTitle,
        "winner": game.gameWinner,
        "home_periods": [game.homeTeamPeriod1, game.homeTeamPeriod2,
                         game.homeTeamPeriod3, game.homeTeamPeriod4,
                         game.homeTeamPeriodOT],
        "away_periods": [game.awayTeamPeriod1, game.awayTeamPeriod2,
                         game.awayTeamPeriod3, game.awayTeamPeriod4,
                         game.awayTeamPeriodOT],
    }


def _redis_client():
    """A sync redis-py client from REDIS_URL, or None if unset."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    import redis

    return redis.from_url(url)


def publish_event(channel, payload):
    """Best-effort publish of one event to a Redis channel. Never raises."""
    try:
        client = _redis_client()
        if client is None:
            return
        client.publish(channel, json.dumps(payload))
    except Exception:
        logger.warning("live event publish failed", exc_info=True)


def publish_score_event(season, week, payload):
    """Best-effort publish of one score change. Never raises."""
    publish_event(scores_channel(season, week), payload)


# Period fields also trigger a scores publish (clock/quarter live updates).
_PERIOD_FIELDS = (
    "homeTeamPeriod1", "homeTeamPeriod2", "homeTeamPeriod3", "homeTeamPeriod4",
    "homeTeamPeriodOT", "awayTeamPeriod1", "awayTeamPeriod2", "awayTeamPeriod3",
    "awayTeamPeriod4", "awayTeamPeriodOT",
)
SCORE_TRIGGER_FIELDS = LIVE_SCORE_FIELDS + _PERIOD_FIELDS


def standings_channel(pool_id, season):
    """Redis pub/sub channel for a pool+season's live standings."""
    return f"standings:{pool_id}:{season}"


def standings_event_payload(row, week):
    """Compact JSON-serializable dict of a standings row's live fields."""
    return {
        "user_id": row.userID,
        "total_points": row.total_points,
        "week": week,
        "week_points": getattr(row, f"week_{week}_points", None),
        "current_rank": getattr(row, "current_rank", None),
    }
