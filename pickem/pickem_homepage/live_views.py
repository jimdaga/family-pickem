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
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    StreamingHttpResponse,
)

from pickem_api.live_events import scores_channel, standings_channel

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


def _resolve_pool_for_member(user, family_slug, pool_slug):
    """(pool_id, season) if `user` is a member of the pool, else None. Sync — call
    via sync_to_async from the async view.

    Mirrors the status filtering in pickem_api.authz (resolve_family /
    resolve_pool_context / require_family_membership): an inactive Family
    (soft-deleted — see family_pool_admin_delete_family), an inactive/archived
    Pool, or an inactive membership must all be treated the same as "not a
    member" here, matching how the rest of the tenant surface 404s them.
    """
    from pickem_api.models import Family, FamilyMembership, Pool

    pool = (
        Pool.objects.filter(
            family__slug=family_slug,
            slug=pool_slug,
            status=Pool.Status.ACTIVE,
            family__status=Family.Status.ACTIVE,
        )
        .values("id", "season", "family_id")
        .first()
    )
    if not pool:
        return None
    if not FamilyMembership.objects.filter(
        user=user,
        family_id=pool["family_id"],
        status=FamilyMembership.Status.ACTIVE,
    ).exists():
        return None
    return pool["id"], pool["season"]


async def live_standings_events(request):
    """SSE stream of live standings changes for ?family=<slug>&pool=<slug>.

    Membership is verified per-request via _resolve_pool_for_member (run off
    the event loop through sync_to_async) — no sync ORM access in this view
    body itself.
    """
    family_slug = request.GET.get("family", "").strip()
    pool_slug = request.GET.get("pool", "").strip()
    if not family_slug or not pool_slug:
        return HttpResponseBadRequest("family and pool required")

    resolved = await sync_to_async(_resolve_pool_for_member)(
        request.user, family_slug, pool_slug
    )
    if resolved is None:
        return HttpResponseForbidden("not a member of this pool")
    pool_id, season = resolved

    resp = StreamingHttpResponse(
        _event_stream(standings_channel(pool_id, season)),
        content_type="text/event-stream",
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"  # defeat proxy/Cloudflare buffering
    return resp
