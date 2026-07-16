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
    from django_apscheduler.models import DjangoJob, DjangoJobExecution

    executions = Paginator(
        DjangoJobExecution.objects.select_related('job').order_by('-run_time'), 25,
    ).get_page(request.GET.get('page'))

    schedule_configs = ScheduledJobConfig.objects.all()

    return render(request, 'superadmin/jobs.html', {
        'registered_jobs': DjangoJob.objects.all().order_by('id'),
        'executions': executions,
        'queueable': jobs.QUEUEABLE_COMMANDS,
        'health': jobs.scheduler_health(),
        'schedule_configs': schedule_configs,
        'schedule_forms': {
            c.pk: ScheduledJobConfigForm(instance=c, prefix=str(c.pk))
            for c in schedule_configs
        },
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
