from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_homepage.emailing import send_test_email
from pickem_superadmin.forms import EmailProviderSettingsForm, EmailTestSendForm
from pickem_superadmin.models import EmailProviderSettings, SuperAdminAuditLog


def _settings_snapshot(settings_obj):
    return {
        'provider': settings_obj.provider,
        'invites_enabled': settings_obj.invites_enabled,
        'from_email': settings_obj.from_email,
        'reply_to_email': settings_obj.reply_to_email,
        'has_api_key': settings_obj.has_api_key,
    }


@superadmin_required
@require_http_methods(["GET", "POST"])
def email_settings(request):
    settings_obj = EmailProviderSettings.load()
    before = _settings_snapshot(settings_obj)
    test_form = EmailTestSendForm()

    if request.method == 'POST':
        action = request.POST.get('action', 'save_settings')
        if action == 'send_test_email':
            form = EmailProviderSettingsForm(instance=settings_obj)
            test_form = EmailTestSendForm(request.POST)
            if test_form.is_valid():
                to_email = test_form.cleaned_data['to_email']
                result = send_test_email(to_email=to_email)
                if result['status'] == 'sent':
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_TEST_SENT,
                        target=settings_obj,
                        summary=f'Sent test email to {to_email}',
                        changes={'to_email': [None, to_email]},
                    )
                    messages.success(request, f'Test email sent to {to_email}.')
                    return redirect('superadmin:email_settings')
                if result['reason'] == 'not_configured':
                    messages.error(request, 'Email provider is not fully configured yet.')
                else:
                    messages.error(request, f'Failed to send test email to {to_email}.')
        else:
            form = EmailProviderSettingsForm(request.POST, instance=settings_obj)
            if form.is_valid():
                settings_obj = form.save(commit=False)
                raw_api_key = (form.cleaned_data.get('api_key') or '').strip()
                rotated = False
                if raw_api_key:
                    settings_obj.set_api_key(raw_api_key)
                    rotated = True
                settings_obj.save()

                after = _settings_snapshot(settings_obj)
                changes = diff_fields(before, after)
                if rotated:
                    changes['api_key_rotated'] = [False, True]
                if changes:
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_SETTINGS_UPDATED,
                        target=settings_obj,
                        summary='Updated email provider settings',
                        changes=changes,
                    )
                messages.success(request, 'Email settings saved.')
                return redirect('superadmin:email_settings')
    else:
        form = EmailProviderSettingsForm(instance=settings_obj)

    return render(request, 'superadmin/email.html', {
        'form': form,
        'test_form': test_form,
        'email_settings': settings_obj,
    })
