from django.core.paginator import Paginator
from django.shortcuts import render

from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminLogEntry

LOGS_PER_PAGE = 50


@superadmin_required
def logs(request):
    entries = SuperAdminLogEntry.objects.all()

    level = request.GET.get('level', '').strip()
    if level:
        try:
            entries = entries.filter(level_no__gte=int(level))
        except ValueError:
            pass

    logger_name = request.GET.get('logger', '').strip()
    if logger_name:
        entries = entries.filter(logger_name__icontains=logger_name)

    query = request.GET.get('q', '').strip()
    if query:
        entries = entries.filter(message__icontains=query)

    job = request.GET.get('job', '').strip()
    if job:
        entries = entries.filter(job_id__icontains=job)

    # Deep-linked from the jobs page: show exactly one run's log lines.
    run_id = request.GET.get('run_id', '').strip()
    if run_id:
        import uuid as _uuid
        try:
            entries = entries.filter(run_id=_uuid.UUID(run_id))
        except (ValueError, TypeError):
            entries = entries.none()

    page_obj = Paginator(entries, LOGS_PER_PAGE).get_page(request.GET.get('page'))

    return render(request, 'superadmin/logs.html', {
        'page_obj': page_obj,
        'levels': SuperAdminLogEntry.LEVELS,
        'level_filter': level,
        'logger_filter': logger_name,
        'q': query,
        'job_filter': job,
        'run_id_filter': run_id,
    })
