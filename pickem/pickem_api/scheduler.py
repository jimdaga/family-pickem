"""In-process APScheduler that runs the update pipeline on an interval.

Started from ``PickemApiConfig.ready()`` only when ``RUN_SCHEDULER=true`` is
set in the environment and the actual web-server process is starting. That
guard is important: with Django's autoreloader or multiple workers, an
unguarded scheduler would start multiple times and fire duplicate jobs. Set
``RUN_SCHEDULER=true`` on exactly one process (e.g. a single-replica web
deployment or a dedicated scheduler pod).

Job state is persisted in the database via django-apscheduler's DjangoJobStore,
so ``replace_existing`` keeps a single ``update_all`` job registered across
restarts.
"""

import logging
from datetime import timedelta

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_SUBMITTED
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)

# How often to run the pipeline, in minutes (matches the old */1 K8s CronJob).
UPDATE_INTERVAL_MINUTES = 1
RECORDS_INTERVAL_MINUTES = 30

# A marker older than this is treated as a crash between submit and finish, so
# the UI never gets stuck showing "running" forever.
STALE_RUNNING_AFTER = timedelta(minutes=10)

_scheduler = None


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


def run_update_all():
    """Job target: run the full data-update pipeline."""
    from pickem_api.log_bridge import call_command_logged

    call_command_logged("update_all", skip_records=True)


def run_update_records():
    """Job target: refresh team records on a slower cadence."""
    from pickem_api.log_bridge import call_command_logged

    call_command_logged("update_records")


def run_prune_logs():
    """Job target: age out captured log rows."""
    call_command('prune_superadmin_logs')


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


def start():
    """Start the background scheduler. Idempotent within a process."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    from django_apscheduler.jobstores import DjangoJobStore

    from pickem_api.models import ScheduledJobConfig

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(DjangoJobStore(), "default")

    ScheduledJobConfig.seed_from_registry()
    for cfg in ScheduledJobConfig.objects.filter(job_id__in=JOB_REGISTRY.keys()):
        if cfg.enabled:
            _register_job(scheduler, cfg.job_id, cfg.interval_minutes)

    scheduler.add_job(
        run_prune_logs,
        trigger=IntervalTrigger(hours=24),
        id='prune_superadmin_logs',
        name='Prune superadmin logs',
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.add_listener(_on_job_submitted, EVENT_JOB_SUBMITTED)
    scheduler.add_listener(_on_job_done, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "APScheduler started: update_all every %s minute(s)", UPDATE_INTERVAL_MINUTES
    )
    return scheduler
