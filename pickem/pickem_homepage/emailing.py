import logging

from django.conf import settings
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
    params = {
        'from': config['from_email'],
        'to': [recipient_email],
        'subject': f"You're invited to join {invitation.family.name} on Family Pick'em",
        'html': (
            f"<p>You have been invited to join <strong>{invitation.family.name}</strong>"
            f" in <strong>{pool_name}</strong>.</p>"
            f"<p><a href=\"{invite_link}\">Accept your invite</a></p>"
            f"<p>If the button does not work, use this invite link:</p>"
            f"<p>{invite_link}</p>"
        ),
        'text': (
            f"You have been invited to join {invitation.family.name} on Family Pick'em.\n\n"
            f"Accept your invite: {invite_link}"
        ),
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
        'subject': 'Family Pickem email configuration test',
        'html': (
            '<p>This is a test email from Family Pickem.</p>'
            '<p>Your Resend configuration is working.</p>'
        ),
        'text': 'This is a test email from Family Pickem. Your Resend configuration is working.',
    }
    if config['reply_to']:
        params['reply_to'] = config['reply_to']

    try:
        response = resend.Emails.send(params)
    except Exception:
        logger.exception('Failed to send test email via Resend.', extra={'to_email': to_email})
        return {'status': 'error', 'reason': 'send_failed'}
    return {'status': 'sent', 'response': response}
