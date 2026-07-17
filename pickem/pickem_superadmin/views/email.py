from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from pickem_homepage.emailing import (
    send_due_email_campaigns,
    send_test_email,
    send_weekly_picks_preview_email,
)
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import (
    EmailNotificationCampaignForm,
    EmailProviderSettingsForm,
    EmailTestSendForm,
    WeeklyPicksPreviewForm,
)
from pickem_superadmin.models import (
    EmailNotificationCampaign,
    EmailProviderSettings,
    SuperAdminAuditLog,
)


def _settings_snapshot(settings_obj):
    return {
        'provider': settings_obj.provider,
        'invites_enabled': settings_obj.invites_enabled,
        'from_email': settings_obj.from_email,
        'reply_to_email': settings_obj.reply_to_email,
        'has_api_key': settings_obj.has_api_key,
    }


def _campaign_snapshot(campaign):
    return {
        'enabled': campaign.enabled,
        'weekday': campaign.weekday,
        'hour': campaign.hour,
        'minute': campaign.minute,
        'timezone_name': campaign.timezone_name,
        'rollout_mode': campaign.rollout_mode,
        'allowlist_emails': campaign.allowlist_emails,
        'family_link_strategy': campaign.family_link_strategy,
    }


@superadmin_required
@require_http_methods(["GET", "POST"])
def email_settings(request):
    settings_obj = EmailProviderSettings.load()
    weekly_campaign = EmailNotificationCampaign.load_weekly_picks()
    before = _settings_snapshot(settings_obj)
    campaign_before = _campaign_snapshot(weekly_campaign)
    test_form = EmailTestSendForm()
    campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
    preview_form = WeeklyPicksPreviewForm(prefix='preview')

    if request.method == 'POST':
        action = request.POST.get('action', 'save_settings')
        if action == 'send_test_email':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
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
        elif action == 'save_weekly_campaign':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(
                request.POST, instance=weekly_campaign, prefix='campaign',
            )
            if campaign_form.is_valid():
                weekly_campaign = campaign_form.save()
                changes = diff_fields(campaign_before, _campaign_snapshot(weekly_campaign))
                if changes:
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_CAMPAIGN_UPDATED,
                        target=weekly_campaign,
                        summary='Updated weekly picks email campaign',
                        changes=changes,
                    )
                messages.success(request, 'Weekly picks campaign saved.')
                return redirect('superadmin:email_settings')
        elif action == 'send_weekly_preview':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
            preview_form = WeeklyPicksPreviewForm(request.POST, prefix='preview')
            if preview_form.is_valid():
                to_email = preview_form.cleaned_data['to_email']
                sample_user_email = preview_form.cleaned_data.get('sample_user_email', '')
                result = send_weekly_picks_preview_email(
                    to_email=to_email,
                    sample_user_email=sample_user_email,
                )
                if result['status'] == 'sent':
                    log_action(
                        request,
                        action=SuperAdminAuditLog.Action.EMAIL_PREVIEW_SENT,
                        target=weekly_campaign,
                        summary=f'Sent weekly picks preview to {to_email}',
                        changes={
                            'to_email': [None, to_email],
                            'sample_user_email': [None, sample_user_email or None],
                        },
                    )
                    messages.success(request, f'Weekly picks preview sent to {to_email}.')
                    return redirect('superadmin:email_settings')
                if result['reason'] == 'not_configured':
                    messages.error(request, 'Email provider is not fully configured yet.')
                elif result['reason'] == 'no_sample_user':
                    messages.error(request, 'No eligible member exists to render the preview.')
                elif result['reason'] == 'no_upcoming_week':
                    messages.error(request, 'No active NFL week is available from game data yet.')
                else:
                    messages.error(request, f'Failed to send preview to {to_email}.')
        elif action == 'send_weekly_now':
            form = EmailProviderSettingsForm(instance=settings_obj)
            campaign_form = EmailNotificationCampaignForm(instance=weekly_campaign, prefix='campaign')
            result = send_due_email_campaigns(force_weekly_picks=True)
            campaign_rows = result.get('campaigns', [])
            if campaign_rows:
                row = campaign_rows[0]
                log_action(
                    request,
                    action=SuperAdminAuditLog.Action.EMAIL_CAMPAIGN_SENT,
                    target=weekly_campaign,
                    summary=(
                        f"Ran weekly picks campaign for {row['season']} week {row['week']}"
                    ),
                    changes={'sent_count': [None, row['sent_count']]},
                )
                messages.success(
                    request,
                    f"Weekly picks campaign ran for week {row['week']} and sent {row['sent_count']} email(s).",
                )
                return redirect('superadmin:email_settings')
            messages.error(
                request,
                'Weekly picks campaign is not in an active NFL week window from game data.',
            )
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
        'campaign_form': campaign_form,
        'preview_form': preview_form,
        'weekly_campaign': weekly_campaign,
        'email_settings': settings_obj,
    })
