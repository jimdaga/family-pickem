import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from pickem.utils import get_season
from pickem_api.authz import LEGACY_FAMILY_SLUG
from pickem_api.models import FamilyMembership, GameWeeks, GamesAndScores, Pool, Teams, UserProfile
from pickem_superadmin.models import EmailNotificationCampaign
from pickem_superadmin.models import EmailProviderSettings

try:
    import resend
except ImportError:  # pragma: no cover - dependency is installed in real envs
    resend = None


logger = logging.getLogger(__name__)

EMAIL_LINK_ROLE_ORDER = {
    FamilyMembership.Role.MEMBER: 10,
    FamilyMembership.Role.ADMIN: 20,
    FamilyMembership.Role.OWNER: 30,
}


def _email_provider_config():
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


def _invite_email_config():
    return _email_provider_config()


def _notification_email_config():
    config = _email_provider_config()
    if not config:
        return None
    return config


def _send_via_resend(params):
    resend.api_key = params.pop('api_key')
    return resend.Emails.send(params)


def _site_base_url():
    return getattr(settings, 'SITE_BASE_URL', 'http://localhost:8000').rstrip('/')


def _absolute_url(path):
    if not path:
        return ''
    if path.startswith(('http://', 'https://')):
        return path
    base = _site_base_url()
    if not path.startswith('/'):
        path = f'/{path}'
    return f'{base}{path}'


def _absolute_static_url(path):
    return _absolute_url(path)


def _weekly_picks_email_logo_url():
    return (getattr(settings, 'WEEKLY_PICKS_EMAIL_LOGO_URL', '') or '').strip()


def _team_logo_map(slugs):
    rows = (
        Teams.objects.filter(teamNameSlug__in=slugs)
        .order_by('teamNameSlug', '-id')
        .values_list('teamNameSlug', 'teamLogo')
    )
    logos = {}
    for slug, logo in rows:
        logos.setdefault(slug, logo or '/static/images/nfl.svg')
    return logos


def _get_weekly_target(now=None):
    now = now or timezone.now()
    next_game = (
        GamesAndScores.objects.filter(startTimestamp__gte=now)
        .order_by('startTimestamp', 'id')
        .first()
    )
    if next_game is None:
        return None

    week = int(next_game.gameWeek)
    season = next_game.gameseason or get_season()
    week_dates = list(
        GameWeeks.objects.filter(season=season, weekNumber=week, competition=next_game.competition)
        .order_by('date')
        .values_list('date', flat=True)
    )
    first_game_date = week_dates[0] if week_dates else timezone.localdate(next_game.startTimestamp)
    return {
        'season': season,
        'week': week,
        'competition': next_game.competition,
        'first_game_date': first_game_date,
        'next_game': next_game,
    }


def _get_week_games(*, season, week, competition):
    games = list(
        GamesAndScores.objects.filter(
            gameseason=season,
            competition=competition,
            gameWeek=str(week),
        ).order_by('startTimestamp', 'id')
    )
    logos = _team_logo_map(
        {
            slug
            for game in games
            for slug in (game.homeTeamSlug, game.awayTeamSlug)
            if slug
        }
    )
    for game in games:
        game.home_logo = _absolute_url(logos.get(game.homeTeamSlug, '/static/images/nfl.svg'))
        game.away_logo = _absolute_url(logos.get(game.awayTeamSlug, '/static/images/nfl.svg'))
    return games


def _pool_queryset_for_family(family, *, season=None, competition=None):
    queryset = Pool.objects.filter(
        family=family,
        status=Pool.Status.ACTIVE,
    )
    if season is not None:
        queryset = queryset.filter(season=season)
    if competition:
        queryset = queryset.filter(competition=competition)
    return queryset


def _default_active_pool_for_family(family, *, season=None, competition=None):
    pool = (
        _pool_queryset_for_family(
            family,
            season=season,
            competition=competition,
        )
        .filter(is_default=True)
        .order_by('-season', 'slug')
        .first()
    )
    if pool:
        return pool
    return (
        _pool_queryset_for_family(
            family,
            season=season,
            competition=competition,
        )
        .order_by('-season', 'slug')
        .first()
    )


def _pick_link_membership(user, *, season=None, competition=None):
    memberships = list(
        FamilyMembership.objects.select_related('family')
        .filter(
            user=user,
            status=FamilyMembership.Status.ACTIVE,
            family__status='active',
        )
        .order_by('created_at', 'id')
    )

    ordered_memberships = sorted(
        memberships,
        key=lambda membership: (
            membership.family.slug == LEGACY_FAMILY_SLUG,
            -EMAIL_LINK_ROLE_ORDER.get(membership.role, 0),
            -(membership.created_at.timestamp() if membership.created_at else 0),
            membership.id,
        ),
    )
    for membership in ordered_memberships:
        pool = _default_active_pool_for_family(
            membership.family,
            season=season,
            competition=competition,
        )
        if pool is not None:
            return membership, pool
    return None, None


def _build_picks_link(user, *, season=None, competition=None):
    membership, pool = _pick_link_membership(
        user,
        season=season,
        competition=competition,
    )
    if membership is None or pool is None:
        return '', None, None
    return _absolute_url(
        reverse(
            'family_pool_game_picks',
            kwargs={'family_slug': membership.family.slug, 'pool_slug': pool.slug},
        )
    ), membership.family, pool


def _campaign_safety_allowlist():
    return {
        email.strip().lower()
        for email in getattr(settings, 'EMAIL_NOTIFICATION_SAFE_ALLOWLIST', [])
        if email.strip()
    }


def _eligible_weekly_picks_users(campaign):
    base_qs = (
        User.objects.select_related('profile')
        .filter(
            is_active=True,
            email__isnull=False,
        )
        .exclude(email='')
    )
    users = []
    safety_allowlist = _campaign_safety_allowlist()
    campaign_allowlist = set(campaign.allowlist)
    for user in base_qs:
        # Eligibility is a read: no profile means default flags (notifications
        # on, not blocked) — never create a UserProfile row from here, this
        # also runs on the preview path.
        profile = getattr(user, 'profile', None)
        if profile is not None:
            if not profile.email_notifications:
                continue
            if profile.blocked_at is not None:
                continue
        email_value = (user.email or '').strip().lower()
        if campaign.rollout_mode == EmailNotificationCampaign.RolloutMode.ALLOWLIST:
            if email_value not in campaign_allowlist:
                continue
        if getattr(settings, 'EMAIL_NOTIFICATION_SAFE_ALLOWLIST_ONLY', True):
            if email_value not in safety_allowlist:
                continue
        link, family, pool = _build_picks_link(user)
        if not link:
            continue
        user._weekly_picks_link = link
        user._weekly_picks_family = family
        user._weekly_picks_pool = pool
        users.append(user)
    return users


def _week_window(target, campaign):
    zone = ZoneInfo(campaign.timezone_name or settings.TIME_ZONE)
    first_game_date = target['first_game_date']
    days_back = (first_game_date.weekday() - campaign.weekday) % 7
    scheduled_date = first_game_date - timedelta(days=days_back)
    scheduled_at = timezone.make_aware(
        datetime.combine(scheduled_date, time(campaign.hour, campaign.minute)),
        zone,
    )
    week_games = _get_week_games(
        season=target['season'],
        week=target['week'],
        competition=target['competition'],
    )
    if not week_games:
        return None
    last_game_local = timezone.localtime(week_games[-1].startTimestamp, zone)
    closes_at = last_game_local + timedelta(days=1)
    return scheduled_at, closes_at


def _weekly_picks_due(campaign, *, now=None, ignore_clock=False):
    now = now or timezone.now()
    target = _get_weekly_target(now=now)
    if target is None:
        return None

    zone = ZoneInfo(campaign.timezone_name or settings.TIME_ZONE)
    now_local = timezone.localtime(now, zone)
    window = _week_window(target, campaign)
    if window is None:
        return None
    scheduled_at, closes_at = window
    if not ignore_clock and now_local < scheduled_at:
        return None
    if now_local > closes_at:
        return None
    if (
        campaign.last_sent_season == target['season']
        and campaign.last_sent_week == target['week']
    ):
        return None
    target['scheduled_at'] = scheduled_at
    return target


def _weekly_picks_context(*, user, target, preview=False):
    games = _get_week_games(
        season=target['season'],
        week=target['week'],
        competition=target['competition'],
    )
    if not games:
        return None
    picks_link = getattr(user, '_weekly_picks_link', '')
    if not picks_link:
        picks_link, family, pool = _build_picks_link(
            user,
            season=target['season'],
            competition=target['competition'],
        )
    else:
        family = getattr(user, '_weekly_picks_family', None)
        pool = getattr(user, '_weekly_picks_pool', None)
    return {
        'user': user,
        'family': family,
        'pool': pool,
        'games': games,
        'week': target['week'],
        'season': target['season'],
        'picks_link': picks_link,
        'site_url': _site_base_url(),
        'logo_url': _weekly_picks_email_logo_url(),
        'preview': preview,
    }


def send_weekly_picks_preview_email(*, to_email, sample_user_email='', now=None):
    sample_user = None
    if sample_user_email:
        sample_user = User.objects.filter(email__iexact=sample_user_email.strip()).first()
    if sample_user is None:
        campaign = EmailNotificationCampaign.load_weekly_picks()
        eligible = _eligible_weekly_picks_users(campaign)
        sample_user = eligible[0] if eligible else None
    if sample_user is None:
        return {'status': 'skipped', 'reason': 'no_sample_user'}
    target = _get_weekly_target(now=now or timezone.now())
    if target is None:
        return {'status': 'skipped', 'reason': 'no_upcoming_week'}
    return _send_weekly_picks_email(
        user=sample_user,
        recipient_email=to_email,
        target=target,
        preview=True,
    )


def _send_weekly_picks_email(*, user, recipient_email, target, preview=False):
    config = _notification_email_config()
    if not resend or not config or config['provider'] != EmailProviderSettings.Provider.RESEND:
        return {'status': 'skipped', 'reason': 'not_configured'}

    context = _weekly_picks_context(user=user, target=target, preview=preview)
    if context is None:
        return {'status': 'skipped', 'reason': 'no_games'}

    params = {
        'api_key': config['api_key'],
        'from': config['from_email'],
        'to': [recipient_email],
        'subject': f"Picks for Week {target['week']} are available",
        'html': render_to_string('emails/weekly_picks_available.html', context),
        'text': render_to_string('emails/weekly_picks_available.txt', context),
    }
    if config['reply_to']:
        params['reply_to'] = config['reply_to']
    try:
        response = _send_via_resend(params)
    except Exception:
        logger.exception(
            'Failed to send weekly picks email.',
            extra={'to_email': recipient_email, 'user_id': user.id, 'week': target['week']},
        )
        return {'status': 'error', 'reason': 'send_failed'}
    return {'status': 'sent', 'response': response}


def send_due_email_campaigns(*, now=None, force_weekly_picks=False):
    now = now or timezone.now()
    campaign = EmailNotificationCampaign.load_weekly_picks()
    if not campaign.enabled and not force_weekly_picks:
        return {'campaigns': []}

    target = _weekly_picks_due(
        campaign,
        now=now,
        ignore_clock=force_weekly_picks,
    )
    if target is None:
        return {'campaigns': []}

    recipients = _eligible_weekly_picks_users(campaign)
    sent = 0
    skipped = []
    for user in recipients:
        result = _send_weekly_picks_email(
            user=user,
            recipient_email=user.email,
            target=target,
        )
        if result['status'] == 'sent':
            sent += 1
        else:
            skipped.append({'email': user.email, 'reason': result.get('reason', 'unknown')})

    # Only mark the week sent when at least one email actually went out:
    # marking it on a zero-send (provider outage, empty eligible set) would
    # permanently suppress the week's reminder. While sent == 0 the campaign
    # stays due and retries on the next scheduler tick until the window closes.
    if sent > 0:
        campaign.last_sent_season = target['season']
        campaign.last_sent_week = target['week']
        campaign.last_sent_at = now
        campaign.last_sent_count = sent
        campaign.save(update_fields=[
            'last_sent_season', 'last_sent_week', 'last_sent_at', 'last_sent_count', 'updated_at',
        ])

    logger.info(
        'Weekly picks campaign evaluated.',
        extra={
            'campaign_key': campaign.campaign_key,
            'season': target['season'],
            'week': target['week'],
            'sent_count': sent,
            'skipped': skipped,
            'forced': force_weekly_picks,
        },
    )
    return {
        'campaigns': [{
            'campaign_key': campaign.campaign_key,
            'season': target['season'],
            'week': target['week'],
            'sent_count': sent,
            'skipped': skipped,
        }],
    }

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
        params['api_key'] = config['api_key']
        response = _send_via_resend(params)
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

    params = {
        'api_key': config['api_key'],
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
        response = _send_via_resend(params)
    except Exception:
        logger.exception('Failed to send test email via Resend.', extra={'to_email': to_email})
        return {'status': 'error', 'reason': 'send_failed'}
    return {'status': 'sent', 'response': response}
