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
    """The live scheduler in this process, or a jobstore-only scheduler that can
    still write to the shared DjangoJobStore from a web worker."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from django.conf import settings
    from django_apscheduler.jobstores import DjangoJobStore

    from pickem_api import scheduler as scheduler_module

    if scheduler_module._scheduler is not None:
        return scheduler_module._scheduler

    # This process has no running scheduler (a plain web worker). Build one just
    # to reach the jobstore; we never .start() it, so it only writes the row.
    writer = BackgroundScheduler(timezone=settings.TIME_ZONE)
    writer.add_jobstore(DjangoJobStore(), 'default')
    return writer


def queue_command(command_name):
    """Enqueue a one-off run. Returns the job id."""
    if command_name not in QUEUEABLE_COMMANDS:
        raise ValueError(f'Command not allowed: {command_name}')

    job_id = f'manual:{command_name}:{int(time.time())}'
    get_scheduler().add_job(
        run_command,
        trigger='date',
        run_date=timezone.now(),
        id=job_id,
        name=f'Manual run: {command_name}',
        args=[command_name],
        max_instances=1,
        replace_existing=True,
    )
    return job_id


def scheduler_health():
    """Is anything actually executing jobs? A queued job on a dead scheduler sits
    in the jobstore forever, so the console must be able to tell."""
    from django_apscheduler.models import DjangoJobExecution

    last = DjangoJobExecution.objects.order_by('-run_time').first()
    if last is None:
        return {'alive': False, 'last_run': None, 'last_status': None, 'stale': True}

    stale = (timezone.now() - last.run_time) > STALE_AFTER
    return {
        'alive': not stale,
        'last_run': last.run_time,
        'last_status': last.status,
        'stale': stale,
    }
