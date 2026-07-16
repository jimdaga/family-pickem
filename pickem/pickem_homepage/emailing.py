import logging

from django.conf import settings
from django.template.loader import render_to_string

from pickem_superadmin.models import EmailProviderSettings

try:
    import resend
except ImportError:  # pragma: no cover - dependency is installed in real envs
    resend = None


logger = logging.getLogger(__name__)


def _invite_email_config():
    config = EmailProviderSettings.current()
    if config is not None:
        api_key = config.get_api_key()
        if config.invites_enabled and api_key and config.from_email:
            return {
                'provider': config.provider,
                'api_key': api_key,
                'from_email': config.from_email,
                'reply_to': config.reply_to_email,
                'source': 'database',
            }
        return None

    if settings.RESEND_API_KEY and settings.RESEND_FROM_EMAIL:
        return {
            'provider': EmailProviderSettings.Provider.RESEND,
            'api_key': settings.RESEND_API_KEY,
            'from_email': settings.RESEND_FROM_EMAIL,
            'reply_to': settings.RESEND_INVITE_REPLY_TO,
            'source': 'environment',
        }
    return None


def resend_invite_email_is_configured():
    config = _invite_email_config()
    return bool(resend and config and config['provider'] == EmailProviderSettings.Provider.RESEND)


def send_family_invitation_email(*, invitation, invite_link, invite_code):
    recipient_email = (invitation.recipient_email or '').strip()
    if not recipient_email:
        return {'status': 'skipped', 'reason': 'no_recipient'}

    config = _invite_email_config()
    if not resend or not config or config['provider'] != EmailProviderSettings.Provider.RESEND:
        logger.info(
            'Invite email not sent because Resend is not configured.',
            extra={
                'family_id': invitation.family_id,
                'pool_id': invitation.pool_id,
                'invitation_id': invitation.id,
                'recipient_email': recipient_email,
            },
        )
        return {'status': 'skipped', 'reason': 'not_configured'}

    resend.api_key = config['api_key']
    pool_name = invitation.pool.name if invitation.pool else "Family Pick'em"
    # Render from templates: Django auto-escapes the HTML context (family/pool
    # names are user-controlled, so building the HTML by hand would be an
    # injection hole) and keeps the branding in one place.
    email_context = {
        'family_name': invitation.family.name,
        'pool_name': pool_name,
        'invite_link': invite_link,
        'logo_url': getattr(settings, 'INVITE_EMAIL_LOGO_URL', ''),
    }
    params = {
        'from': config['from_email'],
        'to': [recipient_email],
        'subject': f"You're invited to join {invitation.family.name} on Family Pick'em",
        'html': render_to_string('emails/family_invite.html', email_context),
        'text': render_to_string('emails/family_invite.txt', email_context),
    }
    if config['reply_to']:
        params['reply_to'] = config['reply_to']

    try:
        response = resend.Emails.send(params)
    except Exception:
        logger.exception(
            'Failed to send family invitation email via Resend.',
            extra={
                'family_id': invitation.family_id,
                'pool_id': invitation.pool_id,
                'invitation_id': invitation.id,
                'recipient_email': recipient_email,
            },
        )
        return {'status': 'error', 'reason': 'send_failed'}

    logger.info(
        'Sent family invitation email via Resend.',
        extra={
            'family_id': invitation.family_id,
            'pool_id': invitation.pool_id,
            'invitation_id': invitation.id,
            'recipient_email': recipient_email,
            'resend_response': response,
        },
    )
    return {'status': 'sent', 'response': response}


def send_test_email(*, to_email):
    config = _invite_email_config()
    if not resend or not config or config['provider'] != EmailProviderSettings.Provider.RESEND:
        return {'status': 'skipped', 'reason': 'not_configured'}

    resend.api_key = config['api_key']
    params = {
        'from': config['from_email'],
        'to': [to_email],
        'subject': "Family Pick'em email configuration test",
        'html': (
            '<div style="font-family:\'Segoe UI\',Helvetica,Arial,sans-serif; max-width:480px; margin:0 auto;">'
            '<div style="background:#0B3D91; color:#fff; padding:20px 24px; border-radius:12px 12px 0 0; font-weight:800; font-size:18px;">🏈 Family Pick&rsquo;em</div>'
            '<div style="border:1px solid #eef1f5; border-top:0; border-radius:0 0 12px 12px; padding:24px;">'
            '<p style="margin:0 0 8px; font-size:16px; color:#111827;">Your Resend email configuration is working. ✅</p>'
            '<p style="margin:0; font-size:14px; color:#6b7280;">This is a test message sent from the Family Pick&rsquo;em superadmin console.</p>'
            '</div></div>'
        ),
        'text': "Family Pick'em: your Resend email configuration is working. This is a test message from the superadmin console.",
    }
    if config['reply_to']:
        params['reply_to'] = config['reply_to']

    try:
        response = resend.Emails.send(params)
    except Exception:
        logger.exception('Failed to send test email via Resend.', extra={'to_email': to_email})
        return {'status': 'error', 'reason': 'send_failed'}
    return {'status': 'sent', 'response': response}
