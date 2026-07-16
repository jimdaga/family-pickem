# Superadmin Observability & Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six operator improvements to the `/superadmin/` console: a clickable SUPERUSER pill, a fixed "stale current pools" anomaly, mobile-friendly pages, editable job schedules, a live "running now" indicator, and a database-backed logs subsystem.

**Architecture:** Follow existing superadmin conventions exactly — every new URL carries `@superadmin_required` and is registered in `tests/test_auth.py`; every write goes through `log_action()`; editable rows reuse `save_matrix()`. Two scheduler-owned models (`ScheduledJobConfig`, `RunningJobMarker`) live in `pickem_api` alongside the scheduler; the log model + handler live in `pickem_superadmin`. The in-process APScheduler (single web replica, `RUN_SCHEDULER=true`) is the source of truth for live scheduling; cross-request signals (running markers) live in the DB because a console request may hit a different gunicorn worker than the scheduler.

**Tech Stack:** Django 4.0.2, django-apscheduler, APScheduler `BackgroundScheduler`, hand-written `.sa-*` CSS compiled by Tailwind CLI, Django `unittest`-style `TestCase`.

## Global Constraints

- **Every new superadmin URL** must be added to `pickem_superadmin/tests/test_auth.py` (`SUPERADMIN_URLS` for no-arg GET, `SUPERADMIN_POST_URLS` for POST, `SUPERADMIN_GET_ARG_URLS` for arg GET) or `test_all_urls_are_covered` fails. This is mandatory, not optional.
- **Every superadmin write** goes through `pickem_superadmin.audit.log_action(...)` — never `SuperAdminAuditLog.objects.create()` directly. New action verbs are added to `SuperAdminAuditLog.Action` (`pickem_superadmin/models.py`).
- **Non-superusers get 404** (not 403) from every view; anonymous users are redirected to `/accounts/...` by middleware before the view runs.
- **CSS is compiled:** `.sa-*` classes are hand-written in `pickem/pickem_homepage/static/css/input.css`. After editing it you MUST run `npm run build:prod` (from repo root) to regenerate `pickem/pickem_homepage/static/css/tailwind.css`, and commit BOTH files.
- **Editable matrices** use `pickem_superadmin.matrix.save_matrix(...)`: per-row `ModelForm` prefixed by the row's own `pk`, optimistic concurrency via a `{pk}-updated_at` hidden field, only-changed rows saved, `on_save(obj, changes)` does the `log_action()`.
- **Run tests** from the `pickem/` directory: `python manage.py test pickem_superadmin -v2` (all new tests live under `pickem_superadmin/tests/`).
- **Locked pool settings** (`pick_type`, `include_playoffs`) stay locked — do not touch that behavior.
- **Season format** is `YYZZ` int (e.g. `2627`); current season is `pickem_api.models.currentSeason` (a singleton, read via `.first()`).

---

## Task 1: SUPERUSER pill links to the console

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/base.html:49-55`
- Test: `pickem/pickem_superadmin/tests/test_navbar_link.py` (create)

**Interfaces:**
- Consumes: existing URL name `superadmin:overview` (route `/superadmin/`).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_superadmin/tests/test_navbar_link.py`:

```python
from django.contrib.auth.models import User
from django.test import TestCase


class SuperuserPillLinkTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.member = User.objects.create_user(
            username='member', email='member@example.com', password='pw',
        )

    def test_superuser_pill_links_to_console(self):
        self.client.force_login(self.root)
        html = self.client.get('/', follow=True).content.decode()
        self.assertIn('superuser-badge', html)
        # The badge must be wrapped in (or be) a link to the console.
        self.assertIn('href="/superadmin/"', html)

    def test_no_pill_for_ordinary_member(self):
        self.client.force_login(self.member)
        html = self.client.get('/', follow=True).content.decode()
        self.assertNotIn('superuser-badge', html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_navbar_link -v2`
Expected: `test_superuser_pill_links_to_console` FAILS (no `href="/superadmin/"` around the badge). If `/` does not render `base.html` for a bare superuser in your data, point the GET at `/rules/` instead (it renders `base.html` and needs only auth) and keep the same assertions.

- [ ] **Step 3: Wrap the pill in an anchor**

In `pickem/pickem_homepage/templates/pickem/base.html`, replace the superuser `<span>` block (lines ~49-55) with an anchor wrapper. Keep all existing badge styling on the inner span:

```html
{% if user.is_superuser %}
<!-- Superuser (god mode) indicator: links to the site-operator console -->
<a href="{% url 'superadmin:overview' %}"
   class="inline-flex items-center gap-1.5 rounded-full border border-yellow-400/60 bg-yellow-400/15 px-3 py-1 text-xs font-black uppercase tracking-wide text-yellow-300 hover:bg-yellow-400/25 transition-colors"
   data-testid="superuser-badge"
   title="Open the superadmin operator console">
    <i class="fas fa-bolt" aria-hidden="true"></i>
    Superuser
</a>
{% endif %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_navbar_link -v2`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/base.html pickem/pickem_superadmin/tests/test_navbar_link.py
git commit -m "feat(superadmin): make navbar SUPERUSER pill link to the console

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: "Off-season pools" anomaly → "families not on the current season"

**Files:**
- Modify: `pickem/pickem_superadmin/views/overview.py:25-50` (`_anomalies`)
- Modify: `pickem/pickem_superadmin/templates/superadmin/overview.html` (the `pools_off_season` block)
- Test: `pickem/pickem_superadmin/tests/test_overview.py` (add cases)

**Interfaces:**
- Consumes: `pickem_api.models.Pool` (`.season` int, `.family`), `currentSeason.first().season`.
- Produces: `anomalies['families_off_season']` — a list of dicts `{'family': Family, 'latest_pool': Pool}`. The old key `pools_off_season` is removed.

- [ ] **Step 1: Write the failing tests**

Add to `pickem/pickem_superadmin/tests/test_overview.py` (inside `OverviewTests`):

```python
def test_family_on_current_season_not_flagged(self):
    from pickem_api.models import currentSeason
    currentSeason.objects.create(season=2627, display_name='2026-2027')
    # self.pool (season 2627) is this family's latest; an older pool exists too.
    Pool.objects.create(
        family=self.family, name='Old', slug='old', season=2526,
    )
    response = self.client.get(reverse('superadmin:overview'))
    flagged = [e['family'] for e in response.context['anomalies']['families_off_season']]
    self.assertNotIn(self.family, flagged)

def test_family_whose_latest_pool_is_stale_is_flagged(self):
    from pickem_api.models import currentSeason
    currentSeason.objects.create(season=2728, display_name='2027-2028')
    # self.family's newest pool is season 2627 < current 2728 -> stale.
    response = self.client.get(reverse('superadmin:overview'))
    flagged = {e['family'].id: e for e in response.context['anomalies']['families_off_season']}
    self.assertIn(self.family.id, flagged)
    self.assertEqual(flagged[self.family.id]['latest_pool'].season, 2627)

def test_no_current_season_flags_nothing(self):
    response = self.client.get(reverse('superadmin:overview'))
    self.assertEqual(response.context['anomalies']['families_off_season'], [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_overview -v2`
Expected: the three new tests FAIL with `KeyError: 'families_off_season'`.

- [ ] **Step 3: Rewrite the anomaly logic**

In `pickem/pickem_superadmin/views/overview.py`, replace the `pools_off_season` line and return key in `_anomalies(season)`:

```python
    # "Stale current pools": a family whose most-recent pool never rolled forward
    # to the current season. Historical pools are expected and never flagged —
    # only the newest pool per family, and only if it is behind the current season.
    families_off_season = []
    if season:
        latest_by_family = {}
        for pool in Pool.objects.select_related('family').order_by('family_id', '-season', '-id'):
            latest_by_family.setdefault(pool.family_id, pool)
        for pool in latest_by_family.values():
            if pool.season != season:
                families_off_season.append({'family': pool.family, 'latest_pool': pool})

    return {
        'pools_without_settings': pools_without_settings,
        'stuck_games': stuck_games,
        'families_without_members': families_without_members,
        'families_off_season': families_off_season,
    }
```

Delete the old `pools_off_season = ...` line.

- [ ] **Step 4: Update the template**

In `pickem/pickem_superadmin/templates/superadmin/overview.html`, find the block iterating `anomalies.pools_off_season` and replace it with one iterating `anomalies.families_off_season`. Example (match the surrounding card markup already in the file):

```html
{% if anomalies.families_off_season %}
  <div class="sa-card p-4">
    <div class="sa-h2 mb-2">Families not on the current season</div>
    <ul class="space-y-1 text-[13px]">
      {% for entry in anomalies.families_off_season %}
        <li class="flex items-center justify-between gap-2">
          <span>{{ entry.family.name }}</span>
          <span class="sa-mono text-[#98a2b3]">latest: {{ entry.latest_pool.display_season }}</span>
        </li>
      {% endfor %}
    </ul>
  </div>
{% endif %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_overview -v2`
Expected: PASS (all, including the pre-existing overview tests).

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_superadmin/views/overview.py pickem/pickem_superadmin/templates/superadmin/overview.html pickem/pickem_superadmin/tests/test_overview.py
git commit -m "fix(superadmin): flag only families whose latest pool is off-season

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Mobile-friendly superadmin pages

Every wide `<table>` already sits in a `.sa-table-wrap.sa-table-scroll` container (`overflow-x:auto`), and the overview/jobs grids already collapse below `lg:`. The one element that overflows the viewport is the tab `<nav>` (a non-wrapping flex of 7 tabs). Fix that, then verify each page in the browser at a phone width and fix any page that still overflows the body.

**Files:**
- Modify: `pickem/pickem_superadmin/templates/superadmin/base.html:23` (the `<nav>`)
- Modify (only if browser check finds overflow): the offending template
- Build: `pickem/pickem_homepage/static/css/tailwind.css` (regenerated) — only if you change `input.css`

**Interfaces:** none consumed/produced by other tasks.

- [ ] **Step 1: Make the tab nav wrap instead of overflowing**

In `pickem/pickem_superadmin/templates/superadmin/base.html`, change the nav opening tag:

```html
    <nav class="flex flex-wrap gap-x-0.5 gap-y-0.5 px-3">
```

(`flex-wrap` lets the 7 short tabs wrap to a second row on narrow screens instead of pushing the page wider than the viewport. No CSS rebuild needed — these are Tailwind utility classes already present in the compiled output.)

- [ ] **Step 2: Verify no page scrolls the body horizontally at phone width**

The dev server is already running at `http://localhost:8000` (do not start it). Load the browser tools, then for each superadmin page check that the document is not wider than the viewport.

Load Chrome tools:
`ToolSearch` query `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__resize_window,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__computer`

Resize to ~390px wide, then for each of `/superadmin/`, `/superadmin/users/`, `/superadmin/pools/`, `/superadmin/families/`, `/superadmin/teams/`, `/superadmin/jobs/`, `/superadmin/audit/`, navigate and run:

```javascript
JSON.stringify({
  path: location.pathname,
  bodyOverflowsViewport: document.documentElement.scrollWidth > window.innerWidth + 1,
  scrollWidth: document.documentElement.scrollWidth,
  innerWidth: window.innerWidth,
})
```

Expected on every page: `bodyOverflowsViewport: false`. (Tables may still scroll **inside** their own boxes — that is correct and expected. We only care that the whole page doesn't scroll sideways.)

- [ ] **Step 3: Fix any page that still overflows**

For any page where `bodyOverflowsViewport` is `true`, find the widest element (run the snippet below in that page) and constrain it: wrap a stray wide element in `<div class="sa-table-scroll">`, add `min-w-0` to a flex child, or add `flex-wrap`. If the fix needs a new `.sa-*` rule, edit `input.css` and rebuild (Step 5).

```javascript
[...document.querySelectorAll('*')]
  .filter(el => el.scrollWidth > window.innerWidth + 1)
  .slice(0, 8)
  .map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 60))
```

- [ ] **Step 4: Confirm the fix in the browser**

Re-run the Step 2 snippet on the pages you changed. Expected: `bodyOverflowsViewport: false` everywhere.

- [ ] **Step 5: Rebuild CSS only if you edited input.css**

If (and only if) you edited `input.css`:

Run (from repo root): `npm run build:prod`
Expected: writes `pickem/pickem_homepage/static/css/tailwind.css` with no errors.

- [ ] **Step 6: Run the superadmin test suite (no regressions)**

Run: `cd pickem && python manage.py test pickem_superadmin -v2`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_superadmin/templates/superadmin/
# include the two CSS files only if you rebuilt them:
# git add pickem/pickem_homepage/static/css/input.css pickem/pickem_homepage/static/css/tailwind.css
git commit -m "fix(superadmin): make console pages usable at phone widths

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `ScheduledJobConfig` model + job registry

**Files:**
- Modify: `pickem/pickem_api/scheduler.py` (add `JOB_REGISTRY`)
- Modify: `pickem/pickem_api/models.py` (add `ScheduledJobConfig`)
- Create migration: `pickem/pickem_api/migrations/00NN_scheduledjobconfig.py` (generated)
- Test: `pickem/pickem_superadmin/tests/test_scheduling.py` (create)

**Interfaces:**
- Produces: `pickem_api.scheduler.JOB_REGISTRY` — `dict[str, {'func': callable, 'name': str, 'default_minutes': int}]` for `'update_all'` and `'update_records'`.
- Produces: `pickem_api.models.ScheduledJobConfig(job_id, interval_minutes, enabled, updated_at)` with classmethod `seed_from_registry()`.

- [ ] **Step 1: Add the job registry to the scheduler**

In `pickem/pickem_api/scheduler.py`, after the existing `run_update_all` / `run_update_records` function definitions, add:

```python
# The recurring jobs whose cadence is editable from the superadmin console.
# The console reads this to know which jobs exist and their seed defaults;
# start() and reschedule_live() read it to (re)register those jobs. Keep this
# to genuinely user-tunable pipeline jobs only (maintenance jobs like the log
# prune are registered separately and are NOT listed here, so they can't be
# edited).
JOB_REGISTRY = {
    'update_all': {
        'func': run_update_all,
        'name': 'Run full data-update pipeline',
        'default_minutes': UPDATE_INTERVAL_MINUTES,
    },
    'update_records': {
        'func': run_update_records,
        'name': 'Run team records refresh',
        'default_minutes': RECORDS_INTERVAL_MINUTES,
    },
}
```

- [ ] **Step 2: Write the failing model test**

Create `pickem/pickem_superadmin/tests/test_scheduling.py`:

```python
from django.core.exceptions import ValidationError
from django.test import TestCase

from pickem_api.models import ScheduledJobConfig


class ScheduledJobConfigTests(TestCase):
    def test_seed_from_registry_creates_a_row_per_registry_job(self):
        from pickem_api.scheduler import JOB_REGISTRY

        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_registry()
        self.assertEqual(
            set(ScheduledJobConfig.objects.values_list('job_id', flat=True)),
            set(JOB_REGISTRY.keys()),
        )

    def test_seed_uses_registry_default_minutes(self):
        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_registry()
        cfg = ScheduledJobConfig.objects.get(job_id='update_records')
        self.assertEqual(cfg.interval_minutes, 30)
        self.assertTrue(cfg.enabled)

    def test_seed_is_idempotent_and_preserves_edits(self):
        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_registry()
        cfg = ScheduledJobConfig.objects.get(job_id='update_all')
        cfg.interval_minutes = 5
        cfg.save()
        ScheduledJobConfig.seed_from_registry()  # must not reset the edit
        self.assertEqual(
            ScheduledJobConfig.objects.get(job_id='update_all').interval_minutes, 5,
        )

    def test_interval_must_be_at_least_one(self):
        cfg = ScheduledJobConfig(job_id='x', interval_minutes=0)
        with self.assertRaises(ValidationError):
            cfg.full_clean()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_scheduling -v2`
Expected: FAIL with `ImportError: cannot import name 'ScheduledJobConfig'`.

- [ ] **Step 4: Add the model**

In `pickem/pickem_api/models.py`, add (near the top ensure `from django.core.validators import MinValueValidator` is imported):

```python
class ScheduledJobConfig(models.Model):
    """Editable cadence for a recurring APScheduler job (see scheduler.JOB_REGISTRY).

    The scheduler reads this at start() and on live reschedule; the superadmin
    console edits it. Only job_ids present in JOB_REGISTRY are ever created here.
    """
    job_id = models.CharField(max_length=100, unique=True)
    interval_minutes = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
    )
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['job_id']

    def __str__(self):
        state = 'on' if self.enabled else 'off'
        return f'{self.job_id}: every {self.interval_minutes}m ({state})'

    @classmethod
    def seed_from_registry(cls):
        """Create a config row for any registry job that has none. Never
        overwrites an existing (possibly edited) row."""
        from pickem_api.scheduler import JOB_REGISTRY  # local: scheduler imports models

        for job_id, spec in JOB_REGISTRY.items():
            cls.objects.get_or_create(
                job_id=job_id,
                defaults={'interval_minutes': spec['default_minutes']},
            )
```

- [ ] **Step 5: Generate and apply the migration**

Run: `cd pickem && python manage.py makemigrations pickem_api && python manage.py migrate`
Expected: creates `pickem_api/migrations/00NN_scheduledjobconfig.py`, applies cleanly.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_scheduling -v2`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_api/scheduler.py pickem/pickem_api/models.py pickem/pickem_api/migrations/ pickem/pickem_superadmin/tests/test_scheduling.py
git commit -m "feat(scheduler): add editable ScheduledJobConfig + job registry

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Scheduler reads config on start + live reschedule helper

**Files:**
- Modify: `pickem/pickem_api/scheduler.py` (`start()`, add `reschedule_live()`)
- Test: `pickem/pickem_superadmin/tests/test_scheduling.py` (add cases)

**Interfaces:**
- Consumes: `JOB_REGISTRY`, `ScheduledJobConfig` (Task 4).
- Produces: `pickem_api.scheduler.reschedule_live(job_id, interval_minutes, enabled) -> bool` (True if a live scheduler applied it, False if none). `start()` now registers registry jobs from `ScheduledJobConfig`.

- [ ] **Step 1: Write the failing test**

Add to `pickem/pickem_superadmin/tests/test_scheduling.py`:

```python
class RescheduleLiveTests(TestCase):
    def test_reschedule_live_returns_false_without_a_scheduler(self):
        from pickem_api import scheduler

        original = scheduler._scheduler
        scheduler._scheduler = None
        try:
            self.assertFalse(scheduler.reschedule_live('update_all', 5, True))
        finally:
            scheduler._scheduler = original

    def test_reschedule_live_reregisters_on_a_live_scheduler(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from pickem_api import scheduler

        fake = BackgroundScheduler()
        fake.start(paused=True)
        original = scheduler._scheduler
        scheduler._scheduler = fake
        try:
            self.assertTrue(scheduler.reschedule_live('update_all', 5, True))
            job = fake.get_job('update_all')
            self.assertIsNotNone(job)
            # Disabling removes it entirely.
            self.assertTrue(scheduler.reschedule_live('update_all', 5, False))
            self.assertIsNone(fake.get_job('update_all'))
        finally:
            fake.shutdown(wait=False)
            scheduler._scheduler = original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_scheduling.RescheduleLiveTests -v2`
Expected: FAIL with `AttributeError: module 'pickem_api.scheduler' has no attribute 'reschedule_live'`.

- [ ] **Step 3: Add `reschedule_live` and a shared register helper**

In `pickem/pickem_api/scheduler.py`, add the import at the top with the other apscheduler imports:

```python
from apscheduler.jobstores.base import JobLookupError
```

Then add:

```python
def _register_job(scheduler, job_id, interval_minutes):
    """(Re)register one registry job at the given cadence."""
    spec = JOB_REGISTRY[job_id]
    scheduler.add_job(
        spec['func'],
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=job_id,
        name=spec['name'],
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )


def reschedule_live(job_id, interval_minutes, enabled):
    """Apply a schedule change to the running scheduler in THIS process.

    Returns True if applied live, False if this process has no live scheduler
    (the change is still persisted in ScheduledJobConfig and takes effect on the
    next start()). Re-registers from scratch so an interval change and an
    enable/disable use one code path.
    """
    if _scheduler is None or job_id not in JOB_REGISTRY:
        return False
    try:
        _scheduler.remove_job(job_id)
    except JobLookupError:
        pass
    if enabled:
        _register_job(_scheduler, job_id, interval_minutes)
    return True
```

- [ ] **Step 4: Make `start()` read config**

In `pickem/pickem_api/scheduler.py`, replace the two hardcoded `scheduler.add_job(run_update_all, ...)` / `scheduler.add_job(run_update_records, ...)` calls in `start()` with a config-driven loop:

```python
    from pickem_api.models import ScheduledJobConfig

    ScheduledJobConfig.seed_from_registry()
    for cfg in ScheduledJobConfig.objects.filter(job_id__in=JOB_REGISTRY.keys()):
        if cfg.enabled:
            _register_job(scheduler, cfg.job_id, cfg.interval_minutes)
```

Leave `scheduler.start()`, `_scheduler = scheduler`, and the log line intact below this.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_scheduling -v2`
Expected: PASS (all scheduling tests).

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_api/scheduler.py pickem/pickem_superadmin/tests/test_scheduling.py
git commit -m "feat(scheduler): register recurring jobs from config + live reschedule

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Editable schedule form on the jobs page

**Files:**
- Modify: `pickem/pickem_superadmin/forms.py` (add `ScheduledJobConfigForm`)
- Modify: `pickem/pickem_superadmin/models.py` (add `SCHEDULE_UPDATED` action)
- Create migration: `pickem/pickem_superadmin/migrations/00NN_*.py` (generated, for the new Action choice — Django records choices changes; if no migration is produced that is fine)
- Modify: `pickem/pickem_superadmin/views/jobs.py` (`jobs_page` context + new `jobs_schedule_save`)
- Modify: `pickem/pickem_superadmin/urls.py` (new route)
- Modify: `pickem/pickem_superadmin/templates/superadmin/jobs.html` (schedule editor)
- Modify: `pickem/pickem_superadmin/tests/test_auth.py` (register the new POST URL)
- Test: `pickem/pickem_superadmin/tests/test_jobs.py` (add cases)

**Interfaces:**
- Consumes: `save_matrix`, `log_action`, `ScheduledJobConfig`, `scheduler.reschedule_live`.
- Produces: URL `superadmin:jobs_schedule_save` (POST).

- [ ] **Step 1: Add the audit action verb**

In `pickem/pickem_superadmin/models.py`, add to `SuperAdminAuditLog.Action`:

```python
        SCHEDULE_UPDATED = 'schedule_updated', 'Job schedule updated'
```

Run: `cd pickem && python manage.py makemigrations pickem_superadmin && python manage.py migrate`
Expected: a small migration for the choices change (or none — both are acceptable).

- [ ] **Step 2: Add the row form**

In `pickem/pickem_superadmin/forms.py`, add:

```python
from pickem_api.models import ScheduledJobConfig  # add to existing imports


class ScheduledJobConfigForm(forms.ModelForm):
    """One editable schedule row (interval minutes + enabled), prefixed by pk."""

    class Meta:
        model = ScheduledJobConfig
        fields = ('interval_minutes', 'enabled')
        widgets = {
            'interval_minutes': forms.NumberInput(attrs={'class': NUM_CELL, 'min': 1}),
        }
```

- [ ] **Step 3: Write the failing tests**

Add to `pickem/pickem_superadmin/tests/test_jobs.py` (create the file if it lacks a superuser fixture; mirror the pattern below):

```python
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import ScheduledJobConfig
from pickem_superadmin.models import SuperAdminAuditLog


class ScheduleEditTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        ScheduledJobConfig.seed_from_registry()
        self.client.force_login(self.root)

    def _post(self, cfg, **overrides):
        data = {
            f'{cfg.pk}-interval_minutes': cfg.interval_minutes,
            f'{cfg.pk}-enabled': 'on' if cfg.enabled else '',
            f'{cfg.pk}-updated_at': cfg.updated_at.isoformat(),
        }
        data.update(overrides)
        return self.client.post(reverse('superadmin:jobs_schedule_save'), data)

    def test_editing_the_interval_persists_and_audits(self):
        cfg = ScheduledJobConfig.objects.get(job_id='update_all')
        self._post(cfg, **{f'{cfg.pk}-interval_minutes': 5})
        cfg.refresh_from_db()
        self.assertEqual(cfg.interval_minutes, 5)
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.SCHEDULE_UPDATED)
        self.assertEqual(entry.changes['interval_minutes'], [1, 5])

    def test_interval_below_one_is_rejected(self):
        cfg = ScheduledJobConfig.objects.get(job_id='update_all')
        self._post(cfg, **{f'{cfg.pk}-interval_minutes': 0})
        cfg.refresh_from_db()
        self.assertEqual(cfg.interval_minutes, 1)  # unchanged

    def test_disabling_a_job_persists(self):
        cfg = ScheduledJobConfig.objects.get(job_id='update_records')
        self._post(cfg, **{f'{cfg.pk}-enabled': ''})
        cfg.refresh_from_db()
        self.assertFalse(cfg.enabled)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_jobs.ScheduleEditTests -v2`
Expected: FAIL — `NoReverseMatch: 'jobs_schedule_save'`.

- [ ] **Step 5: Add the URL**

In `pickem/pickem_superadmin/urls.py`, add after the `jobs_queue` line:

```python
    path('jobs/schedule/save/', views.jobs_schedule_save, name='jobs_schedule_save'),
```

- [ ] **Step 6: Register the URL in the auth-coverage test**

In `pickem/pickem_superadmin/tests/test_auth.py`, add to `SUPERADMIN_POST_URLS`:

```python
    ('superadmin:jobs_schedule_save', []),
```

- [ ] **Step 7: Implement the view**

In `pickem/pickem_superadmin/views/jobs.py`, add imports and the view, and add the schedule configs to `jobs_page`'s context:

```python
from pickem_api.models import ScheduledJobConfig
from pickem_api import scheduler as scheduler_module
from pickem_superadmin.forms import ScheduledJobConfigForm
from pickem_superadmin.matrix import save_matrix
```

Add to the `jobs_page` render context dict:

```python
        'schedule_configs': ScheduledJobConfig.objects.all(),
        'schedule_forms': {
            c.pk: ScheduledJobConfigForm(instance=c, prefix=str(c.pk))
            for c in ScheduledJobConfig.objects.all()
        },
```

Then the save view:

```python
@superadmin_required
@require_POST
def jobs_schedule_save(request):
    ScheduledJobConfig.seed_from_registry()
    configs = list(ScheduledJobConfig.objects.all())

    def on_save(cfg, changes):
        log_action(
            request,
            action=SuperAdminAuditLog.Action.SCHEDULE_UPDATED,
            target=cfg,
            summary=f'Updated schedule for {cfg.job_id}',
            changes=changes,
        )
        # Apply to the live scheduler if this process is the scheduler process;
        # otherwise the change is already persisted and applies on next start().
        scheduler_module.reschedule_live(cfg.job_id, cfg.interval_minutes, cfg.enabled)

    saved, failed, stale = save_matrix(
        request,
        objects=configs,
        form_class=ScheduledJobConfigForm,
        tracked_fields=('interval_minutes', 'enabled'),
        key_field='interval_minutes',
        on_save=on_save,
    )

    if saved:
        messages.success(request, f'Updated {saved} schedule(s).')
    if stale:
        messages.error(request, 'Not saved — changed since you loaded it. Reload and retry.')
    if failed:
        messages.error(request, 'Invalid interval (must be a whole number ≥ 1).')
    if not saved and not stale and not failed:
        messages.success(request, 'No changes.')
    return redirect('superadmin:jobs')
```

- [ ] **Step 8: Add the editor to the template**

In `pickem/pickem_superadmin/templates/superadmin/jobs.html`, inside the left column card (after the "Registered jobs" list, before the closing `</div>` of that card), add:

```html
      <div class="sa-h2 mt-5 mb-2">Schedules</div>
      <form method="post" action="{% url 'superadmin:jobs_schedule_save' %}" class="space-y-2">
        {% csrf_token %}
        {% for cfg in schedule_configs %}
          {% with form=schedule_forms|dictkey:cfg.pk %}
          <div class="flex items-center justify-between gap-2 text-[12px]">
            <span class="sa-mono">{{ cfg.job_id }}</span>
            <span class="flex items-center gap-1">
              every {{ form.interval_minutes }} min
              <label class="ml-2 inline-flex items-center gap-1">{{ form.enabled }} on</label>
              <input type="hidden" name="{{ cfg.pk }}-updated_at" value="{{ cfg.updated_at.isoformat }}">
            </span>
          </div>
          {% endwith %}
        {% endfor %}
        <button type="submit" class="sa-btn sa-btn-default sa-btn-sm justify-center w-full">Save schedules</button>
      </form>
```

This uses a `dictkey` filter to fetch `schedule_forms[cfg.pk]`. Add it to `pickem/pickem_superadmin/templatetags/sa_extras.py`:

```python
@register.filter
def dictkey(mapping, key):
    """Look up mapping[key] in a template (Django can't index by variable key)."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None
```

(`from django import template` / `register = template.Library()` already exist at the top of that file — reuse them.)

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_jobs pickem_superadmin.tests.test_auth -v2`
Expected: PASS (schedule edit tests + the full auth-coverage suite).

- [ ] **Step 10: Verify in the browser**

Navigate to `http://localhost:8000/superadmin/jobs/`, change `update_records` to a different interval, Save, and confirm the success message and the persisted value on reload.

- [ ] **Step 11: Commit**

```bash
git add pickem/pickem_superadmin/ pickem/pickem_api/
git commit -m "feat(superadmin): edit recurring job schedules from the jobs page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: `RunningJobMarker` model + marker helpers

**Files:**
- Modify: `pickem/pickem_api/models.py` (add `RunningJobMarker`)
- Modify: `pickem/pickem_api/scheduler.py` (marker helpers)
- Create migration: `pickem/pickem_api/migrations/00NN_runningjobmarker.py` (generated)
- Test: `pickem/pickem_superadmin/tests/test_running_markers.py` (create)

**Interfaces:**
- Produces: `pickem_api.models.RunningJobMarker(job_id, started_at)`.
- Produces in `pickem_api.scheduler`: `mark_job_started(job_id)`, `mark_job_finished(job_id)`, `current_running_jobs() -> list[RunningJobMarker]` (excludes markers older than `STALE_RUNNING_AFTER`).

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_superadmin/tests/test_running_markers.py`:

```python
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from pickem_api import scheduler
from pickem_api.models import RunningJobMarker


class RunningMarkerTests(TestCase):
    def test_start_then_finish_clears_the_marker(self):
        scheduler.mark_job_started('update_all')
        self.assertEqual(len(scheduler.current_running_jobs()), 1)
        scheduler.mark_job_finished('update_all')
        self.assertEqual(scheduler.current_running_jobs(), [])

    def test_start_is_idempotent_per_job(self):
        scheduler.mark_job_started('update_all')
        scheduler.mark_job_started('update_all')
        self.assertEqual(RunningJobMarker.objects.filter(job_id='update_all').count(), 1)

    def test_stale_markers_are_not_reported_running(self):
        RunningJobMarker.objects.create(
            job_id='update_all',
            started_at=timezone.now() - timedelta(minutes=30),
        )
        self.assertEqual(scheduler.current_running_jobs(), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_running_markers -v2`
Expected: FAIL with `ImportError` / `AttributeError` for `RunningJobMarker` / `mark_job_started`.

- [ ] **Step 3: Add the model**

In `pickem/pickem_api/models.py`:

```python
class RunningJobMarker(models.Model):
    """A row exists while an APScheduler job is executing. Written by scheduler
    event listeners, read by the superadmin jobs status endpoint. DB-backed (not
    in-memory) because a console request may run in a different worker than the
    scheduler."""
    job_id = models.CharField(max_length=100, unique=True)
    started_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['started_at']

    def __str__(self):
        return f'{self.job_id} running since {self.started_at}'
```

Ensure `from django.utils import timezone` is imported in `models.py` (add if missing).

- [ ] **Step 4: Add the helpers**

In `pickem/pickem_api/scheduler.py` add near the top-level constants:

```python
from datetime import timedelta

# A marker older than this is treated as a crash between submit and finish, so
# the UI never gets stuck showing "running" forever.
STALE_RUNNING_AFTER = timedelta(minutes=10)
```

And the functions:

```python
def mark_job_started(job_id):
    from django.utils import timezone
    from pickem_api.models import RunningJobMarker

    RunningJobMarker.objects.update_or_create(
        job_id=job_id, defaults={'started_at': timezone.now()},
    )


def mark_job_finished(job_id):
    from pickem_api.models import RunningJobMarker

    RunningJobMarker.objects.filter(job_id=job_id).delete()


def current_running_jobs():
    from django.utils import timezone
    from pickem_api.models import RunningJobMarker

    cutoff = timezone.now() - STALE_RUNNING_AFTER
    return list(RunningJobMarker.objects.filter(started_at__gte=cutoff))
```

- [ ] **Step 5: Generate and apply the migration**

Run: `cd pickem && python manage.py makemigrations pickem_api && python manage.py migrate`
Expected: creates `00NN_runningjobmarker.py`, applies cleanly.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_running_markers -v2`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_api/models.py pickem/pickem_api/scheduler.py pickem/pickem_api/migrations/ pickem/pickem_superadmin/tests/test_running_markers.py
git commit -m "feat(scheduler): DB-backed running-job markers with stale cutoff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Wire scheduler event listeners

**Files:**
- Modify: `pickem/pickem_api/scheduler.py` (`start()` + listener callbacks)
- Test: `pickem/pickem_superadmin/tests/test_running_markers.py` (add a listener-callback case)

**Interfaces:**
- Consumes: `mark_job_started`, `mark_job_finished` (Task 7).
- Produces: `_on_job_submitted(event)`, `_on_job_done(event)` registered on the scheduler.

- [ ] **Step 1: Write the failing test**

Add to `pickem/pickem_superadmin/tests/test_running_markers.py`:

```python
class ListenerCallbackTests(TestCase):
    def test_submitted_then_executed_callbacks_toggle_the_marker(self):
        from types import SimpleNamespace

        from pickem_api import scheduler

        scheduler._on_job_submitted(SimpleNamespace(job_id='update_all'))
        self.assertEqual(len(scheduler.current_running_jobs()), 1)
        scheduler._on_job_done(SimpleNamespace(job_id='update_all'))
        self.assertEqual(scheduler.current_running_jobs(), [])

    def test_callbacks_swallow_errors(self):
        from types import SimpleNamespace

        from pickem_api import scheduler

        # A malformed event (no job_id) must not raise out of the listener, and
        # must not create a junk marker row.
        scheduler._on_job_submitted(SimpleNamespace())
        scheduler._on_job_done(SimpleNamespace())
        self.assertEqual(scheduler.current_running_jobs(), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_running_markers.ListenerCallbackTests -v2`
Expected: FAIL with `AttributeError: ... has no attribute '_on_job_submitted'`.

- [ ] **Step 3: Add listener callbacks**

In `pickem/pickem_api/scheduler.py`:

```python
def _on_job_submitted(event):
    """APScheduler EVENT_JOB_SUBMITTED: a job started executing."""
    try:
        mark_job_started(event.job_id)
    except Exception:
        logger.exception('Failed to record job start marker')


def _on_job_done(event):
    """APScheduler EVENT_JOB_EXECUTED | EVENT_JOB_ERROR: a job finished."""
    try:
        mark_job_finished(event.job_id)
    except Exception:
        logger.exception('Failed to clear job start marker')
```

(`getattr(event, 'job_id')` is accessed inside the `try`; a malformed event without it raises `AttributeError`, which is swallowed — satisfying `test_callbacks_swallow_errors`.)

- [ ] **Step 4: Register the listeners in `start()`**

Add the import at the top of `scheduler.py`:

```python
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_SUBMITTED
```

In `start()`, after the job-registration loop and before `scheduler.start()`:

```python
    scheduler.add_listener(_on_job_submitted, EVENT_JOB_SUBMITTED)
    scheduler.add_listener(_on_job_done, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_running_markers -v2`
Expected: PASS (all marker tests).

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_api/scheduler.py pickem/pickem_superadmin/tests/test_running_markers.py
git commit -m "feat(scheduler): mark running jobs via APScheduler event listeners

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Live "running now" status endpoint + polling

**Files:**
- Modify: `pickem/pickem_superadmin/views/jobs.py` (add `jobs_status`)
- Modify: `pickem/pickem_superadmin/urls.py` (new route)
- Modify: `pickem/pickem_superadmin/tests/test_auth.py` (register new GET URL)
- Modify: `pickem/pickem_superadmin/templates/superadmin/jobs.html` (live badge + poll)
- Test: `pickem/pickem_superadmin/tests/test_jobs.py` (add cases)

**Interfaces:**
- Consumes: `scheduler.current_running_jobs`, `jobs.scheduler_health`.
- Produces: URL `superadmin:jobs_status` (GET) returning JSON `{"running": [...], "health": {...}}`.

- [ ] **Step 1: Write the failing tests**

Add to `pickem/pickem_superadmin/tests/test_jobs.py`:

```python
class JobsStatusEndpointTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root2', email='root2@example.com', password='pw',
        )
        self.client.force_login(self.root)

    def test_status_json_reports_running_jobs(self):
        from pickem_api import scheduler

        scheduler.mark_job_started('update_all')
        data = self.client.get(reverse('superadmin:jobs_status')).json()
        self.assertEqual([r['job_id'] for r in data['running']], ['update_all'])
        self.assertIn('health', data)

    def test_status_json_empty_when_idle(self):
        data = self.client.get(reverse('superadmin:jobs_status')).json()
        self.assertEqual(data['running'], [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_jobs.JobsStatusEndpointTests -v2`
Expected: FAIL — `NoReverseMatch: 'jobs_status'`.

- [ ] **Step 3: Add the URL + register it in the auth test**

In `pickem/pickem_superadmin/urls.py`:

```python
    path('jobs/status.json', views.jobs_status, name='jobs_status'),
```

In `pickem/pickem_superadmin/tests/test_auth.py`, add to `SUPERADMIN_URLS`:

```python
    'superadmin:jobs_status',
```

(It is a no-arg GET that returns JSON 200 for a superuser, so `SUPERADMIN_URLS` — which asserts GET-200 — is correct for it.)

- [ ] **Step 4: Implement the view**

In `pickem/pickem_superadmin/views/jobs.py`:

```python
from django.http import JsonResponse
from django.utils import timezone


@superadmin_required
def jobs_status(request):
    now = timezone.now()
    running = [
        {
            'job_id': m.job_id,
            'started_at': m.started_at.isoformat(),
            'seconds': int((now - m.started_at).total_seconds()),
        }
        for m in scheduler_module.current_running_jobs()
    ]
    health = jobs.scheduler_health()
    return JsonResponse({
        'running': running,
        'health': {
            'alive': health['alive'],
            'last_run': health['last_run'].isoformat() if health['last_run'] else None,
            'last_status': health['last_status'],
        },
    })
```

(`scheduler_module` and `jobs` are already imported in `views/jobs.py` from Task 6 / the existing file.)

- [ ] **Step 5: Add the live badge + polling to the template**

In `pickem/pickem_superadmin/templates/superadmin/jobs.html`, add a status badge near the top of the right column (above "Run history"):

```html
      <div id="sa-live-status" class="mb-2 flex items-center gap-2 text-[12px] text-[#667085]">
        <span class="sa-dot sa-dot-muted"></span> checking…
      </div>
```

Then at the end of the template (after `{% endblock %}`'s content, inside the block), add a script:

```html
  <script>
    (function () {
      const el = document.getElementById('sa-live-status');
      const url = "{% url 'superadmin:jobs_status' %}";
      let timer = null;

      function render(data) {
        if (data.running && data.running.length) {
          const names = data.running.map(r => r.job_id + ' (' + r.seconds + 's)').join(', ');
          el.innerHTML = '<span class="sa-dot sa-dot-bad"></span> running: ' + names;
        } else if (data.health && data.health.alive) {
          el.innerHTML = '<span class="sa-dot sa-dot-ok"></span> idle · scheduler alive';
        } else {
          el.innerHTML = '<span class="sa-dot sa-dot-bad"></span> scheduler not running';
        }
      }

      async function poll() {
        try {
          const res = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
          if (res.ok) render(await res.json());
        } catch (e) { /* transient; next tick retries */ }
      }

      function start() { if (!timer) { poll(); timer = setInterval(poll, 3000); } }
      function stop() { if (timer) { clearInterval(timer); timer = null; } }

      document.addEventListener('visibilitychange', () =>
        document.hidden ? stop() : start());
      start();
    })();
  </script>
```

Add a muted dot style if not present. In `pickem/pickem_homepage/static/css/input.css`, near the other `.sa-dot-*` rules, add:

```css
.sa-dot-muted { background: #cbd5e1; }
```

Then rebuild CSS (from repo root): `npm run build:prod`

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_jobs pickem_superadmin.tests.test_auth -v2`
Expected: PASS.

- [ ] **Step 7: Verify in the browser**

Load `http://localhost:8000/superadmin/jobs/`; confirm the status line shows "idle · scheduler alive" (or "scheduler not running" in a dev process without `RUN_SCHEDULER=true`) and updates without a page reload.

- [ ] **Step 8: Commit**

```bash
git add pickem/pickem_superadmin/ pickem/pickem_homepage/static/css/
git commit -m "feat(superadmin): live running-job indicator on the jobs page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: `SuperAdminLogEntry` model

**Files:**
- Create: `pickem/pickem_superadmin/models.py` (add `SuperAdminLogEntry`)
- Create migration: `pickem/pickem_superadmin/migrations/00NN_superadminlogentry.py` (generated)
- Test: `pickem/pickem_superadmin/tests/test_logs.py` (create)

**Interfaces:**
- Produces: `pickem_superadmin.models.SuperAdminLogEntry(timestamp, level, level_no, logger_name, message, traceback, pathname, lineno)`.

- [ ] **Step 1: Write the failing test**

Create `pickem/pickem_superadmin/tests/test_logs.py`:

```python
from django.test import TestCase

from pickem_superadmin.models import SuperAdminLogEntry


class LogEntryModelTests(TestCase):
    def test_can_store_a_log_row(self):
        entry = SuperAdminLogEntry.objects.create(
            level='INFO', level_no=20, logger_name='pickem_api.x', message='hi',
        )
        self.assertEqual(SuperAdminLogEntry.objects.get().message, 'hi')
        self.assertIsNotNone(entry.timestamp)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs -v2`
Expected: FAIL — `ImportError: cannot import name 'SuperAdminLogEntry'`.

- [ ] **Step 3: Add the model**

In `pickem/pickem_superadmin/models.py` (ensure `from django.utils import timezone` is imported):

```python
class SuperAdminLogEntry(models.Model):
    """Application log records captured to the DB so the console can show them
    without shell/kubectl access. Written by pickem_superadmin.logging.DatabaseLogHandler,
    aged out by the prune_superadmin_logs command."""

    LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    level = models.CharField(max_length=10, choices=[(l, l) for l in LEVELS])
    level_no = models.PositiveSmallIntegerField(default=0)
    logger_name = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    traceback = models.TextField(blank=True, null=True)
    pathname = models.CharField(max_length=255, blank=True, null=True)
    lineno = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['level_no', '-timestamp'], name='sa_log_level_ts_idx'),
            models.Index(fields=['-timestamp'], name='sa_log_ts_idx'),
        ]

    def __str__(self):
        return f'[{self.level}] {self.logger_name}: {self.message[:60]}'
```

- [ ] **Step 4: Generate and apply the migration**

Run: `cd pickem && python manage.py makemigrations pickem_superadmin && python manage.py migrate`
Expected: creates the migration, applies cleanly.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs -v2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_superadmin/models.py pickem/pickem_superadmin/migrations/ pickem/pickem_superadmin/tests/test_logs.py
git commit -m "feat(superadmin): add SuperAdminLogEntry model

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: Database logging handler

**Files:**
- Create: `pickem/pickem_superadmin/logging.py`
- Test: `pickem/pickem_superadmin/tests/test_logs.py` (add handler cases)

**Interfaces:**
- Consumes: `SuperAdminLogEntry` (Task 10).
- Produces: `pickem_superadmin.logging.DatabaseLogHandler` (a `logging.Handler` subclass); module constants `MAX_MESSAGE_LEN`, `MAX_TB_LEN`, `EXCLUDED_LOGGER_PREFIXES`.

- [ ] **Step 1: Write the failing tests**

Add to `pickem/pickem_superadmin/tests/test_logs.py`:

```python
import logging

from pickem_superadmin.models import SuperAdminLogEntry


class DatabaseLogHandlerTests(TestCase):
    def _handler(self):
        from pickem_superadmin.logging import DatabaseLogHandler

        return DatabaseLogHandler()

    def _record(self, name='pickem_api.test', level=logging.INFO, msg='hello', exc_info=None):
        return logging.LogRecord(
            name=name, level=level, pathname='/app/x.py', lineno=42,
            msg=msg, args=(), exc_info=exc_info,
        )

    def test_emit_writes_a_row(self):
        self._handler().emit(self._record(msg='captured'))
        row = SuperAdminLogEntry.objects.get()
        self.assertEqual(row.message, 'captured')
        self.assertEqual(row.level, 'INFO')
        self.assertEqual(row.level_no, logging.INFO)
        self.assertEqual(row.logger_name, 'pickem_api.test')

    def test_db_logger_records_are_dropped(self):
        # A record from the DB layer must never be written back into the DB,
        # or a DB error while logging would loop.
        self._handler().emit(self._record(name='django.db.backends'))
        self.assertEqual(SuperAdminLogEntry.objects.count(), 0)

    def test_long_message_is_truncated(self):
        from pickem_superadmin.logging import MAX_MESSAGE_LEN

        self._handler().emit(self._record(msg='x' * (MAX_MESSAGE_LEN + 500)))
        self.assertEqual(len(SuperAdminLogEntry.objects.get().message), MAX_MESSAGE_LEN)

    def test_exception_records_capture_a_traceback(self):
        try:
            raise ValueError('boom')
        except ValueError:
            import sys
            rec = self._record(level=logging.ERROR, msg='failed', exc_info=sys.exc_info())
        self._handler().emit(rec)
        row = SuperAdminLogEntry.objects.get()
        self.assertIn('ValueError: boom', row.traceback)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs.DatabaseLogHandlerTests -v2`
Expected: FAIL — `ModuleNotFoundError: No module named 'pickem_superadmin.logging'`.

- [ ] **Step 3: Implement the handler**

Create `pickem/pickem_superadmin/logging.py`:

```python
"""A logging.Handler that writes records into SuperAdminLogEntry so the console
can show application logs without shell/kubectl access.

Two failure modes are designed around:

1. Recursion — writing a log row runs DB queries, which the DB layer logs. If we
   captured those, a single DB error while logging would generate more log rows
   and loop. So records from the DB loggers (and this module) are dropped.
2. Bootstrap — before migrations create the table, create() raises. emit() routes
   every failure to handleError() (stderr), never back into logging, so a missing
   table simply drops the record instead of crashing the request.
"""
import logging

MAX_MESSAGE_LEN = 10000
MAX_TB_LEN = 20000

# Records from these logger prefixes are never captured (see recursion note).
EXCLUDED_LOGGER_PREFIXES = ('django.db', 'pickem_superadmin.logging')


class DatabaseLogHandler(logging.Handler):
    def emit(self, record):
        if record.name.startswith(EXCLUDED_LOGGER_PREFIXES):
            return
        try:
            from pickem_superadmin.models import SuperAdminLogEntry

            message = self.format(record)[:MAX_MESSAGE_LEN]
            traceback_text = None
            if record.exc_info:
                traceback_text = logging.Formatter().formatException(
                    record.exc_info
                )[:MAX_TB_LEN]

            SuperAdminLogEntry.objects.create(
                level=record.levelname,
                level_no=record.levelno,
                logger_name=record.name,
                message=message,
                traceback=traceback_text,
                pathname=(record.pathname or '')[:255] or None,
                lineno=record.lineno,
            )
        except Exception:
            # Never raise out of logging, and never log this failure back into
            # the DB. handleError() writes to stderr only.
            self.handleError(record)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs.DatabaseLogHandlerTests -v2`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_superadmin/logging.py pickem/pickem_superadmin/tests/test_logs.py
git commit -m "feat(superadmin): DB logging handler with loop guard + truncation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 12: Wire the handler into Django `LOGGING`

**Files:**
- Modify: `pickem/pickem/settings.py` (add `LOGGING` + constants)
- Test: `pickem/pickem_superadmin/tests/test_logs.py` (add wiring cases)

**Interfaces:**
- Consumes: `DatabaseLogHandler` (Task 11).
- Produces: settings `SUPERADMIN_LOG_APP_LEVEL`, `SUPERADMIN_LOG_ROOT_LEVEL`, `LOG_RETENTION_DAYS`, `LOG_MAX_ROWS`, and a configured `LOGGING` dict.

- [ ] **Step 1: Write the failing tests**

Add to `pickem/pickem_superadmin/tests/test_logs.py`:

```python
import logging

from pickem_superadmin.models import SuperAdminLogEntry


class LoggingWiringTests(TestCase):
    def test_app_logger_info_is_captured(self):
        logging.getLogger('pickem_api').info('WIRING-APP-INFO-marker')
        self.assertTrue(
            SuperAdminLogEntry.objects.filter(message__contains='WIRING-APP-INFO-marker').exists()
        )

    def test_unrelated_info_is_not_captured(self):
        logging.getLogger('some.random.thirdparty').info('WIRING-ROOT-INFO-marker')
        self.assertFalse(
            SuperAdminLogEntry.objects.filter(message__contains='WIRING-ROOT-INFO-marker').exists()
        )

    def test_unrelated_warning_is_captured(self):
        logging.getLogger('some.random.thirdparty').warning('WIRING-ROOT-WARN-marker')
        self.assertTrue(
            SuperAdminLogEntry.objects.filter(message__contains='WIRING-ROOT-WARN-marker').exists()
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs.LoggingWiringTests -v2`
Expected: FAIL (no `LOGGING` config yet, so nothing is captured).

- [ ] **Step 3: Add the LOGGING config**

Confirm `import os` is present at the top of `pickem/pickem/settings.py` (it is used elsewhere). Append near the end of the file:

```python
# --- Application logging -> superadmin console -------------------------------
# App loggers are captured at INFO so the pipeline's own activity is visible in
# the console ("I feel blind"); everything else at WARNING to avoid per-request
# noise. Both are env-tunable. The DB handler writes SuperAdminLogEntry rows;
# the console handler keeps stdout intact for `kubectl logs`.
SUPERADMIN_LOG_APP_LEVEL = os.environ.get('SUPERADMIN_LOG_APP_LEVEL', 'INFO')
SUPERADMIN_LOG_ROOT_LEVEL = os.environ.get('SUPERADMIN_LOG_ROOT_LEVEL', 'WARNING')
LOG_RETENTION_DAYS = int(os.environ.get('LOG_RETENTION_DAYS', '14'))
LOG_MAX_ROWS = int(os.environ.get('LOG_MAX_ROWS', '10000'))

_SUPERADMIN_APP_LOGGERS = ('pickem_api', 'pickem_homepage', 'pickem_superadmin')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
        'superadmin_db': {'class': 'pickem_superadmin.logging.DatabaseLogHandler'},
    },
    'root': {
        'handlers': ['console', 'superadmin_db'],
        'level': SUPERADMIN_LOG_ROOT_LEVEL,
    },
    'loggers': {
        name: {
            'handlers': ['console', 'superadmin_db'],
            'level': SUPERADMIN_LOG_APP_LEVEL,
            'propagate': False,
        }
        for name in _SUPERADMIN_APP_LOGGERS
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs.LoggingWiringTests -v2`
Expected: PASS (3 tests).

- [ ] **Step 5: Full suite sanity check (logging is global now)**

Run: `cd pickem && python manage.py test pickem_superadmin -v2`
Expected: PASS. (If unrelated tests slow noticeably from log-row writes, that is expected and acceptable for this suite size.)

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem/settings.py pickem/pickem_superadmin/tests/test_logs.py
git commit -m "feat(superadmin): route app logs to the DB handler (INFO app / WARNING root)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 13: Logs console page

**Files:**
- Create: `pickem/pickem_superadmin/views/logs.py`
- Modify: `pickem/pickem_superadmin/views/__init__.py` (re-export)
- Modify: `pickem/pickem_superadmin/urls.py` (route)
- Modify: `pickem/pickem_superadmin/tests/test_auth.py` (register GET URL)
- Modify: `pickem/pickem_superadmin/templates/superadmin/base.html` (nav tab)
- Create: `pickem/pickem_superadmin/templates/superadmin/logs.html`
- Test: `pickem/pickem_superadmin/tests/test_logs.py` (add view cases)

**Interfaces:**
- Consumes: `SuperAdminLogEntry`.
- Produces: URL `superadmin:logs` (GET) rendering `superadmin/logs.html` with a paginated, filtered queryset.

- [ ] **Step 1: Write the failing tests**

Add to `pickem/pickem_superadmin/tests/test_logs.py`:

```python
import logging

from django.contrib.auth.models import User
from django.urls import reverse

from pickem_superadmin.models import SuperAdminLogEntry


class LogsViewTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.client.force_login(self.root)
        SuperAdminLogEntry.objects.create(level='INFO', level_no=logging.INFO,
                                          logger_name='pickem_api.a', message='info-row')
        SuperAdminLogEntry.objects.create(level='ERROR', level_no=logging.ERROR,
                                          logger_name='pickem_api.b', message='error-row')

    def test_page_renders(self):
        response = self.client.get(reverse('superadmin:logs'))
        self.assertEqual(response.status_code, 200)

    def test_level_filter_limits_rows(self):
        response = self.client.get(reverse('superadmin:logs'), {'level': str(logging.ERROR)})
        messages = [e.message for e in response.context['page_obj']]
        self.assertIn('error-row', messages)
        self.assertNotIn('info-row', messages)

    def test_text_search_filters_message(self):
        response = self.client.get(reverse('superadmin:logs'), {'q': 'error-row'})
        messages = [e.message for e in response.context['page_obj']]
        self.assertEqual(messages, ['error-row'])

    def test_logger_filter(self):
        response = self.client.get(reverse('superadmin:logs'), {'logger': 'pickem_api.b'})
        messages = [e.message for e in response.context['page_obj']]
        self.assertEqual(messages, ['error-row'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs.LogsViewTests -v2`
Expected: FAIL — `NoReverseMatch: 'logs'`.

- [ ] **Step 3: Implement the view**

Create `pickem/pickem_superadmin/views/logs.py`:

```python
from django.core.paginator import Paginator
from django.shortcuts import render

from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminLogEntry

LOGS_PER_PAGE = 50


@superadmin_required
def logs(request):
    entries = SuperAdminLogEntry.objects.all()

    level = request.GET.get('level', '').strip()
    if level:
        try:
            entries = entries.filter(level_no__gte=int(level))
        except ValueError:
            pass

    logger_name = request.GET.get('logger', '').strip()
    if logger_name:
        entries = entries.filter(logger_name__icontains=logger_name)

    query = request.GET.get('q', '').strip()
    if query:
        entries = entries.filter(message__icontains=query)

    page_obj = Paginator(entries, LOGS_PER_PAGE).get_page(request.GET.get('page'))

    return render(request, 'superadmin/logs.html', {
        'page_obj': page_obj,
        'levels': SuperAdminLogEntry.LEVELS,
        'level_filter': level,
        'logger_filter': logger_name,
        'q': query,
    })
```

- [ ] **Step 4: Re-export + route + auth coverage**

In `pickem/pickem_superadmin/views/__init__.py` add:

```python
from pickem_superadmin.views.logs import logs
```

and add `'logs'` to its `__all__` list.

In `pickem/pickem_superadmin/urls.py`:

```python
    path('logs/', views.logs, name='logs'),
```

In `pickem/pickem_superadmin/tests/test_auth.py`, add to `SUPERADMIN_URLS`:

```python
    'superadmin:logs',
```

- [ ] **Step 5: Add the nav tab**

In `pickem/pickem_superadmin/templates/superadmin/base.html`, add after the `audit` tab:

```html
      {% url 'superadmin:logs' as u_logs %}
      <a href="{{ u_logs }}" class="sa-tab {% if '/logs' in request.path %}sa-tab-active{% endif %}">logs</a>
```

- [ ] **Step 6: Create the template**

Create `pickem/pickem_superadmin/templates/superadmin/logs.html`:

```html
{% extends 'superadmin/base.html' %}
{% block title %}logs{% endblock %}
{% block eyebrow %}observability{% endblock %}
{% block heading %}Logs{% endblock %}
{% block content %}
  <form method="get" class="mb-3 flex flex-wrap items-center gap-2">
    <select name="level" class="sa-select">
      <option value="">all levels</option>
      {% for lvl in levels %}
        <option value="{{ lvl|level_no }}" {% if level_filter == lvl|level_no|stringformat:'s' %}selected{% endif %}>{{ lvl }}+</option>
      {% endfor %}
    </select>
    <input type="text" name="logger" value="{{ logger_filter }}" placeholder="logger contains…" class="sa-input">
    <input type="text" name="q" value="{{ q }}" placeholder="search message…" class="sa-input">
    <button type="submit" class="sa-btn sa-btn-default sa-btn-sm">Filter</button>
  </form>

  <div class="sa-table-wrap sa-table-scroll">
    <table class="sa-table">
      <thead>
        <tr><th>time</th><th>level</th><th>logger</th><th>message</th></tr>
      </thead>
      <tbody>
        {% for entry in page_obj %}
          <tr>
            <td class="sa-mono text-[#667085] whitespace-nowrap">{{ entry.timestamp|date:"m-d H:i:s" }}</td>
            <td>
              {% if entry.level == 'ERROR' or entry.level == 'CRITICAL' %}<span class="sa-pill sa-pill-bad">{{ entry.level }}</span>
              {% elif entry.level == 'WARNING' %}<span class="sa-pill sa-pill-warn">{{ entry.level }}</span>
              {% else %}<span class="sa-pill sa-pill-muted">{{ entry.level }}</span>{% endif %}
            </td>
            <td class="sa-mono text-[#667085] whitespace-nowrap">{{ entry.logger_name }}</td>
            <td>
              <div>{{ entry.message }}</div>
              {% if entry.traceback %}<details class="mt-1"><summary class="sa-link cursor-pointer text-[12px]">traceback</summary><pre class="sa-changes whitespace-pre-wrap">{{ entry.traceback }}</pre></details>{% endif %}
            </td>
          </tr>
        {% empty %}
          <tr><td colspan="4" class="sa-empty">No log entries match.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% include 'superadmin/_pagination.html' with page_obj=page_obj %}
{% endblock %}
```

Add a `level_no` filter (maps a level name to its numeric value for the dropdown) to `pickem/pickem_superadmin/templatetags/sa_extras.py`:

```python
import logging


@register.filter
def level_no(level_name):
    return getattr(logging, level_name, 0)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs pickem_superadmin.tests.test_auth -v2`
Expected: PASS.

- [ ] **Step 8: Verify in the browser**

Load `http://localhost:8000/superadmin/logs/`; confirm rows render, the level dropdown filters, and text search works.

- [ ] **Step 9: Commit**

```bash
git add pickem/pickem_superadmin/
git commit -m "feat(superadmin): logs console page with level/logger/text filters

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 14: Log rotation — `prune_superadmin_logs` + daily job

**Files:**
- Create: `pickem/pickem_superadmin/management/__init__.py`, `pickem/pickem_superadmin/management/commands/__init__.py`
- Create: `pickem/pickem_superadmin/management/commands/prune_superadmin_logs.py`
- Modify: `pickem/pickem_superadmin/jobs.py` (`QUEUEABLE_COMMANDS`)
- Modify: `pickem/pickem_api/scheduler.py` (`start()` registers the daily prune job)
- Test: `pickem/pickem_superadmin/tests/test_logs.py` (add prune cases)

**Interfaces:**
- Consumes: `SuperAdminLogEntry`, settings `LOG_RETENTION_DAYS` / `LOG_MAX_ROWS`.
- Produces: management command `prune_superadmin_logs`; scheduler job id `prune_superadmin_logs`.

- [ ] **Step 1: Write the failing tests**

Add to `pickem/pickem_superadmin/tests/test_logs.py`:

```python
import logging

from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from pickem_superadmin.models import SuperAdminLogEntry


class PruneLogsTests(TestCase):
    @override_settings(LOG_RETENTION_DAYS=14, LOG_MAX_ROWS=100000)
    def test_prunes_rows_older_than_retention(self):
        old = SuperAdminLogEntry.objects.create(level='INFO', level_no=20, message='old')
        SuperAdminLogEntry.objects.filter(pk=old.pk).update(
            timestamp=timezone.now() - timedelta(days=30),
        )
        SuperAdminLogEntry.objects.create(level='INFO', level_no=20, message='fresh')
        call_command('prune_superadmin_logs')
        remaining = list(SuperAdminLogEntry.objects.values_list('message', flat=True))
        self.assertEqual(remaining, ['fresh'])

    @override_settings(LOG_RETENTION_DAYS=3650, LOG_MAX_ROWS=5)
    def test_trims_to_row_cap_keeping_newest(self):
        for i in range(9):
            SuperAdminLogEntry.objects.create(level='INFO', level_no=20, message=f'm{i}')
        call_command('prune_superadmin_logs')
        self.assertEqual(SuperAdminLogEntry.objects.count(), 5)
        # Newest kept (m8..m4), oldest (m0..m3) removed.
        self.assertTrue(SuperAdminLogEntry.objects.filter(message='m8').exists())
        self.assertFalse(SuperAdminLogEntry.objects.filter(message='m0').exists())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs.PruneLogsTests -v2`
Expected: FAIL — `CommandError: Unknown command: 'prune_superadmin_logs'`.

- [ ] **Step 3: Create the command package + command**

Create empty `pickem/pickem_superadmin/management/__init__.py` and `pickem/pickem_superadmin/management/commands/__init__.py`.

Create `pickem/pickem_superadmin/management/commands/prune_superadmin_logs.py`:

```python
"""Age out SuperAdminLogEntry rows: delete anything older than LOG_RETENTION_DAYS,
then trim to the newest LOG_MAX_ROWS. Queueable from the jobs page and registered
as a daily scheduler job."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from pickem_superadmin.models import SuperAdminLogEntry


class Command(BaseCommand):
    help = 'Delete old/excess superadmin log entries.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.LOG_RETENTION_DAYS)
        by_age, _ = SuperAdminLogEntry.objects.filter(timestamp__lt=cutoff).delete()

        by_cap = 0
        max_rows = settings.LOG_MAX_ROWS
        total = SuperAdminLogEntry.objects.count()
        if total > max_rows:
            overflow_ids = list(
                SuperAdminLogEntry.objects.order_by('-timestamp')
                .values_list('id', flat=True)[max_rows:]
            )
            by_cap, _ = SuperAdminLogEntry.objects.filter(id__in=overflow_ids).delete()

        self.stdout.write(f'Pruned {by_age} by age, {by_cap} by row cap.')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs.PruneLogsTests -v2`
Expected: PASS (2 tests).

- [ ] **Step 5: Make it queueable + registered daily**

In `pickem/pickem_superadmin/jobs.py`, add to `QUEUEABLE_COMMANDS`:

```python
    'prune_superadmin_logs',
```

In `pickem/pickem_api/scheduler.py`, add a job target and register it in `start()`:

```python
def run_prune_logs():
    """Job target: age out captured log rows."""
    call_command('prune_superadmin_logs')
```

In `start()`, after the registry-job loop and before adding listeners:

```python
    scheduler.add_job(
        run_prune_logs,
        trigger=IntervalTrigger(hours=24),
        id='prune_superadmin_logs',
        name='Prune superadmin logs',
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
```

(This job is intentionally NOT in `JOB_REGISTRY`, so it is not editable from the console — it is fixed-cadence maintenance.)

- [ ] **Step 6: Run the relevant suites**

Run: `cd pickem && python manage.py test pickem_superadmin.tests.test_logs pickem_superadmin.tests.test_jobs -v2`
Expected: PASS. (`prune_superadmin_logs` is now a valid queueable command; existing `test_jobs` queue tests still pass.)

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_superadmin/management/ pickem/pickem_superadmin/jobs.py pickem/pickem_api/scheduler.py pickem/pickem_superadmin/tests/test_logs.py
git commit -m "feat(superadmin): prune_superadmin_logs command + daily rotation job

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 15: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire superadmin suite**

Run: `cd pickem && python manage.py test pickem_superadmin -v2`
Expected: PASS, including `test_auth.test_all_urls_are_covered` (proves `jobs_schedule_save`, `jobs_status`, and `logs` are all gated and registered).

- [ ] **Step 2: Run the whole project test suite**

Run: `cd pickem && python manage.py test -v1`
Expected: PASS (no regressions in other apps from the new `LOGGING` config or model changes).

- [ ] **Step 3: Confirm migrations are complete and consistent**

Run: `cd pickem && python manage.py makemigrations --check --dry-run`
Expected: "No changes detected" (all model changes have migrations committed).

- [ ] **Step 4: Browser smoke test at desktop + phone widths**

With Chrome tools, load `/superadmin/`, `/superadmin/jobs/`, `/superadmin/logs/` at ~1280px and ~390px. Confirm: no body horizontal scroll on any page (Task 3 snippet), the jobs live indicator updates, the schedule editor saves, and the logs page filters.

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "test(superadmin): full-suite + browser verification fixes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review Notes (coverage map)

- **Spec Feature 1 (navbar link)** → Task 1.
- **Spec Feature 2 (off-season → stale current pools)** → Task 2.
- **Spec Feature 3 (mobile)** → Task 3.
- **Spec Feature 4 (editable schedules)** → Tasks 4, 5, 6 (model+registry, scheduler read/reschedule, console form).
- **Spec Feature 5 (live running indicator)** → Tasks 7, 8, 9 (marker model, listeners, status endpoint + poll).
- **Spec Feature 6 (logs subsystem)** → Tasks 10–14 (model, handler, LOGGING wiring, console page, prune/rotation).
- **Auth-coverage contract** → new URLs registered in Tasks 6, 9, 13; asserted green in Task 15.
- **Model-location refinement** vs spec: `ScheduledJobConfig` + `RunningJobMarker` in `pickem_api` (scheduler-owned; keeps app dependency direction correct), `SuperAdminLogEntry` in `pickem_superadmin`. Documented in the Architecture section.
