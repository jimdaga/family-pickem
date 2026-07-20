from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import AIProviderSettingsForm
from pickem_superadmin.models import AIProviderSettings, SuperAdminAuditLog


def _settings_snapshot(settings_obj):
    """Only audit non-secret values; API key content must never enter JSON."""
    return {
        'provider': settings_obj.provider,
        'enabled': settings_obj.enabled,
        'model': settings_obj.model,
        'timeout_seconds': settings_obj.timeout_seconds,
        'retries': settings_obj.retries,
        'max_runs_per_pool_week': settings_obj.max_runs_per_pool_week,
        'has_api_key': settings_obj.has_api_key,
    }


@sensitive_post_parameters('api_key')
@superadmin_required
@require_http_methods(['GET', 'POST'])
def ai_settings(request):
    # Do not create a disabled row merely by viewing this page: until an
    # administrator explicitly saves, existing environment bootstrap settings
    # remain in effect.
    settings_obj = AIProviderSettings.current() or AIProviderSettings()
    before = _settings_snapshot(settings_obj)

    if request.method == 'POST':
        form = AIProviderSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            settings_obj = form.save(commit=False)
            raw_api_key = (form.cleaned_data.get('api_key') or '').strip()
            rotated = bool(raw_api_key)
            if rotated:
                settings_obj.set_api_key(raw_api_key)
            settings_obj.save()

            changes = diff_fields(before, _settings_snapshot(settings_obj))
            if rotated:
                # This deliberately stores a boolean event, never the key or
                # an encrypted blob that could later be copied into logs.
                changes['api_key_rotated'] = [False, True]
            if changes:
                log_action(
                    request,
                    action=SuperAdminAuditLog.Action.AI_SETTINGS_UPDATED,
                    target=settings_obj,
                    summary='Updated AI provider settings',
                    changes=changes,
                )
            messages.success(request, 'AI settings saved.')
            return redirect('superadmin:ai_settings')
    else:
        form = AIProviderSettingsForm(instance=settings_obj)

    return render(request, 'superadmin/ai.html', {
        'form': form,
        'ai_settings': settings_obj,
    })
