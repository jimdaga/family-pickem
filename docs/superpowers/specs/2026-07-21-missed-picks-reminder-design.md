# Missed Picks Reminder — Design

**Date:** 2026-07-21
**Branch:** `feat/missed-picks-reminder`
**Issue:** [#88](https://github.com/jimdaga/family-pickem/issues/88) — Automate email reminders for missing picks
**Status:** Approved design → ready for implementation plan

## Problem

Players who haven't submitted picks before their games lock get no nudge. The
issue requires the reminder to be family/pool scoped and to respect each
user's notification preferences. As of 2026-07-21 there is no reminder code
anywhere in the repo.

## Current state (verified)

- **`EmailNotificationCampaign`** (`pickem_superadmin/models.py:240`) already
  models a schedulable campaign: `enabled`, `weekday`/`hour`/`minute`/
  `timezone_name`, `rollout_mode` (allowlist vs. all-eligible-users),
  `allowlist_emails`, plus `last_sent_season`/`last_sent_week`/`last_sent_at`/
  `last_sent_count` for once-per-week idempotency. Today it has exactly one
  row, `CampaignKey.WEEKLY_PICKS_AVAILABLE`, loaded via
  `load_weekly_picks()`.
- **`send_due_email_campaigns()`** (`pickem_homepage/emailing.py:416`) is the
  single entry point the scheduler calls. It's wired into
  `pickem_api/scheduler.py`'s `STANDALONE` list as job id
  `send_scheduled_email_campaigns`, ticking every
  `EMAIL_CAMPAIGN_INTERVAL_MINUTES` (15 min).
- **Eligibility filtering** (`_eligible_weekly_picks_users`) already checks:
  active user, has email, `profile.email_notifications`, not
  `profile.blocked_at`, campaign `rollout_mode`/`allowlist`, and the global
  `EMAIL_NOTIFICATION_SAFE_ALLOWLIST_ONLY` safety net
  (`settings.EMAIL_NOTIFICATION_SAFE_ALLOWLIST`). All of this is
  campaign-shaped, not weekly-picks-specific, and is directly reusable.
- **Due-window logic** (`_weekly_picks_due`, `_week_window`,
  `_get_weekly_target`) computes a `scheduled_at`/`closes_at` pair from the
  campaign's weekday/hour/minute and the target week's games, and skips
  re-sending once `last_sent_season`/`last_sent_week` match the target — i.e.
  the campaign is evaluated **once per week**, which is what makes the
  no-per-user-tracking approach below safe.
- **Locking**: `is_pick_locked_for_pool(game, pool)` (`pickem/utils.py:110`)
  already encodes each pool's `picks_lock_mode` (kickoff-per-game vs. Sunday
  1PM ET cutoff). This is the source of truth for "can this user still act on
  this game."
- **`GamePicks`** rows are keyed by `(pool, userID, pick_game_id)` — a missing
  row for an unlocked game in a pool is exactly "still-open, unpicked."
- **Admin UI**: `pickem_superadmin/views/email.py::email_settings` currently
  hard-codes the one weekly-picks campaign into a single page, branching on a
  `request.POST['action']` string (`save_weekly_campaign`,
  `send_weekly_preview`, `send_weekly_now`). `EmailNotificationCampaignForm`
  and `WeeklyPicksPreviewForm` are already generic (bound to whichever
  campaign instance is passed in) — no campaign-specific fields — so they're
  reusable as-is with a different `prefix`.
- **Audit log actions** (`EMAIL_CAMPAIGN_UPDATED/SENT`, `EMAIL_PREVIEW_SENT`)
  are already generic (`SuperAdminAuditLog.Action`), not weekly-picks-specific.

## Decisions (confirmed with user)

1. **"Missing" trigger**: only games that have **not yet locked** and have no
   `GamePicks` row for that user+pool count. A game the user missed before it
   locked is not re-flagged (nothing actionable left).
2. **Multi-pool handling**: **one consolidated email per user**, listing every
   pool that currently has outstanding games for them, each with its own link.
3. **Timing model**: fixed admin-configurable weekday/hour/minute/timezone —
   the same shape as the weekly-picks campaign, not a per-pool
   relative-to-lock computation.
4. **Admin UI**: full parity with the weekly-picks campaign card (enable
   toggle, rollout mode + allowlist, preview-send, run-now) so it can be
   staged the same way (allowlist-only first, flip to all-users once
   verified).

## Design

### 1. Model: new campaign key, no new tables

Add to `EmailNotificationCampaign.CampaignKey`:

```python
MISSED_PICKS_REMINDER = 'missed_picks_reminder', 'Missed picks reminder'
```

Add `load_missed_picks_reminder()` alongside the existing
`load_weekly_picks()` classmethod. All other fields (weekday/hour/minute/
timezone/rollout_mode/allowlist/last_sent_*) are reused unchanged — this is a
second row in the same table, not a new model. `family_link_strategy` exists
on the model but is meaningless for a multi-pool consolidated email; it's
simply left at its default and unused by this campaign's send path (no schema
change needed to omit using a field).

**Dedup / idempotency**: identical mechanism to weekly-picks — the campaign
row's `last_sent_season`/`last_sent_week` gates evaluation to once per
target week (as determined by the shared `_get_weekly_target()`). No new
per-user tracking table. This is only safe because the campaign is evaluated
as a whole once due; if 0 emails go out (all skipped/failed) the week stays
retryable, matching the existing weekly-picks behavior.

Migration: `makemigrations` will generate an `AlterField` migration for
`campaign_key` since its `choices=` changed. This is a no-op at the database
level (no column type change, no data change) but is required for
`python manage.py makemigrations --check --dry-run` (part of the standard
PR verification) to pass.

### 2. Eligibility & missing-picks query (the new logic)

New functions in `pickem_homepage/emailing.py`:

```python
def _eligible_campaign_users(campaign):
    """Shared base filter: active, has email, notification prefs, campaign
    rollout/allowlist, global safety allowlist. Extracted from
    _eligible_weekly_picks_users so both campaigns share it."""

def _user_pools_with_missing_picks(user, *, target):
    """For one user: active pools (via active FamilyMembership -> active
    Family -> active Pool, matching target season/competition), each pool's
    week games via _get_week_games, keep games where
    is_pick_locked_for_pool() is False and no GamePicks row exists for
    (pool, user). Returns a list of {pool, family, missing_games, picks_link}
    for pools with 1+ such games."""
```

`_eligible_weekly_picks_users` keeps its current behavior (unchanged, still
used only by the weekly-picks send path); the new `_eligible_campaign_users`
becomes the shared base and `_eligible_weekly_picks_users` calls it plus its
existing pick-link-building step.

### 3. Send path

```python
def _send_missed_picks_reminder(*, user, recipient_email, bundle, preview=False): ...

def _missed_picks_due(campaign, *, now=None, ignore_clock=False): ...  # mirrors _weekly_picks_due

def send_missed_picks_preview_email(*, to_email, sample_user_email=''): ...  # mirrors send_weekly_picks_preview_email
```

`send_due_email_campaigns()` is extended to also evaluate the missed-picks
campaign in the same call, appending a second entry to the returned
`'campaigns'` list when due. Signature gains `force_missed_picks=False`
alongside the existing `force_weekly_picks=False`, mirroring the existing
force-run pattern used by the admin "run now" button.

No scheduler change: this still runs inside the existing
`send_scheduled_email_campaigns` STANDALONE job
(`pickem_api/scheduler.py`), same 15-minute interval.

### 4. Template

New `emails/missed_picks_reminder.html` + `.txt`, styled like
`weekly_picks_available.{html,txt}` (same header/footer conventions,
logo, notification-preference disclosure line). Body differs: one card per
pool in the bundle — pool/family name, "N game(s) still need a pick," a
compact per-game line (away @ home, kickoff time — no odds/weather, this is a
nag not a preview) and a per-pool "Open picks page" button. If a user's
bundle has 0 pools, no email is sent at all (checked before render).

### 5. Admin UI

`pickem_superadmin/views/email.py::email_settings`: add a second campaign
instance (`missed_campaign = EmailNotificationCampaign.load_missed_picks_reminder()`)
and mirror the existing three `action` branches with new action strings
(`save_missed_picks_campaign`, `send_missed_picks_preview`,
`send_missed_picks_now`), reusing `EmailNotificationCampaignForm` (prefix
`missed_campaign`) and `WeeklyPicksPreviewForm` (prefix `missed_preview` —
name is generic enough to reuse without renaming, but consider renaming to
`CampaignPreviewForm` during implementation since "weekly" no longer
describes both uses).

`superadmin/email.html`: add a second card below the existing weekly-picks
one, same layout/fields.

No new `SuperAdminAuditLog.Action` values — the existing
`EMAIL_CAMPAIGN_UPDATED`/`EMAIL_CAMPAIGN_SENT`/`EMAIL_PREVIEW_SENT` actions
already just take whatever campaign instance is passed as `target`.

### 6. Testing

Mirroring `pickem_superadmin/tests/test_email.py`'s existing weekly-picks
coverage, plus new cases specific to the missing-picks query:

- Pool with all games picked → excluded from bundle.
- Pool with a missing pick on an already-locked game only → excluded (per
  decision #1).
- Pool with a missing pick on a still-open game → included, with the correct
  per-pool link.
- User in 2 pools, both with outstanding games → one consolidated email with
  two pool sections.
- User in 2 pools, only 1 with outstanding games → email includes only that
  pool.
- Notification-preference off / blocked user / not on allowlist (allowlist
  rollout mode) / not on the global safety allowlist → excluded, mirroring
  existing weekly-picks exclusion tests.
- Dedup: a second scheduler tick within the same target week does not
  resend (`last_sent_season`/`last_sent_week` already set).
- Admin UI: campaign save, preview send, run-now — same shape as the
  existing weekly-picks admin tests.

## Out of scope

- Per-notification-type preferences (there is only the single
  `profile.email_notifications` boolean today; this feature reuses it as-is,
  same as weekly-picks).
- Relative-to-lock dynamic timing (per-pool computed send time) — rejected in
  favor of the fixed admin-configured schedule, consistent with the existing
  campaign.
- Per-user reminder tracking table — the once-per-week campaign-level dedup
  is sufficient given the consolidated-email design.
