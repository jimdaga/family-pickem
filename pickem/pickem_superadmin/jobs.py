"""Queueing pipeline runs.

We do NOT run commands in the web request: update_games makes ESPN calls and
update_all chains the whole pipeline, so either could outlive a gunicorn worker
timeout, and a browser refresh would fire it twice.

Instead we write a one-off job into the APScheduler DjangoJobStore, which is the
database. The scheduler process (the one with RUN_SCHEDULER=true) picks it up on
its next wakeup — at most ~60s away, since update_all already runs every minute —
and django-apscheduler records the execution, so run history needs no new code.

The tradeoff is real: the job is enqueued, not instant. The UI says so.
"""
import time
from datetime import timedelta

from django.utils import timezone

# Allowlist. A POST body must never be able to name an arbitrary management
# command — that would be remote command execution with a superuser session.
QUEUEABLE_COMMANDS = (
    'update_all',
    'update_games',
    'update_picks',
    'update_standings',
    'update_stats',
    'update_records',
    'update_weekly_winners',
    'update_season_winners',
    'update_missed_picks',
    'update_rankings',
    'prune_superadmin_logs',
)

# If the scheduler has not executed anything in this long, treat it as dead.
# update_all runs every minute, so 5 minutes of silence is unambiguous.
STALE_AFTER = timedelta(minutes=5)


def run_command(command_name):
    """APScheduler job target. Must be importable at module level."""
    if command_name not in QUEUEABLE_COMMANDS:
        raise ValueError(f'Command not allowed: {command_name}')
    # Run it through the orchestrator's per-run machinery so a hand-queued run
    # gets a JobRun record, a run_id, and per-step logging — exactly like the
    # scheduled tick.
    from pickem_api.scheduler import run_job_once

    run_job_once(command_name)


def get_scheduler():
    """The live scheduler in this process, if this process IS the scheduler
    process (RUN_SCHEDULER=true), else None.

    On a plain web worker there is no running scheduler in-process, so callers
    must fall back to a short-lived scheduler of their own -- see
    ``queue_command`` for why that fallback has to be started (paused) rather
    than left in the default stopped state.
    """
    from pickem_api import scheduler as scheduler_module

    return scheduler_module._scheduler


def _add_job_via_fallback_scheduler(command_name, job_id):
    """Persist a one-off job from a plain web worker, with no live in-process
    scheduler to hand it to.

    APScheduler only writes to the jobstore from ``add_job()`` when the
    scheduler is not in ``STATE_STOPPED`` -- a freshly constructed
    ``BackgroundScheduler`` that is never ``.start()``-ed stays stopped
    forever, so ``add_job()`` silently just appends to an in-memory
    ``_pending_jobs`` list on an object that is garbage-collected the moment
    this function returns. Zero rows would ever reach the database.

    Starting the scheduler in PAUSED mode moves it to ``STATE_PAUSED``, which
    is enough for ``add_job()`` to take the real persist path
    (``_real_add_job`` -> ``store.add_job``), while guaranteeing it never
    executes anything (a paused scheduler never processes the jobstore). We
    then shut it down immediately -- that only stops our throwaway thread; the
    row already written to the persistent DjangoJobStore remains.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from django.conf import settings
    from django_apscheduler.jobstores import DjangoJobStore

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(DjangoJobStore(), 'default')
    scheduler.start(paused=True)
    try:
        scheduler.add_job(**_one_off_job_kwargs(command_name, job_id))
    finally:
        scheduler.shutdown(wait=False)


def _one_off_job_kwargs(command_name, job_id):
    return dict(
        func=run_command,
        trigger='date',
        run_date=timezone.now(),
        id=job_id,
        name=f'Manual run: {command_name}',
        args=[command_name],
        max_instances=1,
        replace_existing=True,
    )


def queue_command(command_name):
    """Enqueue a one-off run. Returns the job id."""
    if command_name not in QUEUEABLE_COMMANDS:
        raise ValueError(f'Command not allowed: {command_name}')

    job_id = f'manual:{command_name}:{int(time.time())}'

    live_scheduler = get_scheduler()
    if live_scheduler is not None:
        # This process IS the scheduler process: it's already STATE_RUNNING,
        # so add_job() persists immediately through the normal running path.
        live_scheduler.add_job(**_one_off_job_kwargs(command_name, job_id))
    else:
        _add_job_via_fallback_scheduler(command_name, job_id)

    return job_id


def _scheduler_is_scheduling():
    """A running scheduler keeps a registered job's next_run_time in the future.
    On a fresh deploy (or after execution-history cleanup) there are no
    executions yet, but a live scheduler has already registered its jobs — so
    this lets the console recognize it and allow the first manual run, instead
    of hard-blocking on empty history.
    """
    from django_apscheduler.models import DjangoJob

    upcoming = DjangoJob.objects.filter(next_run_time__gte=timezone.now()).exists()
    return upcoming


def scheduler_health():
    """Is the orchestrator alive? A live scheduler always keeps the `pipeline_tick`
    job registered with a future next_run_time; a recent JobRun confirms it is
    actually executing. A dead scheduler leaves a stale (past) next_run_time and
    no recent runs, so it reads as not alive.
    """
    from pickem_api.models import JobRun

    last = JobRun.objects.order_by('-started_at').first()
    scheduling = _scheduler_is_scheduling()
    recent = last is not None and (timezone.now() - last.started_at) <= STALE_AFTER
    alive = scheduling or recent
    return {
        'alive': alive,
        'last_run': last.started_at if last else None,
        'last_status': last.status if last else None,
        'stale': not alive,
    }
