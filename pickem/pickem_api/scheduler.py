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

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)

# How often to run the pipeline, in minutes (matches the old */1 K8s CronJob).
UPDATE_INTERVAL_MINUTES = 1
RECORDS_INTERVAL_MINUTES = 30

_scheduler = None


def run_update_all():
    """Job target: run the full data-update pipeline."""
    call_command("update_all", skip_records=True)


def run_update_records():
    """Job target: refresh team records on a slower cadence."""
    call_command("update_records")


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


def start():
    """Start the background scheduler. Idempotent within a process."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    from django_apscheduler.jobstores import DjangoJobStore

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(DjangoJobStore(), "default")
    scheduler.add_job(
        run_update_all,
        trigger=IntervalTrigger(minutes=UPDATE_INTERVAL_MINUTES),
        id="update_all",
        name="Run full data-update pipeline",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        run_update_records,
        trigger=IntervalTrigger(minutes=RECORDS_INTERVAL_MINUTES),
        id="update_records",
        name="Run team records refresh",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "APScheduler started: update_all every %s minute(s)", UPDATE_INTERVAL_MINUTES
    )
    return scheduler
