# Superadmin console: observability & control — design

**Date:** 2026-07-15
**App:** `pickem_superadmin` (+ `pickem_api/scheduler.py`, `pickem/settings.py`, `pickem_homepage/templates/pickem/base.html`)
**Status:** Approved design, pre-implementation

## Context

The superuser operator console at `/superadmin/` gives site-wide operator access
across every family (see CLAUDE.md → Superadmin Console). This spec covers six
independent improvements, ordered from trivial to large. Each is independently
shippable.

Key deployment facts that shape the design:

- **Single web replica** (`replicaCount: 1`) with the APScheduler running
  **in-process** on that same pod (`RUN_SCHEDULER=true`). The console, the live
  scheduler, and the data pipeline all share one pod.
- Gunicorn worker count is unspecified/may be >1, and the scheduler is guarded to
  run in exactly one worker. Therefore **any cross-request signal must live in the
  DB, not process memory** — a console request may land on a different worker than
  the scheduler.
- No `LOGGING` config exists in `settings.py` today; logging is greenfield.
- Recurring jobs are registered as `IntervalTrigger`s in code at scheduler start:
  `update_all` (1 min), `update_records` (30 min).

Cross-cutting invariants to preserve (from CLAUDE.md):

- Every superadmin write goes through `log_action()` (`audit.py`) — never
  `SuperAdminAuditLog.objects.create()` directly.
- Every new URL carries `@superadmin_required`; `tests/test_auth.py::test_all_urls_are_covered`
  fails if a URL is added without a gate test.
- Editable matrices reuse `save_matrix()` (`matrix.py`) with per-row prefixed forms
  and optimistic concurrency on `updated_at`.

---

## Feature 1 — Navbar SUPERUSER pill links to console

**File:** `pickem_homepage/templates/pickem/base.html` (~line 51).

Wrap the existing `data-testid="superuser-badge"` `<span>` in an anchor to
`{% url 'superadmin:overview' %}`. Preserve pill styling; add a hover affordance
(e.g. `hover:bg-yellow-400/25 transition-colors`) and a `title`/`aria-label`
making it clear it links to the console. No logic change.

**Test:** extend an existing `base.html`/navbar template test (or add one) asserting
the badge is wrapped in a link to the overview URL when `is_superuser`.

---

## Feature 2 — "Off-season pools" anomaly → "stale current pools"

**File:** `pickem_superadmin/views/overview.py` `_anomalies()`; template
`superadmin/overview.html`; test `tests/test_overview.py`.

**Problem:** `pools_off_season = Pool.objects.exclude(season=season)` flags every
historical pool, because pools are created per-season and old ones legitimately
persist. Pure noise after one rollover.

**New behavior — "families not on the current season":** for each family, take its
**most-recent pool** (highest `season`; tie-break by newest `id`). Flag the family
only if that latest pool's `season != current`. Historical pools are never flagged.
This catches families that never rolled a pool forward into the current season.

- Rename the anomaly key `pools_off_season` → `families_off_season`, value is a list
  of `(family, latest_pool)` (or a small dict) so the template can show family name
  + the stale season.
- Update the overview template label to "Families not on the current season" and
  render family + latest pool's `display_season`.
- Guard the empty-DB / no-current-season case (return `[]`, matching existing
  `if season else []`).

**Test:** replace the `pools_off_season` assertions with cases: (a) family whose
latest pool is current → not flagged even if it has old pools; (b) family whose
latest pool is stale → flagged; (c) no current season → empty.

---

## Feature 3 — Mobile-friendly superadmin pages

**Files:** `superadmin/base.html` + every wide-table template (`pools.html`,
`families.html`, `teams.html`, `audit.html`, `jobs.html`, `overview.html`).

**Problem:** wide editable matrices force horizontal scrolling of the whole page on
a phone.

**Approach (CSS/template only, no data/logic change):**

- Wrap every wide `<table>` in an `overflow-x-auto` container so the **table**
  scrolls horizontally inside its own box — the page body never scrolls sideways.
- Make the superadmin tab nav (`superadmin/base.html` `<nav>`) wrap (`flex-wrap`)
  and remain tappable at phone widths.
- Stack the overview stat/anomaly cards into a single column below `sm:`.
- Make the big matrices' first column sticky (`sticky left-0` + background) so row
  identity stays visible while scrolling a row horizontally.
- Ensure tap targets (buttons, toggles) meet a reasonable minimum size on mobile.

**Verification:** drive Chrome at a phone viewport (~390px) across overview, users,
pools, families, teams, jobs, audit, and confirm no horizontal page-body scroll and
that each table is usable. No automated test (visual), but must not regress existing
template tests.

---

## Feature 4 — Editable job schedules

**Files:** new model + migration in `pickem_superadmin`; `pickem_api/scheduler.py`;
new view + URL + template section on `superadmin/jobs.html`; tests.

**Goal:** tweak the cadence of the recurring jobs (`update_all`, `update_records`)
from the console — interval in minutes + enable/disable — persisted and applied to
the live scheduler.

### Model — `ScheduledJobConfig`

| field | type | notes |
|---|---|---|
| `job_id` | CharField, unique | matches the APScheduler job id (`update_all`, `update_records`) |
| `interval_minutes` | PositiveIntegerField | must be ≥ 1 (validated) |
| `enabled` | BooleanField, default True | |
| `updated_at` | DateTimeField(auto_now=True) | for `save_matrix()` optimistic concurrency |

Only the two known recurring jobs are editable. An **allowlist**
(`EDITABLE_JOBS = {'update_all': default 1, 'update_records': default 30}`) is the
source of truth for which ids may exist and their seed defaults; a POST can never
create a config for an arbitrary id.

### Scheduler reads config

`scheduler.start()` seeds missing `ScheduledJobConfig` rows from `EDITABLE_JOBS`
defaults, then registers each job using the row's `interval_minutes` (skipping
`add_job` when `enabled=False`). The hardcoded `UPDATE_INTERVAL_MINUTES` /
`RECORDS_INTERVAL_MINUTES` become the seed defaults only. `replace_existing=True`
keeps behavior across restarts.

### Console edit → live apply

The jobs page gets an editable form per row (interval number input + enabled
checkbox), saved through the existing `save_matrix()` pattern (per-row prefixed
forms, only-changed-rows saved, optimistic concurrency on `updated_at`, keyed on the
config row's own pk). New gated URL `jobs/schedule/save/`.

On save, mirror the live-vs-fallback split already in `jobs.py`:

- If `jobs.get_scheduler()` returns a **live** scheduler (this process is the
  scheduler process): call `reschedule_job(job_id, trigger=IntervalTrigger(minutes=n))`
  for enabled rows and `pause_job`/`remove_job` for disabled rows, applying the
  change immediately.
- Else (local dev / non-scheduler process): persist only; the change takes effect on
  the next scheduler start. The UI communicates which happened.

Every edit goes through `log_action()` with a before/after diff.

Validation: `interval_minutes >= 1`; reject unknown `job_id`s server-side; clamp to a
sane upper bound if desired. Invalid input re-renders with a message, no partial apply.

**Tests:** model defaults/seed; scheduler reads config (unit, without starting a real
background thread — test the registration inputs); view save applies + audits + is
gated (auth-coverage test); disabled job not registered; invalid interval rejected.

---

## Feature 5 — Live "running now" indicator

**Files:** `pickem_api/scheduler.py` (event listeners); new gated JSON view + URL;
`superadmin/jobs.html` (poll + badge); tests.

**Goal:** the jobs page shows, in near-real-time, whether a job is executing right now.

### Running marker (DB, not memory)

A small table `RunningJobMarker` (`job_id`, `started_at`) — or reuse a single-row
status table — records currently-executing jobs. DB-backed because the console
request may hit a different gunicorn worker than the scheduler.

APScheduler event listeners registered in `scheduler.start()`:

- `EVENT_JOB_SUBMITTED` → upsert a marker row (`job_id`, `started_at=now`).
- `EVENT_JOB_EXECUTED` **and** `EVENT_JOB_ERROR` → delete the marker row.

Listeners must swallow their own exceptions so a marker write can never break job
execution. Stale markers (a crash between submit and finish) are ignored by the
reader past a max age (e.g. > 10 min) so the UI can't get stuck showing "running"
forever.

### JSON status endpoint + polling

New `jobs/status.json` (`@superadmin_required`) returns:

```json
{
  "running": [{"job_id": "update_all", "started_at": "...", "seconds": 4}],
  "health": {"alive": true, "last_run": "...", "last_status": "..."}
}
```

The jobs page polls it every ~3s with `fetch` and renders a pulsing "running" badge
per active job (and reflects `health.alive`), or "Idle" when nothing is running.
Polling pauses when the tab is hidden (`visibilitychange`) to avoid needless load —
matching the re-entrancy discipline used on the scores page.

**Tests:** status endpoint auth-gated (coverage test) + returns markers; marker
insert/delete on simulated events; stale-marker filtering; JSON shape.

---

## Feature 6 — Logs subsystem

**Files:** new model + migration; `pickem_superadmin/logging.py` (handler);
`pickem/settings.py` (`LOGGING`); new gated view + URL + `superadmin/logs.html`;
new nav tab; new management command; tests.

### Storage — `SuperAdminLogEntry`

| field | type | notes |
|---|---|---|
| `timestamp` | DateTimeField(db_index=True) | record creation time |
| `level` | CharField (choices: DEBUG..CRITICAL) | |
| `level_no` | PositiveSmallIntegerField | numeric, for range filtering/index |
| `logger_name` | CharField | e.g. `pickem_api.scheduler` |
| `message` | TextField | truncated to a max length (e.g. 10k chars) |
| `traceback` | TextField, null | populated when `exc_info` present |
| `pathname` | CharField, null | |
| `lineno` | PositiveIntegerField, null | |

Indexes: `(level_no, timestamp)` and `timestamp`.

### Capture — custom `logging.Handler`

`pickem_superadmin/logging.py::DatabaseLogHandler(logging.Handler)`:

- `emit(record)` builds and inserts a `SuperAdminLogEntry`, formatting `exc_info`
  into `traceback`, truncating `message`.
- **Loop guard:** the handler must never log its own failures back into itself.
  Excluded loggers: `django.db.backends`, `django.db`, and the handler's own module
  logger. `emit` wraps everything and routes failures to `self.handleError(record)`
  (which must not re-emit to the DB). This prevents a DB error while writing a log
  row from recursively generating more DB-log rows.
- Guard against running before migrations exist (e.g. wrap insert; on
  `Operational/ProgrammingError` for a missing table, silently drop).

### `LOGGING` config in `settings.py`

- Attach `DatabaseLogHandler` alongside the default console handler.
- **Capture level (confirmed):** app loggers `pickem_api`, `pickem_homepage`,
  `pickem_superadmin` at **INFO**; root/everything-else at **WARNING**.
- Level is tunable via settings constants (e.g. `SUPERADMIN_LOG_APP_LEVEL`,
  `SUPERADMIN_LOG_ROOT_LEVEL`) so it can be dialed without a code edit.
- Keep the existing implicit console output intact (still visible to `kubectl logs`).

### Console page — `superadmin/logs/`

New gated view + `logs.html` + nav tab ("logs"). Controls:

- Level filter (dropdown: All / DEBUG / INFO / WARNING / ERROR / CRITICAL — filters
  by `level_no >=`).
- Logger-name filter (text/contains).
- Free-text search over `message`.
- Time-ordered (newest first), paginated via existing `_pagination.html`.
- Color-coded level badges; expandable traceback. Mobile-friendly per Feature 3.

### Rotation / age-out

New management command `prune_superadmin_logs`:

- Delete rows older than `LOG_RETENTION_DAYS` (default 14).
- Trim to newest `LOG_MAX_ROWS` (default 10000) if exceeded.
- Both bounds from settings.

Register it two ways: (a) add to `jobs.QUEUEABLE_COMMANDS` so it can be queued
by hand from the jobs page; (b) register a **daily** APScheduler job in
`scheduler.start()` so it self-maintains. (Daily job is not user-editable in
Feature 4's allowlist — it's maintenance, fixed cadence.)

**Tests:** handler writes a row at/above threshold and drops below; loop-guard
(a `django.db.backends` record is not captured); message truncation; traceback
capture on `exc_info`; missing-table safety; logs view auth-gated (coverage test)
+ filters (level/logger/search); `prune_superadmin_logs` deletes by age and by
row cap.

---

## Build order

1. Feature 1 (navbar link) + Feature 2 (off-season anomaly) — quick wins.
2. Feature 3 (mobile) — CSS/template pass, verify in browser.
3. Feature 4 (editable schedules).
4. Feature 5 (live running indicator) — shares DB-marker infra mindset with #4.
5. Feature 6 (logs subsystem) — largest; model + handler + settings + page + prune.

Each feature: implement → tests (incl. auth-coverage for any new URL) → run
`python manage.py test` → verify in the running app where it has UI surface.

## Out of scope

- External log shipping (Loki/ELK) — DB table is the console's source; stdout remains
  for `kubectl logs`.
- Full cron expressions for job schedules (interval-minutes only, per decision).
- The two new TODO items (soft-delete family; richer Create Family flow) — logged in
  `TODO.md`, separate future work.
