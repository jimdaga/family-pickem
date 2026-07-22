# Missed Picks Reminder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically email each user a consolidated reminder listing every pool where they still have open (not-yet-locked), unsubmitted picks, on an admin-configurable weekly schedule, respecting notification preferences and the existing safe-rollout allowlist.

**Architecture:** A second `EmailNotificationCampaign` row (`missed_picks_reminder`) sibling to the existing `weekly_picks_available` campaign, sharing its scheduling/eligibility/dedup machinery in `pickem_homepage/emailing.py`. The only genuinely new logic is the per-user "which pools have open, unpicked games" query. Both campaigns are evaluated from the same `send_due_email_campaigns()` call already wired into the APScheduler `STANDALONE` job — no new scheduler entry.

**Tech Stack:** Django 4.0.2, Resend (email delivery), APScheduler (django-apscheduler), Django TestCase.

## Global Constraints

- Reuse `profile.email_notifications` as the sole notification-preference gate — there is no per-notification-type preference in this codebase, and adding one is out of scope (see spec's "Out of scope").
- A game counts as "missing a pick" only if it has **not yet locked** (`is_pick_locked_for_pool` returns `False`) and the user has no `GamePicks` row for it. Already-locked misses are never reported.
- Multi-pool reminders are **consolidated into one email per user**, not one email per pool.
- Reminder timing is a fixed admin-configurable weekday/hour/minute/timezone (same shape as the weekly-picks campaign) — not computed relative to each pool's lock time.
- Dedup is once-per-(season, week) at the campaign level (`last_sent_season`/`last_sent_week`), mirroring the existing weekly-picks campaign — no new per-user tracking table.
- Every new/changed Python file must pass `cd pickem && python manage.py test --settings=pickem.test_settings` before each commit.
- `python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` must pass (part of standard PR verification per `skills/release-fp/SKILL.md`).

---

## File Structure

- `pickem/pickem_superadmin/models.py` — add `CampaignKey.MISSED_PICKS_REMINDER` + `load_missed_picks_reminder()` classmethod (modify).
- `pickem/pickem_superadmin/migrations/0010_*.py` — generated migration for the new choice (create).
- `pickem/pickem_homepage/emailing.py` — add `_eligible_campaign_users`, `_user_pools_with_missing_picks`, `_missed_picks_context`, `_send_missed_picks_reminder`, `send_missed_picks_preview_email`, `_mark_campaign_sent`; rename `_weekly_picks_due` → `_campaign_due`; extend `send_due_email_campaigns` (modify).
- `pickem/pickem_homepage/templates/emails/missed_picks_reminder.html` (create).
- `pickem/pickem_homepage/templates/emails/missed_picks_reminder.txt` (create).
- `pickem/pickem_superadmin/views/email.py` — load the second campaign, add 3 new `action` branches, pass new context (modify).
- `pickem/pickem_superadmin/templates/superadmin/email.html` — add a second campaign card + status block (modify).
- `pickem/pickem_superadmin/tests/test_email.py` — new `MissedPicksReminderTests` class + additions to `EmailSettingsViewTests` (modify).

No changes to `pickem_api/scheduler.py` or `pickem_superadmin/forms.py` — both are already generic enough to cover a second campaign.

---

### Task 1: Add the `missed_picks_reminder` campaign key

**Files:**
- Modify: `pickem/pickem_superadmin/models.py:250-305` (the `EmailNotificationCampaign` class)
- Create: `pickem/pickem_superadmin/migrations/0010_*.py` (generated)
- Test: `pickem/pickem_superadmin/tests/test_email.py` (new test, appended near the top after imports)

**Interfaces:**
- Produces: `EmailNotificationCampaign.CampaignKey.MISSED_PICKS_REMINDER`, `EmailNotificationCampaign.load_missed_picks_reminder() -> EmailNotificationCampaign`

- [ ] **Step 1: Write the failing test**

Add to `pickem/pickem_superadmin/tests/test_email.py`, right after the `EmailProviderSettingsModelTests` class (after line 44, before `class EmailSettingsViewTests`):

```python
class EmailNotificationCampaignModelTests(TestCase):
    def test_load_missed_picks_reminder_is_a_distinct_singleton(self):
        weekly = EmailNotificationCampaign.load_weekly_picks()
        missed = EmailNotificationCampaign.load_missed_picks_reminder()

        self.assertNotEqual(weekly.pk, missed.pk)
        self.assertEqual(missed.campaign_key, EmailNotificationCampaign.CampaignKey.MISSED_PICKS_REMINDER)
        # Idempotent: loading again returns the same row, not a new one.
        again = EmailNotificationCampaign.load_missed_picks_reminder()
        self.assertEqual(missed.pk, again.pk)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.EmailNotificationCampaignModelTests --settings=pickem.test_settings -v 2`
Expected: FAIL with `AttributeError: type object 'EmailNotificationCampaign' has no attribute 'load_missed_picks_reminder'` (or similar — the method doesn't exist yet).

- [ ] **Step 3: Add the campaign key and loader**

In `pickem/pickem_superadmin/models.py`, find the `CampaignKey` class (around line 250):

```python
    class CampaignKey(models.TextChoices):
        WEEKLY_PICKS_AVAILABLE = 'weekly_picks_available', 'Weekly picks available'
```

Replace with:

```python
    class CampaignKey(models.TextChoices):
        WEEKLY_PICKS_AVAILABLE = 'weekly_picks_available', 'Weekly picks available'
        MISSED_PICKS_REMINDER = 'missed_picks_reminder', 'Missed picks reminder'
```

Find `load_weekly_picks` (around line 300):

```python
    @classmethod
    def load_weekly_picks(cls):
        obj, _created = cls.objects.get_or_create(
            campaign_key=cls.CampaignKey.WEEKLY_PICKS_AVAILABLE,
        )
        return obj
```

Add immediately after it:

```python
    @classmethod
    def load_missed_picks_reminder(cls):
        obj, _created = cls.objects.get_or_create(
            campaign_key=cls.CampaignKey.MISSED_PICKS_REMINDER,
        )
        return obj
```

- [ ] **Step 4: Generate the migration**

Run: `cd pickem && python manage.py makemigrations pickem_superadmin --settings=pickem.test_settings`
Expected output: a new file `pickem_superadmin/migrations/0010_alter_emailnotificationcampaign_campaign_key.py` (exact name may vary) containing an `AlterField` on `campaign_key` with the new choices. This is a no-op at the database level (no column type change).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.EmailNotificationCampaignModelTests --settings=pickem.test_settings -v 2`
Expected: PASS

- [ ] **Step 6: Run the migration check and full suite**

Run: `cd pickem && python manage.py makemigrations --check --dry-run --settings=pickem.test_settings && python manage.py test --settings=pickem.test_settings`
Expected: no missing migrations detected, full suite passes.

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_superadmin/models.py pickem/pickem_superadmin/migrations/ pickem/pickem_superadmin/tests/test_email.py
git commit -m "feat: add missed_picks_reminder campaign key"
```

---

### Task 2: Extract shared eligibility filter (`_eligible_campaign_users`)

Pure refactor: pulls the campaign-agnostic parts of `_eligible_weekly_picks_users` into a new function so the missed-picks campaign can reuse them. Behavior-preserving — the existing `WeeklyPicksCampaignTests` suite is the regression test for this step.

**Files:**
- Modify: `pickem/pickem_homepage/emailing.py:248-284` (`_eligible_weekly_picks_users`)
- Test: `pickem/pickem_superadmin/tests/test_email.py`

**Interfaces:**
- Produces: `_eligible_campaign_users(campaign) -> list[User]` (profile-preloaded, no campaign-specific link attached)
- Consumes (unchanged): `_campaign_safety_allowlist()`, `EmailNotificationCampaign.RolloutMode`

- [ ] **Step 1: Write the failing test**

Add to `pickem/pickem_superadmin/tests/test_email.py`, inside the existing `WeeklyPicksCampaignTests` class (after `test_eligibility_enumeration_does_not_create_profiles`, around line 515):

```python
    def test_eligible_campaign_users_applies_same_filters_as_weekly_helper(self):
        from pickem_homepage.emailing import _eligible_campaign_users

        base = _eligible_campaign_users(self.campaign)
        weekly = _eligible_weekly_picks_users(self.campaign)

        self.assertEqual(
            {u.id for u in base},
            {u.id for u in weekly},
        )
```

This test needs `_eligible_weekly_picks_users` imported at the top of the test file. Add it to the existing import from `pickem_homepage.emailing` (line 12-17):

```python
from pickem_homepage.emailing import (
    _eligible_weekly_picks_users,
    resend_invite_email_is_configured,
    send_due_email_campaigns,
    send_family_invitation_email,
    send_test_email,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.WeeklyPicksCampaignTests.test_eligible_campaign_users_applies_same_filters_as_weekly_helper --settings=pickem.test_settings -v 2`
Expected: FAIL with `ImportError: cannot import name '_eligible_campaign_users'`

- [ ] **Step 3: Extract the shared function**

In `pickem/pickem_homepage/emailing.py`, replace `_eligible_weekly_picks_users` (lines 248-284):

```python
def _eligible_weekly_picks_users(campaign):
    base_qs = (
        User.objects.select_related('profile')
        .filter(
            is_active=True,
            email__isnull=False,
        )
        .exclude(email='')
    )
    users = []
    safety_allowlist = _campaign_safety_allowlist()
    campaign_allowlist = set(campaign.allowlist)
    for user in base_qs:
        # Eligibility is a read: no profile means default flags (notifications
        # on, not blocked) — never create a UserProfile row from here, this
        # also runs on the preview path.
        profile = getattr(user, 'profile', None)
        if profile is not None:
            if not profile.email_notifications:
                continue
            if profile.blocked_at is not None:
                continue
        email_value = (user.email or '').strip().lower()
        if campaign.rollout_mode == EmailNotificationCampaign.RolloutMode.ALLOWLIST:
            if email_value not in campaign_allowlist:
                continue
        if getattr(settings, 'EMAIL_NOTIFICATION_SAFE_ALLOWLIST_ONLY', True):
            if email_value not in safety_allowlist:
                continue
        link, family, pool = _build_picks_link(user)
        if not link:
            continue
        user._weekly_picks_link = link
        user._weekly_picks_family = family
        user._weekly_picks_pool = pool
        users.append(user)
    return users
```

with:

```python
def _eligible_campaign_users(campaign):
    """Base filter shared by every email campaign: active user, has email,
    opted into notifications, not blocked, campaign rollout/allowlist, and
    the global safety allowlist. Campaign-specific steps (like building a
    picks link) happen in each campaign's own wrapper."""
    base_qs = (
        User.objects.select_related('profile')
        .filter(
            is_active=True,
            email__isnull=False,
        )
        .exclude(email='')
    )
    users = []
    safety_allowlist = _campaign_safety_allowlist()
    campaign_allowlist = set(campaign.allowlist)
    for user in base_qs:
        # Eligibility is a read: no profile means default flags (notifications
        # on, not blocked) — never create a UserProfile row from here, this
        # also runs on the preview path.
        profile = getattr(user, 'profile', None)
        if profile is not None:
            if not profile.email_notifications:
                continue
            if profile.blocked_at is not None:
                continue
        email_value = (user.email or '').strip().lower()
        if campaign.rollout_mode == EmailNotificationCampaign.RolloutMode.ALLOWLIST:
            if email_value not in campaign_allowlist:
                continue
        if getattr(settings, 'EMAIL_NOTIFICATION_SAFE_ALLOWLIST_ONLY', True):
            if email_value not in safety_allowlist:
                continue
        users.append(user)
    return users


def _eligible_weekly_picks_users(campaign):
    users = []
    for user in _eligible_campaign_users(campaign):
        link, family, pool = _build_picks_link(user)
        if not link:
            continue
        user._weekly_picks_link = link
        user._weekly_picks_family = family
        user._weekly_picks_pool = pool
        users.append(user)
    return users
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email --settings=pickem.test_settings -v 2`
Expected: PASS, all tests in the file (this confirms the refactor didn't change weekly-picks behavior).

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/emailing.py pickem/pickem_superadmin/tests/test_email.py
git commit -m "refactor: extract _eligible_campaign_users shared filter"
```

---

### Task 3: Rename `_weekly_picks_due` to `_campaign_due`

Pure rename/refactor — the function body already only reads `campaign.weekday/hour/minute/timezone_name` and `campaign.last_sent_season/last_sent_week`, nothing weekly-picks-specific. Renaming it now (before adding a second caller) avoids ending up with two near-identical `_weekly_picks_due`/`_missed_picks_due` functions.

**Files:**
- Modify: `pickem/pickem_homepage/emailing.py:308-330` (`_weekly_picks_due`) and its one call site in `send_due_email_campaigns` (line ~422)

**Interfaces:**
- Produces: `_campaign_due(campaign, *, now=None, ignore_clock=False) -> dict | None` (same shape as the old `_weekly_picks_due`)

- [ ] **Step 1: Rename the function**

In `pickem/pickem_homepage/emailing.py`, change:

```python
def _weekly_picks_due(campaign, *, now=None, ignore_clock=False):
```

to:

```python
def _campaign_due(campaign, *, now=None, ignore_clock=False):
```

(body unchanged).

- [ ] **Step 2: Update the call site**

In `send_due_email_campaigns` (around line 422), change:

```python
    target = _weekly_picks_due(
        campaign,
        now=now,
        ignore_clock=force_weekly_picks,
    )
```

to:

```python
    target = _campaign_due(
        campaign,
        now=now,
        ignore_clock=force_weekly_picks,
    )
```

- [ ] **Step 3: Run the full suite to confirm the rename didn't break anything**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email --settings=pickem.test_settings -v 2`
Expected: PASS (no test references `_weekly_picks_due` by name, so this is a safe internal rename; if any test does reference it, update that reference too).

- [ ] **Step 4: Commit**

```bash
git add pickem/pickem_homepage/emailing.py
git commit -m "refactor: rename _weekly_picks_due to _campaign_due (now shared)"
```

---

### Task 4: Missing-picks query — `_user_pools_with_missing_picks`

This is the core new logic: for one user, which of their active pools currently have open (unlocked), unpicked games in the target week.

**Files:**
- Modify: `pickem/pickem_homepage/emailing.py` (imports + new function, placed after `_build_picks_link`, around line 238)
- Test: `pickem/pickem_superadmin/tests/test_email.py` (new `MissedPicksReminderTests` class)

**Interfaces:**
- Consumes: `_get_week_games(*, season, week, competition)` (existing), `is_pick_locked_for_pool(game, pool, week_games)` (existing, from `pickem.utils`), `FamilyMembership`, `Family`, `Pool`, `GamePicks` (models)
- Produces: `_user_pools_with_missing_picks(user, *, target) -> list[dict]` where each dict is `{'pool': Pool, 'family': Family, 'missing_games': list[GamesAndScores], 'picks_link': str}`

- [ ] **Step 1: Update imports**

In `pickem/pickem_homepage/emailing.py`, change the models import (line 13):

```python
from pickem_api.models import FamilyMembership, GameWeeks, GamesAndScores, Pool, Teams, UserProfile
```

to:

```python
from pickem_api.models import Family, FamilyMembership, GamePicks, GameWeeks, GamesAndScores, Pool, Teams, UserProfile
```

Change the utils import (line 11):

```python
from pickem.utils import get_season
```

to:

```python
from pickem.utils import get_season, is_pick_locked_for_pool
```

- [ ] **Step 2: Write the failing tests**

Add a new class to `pickem/pickem_superadmin/tests/test_email.py`, after the closing of `WeeklyPicksCampaignTests` and before `EmailEnvironmentFallbackTests` (find the `class EmailEnvironmentFallbackTests(TestCase):` line and insert before it):

```python
class MissedPicksReminderTests(TestCase):
    def setUp(self):
        settings_obj = EmailProviderSettings.load()
        settings_obj.invites_enabled = True
        settings_obj.from_email = 'Family Pickem <invite@family-pickem.com>'
        settings_obj.reply_to_email = 'reply@family-pickem.com'
        settings_obj.set_api_key('re_configured_secret')
        settings_obj.save()

        self.campaign = EmailNotificationCampaign.load_missed_picks_reminder()
        self.campaign.enabled = True
        self.campaign.weekday = 2
        self.campaign.hour = 9
        self.campaign.minute = 0
        self.campaign.timezone_name = 'America/New_York'
        self.campaign.rollout_mode = EmailNotificationCampaign.RolloutMode.ALL_ENABLED_USERS
        self.campaign.save()

        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family,
            name='Main Pool',
            slug='main-pool',
            season=2627,
            is_default=True,
        )
        PoolSettings.objects.create(pool=self.pool)

        self.user = User.objects.create_user(
            username='jdag', email='jdagostino2@gmail.com', password='pw',
        )
        UserProfile.objects.create(user=self.user, email_notifications=True)
        FamilyMembership.objects.create(
            family=self.family, user=self.user, role=FamilyMembership.Role.MEMBER,
        )

        GameWeeks.objects.create(
            weekNumber=1, competition='nfl', date=datetime(2026, 9, 10).date(), season=2627,
        )
        self.open_game = GamesAndScores.objects.create(
            id=1, slug='bears-packers', competition='nfl', gameWeek='1', gameyear='2026',
            gameseason=2627,
            startTimestamp=timezone.make_aware(datetime(2026, 9, 13, 13, 0)),
            statusType='notstarted', statusTitle='Scheduled',
            homeTeamId=1, homeTeamSlug='packers', homeTeamName='Green Bay Packers',
            awayTeamId=2, awayTeamSlug='bears', awayTeamName='Chicago Bears',
        )
        self.locked_game = GamesAndScores.objects.create(
            id=2, slug='chiefs-bills', competition='nfl', gameWeek='1', gameyear='2026',
            gameseason=2627,
            startTimestamp=timezone.make_aware(datetime(2026, 9, 10, 20, 20)),
            statusType='final', statusTitle='Final',
            homeTeamId=3, homeTeamSlug='bills', homeTeamName='Buffalo Bills',
            awayTeamId=4, awayTeamSlug='chiefs', awayTeamName='Kansas City Chiefs',
        )
        self.target = {'season': 2627, 'week': 1, 'competition': 'nfl'}

    def test_pool_with_open_unpicked_game_is_included(self):
        from pickem_homepage.emailing import _user_pools_with_missing_picks

        bundle = _user_pools_with_missing_picks(self.user, target=self.target)

        self.assertEqual(len(bundle), 1)
        entry = bundle[0]
        self.assertEqual(entry['pool'], self.pool)
        self.assertEqual(entry['family'], self.family)
        self.assertEqual([g.id for g in entry['missing_games']], [self.open_game.id])
        self.assertIn('/families/dagostino/pools/main-pool/picks/', entry['picks_link'])

    def test_already_locked_miss_does_not_trigger_reminder(self):
        from pickem_homepage.emailing import _user_pools_with_missing_picks

        GamePicks.objects.create(
            id=f'{self.pool.id}-{self.user.id}-{self.open_game.id}',
            pool=self.pool, userEmail=self.user.email, uid=self.user.id,
            userID=str(self.user.id), slug=self.open_game.slug, competition='nfl',
            gameWeek='1', gameyear='2026', gameseason=2627,
            pick_game_id=self.open_game.id, pick='packers',
        )
        # Only the already-started/locked game is unpicked now.
        bundle = _user_pools_with_missing_picks(self.user, target=self.target)

        self.assertEqual(bundle, [])

    def test_fully_picked_pool_is_excluded(self):
        from pickem_homepage.emailing import _user_pools_with_missing_picks

        for game in (self.open_game, self.locked_game):
            GamePicks.objects.create(
                id=f'{self.pool.id}-{self.user.id}-{game.id}',
                pool=self.pool, userEmail=self.user.email, uid=self.user.id,
                userID=str(self.user.id), slug=game.slug, competition='nfl',
                gameWeek='1', gameyear='2026', gameseason=2627,
                pick_game_id=game.id, pick=game.homeTeamSlug,
            )

        bundle = _user_pools_with_missing_picks(self.user, target=self.target)

        self.assertEqual(bundle, [])

    def test_second_pool_with_missing_picks_both_included(self):
        from pickem_homepage.emailing import _user_pools_with_missing_picks

        other_pool = Pool.objects.create(
            family=self.family, name='Side Pool', slug='side-pool', season=2627,
        )
        PoolSettings.objects.create(pool=other_pool)

        bundle = _user_pools_with_missing_picks(self.user, target=self.target)

        self.assertEqual({entry['pool'].slug for entry in bundle}, {'main-pool', 'side-pool'})

    def test_inactive_membership_pool_excluded(self):
        from pickem_homepage.emailing import _user_pools_with_missing_picks

        membership = FamilyMembership.objects.get(user=self.user, family=self.family)
        membership.status = FamilyMembership.Status.INACTIVE
        membership.save(update_fields=['status'])

        bundle = _user_pools_with_missing_picks(self.user, target=self.target)

        self.assertEqual(bundle, [])
```

This test needs `PoolSettings` and `GamePicks` imported at the top of `test_email.py`. Update the existing import (line 9-11):

```python
from pickem_api.models import (
    Family, FamilyInvitation, FamilyMembership, GameWeeks, GamesAndScores, Pool, Teams, UserProfile,
)
```

to:

```python
from pickem_api.models import (
    Family, FamilyInvitation, FamilyMembership, GamePicks, GameWeeks, GamesAndScores, Pool,
    PoolSettings, Teams, UserProfile,
)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.MissedPicksReminderTests --settings=pickem.test_settings -v 2`
Expected: FAIL — `ImportError: cannot import name '_user_pools_with_missing_picks'`

- [ ] **Step 4: Implement `_user_pools_with_missing_picks`**

In `pickem/pickem_homepage/emailing.py`, add after `_build_picks_link` (after the function ending around line 238, before `_campaign_safety_allowlist`):

```python
def _user_pools_with_missing_picks(user, *, target):
    """Active pools (via this user's active memberships in active families)
    for the target season/competition where 1+ of the week's games are still
    open (not yet locked per that pool's own lock mode) and unpicked by this
    user. Returns [{'pool', 'family', 'missing_games', 'picks_link'}, ...]
    for pools with at least one such game; pools with nothing outstanding are
    omitted entirely."""
    memberships = FamilyMembership.objects.select_related('family').filter(
        user=user,
        status=FamilyMembership.Status.ACTIVE,
        family__status=Family.Status.ACTIVE,
    )
    families_by_id = {m.family_id: m.family for m in memberships}
    if not families_by_id:
        return []

    pools = list(
        Pool.objects.filter(
            family_id__in=families_by_id.keys(),
            status=Pool.Status.ACTIVE,
            season=target['season'],
            competition=target['competition'],
        )
    )
    if not pools:
        return []

    week_games = _get_week_games(
        season=target['season'],
        week=target['week'],
        competition=target['competition'],
    )
    if not week_games:
        return []
    game_ids = [game.id for game in week_games]

    bundle = []
    for pool in pools:
        picked_game_ids = set(
            GamePicks.objects.filter(
                pool=pool,
                userID=str(user.id),
                pick_game_id__in=game_ids,
            ).values_list('pick_game_id', flat=True)
        )
        missing_games = [
            game for game in week_games
            if game.id not in picked_game_ids
            and not is_pick_locked_for_pool(game, pool, week_games)[0]
        ]
        if not missing_games:
            continue
        family = families_by_id[pool.family_id]
        bundle.append({
            'pool': pool,
            'family': family,
            'missing_games': missing_games,
            'picks_link': _absolute_url(
                reverse(
                    'family_pool_game_picks',
                    kwargs={'family_slug': family.slug, 'pool_slug': pool.slug},
                )
            ),
        })
    return bundle
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.MissedPicksReminderTests --settings=pickem.test_settings -v 2`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_homepage/emailing.py pickem/pickem_superadmin/tests/test_email.py
git commit -m "feat: add missing-picks query for the reminder campaign"
```

---

### Task 5: Email templates

**Files:**
- Create: `pickem/pickem_homepage/templates/emails/missed_picks_reminder.html`
- Create: `pickem/pickem_homepage/templates/emails/missed_picks_reminder.txt`

**Interfaces:**
- Consumes: context dict `{'user', 'bundle', 'site_url', 'logo_url', 'preview'}` where `bundle` is the list produced by `_user_pools_with_missing_picks` (each entry has `pool`, `family`, `missing_games`, `picks_link`)

- [ ] **Step 1: Create the HTML template**

```html
<!doctype html>
<html lang="en">
<body style="margin:0; padding:0; background:#f3f6fb; font-family:'Segoe UI',Helvetica,Arial,sans-serif; color:#111827;">
  <div style="max-width:700px; margin:0 auto; padding:24px 16px;">
    <div style="background:linear-gradient(135deg,#92400e,#c2410c); border-radius:20px 20px 0 0; padding:28px 28px 20px; color:#ffffff;">
      <img src="{{ logo_url }}" alt="Family Pick'em" style="height:48px; width:auto; display:block; margin:0 0 16px;">
      <div style="font-size:13px; letter-spacing:0.08em; text-transform:uppercase; opacity:0.8;">Family Pick'em</div>
      <h1 style="margin:8px 0 10px; font-size:30px; line-height:1.15;">You still have picks to make</h1>
      <p style="margin:0; font-size:16px; line-height:1.6; color:rgba(255,255,255,0.88);">
        Kickoff is coming up and a few games are still missing your pick.
      </p>
    </div>

    <div style="background:#ffffff; border:1px solid #dbe4f0; border-top:0; border-radius:0 0 20px 20px; padding:24px 28px 28px;">
      {% for entry in bundle %}
      <div style="margin-bottom:22px; padding:18px 20px; border-radius:16px; background:#fff7ed; border:1px solid #fed7aa;">
        <div style="font-size:14px; color:#9a3412; font-weight:700; margin-bottom:6px;">
          {{ entry.family.name }} &middot; {{ entry.pool.name }}
        </div>
        <div style="font-size:15px; color:#334155; line-height:1.6; margin-bottom:14px;">
          {{ entry.missing_games|length }} game{{ entry.missing_games|length|pluralize }} still open — pick before kickoff:
        </div>
        <ul style="margin:0 0 14px; padding-left:18px; font-size:14px; color:#475569; line-height:1.8;">
          {% for game in entry.missing_games %}
          <li>{{ game.awayTeamName }} at {{ game.homeTeamName }} &mdash; {{ game.startTimestamp|date:"D, M j g:i A T" }}</li>
          {% endfor %}
        </ul>
        <a href="{{ entry.picks_link }}" style="display:inline-block; background:#9a3412; color:#ffffff; text-decoration:none; font-weight:700; padding:12px 18px; border-radius:999px;">Open picks page</a>
      </div>
      {% endfor %}

      <div style="margin-top:22px; font-size:13px; line-height:1.7; color:#64748b;">
        You are receiving this because email notifications are enabled on your profile and your account is active.
        {% if preview %}This is a preview email generated from the superadmin console.{% endif %}
      </div>
    </div>
  </div>
</body>
</html>
```

- [ ] **Step 2: Create the text template**

```
Family Pick'em

You still have picks to make before kickoff.
{% for entry in bundle %}
{{ entry.family.name }} - {{ entry.pool.name }} ({{ entry.missing_games|length }} game{{ entry.missing_games|length|pluralize }} still open)
Picks page: {{ entry.picks_link }}
{% for game in entry.missing_games %}
- {{ game.startTimestamp|date:"D, M j g:i A T" }}: {{ game.awayTeamName }} at {{ game.homeTeamName }}
{% endfor %}
{% endfor %}
You are receiving this because email notifications are enabled on your profile and your account is active.
{% if preview %}This is a preview email generated from the superadmin console.{% endif %}
```

- [ ] **Step 3: Commit**

(No automated test yet — the next task's tests render these templates and will catch any template syntax errors.)

```bash
git add pickem/pickem_homepage/templates/emails/missed_picks_reminder.html pickem/pickem_homepage/templates/emails/missed_picks_reminder.txt
git commit -m "feat: add missed-picks reminder email templates"
```

---

### Task 6: Send path — `_send_missed_picks_reminder` + preview

**Files:**
- Modify: `pickem/pickem_homepage/emailing.py` (new functions, placed after `_send_weekly_picks_email`, around line 414)
- Test: `pickem/pickem_superadmin/tests/test_email.py` (`MissedPicksReminderTests`)

**Interfaces:**
- Consumes: `_notification_email_config()`, `_user_pools_with_missing_picks` (Task 4), `_send_via_resend`, `_absolute_url`, `_weekly_picks_email_logo_url`, `_site_base_url`, `_get_weekly_target`, `_eligible_campaign_users` (Task 2)
- Produces: `_missed_picks_context(*, user, bundle, preview=False) -> dict`, `_send_missed_picks_reminder(*, user, recipient_email, bundle, preview=False) -> dict`, `send_missed_picks_preview_email(*, to_email, sample_user_email='', now=None) -> dict`

- [ ] **Step 1: Write the failing tests**

Add to `MissedPicksReminderTests` (from Task 4), after `test_inactive_membership_pool_excluded`:

```python
    def test_send_missed_picks_reminder_renders_all_pools_in_bundle(self):
        from pickem_homepage.emailing import _send_missed_picks_reminder, _user_pools_with_missing_picks

        other_pool = Pool.objects.create(
            family=self.family, name='Side Pool', slug='side-pool', season=2627,
        )
        PoolSettings.objects.create(pool=other_pool)
        bundle = _user_pools_with_missing_picks(self.user, target=self.target)
        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'missed_picks_1'}

        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = _send_missed_picks_reminder(
                user=self.user, recipient_email=self.user.email, bundle=bundle,
            )

        self.assertEqual(result['status'], 'sent')
        params = resend_mock.Emails.send.call_args.args[0]
        self.assertEqual(params['to'], [self.user.email])
        self.assertIn('Main Pool', params['html'])
        self.assertIn('Side Pool', params['html'])
        self.assertIn('Chicago Bears', params['html'])

    def test_send_missed_picks_preview_email_uses_sample_user(self):
        from pickem_homepage.emailing import send_missed_picks_preview_email

        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'missed_picks_preview'}
        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = send_missed_picks_preview_email(
                to_email='preview@example.com',
                sample_user_email=self.user.email,
                now=timezone.make_aware(datetime(2026, 9, 11, 12, 0)),
            )

        self.assertEqual(result['status'], 'sent')
        params = resend_mock.Emails.send.call_args.args[0]
        self.assertEqual(params['to'], ['preview@example.com'])
        self.assertIn('This is a preview email', params['html'])

    def test_send_missed_picks_preview_email_skips_when_no_one_has_missing_picks(self):
        from pickem_homepage.emailing import send_missed_picks_preview_email

        GamePicks.objects.create(
            id=f'{self.pool.id}-{self.user.id}-{self.open_game.id}',
            pool=self.pool, userEmail=self.user.email, uid=self.user.id,
            userID=str(self.user.id), slug=self.open_game.slug, competition='nfl',
            gameWeek='1', gameyear='2026', gameseason=2627,
            pick_game_id=self.open_game.id, pick='packers',
        )

        result = send_missed_picks_preview_email(
            to_email='preview@example.com',
            now=timezone.make_aware(datetime(2026, 9, 11, 12, 0)),
        )

        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'no_sample_user')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.MissedPicksReminderTests --settings=pickem.test_settings -v 2`
Expected: FAIL — `ImportError: cannot import name '_send_missed_picks_reminder'`

- [ ] **Step 3: Implement the send path**

In `pickem/pickem_homepage/emailing.py`, add after `_send_weekly_picks_email` (after its closing `return {'status': 'sent', 'response': response}`, before `def send_due_email_campaigns`):

```python
def _missed_picks_context(*, user, bundle, preview=False):
    return {
        'user': user,
        'bundle': bundle,
        'site_url': _site_base_url(),
        'logo_url': _weekly_picks_email_logo_url(),
        'preview': preview,
    }


def _send_missed_picks_reminder(*, user, recipient_email, bundle, preview=False):
    config = _notification_email_config()
    if not resend or not config or config['provider'] != EmailProviderSettings.Provider.RESEND:
        return {'status': 'skipped', 'reason': 'not_configured'}

    context = _missed_picks_context(user=user, bundle=bundle, preview=preview)
    total_games = sum(len(entry['missing_games']) for entry in bundle)
    params = {
        'api_key': config['api_key'],
        'from': config['from_email'],
        'to': [recipient_email],
        'subject': f"You have {total_games} pick(s) left before kickoff",
        'html': render_to_string('emails/missed_picks_reminder.html', context),
        'text': render_to_string('emails/missed_picks_reminder.txt', context),
    }
    if config['reply_to']:
        params['reply_to'] = config['reply_to']
    try:
        response = _send_via_resend(params)
    except Exception:
        logger.exception(
            'Failed to send missed picks reminder email.',
            extra={'to_email': recipient_email, 'user_id': user.id, 'pool_count': len(bundle)},
        )
        return {'status': 'error', 'reason': 'send_failed'}
    return {'status': 'sent', 'response': response}


def send_missed_picks_preview_email(*, to_email, sample_user_email='', now=None):
    now = now or timezone.now()
    target = _get_weekly_target(now=now)
    if target is None:
        return {'status': 'skipped', 'reason': 'no_upcoming_week'}

    sample_user, bundle = None, None
    if sample_user_email:
        candidate = User.objects.filter(email__iexact=sample_user_email.strip()).first()
        if candidate is not None:
            candidate_bundle = _user_pools_with_missing_picks(candidate, target=target)
            if candidate_bundle:
                sample_user, bundle = candidate, candidate_bundle

    if sample_user is None:
        # No explicit sample user, or they have nothing outstanding: fall back
        # to the first eligible user who actually has a bundle to render, so
        # the preview always shows real content.
        campaign = EmailNotificationCampaign.load_missed_picks_reminder()
        for candidate in _eligible_campaign_users(campaign):
            candidate_bundle = _user_pools_with_missing_picks(candidate, target=target)
            if candidate_bundle:
                sample_user, bundle = candidate, candidate_bundle
                break

    if sample_user is None or not bundle:
        return {'status': 'skipped', 'reason': 'no_sample_user'}

    return _send_missed_picks_reminder(
        user=sample_user,
        recipient_email=to_email,
        bundle=bundle,
        preview=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.MissedPicksReminderTests --settings=pickem.test_settings -v 2`
Expected: PASS (8 tests total in this class)

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/emailing.py pickem/pickem_superadmin/tests/test_email.py
git commit -m "feat: add missed-picks reminder send path and preview"
```

---

### Task 7: Wire the campaign into `send_due_email_campaigns`

**Files:**
- Modify: `pickem/pickem_homepage/emailing.py:416-477` (`send_due_email_campaigns`)
- Test: `pickem/pickem_superadmin/tests/test_email.py` (`MissedPicksReminderTests`)

**Interfaces:**
- Consumes: `_campaign_due` (Task 3), `_eligible_campaign_users` (Task 2), `_user_pools_with_missing_picks` (Task 4), `_send_missed_picks_reminder` (Task 6)
- Produces: `send_due_email_campaigns(*, now=None, force_weekly_picks=False, force_missed_picks=False) -> {'campaigns': [...]}` — the list now may contain up to 2 entries, one per due campaign, each `{'campaign_key', 'season', 'week', 'sent_count', 'skipped'}`.

- [ ] **Step 1: Write the failing tests**

Add to `MissedPicksReminderTests`:

```python
    def test_send_due_email_campaigns_includes_missed_picks_when_due(self):
        september_9_2026 = timezone.make_aware(datetime(2026, 9, 9, 13, 5))
        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'missed_picks_due'}

        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = send_due_email_campaigns(now=september_9_2026)

        campaign_keys = {row['campaign_key'] for row in result['campaigns']}
        self.assertIn(EmailNotificationCampaign.CampaignKey.MISSED_PICKS_REMINDER, campaign_keys)
        missed_row = next(
            row for row in result['campaigns']
            if row['campaign_key'] == EmailNotificationCampaign.CampaignKey.MISSED_PICKS_REMINDER
        )
        self.assertEqual(missed_row['sent_count'], 1)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.last_sent_season, 2627)
        self.assertEqual(self.campaign.last_sent_week, 1)

    def test_send_due_email_campaigns_does_not_resend_missed_picks_same_week(self):
        september_9_2026 = timezone.make_aware(datetime(2026, 9, 9, 13, 5))
        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'missed_picks_first'}
        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            send_due_email_campaigns(now=september_9_2026)

        resend_mock.Emails.send.reset_mock()
        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = send_due_email_campaigns(now=september_9_2026 + timedelta(minutes=15))

        missed_rows = [
            row for row in result['campaigns']
            if row['campaign_key'] == EmailNotificationCampaign.CampaignKey.MISSED_PICKS_REMINDER
        ]
        self.assertEqual(missed_rows, [])
        resend_mock.Emails.send.assert_not_called()

    def test_send_due_email_campaigns_skips_users_with_nothing_outstanding(self):
        # A user with every game picked must not receive an email at all.
        GamePicks.objects.create(
            id=f'{self.pool.id}-{self.user.id}-{self.open_game.id}',
            pool=self.pool, userEmail=self.user.email, uid=self.user.id,
            userID=str(self.user.id), slug=self.open_game.slug, competition='nfl',
            gameWeek='1', gameyear='2026', gameseason=2627,
            pick_game_id=self.open_game.id, pick='packers',
        )
        september_9_2026 = timezone.make_aware(datetime(2026, 9, 9, 13, 5))
        resend_mock = Mock()

        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = send_due_email_campaigns(now=september_9_2026)

        missed_row = next(
            (row for row in result['campaigns']
             if row['campaign_key'] == EmailNotificationCampaign.CampaignKey.MISSED_PICKS_REMINDER),
            None,
        )
        self.assertIsNone(missed_row)
        resend_mock.Emails.send.assert_not_called()

    def test_force_missed_picks_bypasses_schedule_and_enabled_flag(self):
        self.campaign.enabled = False
        self.campaign.save(update_fields=['enabled'])
        july_17_2026 = timezone.make_aware(datetime(2026, 7, 17, 12, 0))
        resend_mock = Mock()
        resend_mock.Emails.send.return_value = {'id': 'forced'}

        with patch('pickem_homepage.emailing.resend', new=resend_mock):
            result = send_due_email_campaigns(now=july_17_2026, force_missed_picks=True)

        campaign_keys = {row['campaign_key'] for row in result['campaigns']}
        self.assertIn(EmailNotificationCampaign.CampaignKey.MISSED_PICKS_REMINDER, campaign_keys)
```

This test file needs `timedelta` imported — check the top of `test_email.py`; if only `datetime` is imported (line 1: `from datetime import datetime`), change it to:

```python
from datetime import datetime, timedelta
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.MissedPicksReminderTests --settings=pickem.test_settings -v 2`
Expected: FAIL — `result['campaigns']` won't contain a `missed_picks_reminder` entry since `send_due_email_campaigns` doesn't evaluate that campaign yet.

- [ ] **Step 3: Add `_mark_campaign_sent` and rewrite `send_due_email_campaigns`**

In `pickem/pickem_homepage/emailing.py`, add this helper right before `send_due_email_campaigns`:

```python
def _mark_campaign_sent(campaign, *, target, now, sent_count):
    """Record a successful evaluation so the campaign doesn't re-fire for the
    same week. Only called when sent_count > 0 — a zero-send tick (provider
    outage, empty eligible set) must leave the campaign retryable within the
    window, never permanently suppress it."""
    campaign.last_sent_season = target['season']
    campaign.last_sent_week = target['week']
    campaign.last_sent_at = now
    campaign.last_sent_count = sent_count
    campaign.save(update_fields=[
        'last_sent_season', 'last_sent_week', 'last_sent_at', 'last_sent_count', 'updated_at',
    ])
```

Now replace the full `send_due_email_campaigns` function:

```python
def send_due_email_campaigns(*, now=None, force_weekly_picks=False):
    now = now or timezone.now()
    campaign = EmailNotificationCampaign.load_weekly_picks()
    if not campaign.enabled and not force_weekly_picks:
        return {'campaigns': []}

    target = _campaign_due(
        campaign,
        now=now,
        ignore_clock=force_weekly_picks,
    )
    if target is None:
        return {'campaigns': []}

    recipients = _eligible_weekly_picks_users(campaign)
    sent = 0
    skipped = []
    for user in recipients:
        result = _send_weekly_picks_email(
            user=user,
            recipient_email=user.email,
            target=target,
        )
        if result['status'] == 'sent':
            sent += 1
        else:
            skipped.append({'email': user.email, 'reason': result.get('reason', 'unknown')})

    # Only mark the week sent when at least one email actually went out:
    # marking it on a zero-send (provider outage, empty eligible set) would
    # permanently suppress the week's reminder. While sent == 0 the campaign
    # stays due and retries on the next scheduler tick until the window closes.
    if sent > 0:
        campaign.last_sent_season = target['season']
        campaign.last_sent_week = target['week']
        campaign.last_sent_at = now
        campaign.last_sent_count = sent
        campaign.save(update_fields=[
            'last_sent_season', 'last_sent_week', 'last_sent_at', 'last_sent_count', 'updated_at',
        ])

    logger.info(
        'Weekly picks campaign evaluated.',
        extra={
            'campaign_key': campaign.campaign_key,
            'season': target['season'],
            'week': target['week'],
            'sent_count': sent,
            'skipped': skipped,
            'forced': force_weekly_picks,
        },
    )
    return {
        'campaigns': [{
            'campaign_key': campaign.campaign_key,
            'season': target['season'],
            'week': target['week'],
            'sent_count': sent,
            'skipped': skipped,
        }],
    }
```

with:

```python
def _run_weekly_picks_campaign(*, now, force):
    campaign = EmailNotificationCampaign.load_weekly_picks()
    if not campaign.enabled and not force:
        return None

    target = _campaign_due(campaign, now=now, ignore_clock=force)
    if target is None:
        return None

    recipients = _eligible_weekly_picks_users(campaign)
    sent = 0
    skipped = []
    for user in recipients:
        result = _send_weekly_picks_email(
            user=user,
            recipient_email=user.email,
            target=target,
        )
        if result['status'] == 'sent':
            sent += 1
        else:
            skipped.append({'email': user.email, 'reason': result.get('reason', 'unknown')})

    _mark_campaign_sent(campaign, target=target, now=now, sent_count=sent)

    logger.info(
        'Weekly picks campaign evaluated.',
        extra={
            'campaign_key': campaign.campaign_key,
            'season': target['season'],
            'week': target['week'],
            'sent_count': sent,
            'skipped': skipped,
            'forced': force,
        },
    )
    return {
        'campaign_key': campaign.campaign_key,
        'season': target['season'],
        'week': target['week'],
        'sent_count': sent,
        'skipped': skipped,
    }


def _run_missed_picks_campaign(*, now, force):
    campaign = EmailNotificationCampaign.load_missed_picks_reminder()
    if not campaign.enabled and not force:
        return None

    target = _campaign_due(campaign, now=now, ignore_clock=force)
    if target is None:
        return None

    recipients = _eligible_campaign_users(campaign)
    sent = 0
    skipped = []
    for user in recipients:
        bundle = _user_pools_with_missing_picks(user, target=target)
        if not bundle:
            continue
        result = _send_missed_picks_reminder(
            user=user,
            recipient_email=user.email,
            bundle=bundle,
        )
        if result['status'] == 'sent':
            sent += 1
        else:
            skipped.append({'email': user.email, 'reason': result.get('reason', 'unknown')})

    _mark_campaign_sent(campaign, target=target, now=now, sent_count=sent)

    logger.info(
        'Missed picks reminder campaign evaluated.',
        extra={
            'campaign_key': campaign.campaign_key,
            'season': target['season'],
            'week': target['week'],
            'sent_count': sent,
            'skipped': skipped,
            'forced': force,
        },
    )
    return {
        'campaign_key': campaign.campaign_key,
        'season': target['season'],
        'week': target['week'],
        'sent_count': sent,
        'skipped': skipped,
    }


def send_due_email_campaigns(*, now=None, force_weekly_picks=False, force_missed_picks=False):
    now = now or timezone.now()
    campaigns = []

    weekly_result = _run_weekly_picks_campaign(now=now, force=force_weekly_picks)
    if weekly_result is not None:
        campaigns.append(weekly_result)

    missed_picks_result = _run_missed_picks_campaign(now=now, force=force_missed_picks)
    if missed_picks_result is not None:
        campaigns.append(missed_picks_result)

    return {'campaigns': campaigns}
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.MissedPicksReminderTests --settings=pickem.test_settings -v 2`
Expected: PASS (all tests in the class, including the 4 new ones)

- [ ] **Step 5: Run the full existing weekly-picks suite to confirm no regression**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.WeeklyPicksCampaignTests --settings=pickem.test_settings -v 2`
Expected: PASS (the weekly-picks return shape is unchanged — still a list with one entry when due).

- [ ] **Step 6: Run the full test suite**

Run: `cd pickem && python manage.py test --settings=pickem.test_settings`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_homepage/emailing.py pickem/pickem_superadmin/tests/test_email.py
git commit -m "feat: evaluate missed-picks reminder campaign in send_due_email_campaigns"
```

---

### Task 8: Superadmin admin UI

**Files:**
- Modify: `pickem/pickem_superadmin/views/email.py`
- Modify: `pickem/pickem_superadmin/templates/superadmin/email.html`
- Test: `pickem/pickem_superadmin/tests/test_email.py` (`EmailSettingsViewTests`)

**Interfaces:**
- Consumes: `EmailNotificationCampaignForm`, `WeeklyPicksPreviewForm` (both already generic, reused with a new `prefix`), `send_missed_picks_preview_email` (Task 6), `send_due_email_campaigns(force_missed_picks=True)` (Task 7)

- [ ] **Step 1: Write the failing tests**

Add to `EmailSettingsViewTests` in `pickem/pickem_superadmin/tests/test_email.py` (after `test_running_weekly_campaign_now_outside_active_week_errors`, around line 229):

```python
    def test_page_renders_missed_picks_campaign_section(self):
        response = self.client.get(reverse('superadmin:email_settings'))

        self.assertContains(response, 'Missed picks reminder')
        self.assertContains(response, 'save_missed_picks_campaign')

    def test_missed_picks_campaign_save_audits(self):
        response = self.client.post(
            reverse('superadmin:email_settings'),
            {
                'action': 'save_missed_picks_campaign',
                'missed_campaign-enabled': 'on',
                'missed_campaign-weekday': '6',
                'missed_campaign-hour': '11',
                'missed_campaign-minute': '0',
                'missed_campaign-timezone_name': 'America/New_York',
                'missed_campaign-rollout_mode': EmailNotificationCampaign.RolloutMode.ALLOWLIST,
                'missed_campaign-allowlist_emails': 'jdagostino2@gmail.com',
                'missed_campaign-family_link_strategy': EmailNotificationCampaign.FamilyLinkStrategy.EARLIEST_MEMBERSHIP,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        campaign = EmailNotificationCampaign.load_missed_picks_reminder()
        campaign.refresh_from_db()
        self.assertTrue(campaign.enabled)
        self.assertEqual(campaign.weekday, 6)
        self.assertEqual(campaign.hour, 11)
        audit = SuperAdminAuditLog.objects.get(
            action=SuperAdminAuditLog.Action.EMAIL_CAMPAIGN_UPDATED,
            target_id=str(campaign.pk),
        )
        self.assertEqual(audit.summary, 'Updated missed picks reminder email campaign')

    def test_running_missed_picks_campaign_now_outside_active_week_errors(self):
        response = self.client.post(
            reverse('superadmin:email_settings'),
            {'action': 'send_missed_picks_now'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not in an active NFL week window')
```

This mirrors the exact style of the existing `test_weekly_campaign_save_audits`/`test_running_weekly_campaign_now_outside_active_week_errors` tests immediately above it in the same class (no explicit login call needed — `setUp` already does `self.client.force_login(self.root)`). `SuperAdminAuditLog.target_id` disambiguates from the weekly campaign's own `EMAIL_CAMPAIGN_UPDATED` row: `pickem_superadmin/audit.py::log_action` writes `target_id=str(target.pk)`, and `campaign.pk` is that same value, confirmed above.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.EmailSettingsViewTests --settings=pickem.test_settings -v 2 -k missed_picks`
Expected: FAIL — page doesn't contain "Missed picks reminder" yet, `save_missed_picks_campaign` action not handled.

- [ ] **Step 3: Update the view**

In `pickem/pickem_superadmin/views/email.py`, update the import (line 5-9):

```python
from pickem_homepage.emailing import (
    send_due_email_campaigns,
    send_test_email,
    send_weekly_picks_preview_email,
)
```

to:

```python
from pickem_homepage.emailing import (
    send_due_email_campaigns,
    send_missed_picks_preview_email,
    send_test_email,
    send_weekly_picks_preview_email,
)
```

Update `email_settings` (the whole function, currently lines 48-192). Insert missed-campaign loading right after the existing weekly campaign lines near the top:

```python
@superadmin_required
@require_http_methods(["GET", "POST"])
def email_settings(request):
    settings_obj = EmailProviderSettings.load()
    weekly_campaign = EmailNotificationCampaign.load_weekly_picks()
    missed_campaign = EmailNotificationCampaign.load_missed_picks_reminder()
    before = _settings_snapshot(settings_obj)
    campaign_before = _campaign_snapshot(weekly_campaign)
    missed_campaign_before = _campaign_snapshot(missed_campaign)
    test_form = EmailTestSendForm()
    campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
    preview_form = WeeklyPicksPreviewForm(prefix='preview')
    missed_campaign_form = EmailNotificationCampaignForm(instance=missed_campaign, prefix='missed_campaign')
    missed_preview_form = WeeklyPicksPreviewForm(prefix='missed_preview')

    if request.method == 'POST':
        action = request.POST.get('action', 'save_settings')
        if action == 'send_test_email':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
            missed_campaign_form = EmailNotificationCampaignForm(instance=missed_campaign, prefix='missed_campaign')
            test_form = EmailTestSendForm(request.POST)
            if test_form.is_valid():
                to_email = test_form.cleaned_data['to_email']
                result = send_test_email(to_email=to_email)
                if result['status'] == 'sent':
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_TEST_SENT,
                        target=settings_obj,
                        summary=f'Sent test email to {to_email}',
                        changes={'to_email': [None, to_email]},
                    )
                    messages.success(request, f'Test email sent to {to_email}.')
                    return redirect('superadmin:email_settings')
                if result['reason'] == 'not_configured':
                    messages.error(request, 'Email provider is not fully configured yet.')
                else:
                    messages.error(request, f'Failed to send test email to {to_email}.')
        elif action == 'save_weekly_campaign':
            form = EmailProviderSettingsForm(instance=settings_obj)
            missed_campaign_form = EmailNotificationCampaignForm(instance=missed_campaign, prefix='missed_campaign')
            campaign_form = EmailNotificationCampaignForm(
                request.POST, instance=weekly_campaign, prefix='campaign',
            )
            if campaign_form.is_valid():
                weekly_campaign = campaign_form.save()
                changes = diff_fields(campaign_before, _campaign_snapshot(weekly_campaign))
                if changes:
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_CAMPAIGN_UPDATED,
                        target=weekly_campaign,
                        summary='Updated weekly picks email campaign',
                        changes=changes,
                    )
                messages.success(request, 'Weekly picks campaign saved.')
                return redirect('superadmin:email_settings')
        elif action == 'save_missed_picks_campaign':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
            missed_campaign_form = EmailNotificationCampaignForm(
                request.POST, instance=missed_campaign, prefix='missed_campaign',
            )
            if missed_campaign_form.is_valid():
                missed_campaign = missed_campaign_form.save()
                changes = diff_fields(missed_campaign_before, _campaign_snapshot(missed_campaign))
                if changes:
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_CAMPAIGN_UPDATED,
                        target=missed_campaign,
                        summary='Updated missed picks reminder email campaign',
                        changes=changes,
                    )
                messages.success(request, 'Missed picks reminder campaign saved.')
                return redirect('superadmin:email_settings')
        elif action == 'send_weekly_preview':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
            missed_campaign_form = EmailNotificationCampaignForm(instance=missed_campaign, prefix='missed_campaign')
            preview_form = WeeklyPicksPreviewForm(request.POST, prefix='preview')
            if preview_form.is_valid():
                to_email = preview_form.cleaned_data['to_email']
                sample_user_email = preview_form.cleaned_data.get('sample_user_email', '')
                result = send_weekly_picks_preview_email(
                    to_email=to_email,
                    sample_user_email=sample_user_email,
                )
                if result['status'] == 'sent':
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_PREVIEW_SENT,
                        target=weekly_campaign,
                        summary=f'Sent weekly picks preview to {to_email}',
                        changes={
                            'to_email': [None, to_email],
                            'sample_user_email': [None, sample_user_email or None],
                        },
                    )
                    messages.success(request, f'Weekly picks preview sent to {to_email}.')
                    return redirect('superadmin:email_settings')
                if result['reason'] == 'not_configured':
                    messages.error(request, 'Email provider is not fully configured yet.')
                elif result['reason'] == 'no_sample_user':
                    messages.error(request, 'No eligible member exists to render the preview.')
                elif result['reason'] == 'no_upcoming_week':
                    messages.error(request, 'No active NFL week is available from game data yet.')
                else:
                    messages.error(request, f'Failed to send preview to {to_email}.')
        elif action == 'send_missed_picks_preview':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
            missed_campaign_form = EmailNotificationCampaignForm(instance=missed_campaign, prefix='missed_campaign')
            missed_preview_form = WeeklyPicksPreviewForm(request.POST, prefix='missed_preview')
            if missed_preview_form.is_valid():
                to_email = missed_preview_form.cleaned_data['to_email']
                sample_user_email = missed_preview_form.cleaned_data.get('sample_user_email', '')
                result = send_missed_picks_preview_email(
                    to_email=to_email,
                    sample_user_email=sample_user_email,
                )
                if result['status'] == 'sent':
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_PREVIEW_SENT,
                        target=missed_campaign,
                        summary=f'Sent missed picks reminder preview to {to_email}',
                        changes={
                            'to_email': [None, to_email],
                            'sample_user_email': [None, sample_user_email or None],
                        },
                    )
                    messages.success(request, f'Missed picks reminder preview sent to {to_email}.')
                    return redirect('superadmin:email_settings')
                if result['reason'] == 'not_configured':
                    messages.error(request, 'Email provider is not fully configured yet.')
                elif result['reason'] == 'no_sample_user':
                    messages.error(request, 'No eligible member with outstanding picks exists to render the preview.')
                elif result['reason'] == 'no_upcoming_week':
                    messages.error(request, 'No active NFL week is available from game data yet.')
                else:
                    messages.error(request, f'Failed to send preview to {to_email}.')
        elif action == 'send_weekly_now':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
            missed_campaign_form = EmailNotificationCampaignForm(instance=missed_campaign, prefix='missed_campaign')
            result = send_due_email_campaigns(force_weekly_picks=True)
            campaign_rows = [
                row for row in result.get('campaigns', [])
                if row['campaign_key'] == EmailNotificationCampaign.CampaignKey.WEEKLY_PICKS_AVAILABLE
            ]
            if campaign_rows:
                row = campaign_rows[0]
                log_action(
                    request,
                    action=SuperAdminAuditLog.Action.EMAIL_CAMPAIGN_SENT,
                    target=weekly_campaign,
                    summary=(
                        f"Ran weekly picks campaign for {row['season']} week {row['week']}"
                    ),
                    changes={'sent_count': [None, row['sent_count']]},
                )
                messages.success(
                    request,
                    f"Weekly picks campaign ran for week {row['week']} and sent {row['sent_count']} email(s).",
                )
                return redirect('superadmin:email_settings')
            messages.error(
                request,
                'Weekly picks campaign is not in an active NFL week window from game data.',
            )
        elif action == 'send_missed_picks_now':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
            missed_campaign_form = EmailNotificationCampaignForm(instance=missed_campaign, prefix='missed_campaign')
            result = send_due_email_campaigns(force_missed_picks=True)
            campaign_rows = [
                row for row in result.get('campaigns', [])
                if row['campaign_key'] == EmailNotificationCampaign.CampaignKey.MISSED_PICKS_REMINDER
            ]
            if campaign_rows:
                row = campaign_rows[0]
                log_action(
                    request,
                    action=SuperAdminAuditLog.Action.EMAIL_CAMPAIGN_SENT,
                    target=missed_campaign,
                    summary=(
                        f"Ran missed picks reminder campaign for {row['season']} week {row['week']}"
                    ),
                    changes={'sent_count': [None, row['sent_count']]},
                )
                messages.success(
                    request,
                    f"Missed picks reminder ran for week {row['week']} and sent {row['sent_count']} email(s).",
                )
                return redirect('superadmin:email_settings')
            messages.error(
                request,
                'Missed picks reminder is not in an active NFL week window from game data.',
            )
        else:
            form = EmailProviderSettingsForm(request.POST, instance=settings_obj)
            if form.is_valid():
                settings_obj = form.save(commit=False)
                raw_api_key = (form.cleaned_data.get('api_key') or '').strip()
                rotated = False
                if raw_api_key:
                    settings_obj.set_api_key(raw_api_key)
                    rotated = True
                settings_obj.save()

                after = _settings_snapshot(settings_obj)
                changes = diff_fields(before, after)
                if rotated:
                    changes['api_key_rotated'] = [False, True]
                if changes:
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_SETTINGS_UPDATED,
                        target=settings_obj,
                        summary='Updated email provider settings',
                        changes=changes,
                    )
                messages.success(request, 'Email settings saved.')
                return redirect('superadmin:email_settings')
    else:
        form = EmailProviderSettingsForm(instance=settings_obj)

    return render(request, 'superadmin/email.html', {
        'form': form,
        'test_form': test_form,
        'campaign_form': campaign_form,
        'preview_form': preview_form,
        'weekly_campaign': weekly_campaign,
        'missed_campaign_form': missed_campaign_form,
        'missed_preview_form': missed_preview_form,
        'missed_campaign': missed_campaign,
        'email_settings': settings_obj,
    })
```

- [ ] **Step 4: Add the second campaign card to the template**

In `pickem/pickem_superadmin/templates/superadmin/email.html`, insert a new card right after the closing `</div>` of the weekly-picks campaign card and before the outer `</div>` that closes the two-card column (i.e., right after line 132's `</div>` that closes the weekly-picks `sa-card`, still inside the `<div class="space-y-4">` wrapper from line 7):

```html
    <div class="sa-card p-4">
      <div class="sa-h2 mb-1">Missed picks reminder</div>
      <p class="mb-4 text-[12px] text-[#667085]">
        Sends one consolidated email per user listing every pool where they
        still have open (not yet locked), unsubmitted picks for the active week.
      </p>
      <form method="post" class="space-y-4">
        {% csrf_token %}
        <input type="hidden" name="action" value="save_missed_picks_campaign">
        <div class="flex items-center gap-2">
          {{ missed_campaign_form.enabled }}
          <label for="{{ missed_campaign_form.enabled.id_for_label }}" class="text-[13px] font-medium text-[#1b212b]">Enable missed picks email</label>
        </div>
        <div class="grid gap-4 md:grid-cols-3">
          <div>
            <label class="mb-1 block text-[13px] font-medium text-[#1b212b]">Weekday</label>
            {{ missed_campaign_form.weekday }}
          </div>
          <div>
            <label class="mb-1 block text-[13px] font-medium text-[#1b212b]">Hour</label>
            {{ missed_campaign_form.hour }}
            <div class="mt-1 text-[12px] text-[#667085]">{{ missed_campaign_form.hour.help_text }}</div>
          </div>
          <div>
            <label class="mb-1 block text-[13px] font-medium text-[#1b212b]">Minute</label>
            {{ missed_campaign_form.minute }}
          </div>
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          <div>
            <label class="mb-1 block text-[13px] font-medium text-[#1b212b]">Timezone</label>
            {{ missed_campaign_form.timezone_name }}
          </div>
          <div>
            <label class="mb-1 block text-[13px] font-medium text-[#1b212b]">Rollout mode</label>
            {{ missed_campaign_form.rollout_mode }}
          </div>
        </div>
        <div>
          <label class="mb-1 block text-[13px] font-medium text-[#1b212b]">Allowlist emails</label>
          {{ missed_campaign_form.allowlist_emails }}
          <div class="mt-1 text-[12px] text-[#667085]">
            Comma-separated recipients for safe testing. Production safety guard still limits sends to the global allowlist.
          </div>
        </div>
        <button type="submit" class="sa-btn sa-btn-primary">Save missed picks campaign</button>
      </form>

      <div class="mt-5 border-t border-slate-200 pt-4">
        <div class="sa-h2 mb-2">Preview missed picks email</div>
        <form method="post" class="space-y-3">
          {% csrf_token %}
          <input type="hidden" name="action" value="send_missed_picks_preview">
          <div class="grid gap-4 md:grid-cols-2">
            <div>
              <label class="mb-1 block text-[13px] font-medium text-[#1b212b]">Recipient email</label>
              {{ missed_preview_form.to_email }}
              <div class="mt-1 text-[12px] text-[#667085]">{{ missed_preview_form.to_email.help_text }}</div>
            </div>
            <div>
              <label class="mb-1 block text-[13px] font-medium text-[#1b212b]">Sample user email</label>
              {{ missed_preview_form.sample_user_email }}
              <div class="mt-1 text-[12px] text-[#667085]">{{ missed_preview_form.sample_user_email.help_text }}</div>
            </div>
          </div>
          <button type="submit" class="sa-btn sa-btn-default">Send missed picks preview</button>
        </form>
      </div>

      <div class="mt-5 border-t border-slate-200 pt-4">
        <div class="sa-h2 mb-2">Run live campaign now</div>
        <p class="mb-3 text-[12px] text-[#667085]">
          This still respects the active NFL week check, user opt-in, active-user filter, and the production safety allowlist.
        </p>
        <form method="post">
          {% csrf_token %}
          <input type="hidden" name="action" value="send_missed_picks_now">
          <button type="submit" class="sa-btn sa-btn-default">Run missed picks campaign now</button>
        </form>
      </div>
    </div>
```

Also add a status block for the missed-picks campaign to the "Current status" card. In the same template, find the weekly-campaign status block (lines 161-189, from `<div class="pt-3 ... Weekly campaign</div>` through its closing `</div>` before `<div class="mt-5 border-t ...">Send test email`), and insert a matching block right after it:

```html
        <div class="pt-3 text-[12px] font-semibold uppercase tracking-[0.12em] text-[#667085]">Missed picks reminder</div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-[#667085]">Campaign</span>
          <span class="sa-mono">{{ missed_campaign.get_campaign_key_display }}</span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-[#667085]">State</span>
          <span class="sa-pill {% if missed_campaign.enabled %}sa-pill-ok{% else %}sa-pill-muted{% endif %}">
            {% if missed_campaign.enabled %}enabled{% else %}disabled{% endif %}
          </span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-[#667085]">Schedule</span>
          <span class="sa-mono">{{ missed_campaign.weekday_label }} {{ missed_campaign.hour|stringformat:"02d" }}:{{ missed_campaign.minute|stringformat:"02d" }} {{ missed_campaign.timezone_name }}</span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-[#667085]">Rollout</span>
          <span class="sa-mono">{{ missed_campaign.get_rollout_mode_display }}</span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-[#667085]">Last sent</span>
          <span class="sa-mono">
            {% if missed_campaign.last_sent_at %}
              season {{ missed_campaign.last_sent_season }} · week {{ missed_campaign.last_sent_week }} · {{ missed_campaign.last_sent_count }} emails
            {% else %}
              never
            {% endif %}
          </span>
        </div>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_email.EmailSettingsViewTests --settings=pickem.test_settings -v 2`
Expected: PASS (all tests in the class, including the 3 new ones)

- [ ] **Step 6: Run the full test suite**

Run: `cd pickem && python manage.py test --settings=pickem.test_settings`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_superadmin/views/email.py pickem/pickem_superadmin/templates/superadmin/email.html pickem/pickem_superadmin/tests/test_email.py
git commit -m "feat: add missed-picks reminder campaign to superadmin email settings"
```

---

### Task 9: Manual verification

**Files:** none (verification only)

- [ ] **Step 1: Start the dev server** (per this project's CLAUDE.md, it's already running at `http://localhost:8000` — don't start a second instance)

- [ ] **Step 2: Seed a due scenario in the Django shell**

Run: `cd pickem && python manage.py shell --settings=pickem.test_settings` (or against the dev DB without `--settings` if you want to see it against real data) and confirm:

```python
from pickem_superadmin.models import EmailNotificationCampaign
from pickem_homepage.emailing import send_missed_picks_preview_email

campaign = EmailNotificationCampaign.load_missed_picks_reminder()
campaign.enabled = True
campaign.save()

result = send_missed_picks_preview_email(to_email='jdagostino2@gmail.com')
print(result)
```

Expected: `{'status': 'sent', ...}` if there's a real user with outstanding picks in an active NFL week, or `{'status': 'skipped', 'reason': 'no_sample_user'}` / `'no_upcoming_week'` otherwise (both are correct, expected responses, not bugs).

- [ ] **Step 3: Check the superadmin UI in a browser**

Visit `http://localhost:8000/superadmin/email/`, confirm the new "Missed picks reminder" card renders below "Weekly picks campaign", and that "Save missed picks campaign" / "Send missed picks preview" / "Run missed picks campaign now" all work without errors.

- [ ] **Step 4: Confirm no regression to the existing weekly-picks card**

On the same page, confirm the weekly-picks card and its actions still work as before.

---

## Self-Review Notes (for the plan author, not a task)

- Spec coverage: missing trigger (Task 4), consolidated email (Task 4/6), fixed schedule (Task 3/7, reuses existing campaign fields), admin UI parity (Task 8), dedup (Task 1/7 via `_mark_campaign_sent`), tests for all exclusion cases (Tasks 4/6/7) — all spec sections have a corresponding task.
- No new scheduler wiring needed — confirmed `pickem_api/scheduler.py`'s `_run_email_campaigns()` calls `send_due_email_campaigns()` with no arguments, which now evaluates both campaigns.
- `family_link_strategy` field is carried on the missed-picks campaign row (reused model) but never read by the missed-picks send path — this is intentional per the design spec, not an oversight; the admin form still shows the field for the weekly campaign only, not the missed-picks one (the missed-picks card in Task 8 omits the `family_link_strategy` field row deliberately).
