# Per-step jobs, per-run logs, and email edit — design

**Date:** 2026-07-17
**Apps:** `pickem_api` (scheduler, models), `pickem_superadmin` (jobs/logs/email pages, log handler)
**Status:** Approved design (user confirmed the key fork), pre-implementation

## Motivation (user feedback)

1. `/superadmin/email/` "Current status" should have an **Edit** button to edit current values, API key masked/never exposed.
2. Retire the `update_all` umbrella job — register **each pipeline step individually** with its own cadence/enable rules.
3. Logs should carry a **unique key per job + per run** so the jobs page can link each run to its logs.
4. The jobs **status endpoint** must reflect the per-step model.

## Key decision (confirmed with user)

The 9 pipeline steps have **hard data dependencies** (`update_records` → `update_games` → `update_missed_picks` → `update_picks` → `update_standings` → `update_weekly_winners`/`update_rankings`/`update_season_winners` → `update_stats`). So:

- **Order is fixed by code**, shown read-only on the page. **No user reordering** (it would corrupt scoring).
- Per-step controls are **cadence (interval) + enable/disable** only.
- Execution stays a **single coordinated ordered pass** (one APScheduler orchestrator job, `max_instances=1`, `coalesce=True`) so steps never run out of order or concurrently. On each tick, each enabled step runs **only when its own interval is due**.

## Architecture

### Scheduler (`pickem_api/scheduler.py`)

- Replace `JOB_REGISTRY` (`update_all`, `update_records`) with `PIPELINE_STEPS`: the ordered list of the 9 step command names, each with a `default_minutes` (records 30, stats 5, rest 1) and a display label.
- Retire `run_update_all`/`run_update_records`. Add **`run_pipeline_tick()`** — the single orchestrator job, registered on a 1-minute `IntervalTrigger`, `max_instances=1`, `coalesce=True`. It:
  1. `ScheduledJobConfig.seed_from_pipeline()` (one row per step; `update_records`/`update_stats` get their defaults).
  2. Iterates `PIPELINE_STEPS` **in order**. For each step whose config is `enabled` and **due** (`last_run_at is None or now - last_run_at >= interval_minutes`):
     - Create a `JobRun` (uuid `run_id`, `job_id=step`, `started_at`).
     - Set a context (`run_id`, `job_id`) via `contextvars` so the log handler stamps rows (see Logging).
     - `mark_job_started(step)`, run the step command via `call_command_logged(step, logger_name=f'django.job.{step}')`, capturing stdout/stderr into the per-step logger.
     - On finish: set `JobRun.finished_at`, `status` (success/error), `duration_ms`, `exception`; update `ScheduledJobConfig.last_run_at`; `mark_job_finished(step)`; clear the context.
  - A step's failure is logged and does NOT stop later steps (same tolerance as today's `update_all`).
- Keep the daily `prune_superadmin_logs` job (unchanged) and add a companion `prune_job_runs` (age out `JobRun` rows, mirroring log retention).
- `reschedule_live` is no longer per-APScheduler-job (there's one orchestrator); schedule edits just write `ScheduledJobConfig` and the next tick honors them — so `reschedule_live` becomes a no-op/removed and the jobs-save view no longer calls it.

### Models

- **`ScheduledJobConfig`** (`pickem_api`): add `last_run_at` (nullable DateTime). `job_id` now holds a step name. Replace `seed_from_registry` with `seed_from_pipeline` seeding one row per `PIPELINE_STEPS` entry (get_or_create; preserves edits). A `display_label` lookup comes from `PIPELINE_STEPS`.
- **`JobRun`** (`pickem_api`, new): `run_id` (UUIDField, unique, db_index), `job_id` (CharField, db_index), `started_at`, `finished_at` (null), `status` (choices: running/success/error, default running), `duration_ms` (null), `exception` (TextField, null). Ordering `-started_at`. Migration.
- **`SuperAdminLogEntry`** (`pickem_superadmin`): add `run_id` (UUIDField, null, db_index) and `job_id` (CharField, null, db_index). Migration.
- **`RunningJobMarker`**: unchanged shape; now written per step by the orchestrator (already keyed on `job_id`).

### Logging (`pickem_superadmin/logging.py`, `pickem_api/log_bridge.py`)

- `log_bridge.py`: a module-level `contextvars.ContextVar` pair (`_current_run_id`, `_current_job_id`). `call_command_logged(command, *, logger_name=None)` gains an optional per-step `logger_name` (default keeps `pickem_api.pipeline` for ad-hoc/manual). The orchestrator sets the contextvars around each step; the stdout `LoggerWriter` emits under `django.job.<step>`.
- `DatabaseLogHandler.emit`: read the contextvars and set `run_id`/`job_id` on the `SuperAdminLogEntry` it writes. So EVERY log line during a step run (the stdout bridge AND the command's own `pickem_api.*` warnings) is stamped with the run.
- `settings.LOGGING`: add `django.job` to the captured loggers at `SUPERADMIN_LOG_APP_LEVEL` (INFO) with the DB handler, `propagate: False`. (Root stays WARNING; `django.job.*` must be explicitly captured or it'd fall to root.)

### Jobs page (`pickem_superadmin/views/jobs.py`, `templates/superadmin/jobs.html`)

- "Registered jobs"/"Schedules" become one **per-step table**: step label (read-only, in pipeline order), interval input, enabled toggle, last run. Saved through the existing `save_matrix` pattern (now over all step rows). `jobs_schedule_save` audits + writes configs (no `reschedule_live`).
- "Run history" reads **`JobRun`** (not `DjangoJobExecution`): per-step rows with status/duration/exception, each with a **"logs" link → `/superadmin/logs/?run_id=<uuid>`**.
- The manual "Queue a run" keeps working but queues an individual step (allowlist = `PIPELINE_STEPS` names + existing `QUEUEABLE_COMMANDS` extras).

### Status endpoint (`jobs_status`)

- Returns `running` from per-step `RunningJobMarker`s (already keyed by job_id) + `health`. The health check adapts to the orchestrator (a recent `JobRun` or a scheduled orchestrator tick = alive). The jobs page poll shows the live step label.

### Logs page (`pickem_superadmin/views/logs.py`, `templates/superadmin/logs.html`)

- Add a **`run_id`** filter (exact) and a **`job`** filter (`job_id` icontains), plus a `job`/`run` column. A `?run_id=<uuid>` deep-link shows exactly that run's lines.

### Email edit (`templates/superadmin/email.html`)

- "Current status" card gets an **Edit** button that reveals the pre-filled provider form (JS show/hide; the form already exists and pre-fills via the ModelForm instance). API key stays masked in status and blank-to-keep in the form (write-only field; never rendered with the real value). No view change needed beyond the toggle.

## Testing (correctness-critical — this drives live scoring)

- Orchestrator: steps run in dependency order; a step runs only when due (interval respected via `last_run_at`); disabled steps skip; a failing step doesn't stop later steps; `JobRun` + `last_run_at` recorded; `RunningJobMarker` set/cleared per step. (Unit-test the tick logic without a live scheduler thread.)
- Logging: a step run stamps `run_id`/`job_id` on log rows (handler reads contextvars); `django.job.<step>` captured at INFO; `run_id` filter on the logs page returns exactly that run.
- Jobs page: per-step schedule editor saves + audits; run-history links carry the run_id; auth-coverage for any new/changed URL.
- Status endpoint: reports the running step.
- Email: Edit toggle present; key never in the rendered form value.

## Migration / rollout notes

- `ScheduledJobConfig` rows for old `update_all`/`update_records` become the new per-step rows via `seed_from_pipeline` (old `update_all` row is ignored/removed). `update_records`'s 30-min cadence is preserved as its step default.
- New migrations: `pickem_api` (ScheduledJobConfig.last_run_at, JobRun), `pickem_superadmin` (SuperAdminLogEntry.run_id/job_id). Prod applies via the initContainer.
- No data destruction; historical `DjangoJobExecution` rows remain (superseded by `JobRun` going forward).

## Out of scope

- User-defined step ordering (fixed by dependencies).
- Cron-expression schedules (interval-minutes only, consistent with the existing editor).
