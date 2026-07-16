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

from django.core.management import call_command
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
    call_command(command_name)


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
    """Is anything actually executing jobs? A queued job on a dead scheduler sits
    in the jobstore forever, so the console must be able to tell.

    Alive means either a recent execution OR a registered job scheduled to run
    (the fresh-deploy case). A dead scheduler leaves stale (past) next_run_times
    and no recent executions, so it still reads as not alive.
    """
    from django_apscheduler.models import DjangoJobExecution

    last = DjangoJobExecution.objects.order_by('-run_time').first()

    if last is None:
        scheduling = _scheduler_is_scheduling()
        return {
            'alive': scheduling,
            'last_run': None,
            'last_status': None,
            'stale': not scheduling,
        }

    recent = (timezone.now() - last.run_time) <= STALE_AFTER
    alive = recent or _scheduler_is_scheduling()
    return {
        'alive': alive,
        'last_run': last.run_time,
        'last_status': last.status,
        'stale': not alive,
    }
