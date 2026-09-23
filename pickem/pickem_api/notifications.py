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
from django.db import IntegrityError, transaction
from django.urls import reverse

from pickem_api.models import FamilyMembership, Notification, userSeasonPoints

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


def _digest_title(week, won_pools, total_pools):
    """The one line that has to work at a glance in the bell.

    The body always carries the per-pool truth, but the title is what a reader
    sees without opening anything -- so it has to distinguish "you won one of
    your three pools" from "you swept all three", which are very different
    pieces of news wearing the same words otherwise.
    """
    if not won_pools:
        return f"Week {week} winners"
    if total_pools == 1:
        return f"You won Week {week}!"
    if len(won_pools) == total_pools:
        return f"You swept Week {week}: all {total_pools} pools!"
    if len(won_pools) == 1:
        return f"You won Week {week} in {won_pools[0]}"
    return f"You won Week {week} in {len(won_pools)} of {total_pools} pools"


def _pool_label(entry, entries):
    """Family name, plus the pool name when this reader has several pools in it.

    Families can run more than one pool a season, and "Smith: you · Smith: Bob"
    would leave the reader guessing which Smith pool is which.
    """
    family = entry['pool'].family
    same_family = sum(1 for e in entries if e['pool'].family_id == family.pk)
    return f"{family.name} ({entry['pool'].name})" if same_family > 1 else family.name


def _refresh_digest(existing, fields):
    """Bring an existing digest up to date; True if anything changed.

    New information (a pool awarded since, or a corrected winner) resurfaces the
    row as unread. Identical content is left alone, which is the common case on
    every repeat tick.
    """
    if all(getattr(existing, f) == v for f, v in fields.items()):
        return False
    for f, v in fields.items():
        setattr(existing, f, v)
    existing.read_at = None
    existing.save(update_fields=[*fields, 'read_at'])
    return True


def publish_week_winner_digest(season, week, pools, *, create_missing=True):
    """Notify every current member of a week's winners: one digest per person.

    One notification per user rather than one per pool: a member of several
    families would otherwise get a burst of near-identical rows for a single
    event. The digest names each of *their* awarded pools and who won it, and
    the title leads with their own win when they have one.

    Safe to call repeatedly. The digest is keyed per user/season/week, and a
    repeat call with unchanged results is a no-op. When results *have* changed
    since the digest was written -- a pool awarded on a later tick, or a
    --force re-award that changed the winner -- the existing row is rewritten
    and marked unread again, so nobody is left holding a digest that says they
    didn't win a pool they did.

    ``create_missing=False`` only corrects digests that already exist; used by
    --force re-awards, which are corrections and must not announce old weeks.

    Returns the number of notifications created or updated.
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

    # Only people who still belong to the family hear about its pool. A
    # userSeasonPoints row outlives a membership, and the digest links to a
    # standings page a former member can no longer open. (Winners are still
    # *named* either way -- the result is the result.)
    current_members = set(
        FamilyMembership.objects
        .filter(
            status=FamilyMembership.Status.ACTIVE,
            family_id__in={e['pool'].family_id for e in awarded.values()},
        )
        .values_list('user_id', 'family_id')
    )

    # Resolve every id we might name, in one query.
    referenced = {str(r.userID) for e in awarded.values() for r in e['rows']}
    users = {
        str(u.pk): u
        for u in User.objects.filter(pk__in=[i for i in referenced if i.isdigit()])
    }
    names = {uid: _display_name(u) for uid, u in users.items()}

    # Invert to per-user: which awarded pools is this person a member of?
    per_user = {}
    for entry in awarded.values():
        for row in entry['rows']:
            uid = str(row.userID)
            if uid.isdigit() and (int(uid), entry['pool'].family_id) in current_members:
                per_user.setdefault(uid, []).append(entry)

    changed = 0
    for user_id, entries in per_user.items():
        user = users.get(user_id)
        if user is None or not user.is_active:
            # Soft-deleted or blocked accounts don't accumulate notifications.
            continue

        entries.sort(key=lambda e: (e['pool'].family.name or '', e['pool'].name or ''))
        won_pools = [
            _pool_label(e, entries) for e in entries if user_id in e['winner_ids']
        ]

        segments = [
            f"{_pool_label(e, entries)}: {_winner_label(e['winner_ids'], user_id, names)}"
            f" ({e['points']} pts)"
            for e in entries[:MAX_POOLS_LISTED]
        ]
        remaining = len(entries) - len(segments)
        if remaining > 0:
            segments.append(f"and {remaining} more")

        # Link to a pool they won when there is one; otherwise the first listed.
        target = next(
            (e for e in entries if user_id in e['winner_ids']), entries[0],
        )
        fields = {
            'title': _digest_title(week, won_pools, len(entries))[:200],
            'body': " · ".join(segments)[:500],
            'url': _pool_standings_url(target['pool']),
            'family': target['pool'].family,
            'pool': target['pool'],
        }
        key = f"week_winners:{season}:{week}:{user_id}"

        existing = Notification.objects.filter(dedupe_key=key).first()
        if existing is None:
            if not create_missing:
                continue
            try:
                # Savepoint, so a lost race doesn't poison an outer transaction
                # and the re-query below still works.
                with transaction.atomic():
                    Notification.objects.create(
                        dedupe_key=key, recipient=user,
                        kind=Notification.Kind.WEEK_WINNER, **fields,
                    )
            except IntegrityError:
                existing = Notification.objects.filter(dedupe_key=key).first()
                if existing is None:
                    # Not a duplicate-key race -- a real data error. Make it
                    # visible rather than silently dropping this person's digest.
                    logger.exception("Could not create week-winner digest %s", key)
                    continue
                # A concurrent call won the race, possibly with an older snapshot
                # (fewer pools awarded). Fall through and bring it up to date
                # rather than discarding our richer fields.
            else:
                changed += 1
                continue

        if _refresh_digest(existing, fields):
            changed += 1

    return changed
