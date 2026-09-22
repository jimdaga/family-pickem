"""Producers that turn pipeline events into in-app notifications.

The notification model and its navbar UI shipped as a scaffold with no
producers at all; this is the first one. Everything here runs from the update
pipeline, which ticks every minute and back-fills weeks it missed, so each
producer must be safe to call repeatedly with the same arguments. They achieve
that with ``Notification.dedupe_key`` rather than by checking for an existing
row first -- the database rejects the duplicate, so a concurrent second tick
cannot slip one through.
"""

import logging

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse

from pickem_api.models import Notification, userSeasonPoints

logger = logging.getLogger(__name__)

#: Cap on how many pools a digest spells out. Notification.body is 500 chars;
#: a member of many families would otherwise overflow it and raise on save.
MAX_POOLS_LISTED = 6


def _display_name(user):
    """Username, title-cased -- mirrors the ``display_name`` template filter.

    Kept local rather than imported from ``pickem_homepage.templatetags``:
    ``pickem_api`` must not depend on the frontend app, and this is a producer
    writing stored text, not a template rendering a request.
    """
    name = (getattr(user, "username", "") or "").strip()
    return name[:1].upper() + name[1:] if name else "A player"


def _pool_standings_url(pool):
    return reverse(
        'family_pool_standings',
        kwargs={'family_slug': pool.family.slug, 'pool_slug': pool.slug},
    )


def _winner_label(winner_ids, viewer_id, names):
    """How this pool's winners read to one viewer: 'you', or their names."""
    if viewer_id in winner_ids:
        others = [names.get(w, "a player") for w in winner_ids if w != viewer_id]
        return " & ".join(["you"] + others)
    return " & ".join(names.get(w, "a player") for w in winner_ids)


def publish_week_winner_digest(season, week, pools):
    """Notify every participant of a completed week's winners, once.

    One notification per user rather than one per pool: a member of several
    families would otherwise get a burst of near-identical rows for a single
    event. The digest names each of *their* pools and who won it, and the title
    leads with their own win when they have one.

    Only pools with an awarded winner are included -- a pool whose week has not
    been awarded yet simply doesn't appear, and a later run that awards it will
    not retroactively edit anyone's existing digest (the dedupe key is per
    user/season/week). Returns the number of notifications created.
    """
    winner_field = f'week_{week}_winner'
    points_field = f'week_{week}_points'

    pool_ids = [p.pk for p in pools]
    if not pool_ids:
        return 0

    rows = list(
        userSeasonPoints.objects
        .filter(gameseason=season, pool_id__in=pool_ids)
        .select_related('pool', 'pool__family')
    )
    if not rows:
        return 0

    # Group participants and winners by pool, keeping only awarded pools.
    by_pool = {}
    for row in rows:
        by_pool.setdefault(row.pool_id, {'pool': row.pool, 'rows': []})['rows'].append(row)

    awarded = {}
    for pool_id, entry in by_pool.items():
        winners = [r for r in entry['rows'] if getattr(r, winner_field, False)]
        if winners:
            awarded[pool_id] = {
                'pool': entry['pool'],
                'rows': entry['rows'],
                'winner_ids': [str(r.userID) for r in winners],
                'points': getattr(winners[0], points_field, None) or 0,
            }
    if not awarded:
        return 0

    # Resolve every id we might name, in one query.
    referenced = {str(r.userID) for e in awarded.values() for r in e['rows']}
    users = {
        str(u.pk): u
        for u in User.objects.filter(pk__in=[i for i in referenced if i.isdigit()])
    }
    names = {uid: _display_name(u) for uid, u in users.items()}

    # Invert to per-user: which awarded pools is this person in?
    per_user = {}
    for entry in awarded.values():
        for row in entry['rows']:
            per_user.setdefault(str(row.userID), []).append(entry)

    created = 0
    for user_id, entries in per_user.items():
        user = users.get(user_id)
        if user is None or not user.is_active:
            # Soft-deleted or blocked accounts don't accumulate notifications.
            continue

        entries.sort(key=lambda e: (e['pool'].family.name or '', e['pool'].name or ''))
        won_somewhere = any(user_id in e['winner_ids'] for e in entries)

        segments = [
            f"{e['pool'].family.name} — {_winner_label(e['winner_ids'], user_id, names)}"
            f" ({e['points']} pts)"
            for e in entries[:MAX_POOLS_LISTED]
        ]
        remaining = len(entries) - len(segments)
        if remaining > 0:
            segments.append(f"and {remaining} more")
        body = " · ".join(segments)[:500]

        # Link to a pool they won when there is one; otherwise the first listed.
        target = next(
            (e for e in entries if user_id in e['winner_ids']), entries[0],
        )

        try:
            _, was_created = Notification.objects.get_or_create(
                dedupe_key=f"week_winners:{season}:{week}:{user_id}",
                defaults={
                    'recipient': user,
                    'kind': Notification.Kind.WEEK_WINNER,
                    'title': (
                        f"You won Week {week}!" if won_somewhere
                        else f"Week {week} winners"
                    ),
                    'body': body,
                    'url': _pool_standings_url(target['pool']),
                    'family': target['pool'].family,
                    'pool': target['pool'],
                },
            )
        except IntegrityError:
            # Another tick won the race on the unique key -- that is the
            # constraint doing its job, not an error worth propagating.
            continue

        if was_created:
            created += 1

    return created
