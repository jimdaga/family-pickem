"""Server-Sent Events endpoint for live game scores (Phase 3b).

Served by uvicorn (ASGI). Each connection subscribes to the season/week's Redis
channel via redis.asyncio and streams change events published by update_games.
Auth is enforced by RequireLoginForInternalPagesMiddleware (the path is not in
its public allowlist). Uses only async-safe I/O — no sync ORM in this view.
"""
import asyncio
import logging
import os

from asgiref.sync import sync_to_async
from django.http import HttpResponseBadRequest, StreamingHttpResponse

from pickem_api.live_events import scores_channel

logger = logging.getLogger(__name__)

KEEPALIVE_SECONDS = 20


async def _event_stream(channel):
    import redis.asyncio as aioredis

    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        # No broker: end the stream immediately; the client falls back to poll.
        return
    # Created inside the try so a subscribe() failure (Redis blip/auth) still
    # runs the finally cleanup instead of leaking the connection.
    client = None
    pubsub = None
    try:
        client = aioredis.from_url(url)
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        # Prime the connection so proxies flush headers immediately.
        yield ": connected\n\n"
        while True:
            # redis.asyncio's get_message() only blocks when *it* is given a
            # timeout (internally passed to the socket read); wrapping a
            # bare get_message() in asyncio.wait_for() does nothing, since
            # the un-timed call returns None immediately whenever no message
            # is pending (block=False, timeout=0.0 by default) — that turns
            # this loop into a tight CPU-pegging busy loop instead of an
            # idle wait. Passing timeout= here is what actually blocks; the
            # outer wait_for is only a defensive backstop.
            try:
                msg = await asyncio.wait_for(
                    pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=KEEPALIVE_SECONDS
                    ),
                    timeout=KEEPALIVE_SECONDS + 5,
                )
            except asyncio.TimeoutError:
                yield ": ping\n\n"  # keepalive comment (backstop path)
                continue
            if msg is None:
                yield ": ping\n\n"  # keepalive comment (normal path)
                continue
            if msg.get("type") == "message":
                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield f"data: {data}\n\n"
    except Exception:
        # Redis unreachable / dropped: end the stream gracefully so the client
        # falls back to polling, without Django logging an unhandled app error.
        logger.warning("SSE score stream ended on error", exc_info=True)
        return
    finally:
        # Best-effort cleanup; never raise from finally even if subscribe failed.
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                pass
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


async def live_scores_events(request):
    """SSE stream of live score changes for ?week=<n> in the current season."""
    week = request.GET.get("week", "").strip()
    if not week.isdigit():
        return HttpResponseBadRequest("week required")

    from pickem.utils import get_season

    season = await sync_to_async(get_season)()
    channel = scores_channel(season, week)

    resp = StreamingHttpResponse(
        _event_stream(channel), content_type="text/event-stream"
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"  # defeat proxy/Cloudflare buffering
    return resp
