from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from pickem_superadmin import jobs
from pickem_superadmin.audit import log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminAuditLog


@superadmin_required
def jobs_page(request):
    from django_apscheduler.models import DjangoJob, DjangoJobExecution

    executions = Paginator(
        DjangoJobExecution.objects.select_related('job').order_by('-run_time'), 25,
    ).get_page(request.GET.get('page'))

    return render(request, 'superadmin/jobs.html', {
        'registered_jobs': DjangoJob.objects.all().order_by('id'),
        'executions': executions,
        'queueable': jobs.QUEUEABLE_COMMANDS,
        'health': jobs.scheduler_health(),
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
