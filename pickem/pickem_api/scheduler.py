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

import contextvars
import functools
import logging
import traceback
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)

# How often to run the pipeline, in minutes (matches the old */1 K8s CronJob).
UPDATE_INTERVAL_MINUTES = 1
RECORDS_INTERVAL_MINUTES = 30
EMAIL_CAMPAIGN_INTERVAL_MINUTES = 15

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


# --- per-run log context -------------------------------------------------
# Set around each job run so DatabaseLogHandler can stamp run_id/job_id onto
# every log row written during the run (see pickem_superadmin.logging).
_current_run_id = contextvars.ContextVar('pickem_job_run_id', default=None)
_current_job_id = contextvars.ContextVar('pickem_job_id', default=None)


def current_log_context():
    """(run_id, job_id) for the job running in this context, or (None, None)."""
    return _current_run_id.get(), _current_job_id.get()


def _run_command_step(job_id):
    from pickem_api.log_bridge import call_command_logged

    call_command_logged(job_id, logger_name=f'django.job.{job_id}')


def _run_email_campaigns():
    from pickem_homepage.emailing import send_due_email_campaigns

    send_due_email_campaigns()


# The data pipeline in strict dependency order (games -> picks -> standings ->
# winners/rankings -> stats). Order is fixed by data dependencies and is NOT
# user-editable. Each entry: (job_id, label, default_minutes).
PIPELINE = [
    ('update_records', 'Team records', RECORDS_INTERVAL_MINUTES),
    ('update_games', 'Game scores', UPDATE_INTERVAL_MINUTES),
    ('update_missed_picks', 'Missed picks', UPDATE_INTERVAL_MINUTES),
    ('update_picks', 'Score picks', UPDATE_INTERVAL_MINUTES),
    ('update_standings', 'Standings', UPDATE_INTERVAL_MINUTES),
    ('update_weekly_winners', 'Weekly winners', UPDATE_INTERVAL_MINUTES),
    ('update_rankings', 'Rankings', UPDATE_INTERVAL_MINUTES),
    ('update_season_winners', 'Season winners', UPDATE_INTERVAL_MINUTES),
    ('generate_weekly_summaries', 'AI weekly recaps', UPDATE_INTERVAL_MINUTES),
    ('update_stats', 'User stats', 5),
]

# Standalone evaluators with no pipeline dependency; run after the pipeline in
# the same tick when due. Each: (job_id, label, default_minutes, run_callable).
STANDALONE = [
    ('send_scheduled_email_campaigns', 'Email campaigns',
     EMAIL_CAMPAIGN_INTERVAL_MINUTES, _run_email_campaigns),
]


def orchestrated_jobs():
    """Ordered (job_id, label, default_minutes, run) — pipeline steps first (in
    dependency order), then standalone evaluators."""
    jobs = [
        (jid, label, mins, functools.partial(_run_command_step, jid))
        for (jid, label, mins) in PIPELINE
    ]
    jobs += list(STANDALONE)
    return jobs


JOB_DEFAULT_MINUTES = {jid: mins for (jid, _l, mins, _r) in orchestrated_jobs()}
JOB_LABELS = {jid: label for (jid, label, _m, _r) in orchestrated_jobs()}
JOB_ORDER = [jid for (jid, _l, _m, _r) in orchestrated_jobs()]
_RUN_BY_ID = {jid: run for (jid, _l, _m, run) in orchestrated_jobs()}


def run_job_once(job_id, run=None):
    """Execute one orchestrated job now: record a JobRun, set the per-run log
    context, run it, update markers + last_run_at. A failure is captured on the
    JobRun and never propagates (one bad step must not abort the tick)."""
    from django.utils import timezone
    from pickem_api.models import JobRun, ScheduledJobConfig

    if run is None:
        run = _RUN_BY_ID.get(job_id) or functools.partial(_run_command_step, job_id)

    job_run = JobRun.objects.create(job_id=job_id, started_at=timezone.now())
    token_run = _current_run_id.set(job_run.run_id)
    token_job = _current_job_id.set(job_id)
    mark_job_started(job_id)
    status = JobRun.Status.SUCCESS
    exc_text = None
    try:
        run()
    except Exception:
        status = JobRun.Status.ERROR
        exc_text = traceback.format_exc()
        logging.getLogger(f'django.job.{job_id}').exception('Job %s failed', job_id)
    finally:
        finished = timezone.now()
        JobRun.objects.filter(pk=job_run.pk).update(
            finished_at=finished,
            status=status,
            duration_ms=int((finished - job_run.started_at).total_seconds() * 1000),
            exception=exc_text,
        )
        ScheduledJobConfig.objects.filter(job_id=job_id).update(last_run_at=finished)
        mark_job_finished(job_id)
        _current_job_id.reset(token_job)
        _current_run_id.reset(token_run)
    return job_run


def run_pipeline_tick():
    """The single orchestrator job (every minute). Runs each enabled, due job in
    dependency order — sequentially, so steps never overlap or run out of order.
    max_instances=1 means a slow tick just delays the next one."""
    from django.utils import timezone
    from pickem_api.models import ScheduledJobConfig

    ScheduledJobConfig.seed_from_pipeline()
    configs = {c.job_id: c for c in ScheduledJobConfig.objects.all()}
    now = timezone.now()
    for job_id, _label, _mins, run in orchestrated_jobs():
        cfg = configs.get(job_id)
        if cfg is None or not cfg.enabled or not cfg.is_due(now):
            continue
        run_job_once(job_id, run)


def run_prune_logs():
    """Job target: age out captured log rows and old job-run records."""
    from django.utils import timezone
    from pickem_api.models import JobRun

    call_command('prune_superadmin_logs')
    cutoff = timezone.now() - timedelta(days=getattr(settings, 'LOG_RETENTION_DAYS', 14))
    JobRun.objects.filter(started_at__lt=cutoff).delete()


def start():
    """Start the background scheduler. Idempotent within a process."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    from django_apscheduler.jobstores import DjangoJobStore
    from django_apscheduler.models import DjangoJob

    from pickem_api.models import ScheduledJobConfig

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(DjangoJobStore(), "default")

    ScheduledJobConfig.seed_from_pipeline()

    # Retire the old per-job APScheduler jobs (update_all/update_records/etc.):
    # everything now runs through the single orchestrator tick. Removing the
    # stale rows keeps the jobstore from trying to import functions that no
    # longer exist.
    DjangoJob.objects.exclude(
        id__in=('pipeline_tick', 'prune_superadmin_logs')
    ).delete()

    scheduler.add_job(
        run_pipeline_tick,
        trigger=IntervalTrigger(minutes=1),
        id='pipeline_tick',
        name='Pipeline orchestrator',
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        run_prune_logs,
        trigger=IntervalTrigger(hours=24),
        id='prune_superadmin_logs',
        name='Prune superadmin logs',
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info('APScheduler started: pipeline orchestrator tick every 1 minute')
    return scheduler
