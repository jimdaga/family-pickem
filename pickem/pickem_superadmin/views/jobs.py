from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from pickem_api import scheduler as scheduler_module
from pickem_api.models import ScheduledJobConfig
from pickem_superadmin import jobs
from pickem_superadmin.audit import log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import ScheduledJobConfigForm
from pickem_superadmin.matrix import save_matrix
from pickem_superadmin.models import SuperAdminAuditLog


@superadmin_required
def jobs_page(request):
    from pickem_api.models import JobRun

    runs = Paginator(JobRun.objects.all(), 25).get_page(request.GET.get('page'))

    # One editable row per orchestrated job, in fixed pipeline (dependency)
    # order — the order itself is read-only.
    ScheduledJobConfig.seed_from_pipeline()
    configs = {c.job_id: c for c in ScheduledJobConfig.objects.all()}
    schedule_rows = []
    for job_id in scheduler_module.JOB_ORDER:
        cfg = configs.get(job_id)
        if cfg is None:
            continue
        schedule_rows.append({
            'job_id': job_id,
            'label': scheduler_module.JOB_LABELS.get(job_id, job_id),
            'config': cfg,
            'form': ScheduledJobConfigForm(instance=cfg, prefix=str(cfg.pk)),
        })

    return render(request, 'superadmin/jobs.html', {
        'runs': runs,
        'schedule_rows': schedule_rows,
        'queueable': jobs.QUEUEABLE_COMMANDS,
        'health': jobs.scheduler_health(),
    })


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


@superadmin_required
@require_POST
def jobs_queue(request):
    command = request.POST.get('command', '')

    if not jobs.scheduler_health()['alive']:
        messages.error(
            request,
            'Not queued: no live scheduler. A queued job would sit in the jobstore '
            'and never run. Check that a process has RUN_SCHEDULER=true.',
        )
        return redirect('superadmin:jobs')

    try:
        job_id = jobs.queue_command(command)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('superadmin:jobs')

    log_action(
        request,
        action=SuperAdminAuditLog.Action.JOB_QUEUED,
        target=None,
        summary=f'Queued pipeline run: {command}',
        changes={'job_id': [None, job_id]},
    )
    messages.success(
        request,
        f'Queued {command}. It runs on the scheduler within ~60s — watch the history below.',
    )
    return redirect('superadmin:jobs')


@superadmin_required
@require_POST
def jobs_schedule_save(request):
    ScheduledJobConfig.seed_from_pipeline()
    configs = list(ScheduledJobConfig.objects.all())

    def on_save(cfg, changes):
        log_action(
            request,
            action=SuperAdminAuditLog.Action.SCHEDULE_UPDATED,
            target=cfg,
            summary=f'Updated schedule for {cfg.job_id}',
            changes=changes,
        )
        # No live reschedule needed: the orchestrator tick reads ScheduledJobConfig
        # every minute, so an edit takes effect on the next tick.

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
