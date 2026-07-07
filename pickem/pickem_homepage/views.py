from django.http import Http404, HttpResponse, JsonResponse
from django.template import loader
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django import forms
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks, Teams, userSeasonPoints, userStats, UserProfile
from .forms import (
    CreateFamilyForm,
    FamilyInviteCreateForm,
    FamilyAdminSettingsForm,
    FamilyBannerForm,
    FamilyManualPickForm,
    FamilyWeekWinnerForm,
    FamilyMembershipUpdateForm,
    GamePicksForm,
    JoinFamilyForm,
    MessageBoardPostForm,
    MessageBoardCommentForm,
    PickSubmissionForm,
    QuickCommentForm,
)
from .models import MessageBoardPost, MessageBoardComment, MessageBoardVote, SiteBanner

from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.db.models import Sum, Count, Q, Avg
from django.db.models.functions import Coalesce
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from functools import wraps
# from django_ratelimit.decorators import ratelimit  # Disabled for now
from collections import defaultdict
import hashlib
import json
import secrets

from datetime import date, timedelta

from django.forms import formset_factory
from django.utils import timezone
from pickem.utils import get_season as get_season_from_api
from pickem_api.authz import (
    AuthenticationRequired,
    PermissionDeniedForTenant,
    TenantNotFound,
    get_user_family_memberships,
    require_tenant_context,
)
from pickem_api.models import Family, FamilyAuditLog, FamilyInvitation, FamilyMembership, Pool, PoolSettings
from pickem_homepage.authz import family_member_required

def get_season(display_name=False):
    return get_season_from_api(display_name=display_name)

def is_commissioner(user):
    """Check if user is a commissioner or admin"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        profile = user.profile
        return profile.is_commissioner
    except UserProfile.DoesNotExist:
        return False

def current_user_picks(picks, user):
    return picks.filter(Q(userID=str(user.id)) | Q(uid=user.id)).distinct()


def build_user_display_maps(user_ids):
    """Return ({userID: display_name}, {userID: avatar_url}) with two queries.

    Batch replacement for the per-row safe_username / lookupavatar template
    filters, which issue one query per player per section on list pages
    (standings called them dozens of times per render). Keys are strings to
    match the userID CharFields on points models.
    """
    from allauth.socialaccount.models import SocialAccount

    raw_ids = {str(uid) for uid in user_ids if uid}
    numeric_ids = {int(uid) for uid in raw_ids if uid.isdigit()}
    users = User.objects.in_bulk(numeric_ids)
    social_accounts = {}
    for account in SocialAccount.objects.filter(user_id__in=numeric_ids):
        social_accounts.setdefault(account.user_id, account)

    usernames, avatars = {}, {}
    for key in raw_ids:
        user = users.get(int(key)) if key.isdigit() else None
        if user:
            usernames[key] = user.username or (
                user.email.split('@')[0] if user.email else f"User {key}"
            )
        elif key.isdigit():
            usernames[key] = "Unknown User"
        else:
            usernames[key] = f"User {key}"

        account = social_accounts.get(int(key)) if key.isdigit() else None
        if account:
            avatars[key] = account.get_avatar_url()
        elif user:
            email_hash = hashlib.md5((user.email or '').lower().encode('utf-8')).hexdigest()
            avatars[key] = f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=64"
        else:
            avatars[key] = "https://www.gravatar.com/avatar/?d=identicon&s=64"
    return usernames, avatars

def select_dashboard_snapshot_games(games, *, today=None):
    today = today or timezone.localdate()
    weekday = today.weekday()

    if weekday in (1, 2):
        return games

    if weekday == 4:
        target_date = today - timedelta(days=1)
    else:
        target_date = today

    day_games = games.filter(startTimestamp__date=target_date)
    if day_games.exists():
        return day_games
    return games

def attach_dashboard_pick_groups(games, *, pool, family):
    game_ids = [game.id for game in games]
    if not game_ids:
        return games

    active_user_ids = set(
        FamilyMembership.objects.filter(
            family=family,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
        ).values_list('user_id', flat=True)
    )
    picks = GamePicks.objects.filter(
        pool=pool,
        pick_game_id__in=game_ids,
    ).order_by('pick_game_id', 'pick', 'uid', 'userID')

    pick_user_ids = set()
    for pick in picks:
        user_id = pick.uid
        if not user_id and str(pick.userID).isdigit():
            user_id = int(pick.userID)
        if user_id in active_user_ids:
            pick_user_ids.add(user_id)

    users = User.objects.in_bulk(pick_user_ids)
    picks_by_game_team = defaultdict(lambda: defaultdict(list))
    for pick in picks:
        user_id = pick.uid
        if not user_id and str(pick.userID).isdigit():
            user_id = int(pick.userID)
        user = users.get(user_id)
        if user:
            picks_by_game_team[pick.pick_game_id][pick.pick].append(user)

    for game in games:
        groups = []
        for team_slug, team_name in (
            (game.awayTeamSlug, game.awayTeamName),
            (game.homeTeamSlug, game.homeTeamName),
        ):
            users_for_team = sorted(
                picks_by_game_team[game.id].get(team_slug, []),
                key=lambda user: user.username.lower(),
            )
            if users_for_team:
                groups.append({
                    'team_slug': team_slug,
                    'team_name': team_name,
                    'users': users_for_team,
                })
        game.dashboard_pick_groups = groups

    return games

def commissioner_required(view_func):
    """Decorator that ensures only commissioners and admins can access a view"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "You must be logged in to access this page.")
            return redirect('/')
        if not is_commissioner(request.user):
            messages.error(request, "You don't have permission to access this page. Commissioner privileges required.")
            return redirect('/')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def get_default_active_pool_for_family(family):
    """Return a family's default active pool, or first active pool as a safe fallback."""
    default_pool = (
        Pool.objects.filter(
            family=family,
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        .order_by('-season', 'slug')
        .first()
    )
    if default_pool:
        return default_pool

    return (
        Pool.objects.filter(family=family, status=Pool.Status.ACTIVE)
        .order_by('-season', 'slug')
        .first()
    )


def generate_unique_slug(model, value, *, scoped_filters=None, max_length=80):
    base_slug = slugify(value)[:max_length].strip('-') or 'family'
    scoped_filters = scoped_filters or {}
    candidate = base_slug
    suffix = 2

    while model.objects.filter(slug=candidate, **scoped_filters).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base_slug[:max_length - len(suffix_text)]}{suffix_text}"
        suffix += 1

    return candidate


def normalize_invite_code(raw_code):
    return ''.join(
        char.lower()
        for char in (raw_code or '').strip()
        if char.isalnum()
    )


def hash_invite_code(raw_code):
    normalized_code = normalize_invite_code(raw_code)
    digest = hashlib.sha256(normalized_code.encode('utf-8')).hexdigest()
    return f"sha256:{digest}"


def generate_invite_code():
    return secrets.token_urlsafe(24)


def get_family_pool_choices(user):
    choices = []
    for membership in get_user_family_memberships(user):
        family = membership.family
        pool = get_default_active_pool_for_family(family)
        choices.append({
            'membership': membership,
            'family': family,
            'pool': pool,
            'url': reverse(
                'family_pool_home',
                kwargs={'family_slug': family.slug, 'pool_slug': pool.slug},
            ) if pool else None,
        })
    return choices


def build_family_admin_sections(family, pool, user=None):
    route_kwargs = {'family_slug': family.slug, 'pool_slug': pool.slug}
    sections = [
        {
            'label': 'Settings',
            'description': 'Family name, pool name, rules, and display settings.',
            'icon': 'fas fa-sliders-h',
            'url': reverse('family_pool_admin_settings', kwargs=route_kwargs),
            'status': 'Manage settings',
        },
        {
            'label': 'Members',
            'description': 'Review members, roles, and active status.',
            'icon': 'fas fa-user-shield',
            'url': reverse('family_pool_admin_members', kwargs=route_kwargs),
            'status': 'Manage members',
        },
        {
            'label': 'Invites',
            'description': 'Create and revoke family invite links.',
            'icon': 'fas fa-ticket-alt',
            'url': reverse('family_pool_admin_invites', kwargs=route_kwargs),
            'status': 'Manage invites',
        },
        {
            'label': 'Picks',
            'description': 'Tenant-scoped manual pick tools.',
            'icon': 'fas fa-clipboard-check',
            'url': reverse('family_pool_admin_picks', kwargs=route_kwargs),
            'status': 'Manage picks',
        },
        {
            'label': 'Winners',
            'description': 'Weekly winner and bonus point controls.',
            'icon': 'fas fa-trophy',
            'url': reverse('family_pool_admin_winners', kwargs=route_kwargs),
            'status': 'Manage winners',
        },
    ]
    # Scheduler job runs are system-wide data; superuser-only (commissioners
    # govern a single family, not the site).
    if user is not None and getattr(user, 'is_superuser', False):
        sections.append({
            'label': 'Job Runs',
            'description': 'Scheduler run history for the data-update pipeline.',
            'icon': 'fas fa-robot',
            'url': reverse('family_pool_admin_job_runs', kwargs=route_kwargs),
            'status': 'View job runs',
        })
    return sections


def get_current_week_context(gameseason):
    today = date.today()
    try:
        week_obj = GameWeeks.objects.get(date=today)
        return str(week_obj.weekNumber), week_obj.competition
    except GameWeeks.DoesNotExist:
        return '1', 'nfl'


def redirect_to_default_pool_route(request, route_name, **route_kwargs):
    family_choices = get_family_pool_choices(request.user)
    if not family_choices:
        return redirect('onboarding')
    if len(family_choices) > 1:
        return redirect('family_picker')

    choice = family_choices[0]
    pool = choice.get('pool')
    if not pool:
        return redirect('onboarding')

    return redirect(
        route_name,
        family_slug=choice['family'].slug,
        pool_slug=pool.slug,
        **route_kwargs,
    )


def build_pick_id(pool, user, game):
    return f"{pool.id}-{user.id}-{game.id}"


def save_server_derived_pick(*, user, pool, game, selected_pick, tiebreaker_score=None, tiebreaker_yards=None):
    existing_pick = GamePicks.objects.filter(
        pool=pool,
        userID=str(user.id),
        pick_game_id=game.id,
    ).first()
    pick = existing_pick or GamePicks(id=build_pick_id(pool, user, game))

    pick.pool = pool
    pick.userEmail = user.email
    pick.userID = str(user.id)
    pick.uid = user.id
    pick.slug = game.slug
    pick.competition = game.competition
    pick.gameWeek = game.gameWeek
    pick.gameyear = game.gameyear
    pick.gameseason = game.gameseason
    pick.pick_game_id = game.id
    pick.pick = selected_pick
    pick.tieBreakerScore = tiebreaker_score
    pick.tieBreakerYards = tiebreaker_yards
    pick.pick_correct = False
    pick.save()
    return pick


def get_multi_family_pick_target_pools(
    *,
    user,
    current_pool,
    game,
    apply_to_all_families=False,
    selected_pool_ids=None,
    always_include_current_when_selected=True,
):
    """Return active same-season pools this user can submit this game to."""
    if not apply_to_all_families:
        return [current_pool]

    pools = list(
        Pool.objects.filter(
            family__memberships__user=user,
            family__memberships__status=FamilyMembership.Status.ACTIVE,
            status=Pool.Status.ACTIVE,
            season=game.gameseason,
            competition=game.competition,
        )
        .select_related("family")
        .distinct()
        .order_by("family__name", "name")
    )

    by_id = {pool.id: pool for pool in pools}
    by_id[current_pool.id] = current_pool
    if selected_pool_ids:
        selected_ids = {current_pool.id} if always_include_current_when_selected else set()
        for pool_id in selected_pool_ids:
            try:
                selected_ids.add(int(pool_id))
            except (TypeError, ValueError):
                continue
        by_id = {
            pool_id: pool
            for pool_id, pool in by_id.items()
            if pool_id in selected_ids
        }

    return sorted(by_id.values(), key=lambda pool: (pool.id != current_pool.id, pool.family.name, pool.name))


def get_multi_family_pick_target_choices(*, user, current_pool, season, competition):
    pools = list(
        Pool.objects.filter(
            family__memberships__user=user,
            family__memberships__status=FamilyMembership.Status.ACTIVE,
            status=Pool.Status.ACTIVE,
            season=season,
            competition=competition,
        )
        .select_related("family")
        .distinct()
        .order_by("family__name", "name")
    )
    by_id = {pool.id: pool for pool in pools}
    by_id[current_pool.id] = current_pool
    return sorted(by_id.values(), key=lambda pool: (pool.id != current_pool.id, pool.family.name, pool.name))


def get_invite_audit_context(request):
    return {
        'ip_address': request.META.get('REMOTE_ADDR'),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
    }


def get_valid_invitation_for_code(raw_code):
    if not normalize_invite_code(raw_code):
        return None

    invitation = (
        FamilyInvitation.objects.select_for_update(of=('self',))
        .select_related('family', 'pool')
        .filter(code_hash=hash_invite_code(raw_code))
        .first()
    )
    if not invitation:
        return None

    now = timezone.now()
    if invitation.is_revoked:
        return None
    if invitation.expires_at and invitation.expires_at <= now:
        return None
    if invitation.max_uses is not None and invitation.use_count >= invitation.max_uses:
        return None
    if invitation.family.status != Family.Status.ACTIVE:
        return None

    if invitation.pool:
        if invitation.pool.status != Pool.Status.ACTIVE:
            return None
        if invitation.pool.family_id != invitation.family_id:
            return None
    elif not get_default_active_pool_for_family(invitation.family):
        return None

    return invitation


def accept_invitation_for_user(request, raw_code):
    with transaction.atomic():
        invitation = get_valid_invitation_for_code(raw_code)
        if not invitation:
            return None, None, None

        pool = invitation.pool or get_default_active_pool_for_family(invitation.family)
        if not pool or pool.family_id != invitation.family_id:
            return None, None, None

        membership, created = FamilyMembership.objects.select_for_update().get_or_create(
            family=invitation.family,
            user=request.user,
            defaults={
                'role': invitation.role,
                'status': FamilyMembership.Status.ACTIVE,
            },
        )
        previous_role = membership.role
        previous_status = membership.status
        if not created:
            membership.role = invitation.role
            membership.status = FamilyMembership.Status.ACTIVE
            membership.save(update_fields=['role', 'status', 'updated_at'])

        invitation.use_count += 1
        invitation.save(update_fields=['use_count', 'updated_at'])

        FamilyAuditLog.objects.create(
            family=invitation.family,
            pool=pool,
            actor=request.user,
            action=(
                FamilyAuditLog.Action.MEMBERSHIP_CREATED
                if created else FamilyAuditLog.Action.MEMBERSHIP_UPDATED
            ),
            target_type='FamilyMembership',
            target_id=str(membership.id),
            metadata={
                'source': 'invite_acceptance',
                'invitation_id': invitation.id,
                'role': membership.role,
                'previous_role': previous_role,
                'previous_status': previous_status,
                'status': membership.status,
            },
            **get_invite_audit_context(request),
        )

    return invitation, pool, membership


def render_invalid_invite(request, form=None, *, invite_code=''):
    if form is None:
        form = JoinFamilyForm(initial={'code': invite_code} if invite_code else None)
    form.add_error('code', "Invite code is invalid or unavailable.")
    return render(request, 'pickem/join_family.html', {
        'form': form,
        'invite_code': invite_code,
        'gameseason': get_season(),
    })


@login_required
def onboarding(request):
    context = {'gameseason': get_season()}
    return render(request, 'pickem/onboarding.html', context)


@login_required
def create_family(request):
    form = CreateFamilyForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            family = Family.objects.create(
                name=form.cleaned_data['name'],
                slug=generate_unique_slug(Family, form.cleaned_data['name']),
                status=Family.Status.ACTIVE,
            )
            pool = Pool.objects.create(
                family=family,
                name='Pickem Pool',
                slug=generate_unique_slug(
                    Pool,
                    'Pickem Pool',
                    scoped_filters={'family': family},
                ),
                season=get_season(),
                competition='nfl',
                status=Pool.Status.ACTIVE,
                is_default=True,
            )
            PoolSettings.objects.create(pool=pool)
            membership = FamilyMembership.objects.create(
                family=family,
                user=request.user,
                role=FamilyMembership.Role.OWNER,
                status=FamilyMembership.Status.ACTIVE,
            )

            audit_context = {
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            }
            FamilyAuditLog.objects.create(
                family=family,
                pool=pool,
                actor=request.user,
                action=FamilyAuditLog.Action.MEMBERSHIP_CREATED,
                target_type='FamilyMembership',
                target_id=str(membership.id),
                metadata={
                    'role': membership.role,
                    'status': membership.status,
                    'source': 'create_family',
                },
                **audit_context,
            )
            FamilyAuditLog.objects.create(
                family=family,
                pool=pool,
                actor=request.user,
                action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
                target_type='Pool',
                target_id=str(pool.id),
                metadata={
                    'action': 'default_pool_created',
                    'season': pool.season,
                    'competition': pool.competition,
                    'is_default': pool.is_default,
                },
                **audit_context,
            )

        messages.success(request, f"{family.name} is ready.")
        return redirect(
            'family_pool_home',
            family_slug=family.slug,
            pool_slug=pool.slug,
        )

    context = {
        'form': form,
        'gameseason': get_season(),
    }
    return render(request, 'pickem/create_family.html', context)


@login_required
def join_family(request):
    form = JoinFamilyForm(
        request.POST or None,
        initial={'code': request.GET.get('code', '')},
    )

    if request.method == 'POST' and form.is_valid():
        invitation, pool, _membership = accept_invitation_for_user(
            request,
            form.cleaned_data['code'],
        )
        if invitation:
            messages.success(request, f"You joined {invitation.family.name}.")
            return redirect(
                'family_pool_home',
                family_slug=invitation.family.slug,
                pool_slug=pool.slug,
            )
        return render_invalid_invite(request, form)

    context = {
        'form': form,
        'gameseason': get_season(),
    }
    return render(request, 'pickem/join_family.html', context)


@login_required
def accept_invite_link(request, invite_code):
    form = JoinFamilyForm(
        initial={'code': invite_code},
        data={'code': invite_code} if request.method == 'POST' else None,
    )

    if request.method == 'POST' and form.is_valid():
        invitation, pool, _membership = accept_invitation_for_user(
            request,
            form.cleaned_data['code'],
        )
        if invitation:
            messages.success(request, f"You joined {invitation.family.name}.")
            return redirect(
                'family_pool_home',
                family_slug=invitation.family.slug,
                pool_slug=pool.slug,
            )
        return render_invalid_invite(request, form, invite_code=invite_code)

    context = {
        'form': form,
        'invite_code': invite_code,
        'gameseason': get_season(),
    }
    return render(request, 'pickem/join_family.html', context)


@require_http_methods(["POST"])
@family_member_required(minimum_role=FamilyMembership.Role.OWNER)
def create_family_invite(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    raw_code = generate_invite_code()

    with transaction.atomic():
        invitation = FamilyInvitation.objects.create(
            family=tenant_context.family,
            pool=tenant_context.pool,
            code_hash=hash_invite_code(raw_code),
            role=FamilyMembership.Role.MEMBER,
            expires_at=timezone.now() + timedelta(days=14),
            max_uses=20,
            created_by=request.user,
        )
        FamilyAuditLog.objects.create(
            family=tenant_context.family,
            pool=tenant_context.pool,
            actor=request.user,
            action=FamilyAuditLog.Action.INVITATION_CREATED,
            target_type='FamilyInvitation',
            target_id=str(invitation.id),
            metadata={
                'role': invitation.role,
                'expires_at': invitation.expires_at.isoformat(),
                'max_uses': invitation.max_uses,
            },
            **get_invite_audit_context(request),
        )

    context = {
        'family': tenant_context.family,
        'pool': tenant_context.pool,
        'membership': tenant_context.membership,
        'invite_code': raw_code,
        'invite_link': request.build_absolute_uri(
            reverse('accept_invite_link', kwargs={'invite_code': raw_code})
        ),
        'gameseason': get_season(),
    }
    messages.success(request, "Invite created. Copy it now; it will not be shown again.")
    return render(request, 'pickem/family_pool_home.html', context)


@login_required
def family_picker(request):
    choices = get_family_pool_choices(request.user)
    if not choices:
        return redirect('onboarding')

    context = {
        'family_choices': choices,
        'gameseason': get_season(),
    }
    return render(request, 'pickem/family_picker.html', context)


@family_member_required
def family_pool_home(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    family = tenant_context.family
    pool = tenant_context.pool
    gameseason = pool.season or get_season()
    current_week, current_competition = get_current_week_context(gameseason)

    standings_qs = (
        userSeasonPoints.objects.filter(pool=pool, gameseason=gameseason)
        .order_by('-total_points', 'userID')
    )
    top_standings = list(standings_qs)
    standing_user_ids = [
        int(points.userID)
        for points in top_standings
        if str(points.userID).isdigit()
    ]
    standing_users = User.objects.in_bulk(standing_user_ids)
    standings = [
        {
            'rank': rank,
            'points': points,
            'user': standing_users.get(int(points.userID)) if str(points.userID).isdigit() else None,
        }
        for rank, points in enumerate(top_standings, 1)
    ]

    # Skip the week-points podium until something has actually been scored
    # this week; ranking a field of zeros just crowns whoever sorts first.
    week_has_scored_games = GamesAndScores.objects.filter(
        gameseason=gameseason,
        gameWeek=current_week,
        competition=current_competition,
        gameScored=True,
    ).exists()
    week_points_summary = []
    if week_has_scored_games and str(current_week).isdigit() and 1 <= int(current_week) <= 18:
        week_points_field = f"week_{current_week}_points"
        week_points_rows = list(
            userSeasonPoints.objects.filter(pool=pool, gameseason=gameseason)
            .exclude(**{week_points_field: None})
            .order_by(f"-{week_points_field}", "userID")[:3]
        )
        week_points_user_ids = [
            int(points.userID)
            for points in week_points_rows
            if str(points.userID).isdigit()
        ]
        week_points_users = User.objects.in_bulk(week_points_user_ids)
        week_points_summary = [
            {
                'rank': rank,
                'points': points,
                'week_points': getattr(points, week_points_field) or 0,
                'user': week_points_users.get(int(points.userID)) if str(points.userID).isdigit() else None,
            }
            for rank, points in enumerate(week_points_rows, 1)
        ]

    recent_winners = []
    for week_num in range(1, 19):
        winner_field = f"week_{week_num}_winner"
        winner = (
            userSeasonPoints.objects.filter(
                pool=pool,
                gameseason=gameseason,
                **{winner_field: True},
            )
            .order_by('-total_points', 'userID')
            .first()
        )
        if winner:
            winner_user = None
            if str(winner.userID).isdigit():
                winner_user = User.objects.filter(id=int(winner.userID)).first()
            recent_winners.append({
                'week': week_num,
                'winner': winner,
                'user': winner_user,
            })
    recent_winners = recent_winners[-3:]

    current_week_games = GamesAndScores.objects.filter(
        gameseason=gameseason,
        gameWeek=current_week,
        competition=current_competition,
    ).order_by('startTimestamp', 'id')
    current_games = current_week_games.count()

    # Status-aware heading for the games section: "Live This Week" only makes
    # sense when something is actually live (or recently played).
    week_statuses = set(current_week_games.values_list('statusType', flat=True))
    first_kickoff = None
    if 'inprogress' in week_statuses:
        games_section_heading = 'Live This Week'
    elif week_statuses and week_statuses == {'notstarted'}:
        games_section_heading = f'Upcoming: Week {current_week}'
        first_game = current_week_games.first()
        first_kickoff = first_game.startTimestamp if first_game else None
    elif week_statuses:
        games_section_heading = f'Week {current_week} Games'
    else:
        games_section_heading = 'Upcoming Games'
    dashboard_snapshot_games = list(
        select_dashboard_snapshot_games(current_week_games).order_by('startTimestamp', 'id')
    )
    attach_dashboard_pick_groups(
        dashboard_snapshot_games,
        pool=pool,
        family=family,
    )
    user_picks_count = GamePicks.objects.filter(
        pool=pool,
        gameseason=gameseason,
        gameWeek=current_week,
        competition=current_competition,
    )
    user_picks_count = current_user_picks(user_picks_count, request.user).count()
    if user_picks_count == 0:
        user_pick_status = 'pending'
    elif user_picks_count < current_games:
        user_pick_status = 'partial'
    else:
        user_pick_status = 'complete'

    message_posts = (
        MessageBoardPost.objects.filter(family=family, is_active=True)
        .select_related('user')
        .order_by('-is_pinned', '-created_at')[:5]
    )
    active_members = (
        FamilyMembership.objects.filter(
            family=family,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
        )
        .select_related('user')
        .order_by('user__username')[:10]
    )

    context = {
        'family': family,
        'pool': pool,
        'membership': tenant_context.membership,
        'gameseason': gameseason,
        'current_week': current_week,
        'current_competition': current_competition,
        'standings': standings,
        'week_points_summary': week_points_summary,
        'recent_winners': recent_winners,
        'current_week_games': dashboard_snapshot_games,
        'current_games': current_games,
        'games_section_heading': games_section_heading,
        'first_kickoff': first_kickoff,
        'user_picks_count': user_picks_count,
        'user_pick_status': user_pick_status,
        'message_posts': message_posts,
        'active_members': active_members,
    }
    return render(request, 'pickem/family_pool_home.html', context)


@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    family = tenant_context.family
    pool = tenant_context.pool

    recent_audit_logs = (
        FamilyAuditLog.objects.filter(family=family)
        .select_related('actor', 'pool')
        .order_by('-created_at')[:12]
    )
    active_member_count = FamilyMembership.objects.filter(
        family=family,
        status=FamilyMembership.Status.ACTIVE,
        user__is_active=True,
    ).count()
    active_invite_count = FamilyInvitation.objects.filter(
        family=family,
        pool=pool,
        is_revoked=False,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).count()
    pool_settings = PoolSettings.objects.filter(pool=pool).first()

    context = {
        'family': family,
        'pool': pool,
        'membership': tenant_context.membership,
        'gameseason': pool.season or get_season(),
        'recent_audit_logs': recent_audit_logs,
        'admin_sections': build_family_admin_sections(family, pool, request.user),
        'active_member_count': active_member_count,
        'active_invite_count': active_invite_count,
        'pool_settings': pool_settings,
    }
    return render(request, 'pickem/family_admin.html', context)


@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_job_runs(request, family_slug, pool_slug):
    """View scheduler job runs (django-apscheduler). Superuser-only: the
    scheduler and its execution history are system-wide, and commissioners
    only govern a single family."""
    from django.core.paginator import Paginator
    from django.http import HttpResponseForbidden
    from django_apscheduler.models import DjangoJob, DjangoJobExecution

    tenant_context = request.tenant_context
    if not request.user.is_superuser:
        return HttpResponseForbidden('Superuser access is required to view job runs.')

    jobs = DjangoJob.objects.all().order_by('id')
    execution_qs = (
        DjangoJobExecution.objects.select_related('job').order_by('-run_time')
    )
    paginator = Paginator(execution_qs, 25)
    executions = paginator.get_page(request.GET.get('page'))

    context = {
        'family': tenant_context.family,
        'pool': tenant_context.pool,
        'membership': tenant_context.membership,
        'gameseason': tenant_context.pool.season or get_season(),
        'jobs': jobs,
        'executions': executions,
        # Raw exception/traceback output can leak internal paths and config,
        # so it is limited to the site owner (superuser); other commissioners
        # still see run status and duration.
        'can_view_logs': request.user.is_superuser,
    }
    return render(request, 'pickem/family_admin_job_runs.html', context)


# PoolSettings fields managed by the family admin settings form. The form,
# initial values, audit metadata, and save path all iterate this list, so a
# new rule only needs a model field + form field + template input.
ADMIN_POOL_SETTINGS_FIELDS = [
    'picks_lock_at_kickoff',
    'allow_tiebreaker',
    'win_points',
    'tie_points',
    'weekly_winner_points',
    'primary_tiebreaker',
    'secondary_tiebreaker',
    'perfect_week_bonus_enabled',
    'perfect_week_bonus_amount',
    'entry_fee_enabled',
    'entry_fee_amount',
    'pick_type',
    'missed_pick_policy',
    'include_playoffs',
    'late_join_policy',
    'payout_structure',
]


def build_admin_settings_metadata(*, family, pool, settings, cleaned_data):
    before = {
        'family.name': family.name,
        'pool.name': pool.name,
    }
    after = {
        'family.name': cleaned_data['family_name'],
        'pool.name': cleaned_data['pool_name'],
    }
    for field in ADMIN_POOL_SETTINGS_FIELDS:
        before[f'settings.{field}'] = getattr(settings, field)
        after[f'settings.{field}'] = cleaned_data[field]
    changed_fields = [
        field for field, before_value in before.items()
        if before_value != after[field]
    ]
    return changed_fields, {
        'target_type': 'family_pool_settings',
        'family_id': family.id,
        'pool_id': pool.id,
        'changed_fields': changed_fields,
        'before': {field: before[field] for field in changed_fields},
        'after': {field: after[field] for field in changed_fields},
    }


@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_settings(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    family = tenant_context.family
    pool = tenant_context.pool
    pool_settings, _created = PoolSettings.objects.get_or_create(pool=pool)
    current_family_banners = (
        SiteBanner.objects.filter(family=family)
        .order_by('-is_active', '-priority', '-created_at')[:5]
    )

    initial = {
        'family_name': family.name,
        'pool_name': pool.name,
    }
    for field in ADMIN_POOL_SETTINGS_FIELDS:
        initial[field] = getattr(pool_settings, field)
    banner_form = FamilyBannerForm()

    action = request.POST.get('action') if request.method == 'POST' else None
    is_settings_submit = (
        request.method == 'POST'
        and action not in ('create_banner', 'deactivate_banner')
    )
    form = FamilyAdminSettingsForm(
        request.POST if is_settings_submit else None,
        initial=initial,
    )

    if action == 'create_banner':
        banner_form = FamilyBannerForm(request.POST)
        if banner_form.is_valid():
            with transaction.atomic():
                SiteBanner.objects.filter(
                    family=family, is_active=True
                ).update(is_active=False)
                banner = banner_form.save(commit=False)
                banner.family = family
                banner.is_active = True
                banner.start_date = timezone.now()
                banner.save()
                FamilyAuditLog.objects.create(
                    family=family,
                    pool=pool,
                    actor=request.user,
                    action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
                    target_type='SiteBanner',
                    target_id=str(banner.id),
                    metadata={'summary': f'Banner published: {banner.title}'},
                    **get_invite_audit_context(request),
                )
            messages.success(request, "Banner published.")
            return redirect(
                'family_pool_admin_settings',
                family_slug=family.slug,
                pool_slug=pool.slug,
            )

    elif action == 'deactivate_banner':
        banner_id = request.POST.get('banner_id')
        banner = None
        if banner_id and str(banner_id).isdigit():
            banner = SiteBanner.objects.filter(
                id=banner_id,
                family=family,
            ).first()
        if banner:
            banner.is_active = False
            banner.save(update_fields=['is_active', 'updated_at'])
            FamilyAuditLog.objects.create(
                family=family,
                pool=pool,
                actor=request.user,
                action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
                target_type='SiteBanner',
                target_id=str(banner.id),
                metadata={'summary': f'Banner deactivated: {banner.title}'},
                **get_invite_audit_context(request),
            )
            messages.success(request, "Banner deactivated.")
        else:
            messages.info(request, "That banner could not be found.")
        return redirect(
            'family_pool_admin_settings',
            family_slug=family.slug,
            pool_slug=pool.slug,
        )

    elif request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            locked_family = Family.objects.select_for_update().get(id=family.id)
            locked_pool = Pool.objects.select_for_update().get(
                id=pool.id,
                family=locked_family,
            )
            locked_settings, _created = (
                PoolSettings.objects.select_for_update().get_or_create(pool=locked_pool)
            )
            changed_fields, metadata = build_admin_settings_metadata(
                family=locked_family,
                pool=locked_pool,
                settings=locked_settings,
                cleaned_data=form.cleaned_data,
            )

            if changed_fields:
                if 'family.name' in changed_fields:
                    locked_family.name = form.cleaned_data['family_name']
                    locked_family.save(update_fields=['name', 'updated_at'])
                if 'pool.name' in changed_fields:
                    locked_pool.name = form.cleaned_data['pool_name']
                    locked_pool.save(update_fields=['name', 'updated_at'])
                settings_fields = []
                for field in ADMIN_POOL_SETTINGS_FIELDS:
                    if f'settings.{field}' in changed_fields:
                        setattr(locked_settings, field, form.cleaned_data[field])
                        settings_fields.append(field)
                if settings_fields:
                    locked_settings.save(update_fields=settings_fields + ['updated_at'])

                FamilyAuditLog.objects.create(
                    family=locked_family,
                    pool=locked_pool,
                    actor=request.user,
                    action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
                    target_type='AdminSettings',
                    target_id=str(locked_pool.id),
                    metadata=metadata,
                    **get_invite_audit_context(request),
                )
                messages.success(request, "Settings updated.")
            else:
                messages.info(request, "No settings changes to save.")

        return redirect(
            'family_pool_admin_settings',
            family_slug=family.slug,
            pool_slug=pool.slug,
        )

    context = {
        'family': family,
        'pool': pool,
        'membership': tenant_context.membership,
        'gameseason': pool.season or get_season(),
        'form': form,
        'banner_form': banner_form,
        'pool_settings': pool_settings,
        'current_family_banners': current_family_banners,
        'scoring_point_fields': [
            form['win_points'], form['tie_points'], form['weekly_winner_points'],
        ],
        'tiebreaker_fields': [
            form['primary_tiebreaker'], form['secondary_tiebreaker'],
        ],
        'rule_choice_fields': [
            form['pick_type'], form['missed_pick_policy'],
            form['late_join_policy'], form['payout_structure'],
        ],
    }
    return render(request, 'pickem/family_admin_settings.html', context)


@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_members(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    family = tenant_context.family
    pool = tenant_context.pool
    memberships = (
        FamilyMembership.objects.filter(family=family)
        .select_related('user')
        .order_by('status', 'role', 'user__username', 'id')
    )

    context = {
        'family': family,
        'pool': pool,
        'membership': tenant_context.membership,
        'gameseason': pool.season or get_season(),
        'memberships': memberships,
        'role_choices': FamilyMembership.Role.choices,
        'status_choices': FamilyMembership.Status.choices,
        'can_manage_members': (
            tenant_context.membership.role == FamilyMembership.Role.OWNER
        ),
    }
    return render(request, 'pickem/family_admin_members.html', context)


def _membership_update_metadata(*, target_membership, previous_role, previous_status, actor):
    return {
        'target_membership_id': target_membership.id,
        'target_user_id': target_membership.user_id,
        'previous_role': previous_role,
        'new_role': target_membership.role,
        'previous_status': previous_status,
        'new_status': target_membership.status,
        'actor_id': actor.id,
    }


def get_invite_role_choices_for_membership(membership):
    if membership.role == FamilyMembership.Role.OWNER:
        return [FamilyMembership.Role.MEMBER, FamilyMembership.Role.ADMIN]
    return [FamilyMembership.Role.MEMBER]


def get_admin_pick_week(request, pool):
    requested_week = request.POST.get('week') if request.method == 'POST' else request.GET.get('week')
    if requested_week:
        form = forms.IntegerField(min_value=1, max_value=18)
        try:
            return str(form.clean(requested_week))
        except forms.ValidationError:
            return None
    week, _competition = get_current_week_context(pool.season or get_season())
    return str(week)


def get_admin_winner_week(request, pool):
    requested_week = request.POST.get('week_number') if request.method == 'POST' else request.GET.get('week')
    if requested_week:
        form = forms.IntegerField(min_value=1, max_value=18)
        try:
            return form.clean(requested_week)
        except forms.ValidationError:
            return None
    week, _competition = get_current_week_context(pool.season or get_season())
    form = forms.IntegerField(min_value=1, max_value=18)
    try:
        return form.clean(week)
    except forms.ValidationError:
        return 1


def get_manual_pick_members(family):
    return (
        FamilyMembership.objects.filter(
            family=family,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
        )
        .select_related('user')
        .order_by('user__username', 'id')
    )


def resolve_manual_pick_target_user(family, target_user_id):
    membership = (
        FamilyMembership.objects.filter(
            family=family,
            user_id=target_user_id,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
        )
        .select_related('user')
        .first()
    )
    if not membership:
        raise Http404()
    return membership.user


def get_manual_pick_games(pool, week):
    return GamesAndScores.objects.filter(
        gameseason=pool.season,
        competition=pool.competition,
        gameWeek=str(week),
    ).order_by('startTimestamp', 'id')


def resolve_manual_pick_game(pool, *, game_id, week):
    try:
        return GamesAndScores.objects.get(
            id=game_id,
            gameseason=pool.season,
            competition=pool.competition,
            gameWeek=str(week),
        )
    except GamesAndScores.DoesNotExist:
        raise Http404()


def manual_pick_audit_metadata(*, previous_pick, new_pick, target_user, game, actor):
    return {
        'previous_pick': previous_pick,
        'new_pick': new_pick,
        'target_user_id': target_user.id,
        'game_id': game.id,
        'week': str(game.gameWeek),
        'actor_id': actor.id,
    }


def recalculate_season_total(points_row):
    total_points = 0
    for week in range(1, 19):
        total_points += getattr(points_row, f"week_{week}_points", 0) or 0
        total_points += getattr(points_row, f"week_{week}_bonus", 0) or 0
    points_row.total_points = total_points
    return total_points


def get_week_winner_candidates(family, pool, week):
    pick_rows = (
        GamePicks.objects.filter(
            pool=pool,
            gameseason=pool.season,
            competition=pool.competition,
            gameWeek=str(week),
            pick_correct=True,
        )
        .values('uid')
        .annotate(wins=Count('uid'))
        .order_by('-wins', 'uid')
    )
    if not pick_rows:
        return []

    active_memberships = {
        membership.user_id: membership.user
        for membership in FamilyMembership.objects.filter(
            family=family,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
            user_id__in=[row['uid'] for row in pick_rows],
        ).select_related('user')
    }
    standing_user_ids = set(
        userSeasonPoints.objects.filter(
            pool=pool,
            gameseason=pool.season,
            userID__in=[str(user_id) for user_id in active_memberships],
        ).values_list('userID', flat=True)
    )

    candidates = []
    for row in pick_rows:
        user = active_memberships.get(row['uid'])
        if user and str(user.id) in standing_user_ids:
            candidates.append({'user': user, 'uid': user.id, 'wins': row['wins']})
    return candidates


def resolve_week_winner_row(family, pool, winner_uid):
    membership = (
        FamilyMembership.objects.filter(
            family=family,
            user_id=winner_uid,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
        )
        .select_related('user')
        .first()
    )
    if not membership:
        raise Http404()

    points_row = (
        userSeasonPoints.objects.select_for_update()
        .filter(
            pool=pool,
            gameseason=pool.season,
            userID=str(membership.user_id),
        )
        .first()
    )
    if not points_row:
        raise Http404()
    return membership.user, points_row


def week_winner_audit_metadata(*, week, previous_row, new_row, actor):
    return {
        'week': week,
        'previous_winner_user_id': int(previous_row.userID) if previous_row else None,
        'previous_winner_row_id': previous_row.id if previous_row else None,
        'new_winner_user_id': int(new_row.userID),
        'new_winner_row_id': new_row.id,
        'bonus_points': 2,
        'actor_id': actor.id,
    }


def json_tenant_admin_context(request, family_slug, pool_slug):
    try:
        return require_tenant_context(
            request.user,
            family=family_slug,
            pool=pool_slug,
            minimum_role=FamilyMembership.Role.ADMIN,
        ), None
    except AuthenticationRequired:
        return None, JsonResponse(
            {'success': False, 'error': 'authentication_required'},
            status=401,
        )
    except TenantNotFound:
        return None, JsonResponse(
            {'success': False, 'error': 'not_found'},
            status=404,
        )
    except PermissionDeniedForTenant:
        return None, JsonResponse(
            {'success': False, 'error': 'permission_denied'},
            status=403,
        )


def render_family_admin_picks(request, tenant_context, form=None, *, status=200):
    family = tenant_context.family
    pool = tenant_context.pool
    selected_week = get_admin_pick_week(request, pool) or '1'
    members = get_manual_pick_members(family)
    games = get_manual_pick_games(pool, selected_week)
    context = {
        'family': family,
        'pool': pool,
        'membership': tenant_context.membership,
        'gameseason': pool.season or get_season(),
        'selected_week': selected_week,
        'week_choices': range(1, 19),
        'members': members,
        'games': games,
        'form': form,
        'pick_lookup_url': reverse(
            'family_pool_admin_pick_user_picks',
            kwargs={'family_slug': family.slug, 'pool_slug': pool.slug},
        ),
    }
    return render(request, 'pickem/family_admin_picks.html', context, status=status)


def render_family_admin_winners(request, tenant_context, form=None, *, status=200):
    family = tenant_context.family
    pool = tenant_context.pool
    selected_week = get_admin_winner_week(request, pool)
    if selected_week is None:
        selected_week = 1
    winner_field = f"week_{selected_week}_winner"
    candidates = get_week_winner_candidates(family, pool, selected_week)
    current_winner = (
        userSeasonPoints.objects.filter(
            pool=pool,
            gameseason=pool.season,
            **{winner_field: True},
        )
        .order_by('id')
        .first()
    )
    context = {
        'family': family,
        'pool': pool,
        'membership': tenant_context.membership,
        'gameseason': pool.season or get_season(),
        'selected_week': selected_week,
        'week_choices': range(1, 19),
        'candidates': candidates,
        'current_winner': current_winner,
        'form': form,
    }
    return render(request, 'pickem/family_admin_winners.html', context, status=status)


@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_winners(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    if request.method == 'GET':
        return render_family_admin_winners(request, tenant_context)

    form = FamilyWeekWinnerForm(request.POST)
    if not form.is_valid():
        return render_family_admin_winners(request, tenant_context, form, status=400)

    week = form.cleaned_data['week_number']
    winner_field = f"week_{week}_winner"
    bonus_field = f"week_{week}_bonus"
    family = tenant_context.family
    pool = tenant_context.pool

    with transaction.atomic():
        previous_winner = (
            userSeasonPoints.objects.select_for_update()
            .filter(
                pool=pool,
                gameseason=pool.season,
                **{winner_field: True},
            )
            .order_by('id')
            .first()
        )
        _winner_user, winner_row = resolve_week_winner_row(
            family,
            pool,
            form.cleaned_data['winner_uid'],
        )
        affected_rows = list(
            userSeasonPoints.objects.select_for_update().filter(
                pool=pool,
                gameseason=pool.season,
            )
        )
        for points_row in affected_rows:
            if getattr(points_row, winner_field, False) or (points_row.id == winner_row.id):
                setattr(points_row, winner_field, points_row.id == winner_row.id)
                setattr(points_row, bonus_field, 2 if points_row.id == winner_row.id else 0)
                recalculate_season_total(points_row)
                points_row.save(update_fields=[winner_field, bonus_field, 'total_points', 'playerUpdated'])

        winner_row.refresh_from_db()
        FamilyAuditLog.objects.create(
            family=family,
            pool=pool,
            actor=request.user,
            action=FamilyAuditLog.Action.WEEK_WINNER_UPDATED,
            target_type='userSeasonPoints',
            target_id=str(winner_row.id),
            metadata=week_winner_audit_metadata(
                week=week,
                previous_row=previous_winner,
                new_row=winner_row,
                actor=request.user,
            ),
            **get_invite_audit_context(request),
        )

    messages.success(request, f"Week {week} winner updated.")
    return redirect(
        f"{reverse('family_pool_admin_winners', kwargs={'family_slug': family.slug, 'pool_slug': pool.slug})}?week={week}"
    )


@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_picks(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    if request.method == 'GET':
        return render_family_admin_picks(request, tenant_context)

    form = FamilyManualPickForm(request.POST)
    if not form.is_valid():
        return render_family_admin_picks(request, tenant_context, form, status=400)

    family = tenant_context.family
    pool = tenant_context.pool
    target_user = resolve_manual_pick_target_user(
        family,
        form.cleaned_data['target_user_id'],
    )
    game = resolve_manual_pick_game(
        pool,
        game_id=form.cleaned_data['game_id'],
        week=form.cleaned_data['week'],
    )
    selected_pick = form.cleaned_data['pick']
    if selected_pick not in (game.homeTeamSlug, game.awayTeamSlug):
        return render_family_admin_picks(request, tenant_context, form, status=400)

    with transaction.atomic():
        existing_pick = GamePicks.objects.select_for_update().filter(
            pool=pool,
            userID=str(target_user.id),
            pick_game_id=game.id,
        ).first()
        previous_pick = existing_pick.pick if existing_pick else None
        saved_pick = save_server_derived_pick(
            user=target_user,
            pool=pool,
            game=game,
            selected_pick=selected_pick,
            tiebreaker_score=form.cleaned_data.get('tieBreakerScore'),
            tiebreaker_yards=form.cleaned_data.get('tieBreakerYards'),
        )
        FamilyAuditLog.objects.create(
            family=family,
            pool=pool,
            actor=request.user,
            action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED,
            target_type='GamePicks',
            target_id=saved_pick.id,
            metadata=manual_pick_audit_metadata(
                previous_pick=previous_pick,
                new_pick=saved_pick.pick,
                target_user=target_user,
                game=game,
                actor=request.user,
            ),
            **get_invite_audit_context(request),
        )

    messages.success(request, "Manual pick saved.")
    return redirect(
        f"{reverse('family_pool_admin_picks', kwargs={'family_slug': family.slug, 'pool_slug': pool.slug})}?week={game.gameWeek}"
    )


@require_http_methods(["GET"])
def family_pool_admin_pick_user_picks(request, family_slug, pool_slug):
    tenant_context, denial = json_tenant_admin_context(request, family_slug, pool_slug)
    if denial is not None:
        return denial

    target_user_id = request.GET.get('target_user_id')
    selected_week = request.GET.get('week')
    if not target_user_id or not selected_week:
        return JsonResponse(
            {'success': False, 'error': 'missing_required_fields'},
            status=400,
        )
    week_form = forms.IntegerField(min_value=1, max_value=18)
    user_id_form = forms.IntegerField(min_value=1)
    try:
        target_user_id = user_id_form.clean(target_user_id)
        selected_week = str(week_form.clean(selected_week))
    except forms.ValidationError:
        return JsonResponse({'success': False, 'error': 'invalid_request'}, status=400)

    try:
        target_user = resolve_manual_pick_target_user(
            tenant_context.family,
            target_user_id,
        )
    except Http404:
        return JsonResponse({'success': False, 'error': 'not_found'}, status=404)

    picks = GamePicks.objects.filter(
        pool=tenant_context.pool,
        userID=str(target_user.id),
        gameseason=tenant_context.pool.season,
        competition=tenant_context.pool.competition,
        gameWeek=selected_week,
    )
    picks_data = {}
    for pick in picks:
        picks_data[str(pick.pick_game_id)] = {
            'pick': pick.pick,
            'tiebreaker_score': pick.tieBreakerScore,
            'tiebreaker_yards': pick.tieBreakerYards,
            'pick_id': pick.id,
        }

    return JsonResponse({
        'success': True,
        'target_user': {
            'id': target_user.id,
            'username': target_user.username,
        },
        'week': selected_week,
        'picks': picks_data,
    })


def build_invite_audit_metadata(invitation, *, source, replacement_for=None):
    metadata = {
        'source': source,
        'role': invitation.role,
        'expires_at': invitation.expires_at.isoformat() if invitation.expires_at else None,
        'max_uses': invitation.max_uses,
        'use_count': invitation.use_count,
        'is_revoked': invitation.is_revoked,
    }
    if replacement_for is not None:
        metadata['replacement_for_invitation_id'] = replacement_for
    return metadata


def create_admin_invitation(*, family, pool, actor, role, expires_in_days, max_uses, request, replacement_for=None):
    raw_code = generate_invite_code()
    invitation = FamilyInvitation.objects.create(
        family=family,
        pool=pool,
        code_hash=hash_invite_code(raw_code),
        role=role,
        expires_at=timezone.now() + timedelta(days=expires_in_days),
        max_uses=max_uses,
        created_by=actor,
    )
    FamilyAuditLog.objects.create(
        family=family,
        pool=pool,
        actor=actor,
        action=FamilyAuditLog.Action.INVITATION_CREATED,
        target_type='FamilyInvitation',
        target_id=str(invitation.id),
        metadata=build_invite_audit_metadata(
            invitation,
            source='admin_invite_management',
            replacement_for=replacement_for,
        ),
        **get_invite_audit_context(request),
    )
    return invitation, raw_code


def render_family_admin_invites(request, tenant_context, form, *, invite_code=None, invite_link=None, status=200):
    family = tenant_context.family
    pool = tenant_context.pool
    invitations = (
        FamilyInvitation.objects.filter(family=family)
        .select_related('created_by', 'pool')
        .order_by('-created_at')[:50]
    )
    context = {
        'family': family,
        'pool': pool,
        'membership': tenant_context.membership,
        'gameseason': pool.season or get_season(),
        'form': form,
        'invitations': invitations,
        'invite_code': invite_code,
        'invite_link': invite_link,
        'can_create_admin_invites': (
            tenant_context.membership.role == FamilyMembership.Role.OWNER
        ),
    }
    return render(request, 'pickem/family_admin_invites.html', context, status=status)


@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_invites(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    allowed_roles = get_invite_role_choices_for_membership(tenant_context.membership)
    form = FamilyInviteCreateForm(
        request.POST or None,
        allowed_roles=allowed_roles,
        initial={
            'role': FamilyMembership.Role.MEMBER,
            'expires_in_days': 14,
            'max_uses': 20,
        },
    )

    if request.method == 'POST':
        if not form.is_valid():
            return render_family_admin_invites(
                request,
                tenant_context,
                form,
                status=400,
            )

        with transaction.atomic():
            invitation, raw_code = create_admin_invitation(
                family=tenant_context.family,
                pool=tenant_context.pool,
                actor=request.user,
                role=form.cleaned_data['role'],
                expires_in_days=form.cleaned_data['expires_in_days'],
                max_uses=form.cleaned_data['max_uses'],
                request=request,
            )

        messages.success(request, "Invite created. Copy it now; it will not be shown again.")
        return render_family_admin_invites(
            request,
            tenant_context,
            form,
            invite_code=raw_code,
            invite_link=request.build_absolute_uri(
                reverse('accept_invite_link', kwargs={'invite_code': raw_code})
            ),
        )

    return render_family_admin_invites(request, tenant_context, form)


def revoke_admin_invitation(*, request, tenant_context, invitation):
    if not invitation.is_revoked:
        invitation.is_revoked = True
        invitation.save(update_fields=['is_revoked', 'updated_at'])
    FamilyAuditLog.objects.create(
        family=tenant_context.family,
        pool=tenant_context.pool,
        actor=request.user,
        action=FamilyAuditLog.Action.INVITATION_REVOKED,
        target_type='FamilyInvitation',
        target_id=str(invitation.id),
        metadata=build_invite_audit_metadata(
            invitation,
            source='admin_invite_management',
        ),
        **get_invite_audit_context(request),
    )


@require_http_methods(["POST"])
@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_invite_revoke(request, family_slug, pool_slug, invitation_id):
    tenant_context = request.tenant_context

    with transaction.atomic():
        try:
            invitation = FamilyInvitation.objects.select_for_update().get(
                family=tenant_context.family,
                id=invitation_id,
            )
        except FamilyInvitation.DoesNotExist:
            raise Http404()
        revoke_admin_invitation(
            request=request,
            tenant_context=tenant_context,
            invitation=invitation,
        )

    messages.success(request, "Invite revoked.")
    return redirect(
        'family_pool_admin_invites',
        family_slug=tenant_context.family.slug,
        pool_slug=tenant_context.pool.slug,
    )


@require_http_methods(["POST"])
@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_invite_replace(request, family_slug, pool_slug, invitation_id):
    tenant_context = request.tenant_context

    with transaction.atomic():
        try:
            old_invitation = FamilyInvitation.objects.select_for_update().get(
                family=tenant_context.family,
                id=invitation_id,
            )
        except FamilyInvitation.DoesNotExist:
            raise Http404()

        revoke_admin_invitation(
            request=request,
            tenant_context=tenant_context,
            invitation=old_invitation,
        )
        new_invitation, raw_code = create_admin_invitation(
            family=tenant_context.family,
            pool=tenant_context.pool,
            actor=request.user,
            role=old_invitation.role,
            expires_in_days=14,
            max_uses=old_invitation.max_uses or 20,
            request=request,
            replacement_for=old_invitation.id,
        )

    allowed_roles = get_invite_role_choices_for_membership(tenant_context.membership)
    form = FamilyInviteCreateForm(
        allowed_roles=allowed_roles,
        initial={
            'role': FamilyMembership.Role.MEMBER,
            'expires_in_days': 14,
            'max_uses': 20,
        },
    )
    messages.success(request, "Invite replaced. Copy the new code now.")
    return render_family_admin_invites(
        request,
        tenant_context,
        form,
        invite_code=raw_code,
        invite_link=request.build_absolute_uri(
            reverse('accept_invite_link', kwargs={'invite_code': raw_code})
        ),
    )


@require_http_methods(["POST"])
@family_member_required(minimum_role=FamilyMembership.Role.OWNER)
def family_pool_admin_member_update(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    form = FamilyMembershipUpdateForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Invalid membership update.", status=400)

    family = tenant_context.family
    pool = tenant_context.pool
    new_role = form.cleaned_data['role']
    new_status = form.cleaned_data['status']

    with transaction.atomic():
        try:
            target_membership = (
                FamilyMembership.objects.select_for_update()
                .select_related('user')
                .get(
                    family=family,
                    id=form.cleaned_data['membership_id'],
                )
            )
        except FamilyMembership.DoesNotExist:
            raise Http404()

        previous_role = target_membership.role
        previous_status = target_membership.status
        losing_active_owner = (
            previous_role == FamilyMembership.Role.OWNER
            and previous_status == FamilyMembership.Status.ACTIVE
            and (
                new_role != FamilyMembership.Role.OWNER
                or new_status != FamilyMembership.Status.ACTIVE
            )
        )
        if losing_active_owner:
            active_owner_count = (
                FamilyMembership.objects.select_for_update()
                .filter(
                    family=family,
                    role=FamilyMembership.Role.OWNER,
                    status=FamilyMembership.Status.ACTIVE,
                )
                .count()
            )
            if active_owner_count <= 1:
                return HttpResponse(
                    "Cannot remove the last active owner.",
                    status=400,
                )

        if previous_role == new_role and previous_status == new_status:
            messages.info(request, "No member changes to save.")
            return redirect(
                'family_pool_admin_members',
                family_slug=family.slug,
                pool_slug=pool.slug,
            )

        target_membership.role = new_role
        target_membership.status = new_status
        target_membership.save(update_fields=['role', 'status', 'updated_at'])

        FamilyAuditLog.objects.create(
            family=family,
            pool=pool,
            actor=request.user,
            action=FamilyAuditLog.Action.MEMBERSHIP_UPDATED,
            target_type='FamilyMembership',
            target_id=str(target_membership.id),
            metadata=_membership_update_metadata(
                target_membership=target_membership,
                previous_role=previous_role,
                previous_status=previous_status,
                actor=request.user,
            ),
            **get_invite_audit_context(request),
        )

    messages.success(request, "Member updated.")
    return redirect(
        'family_pool_admin_members',
        family_slug=family.slug,
        pool_slug=pool.slug,
    )


# @ratelimit(key='ip', rate='30/m', method='GET', block=True)  # Disabled for now
def index(request):
    if request.user.is_authenticated:
        family_choices = get_family_pool_choices(request.user)
        if not family_choices:
            return redirect('onboarding')
        if len(family_choices) == 1 and family_choices[0]['url']:
            return redirect(family_choices[0]['url'])
        return redirect('family_picker')

    today = date.today()
    today_date = today.strftime("%Y-%m-%d")
    gameseason = get_season()
    
    # Get current week information
    try:
        current_week_obj = GameWeeks.objects.get(date=today_date)
        current_week = current_week_obj.weekNumber
        current_competition = current_week_obj.competition
    except GameWeeks.DoesNotExist:
        current_week = '1'
        current_competition = 'nfl'
    
    # Get season winner
    season_winner = userSeasonPoints.objects.filter(year_winner=True, gameseason=gameseason).first()
    
    # Get top 5 leaderboard
    top_players = userSeasonPoints.objects.filter(gameseason=gameseason).order_by('-total_points')[:5]
    
    # Get current week winner
    winner_object = f"week_{current_week}_winner"
    try:
        current_week_winner = userSeasonPoints.objects.filter(**{winner_object: True}, gameseason=gameseason).first()
    except:
        current_week_winner = None
    
    # Get current week games
    current_games = GamesAndScores.objects.filter(
        gameseason=gameseason,
        gameWeek=current_week,
        competition=current_competition
    ).count()

    # Get today's games (games happening on the current date)
    from datetime import datetime
    today_games = GamesAndScores.objects.filter(
        gameseason=gameseason,
        startTimestamp__date=today
    ).order_by('startTimestamp')

    # Get team records for today's games
    wins_losses = []
    if today_games.exists():
        wins_losses = Teams.objects.filter(gameseason=gameseason)

    # Get total players count
    total_players = User.objects.filter(is_active=True, is_superuser=False).count()
    
    # Get league statistics - only count picks for finished games
    finished_games = GamesAndScores.objects.filter(gameseason=gameseason, statusType='finished')
    finished_game_slugs = finished_games.values_list('slug', flat=True)
    total_picks = GamePicks.objects.filter(gameseason=gameseason, slug__in=finished_game_slugs).count()
    total_correct_picks = GamePicks.objects.filter(gameseason=gameseason, slug__in=finished_game_slugs, pick_correct=True).count()

    # Get week points data for the compact leaderboard
    week_picks = GamePicks.objects.filter(
        gameseason=gameseason,
        gameWeek=current_week,
        competition=current_competition
    )
    week_picks_count = week_picks.count()

    # Calculate week points (correct picks per user)
    week_points = GamePicks.objects.filter(
        gameseason=gameseason,
        gameWeek=current_week,
        competition=current_competition,
        pick_correct=True
    ).values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')

    # Get list of users who have points
    users_with_week_points = week_points.values_list('uid', flat=True).distinct()

    # Get all players who submitted picks this week (for showing 0-point players)
    week_players = week_picks.values_list('uid', flat=True).distinct()

    # Build a lookup of user ID -> overall season rank (use both int and string keys for template compatibility)
    all_user_ranks = {}
    season_standings = userSeasonPoints.objects.filter(gameseason=gameseason).order_by('-total_points')
    for rank, player_points in enumerate(season_standings, 1):
        try:
            user_id = player_points.userID
            # Store with both int and string keys for template lookup compatibility
            all_user_ranks[int(user_id)] = rank
            all_user_ranks[str(user_id)] = rank
        except (ValueError, TypeError):
            continue

    # Calculate league accuracy
    league_accuracy = 0
    if total_picks > 0:
        league_accuracy = round((total_correct_picks / total_picks) * 100, 1)
    
    # Get recent week winners (last 3 weeks)
    recent_winners = []
    for week_num in range(max(1, int(current_week) - 2), int(current_week) + 1):
        winner_field = f"week_{week_num}_winner"
        try:
            winner = userSeasonPoints.objects.filter(**{winner_field: True}, gameseason=gameseason).first()
            if winner:
                recent_winners.append({
                    'week': week_num,
                    'winner': winner
                })
        except:
            pass
    
    # Check if user has submitted picks for current week
    user_has_picks = False
    user_picks_count = 0
    user_pick_status = 'pending'  # pending, partial, complete
    
    if request.user.is_authenticated:
        # Count total games for current week
        total_week_games = current_games
        
        # Count user's submitted picks for current week
        user_picks_count = GamePicks.objects.filter(
            gameseason=gameseason,
            gameWeek=current_week,
            competition=current_competition,
            userEmail=request.user.email
        ).count()
        
        # Determine pick status
        if user_picks_count == 0:
            user_pick_status = 'pending'
            user_has_picks = False
        elif user_picks_count < total_week_games:
            user_pick_status = 'partial'
            user_has_picks = False  # Not fully submitted
        else:
            user_pick_status = 'complete'
            user_has_picks = True  # Fully submitted
    
    template = loader.get_template('pickem/home.html')

    # Get message board posts for homepage (latest 13 - 3 visible + 10 more for scroll)
    message_posts = MessageBoardPost.objects.filter(is_active=True).order_by('-is_pinned', '-created_at')[:13]
    
    # Get user votes for these posts if authenticated
    user_votes = {}
    if request.user.is_authenticated:
        post_ids = [post.id for post in message_posts]
        votes = MessageBoardVote.objects.filter(user=request.user, post_id__in=post_ids)
        user_votes = {vote.post_id: vote.vote_type for vote in votes}
    
    # Message board forms
    post_form = MessageBoardPostForm()
    
    # Get user achievements data for badges
    user_achievements = {}
    user_rankings = {}
    
    # Get all users who have posted messages
    message_user_ids = set()
    for post in message_posts:
        message_user_ids.add(post.user.id)
    
    # Get current season standings for ranking badges
    try:
        current_season_points = userSeasonPoints.objects.filter(gameseason=gameseason).order_by('-total_points')
        for rank, player_points in enumerate(current_season_points, 1):
            try:
                user_id = int(player_points.userID)
                if user_id in message_user_ids:
                    user_rankings[user_id] = {
                        'rank': rank,
                        'total_points': player_points.total_points or 0,
                        'is_season_winner': player_points.year_winner,
                    }
                    
                    # Check if they won any weeks this season
                    weekly_wins = []
                    for week in range(1, 19):  # NFL has up to 18 weeks
                        winner_field = f"week_{week}_winner"
                        if hasattr(player_points, winner_field) and getattr(player_points, winner_field):
                            weekly_wins.append(week)
                    user_rankings[user_id]['weekly_wins'] = weekly_wins
            except (ValueError, TypeError):
                # Skip if userID can't be converted to int
                continue
    except Exception:
        # If there's any error with season points, just skip rankings
        pass
    
    # Get user stats for achievement badges  
    for user_id in message_user_ids:
        user_stats = userStats.objects.filter(userID=str(user_id)).first()
        if user_stats:
            user_achievements[user_id] = {
                'perfect_weeks_season': user_stats.perfectWeeksSeason or 0,
                'perfect_weeks_total': user_stats.perfectWeeksTotal or 0,
                'seasons_won': user_stats.seasonsWon or 0,
                'weeks_won_season': user_stats.weeksWonSeason or 0,
                'weeks_won_total': user_stats.weeksWonTotal or 0,
                'pick_percent_season': user_stats.pickPercentSeason or 0,
                'pick_percent_total': user_stats.pickPercentTotal or 0,
            }
    
    context = {
        'season_winner': season_winner,
        'current_week': current_week,
        'current_competition': current_competition,
        'top_players': top_players,
        'current_week_winner': current_week_winner,
        'current_games': current_games,
        'today_games': today_games,
        'wins_losses': wins_losses,
        'total_players': total_players,
        'total_picks': total_picks,
        'total_correct_picks': total_correct_picks,
        'league_accuracy': league_accuracy,
        'recent_winners': recent_winners,
        'user_has_picks': user_has_picks,
        'user_picks_count': user_picks_count,
        'user_pick_status': user_pick_status,
        'gameseason': gameseason,
        # Week points data for compact leaderboard
        'week_points': week_points,
        'users_with_week_points': users_with_week_points,
        'week_players': week_players,
        'show_week_points': week_picks_count > 0,
        'all_user_ranks': all_user_ranks,
        # Message board data
        'message_posts': message_posts,
        'user_votes': user_votes,
        'post_form': post_form,
        'user_achievements': user_achievements,
        'user_rankings': user_rankings,
    }
    return HttpResponse(template.render(context, request))


def public_home(request):
    return render(request, 'pickem/home.html', {'gameseason': get_season()})


def standings(request):
    if request.user.is_authenticated:
        return redirect_to_default_pool_route(request, 'family_pool_standings')
    return render_standings_page(request)


@family_member_required
def tenant_standings(request, family_slug, pool_slug):
    return render_standings_page(request, tenant_context=request.tenant_context)


def render_standings_page(request, *, tenant_context=None):
    # Get all unique seasons from the database
    all_seasons = GamesAndScores.objects.values_list('gameseason', flat=True).distinct().order_by('-gameseason')
    
    # Determine the selected season
    default_season = tenant_context.pool.season if tenant_context else get_season()
    selected_season = str(request.GET.get('season', default_season))
    
    # Filter player points based on the selected season
    player_points = userSeasonPoints.objects.filter(gameseason=selected_season)
    if tenant_context:
        player_points = player_points.filter(pool=tenant_context.pool)
    player_points = player_points.order_by('-total_points', 'userID')
    
    # Get season winner for the selected season
    season_winner_qs = userSeasonPoints.objects.filter(
        year_winner=True,
        gameseason=selected_season,
    )
    if tenant_context:
        season_winner_qs = season_winner_qs.filter(pool=tenant_context.pool)
    season_winner = season_winner_qs.order_by('-total_points', 'userID').first()

    weekly_winners = {}
    for week_num in range(1, 19):
        winner_field = f"week_{week_num}_winner"
        winner_qs = userSeasonPoints.objects.filter(
            gameseason=selected_season,
            **{winner_field: True},
        )
        if tenant_context:
            winner_qs = winner_qs.filter(pool=tenant_context.pool)
        weekly_winners[week_num] = list(winner_qs.order_by('-total_points', 'userID'))
    
    # Format seasons for the dropdown
    formatted_seasons = []
    for season in all_seasons:
        if season:
            start_year = 2000 + int(str(season)[:2])
            end_year = start_year + 1
            formatted_seasons.append({
                'value': str(season),
                'display': f"{start_year}-{end_year}"
            })

    # Human-readable version of the selected season for the header chip,
    # matching the dropdown labels (e.g. "2026-2027" instead of "2627").
    selected_season_display = next(
        (s['display'] for s in formatted_seasons if s['value'] == selected_season),
        selected_season,
    )

    User = get_user_model()
    if tenant_context:
        member_user_ids = FamilyMembership.objects.filter(
            family=tenant_context.family,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
        ).values_list('user_id', flat=True)
        players = User.objects.filter(id__in=member_user_ids, is_active=True)
    else:
        players = User.objects.filter(is_active=True)

    # One batched lookup for every name/avatar the template needs, instead of
    # the per-row safe_username/lookupavatar filter queries.
    display_ids = [entry.userID for entry in player_points]
    for winners in weekly_winners.values():
        display_ids.extend(winner.userID for winner in winners)
    if season_winner:
        display_ids.append(season_winner.userID)
    usernames, avatars = build_user_display_maps(display_ids)

    context = {
        'players': players,
        'usernames': usernames,
        'avatars': avatars,
        'player_points': player_points,
        'season_winner': season_winner,
        'weekly_winners': weekly_winners,
        'all_seasons': formatted_seasons,
        'selected_season': selected_season,
        'selected_season_display': selected_season_display,
        'gameseason': selected_season,
        'family': tenant_context.family if tenant_context else None,
        'pool': tenant_context.pool if tenant_context else None,
        'membership': tenant_context.membership if tenant_context else None,
        'is_tenant_page': tenant_context is not None,
    }
    return render(request, 'pickem/standings.html', context)


def rules(request):
    if request.user.is_authenticated:
        return redirect_to_default_pool_route(request, 'family_pool_rules')
    return render_rules_page(request)


@family_member_required
def tenant_rules(request, family_slug, pool_slug):
    return render_rules_page(request, tenant_context=request.tenant_context)


def render_rules_page(request, *, tenant_context=None):
    gameseason = tenant_context.pool.season if tenant_context else get_season()
    pool_settings = None
    if tenant_context:
        try:
            pool_settings = tenant_context.pool.settings
        except PoolSettings.DoesNotExist:
            pool_settings = None
    if pool_settings is None:
        # Unsaved instance -> model defaults, so the rules page can always
        # render values (public page shows the default rule set).
        pool_settings = PoolSettings()

    context = {
        'gameseason': gameseason,
        'family': tenant_context.family if tenant_context else None,
        'pool': tenant_context.pool if tenant_context else None,
        'membership': tenant_context.membership if tenant_context else None,
        'pool_settings': pool_settings,
        'is_tenant_page': tenant_context is not None,
    }
    return render(request, 'pickem/rules.html', context)


def scores(request):
    if request.user.is_authenticated:
        return redirect_to_default_pool_route(request, 'family_pool_scores')
    return render_scores_page(request)


@family_member_required
def tenant_scores(request, family_slug, pool_slug):
    return render_scores_page(request, tenant_context=request.tenant_context)


def render_scores_page(request, *, tenant_context=None, competition=None, gameseason=None, week=None):
    today = date.today()
    today_date = today.strftime("%Y-%m-%d")
    gameseason = gameseason or (tenant_context.pool.season if tenant_context else get_season())

    # Track if we're defaulting to week 1 (before season starts)
    is_default_week = False
    if week is None:
        try:
            week_obj = GameWeeks.objects.get(date=today_date)
            game_week = str(week_obj.weekNumber)
            game_competition = week_obj.competition
        except GameWeeks.DoesNotExist:
            game_week = '1'
            game_competition = 'nfl'
            is_default_week = True
    else:
        game_week = str(week)
        game_competition = 'nfl-preseason' if str(competition) == '0' else 'nfl'
    if tenant_context and week is None:
        game_competition = tenant_context.pool.competition
    
    game_list = GamesAndScores.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)

    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    
    picks = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)
    if tenant_context:
        picks = picks.filter(pool=tenant_context.pool)
    picks_total = picks.count()

    points = GamePicks.objects.filter(
        gameseason=gameseason,
        gameWeek=game_week,
        competition=game_competition,
        pick_correct=True,
    )
    if tenant_context:
        points = points.filter(pool=tenant_context.pool)
    points_total = points.count()
    
    user_points = points.values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')
    users_w_points = user_points.values_list('uid', flat=True).distinct()
    
    players = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)
    if tenant_context:
        players = players.filter(pool=tenant_context.pool)
    players_names = players.values_list('uid', flat=True).distinct()
    if tenant_context:
        # Family membership defines the roster; a member who happens to be a
        # site superuser (e.g. the webmaster) still plays in their own pool.
        players_ids_qs = User.objects.filter(
            is_active=True,
            id__in=FamilyMembership.objects.filter(
                family=tenant_context.family,
                status=FamilyMembership.Status.ACTIVE,
                user__is_active=True,
            ).values_list('user_id', flat=True),
        )
    else:
        players_ids_qs = User.objects.filter(is_active=True, is_superuser=False)
    players_ids = players_ids_qs.values_list('id', flat=True).distinct()
    wins_losses = Teams.objects.filter(gameseason=gameseason)

    winner_object = "week_{}_winner".format(game_week)
    week_winner = userSeasonPoints.objects.filter(**{winner_object: True}, gameseason=gameseason)
    if tenant_context:
        week_winner = week_winner.filter(pool=tenant_context.pool)
    week_winner = week_winner.distinct()

    # TODO: Give zero points to users that didn't win yet
    user_weekly_stats = {}
    if request.user.is_authenticated:
        total_games_in_week = game_list.count()
        user_picks = current_user_picks(picks, request.user)

        # Base accuracy on picks made for games that are finished
        finished_games_slugs = game_list.filter(statusType='finished').values_list('slug', flat=True)
        user_picks_for_finished_games = user_picks.filter(slug__in=finished_games_slugs)
        total_graded_picks = user_picks_for_finished_games.count()
        correct_graded_picks = user_picks_for_finished_games.filter(pick_correct=True).count()

        accuracy = 0
        if total_graded_picks > 0:
            accuracy = round((correct_graded_picks / total_graded_picks) * 100, 1)

        # Get weekly points
        points_field = f"week_{game_week}_points"
        weekly_points = 0
        try:
            user_points_lookup = userSeasonPoints.objects.filter(
                userID=str(request.user.id),
                gameseason=gameseason,
            )
            if tenant_context:
                user_points_lookup = user_points_lookup.filter(pool=tenant_context.pool)
            user_points_obj = user_points_lookup.get()
            weekly_points = getattr(user_points_obj, points_field, 0)
        except userSeasonPoints.DoesNotExist:
            weekly_points = 0 # User may not have an entry yet
        
        user_weekly_stats = {
            'total_games_in_week': total_games_in_week,
            'correct_picks': correct_graded_picks, # show correct picks out of finished games
            'total_graded_picks': total_graded_picks,
            'accuracy': accuracy,
            'weekly_points': weekly_points if weekly_points is not None else 0,
        }
    template = loader.get_template('pickem/scores.html')

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': game_competition,
        'wins_losses': wins_losses,
        'picks': picks,
        'week': game_week,
        'user_points': user_points,
        'users_w_points': users_w_points,
        'players_names': players_names,
        'players_ids': players_ids,
        'week_winner': week_winner,
        'current_week': game_week,
        'points_total': points_total,
        'show_week_stats_sidebar': picks_total > 0 or bool(players_ids),
        'game_weeks': range(1,19),
        'gameseason': gameseason,
        'user_weekly_stats': user_weekly_stats,
        'is_default_week': is_default_week,
        'family': tenant_context.family if tenant_context else None,
        'pool': tenant_context.pool if tenant_context else None,
        'membership': tenant_context.membership if tenant_context else None,
        'is_tenant_page': tenant_context is not None,
    }
    return HttpResponse(template.render(context, request))


@family_member_required
def tenant_players(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    member_user_ids = FamilyMembership.objects.filter(
        family=tenant_context.family,
        status=FamilyMembership.Status.ACTIVE,
        user__is_active=True,
    ).values_list('user_id', flat=True)
    players = (
        User.objects.filter(id__in=member_user_ids, is_active=True)
        .order_by('username')
    )
    standings = {
        points.userID: points
        for points in userSeasonPoints.objects.filter(
            pool=tenant_context.pool,
            gameseason=tenant_context.pool.season,
            userID__in=[str(user_id) for user_id in member_user_ids],
        )
    }
    context = {
        'family': tenant_context.family,
        'pool': tenant_context.pool,
        'membership': tenant_context.membership,
        'players': players,
        'standings_by_user_id': standings,
        'gameseason': tenant_context.pool.season,
    }
    return render(request, 'pickem/players.html', context)

def scores_long(request, competition, gameseason, week):
    if request.user.is_authenticated:
        return redirect_to_default_pool_route(
            request,
            'family_pool_scores_long',
            competition=competition,
            gameseason=gameseason,
            week=week,
        )
    return render_scores_page(
        request,
        competition=competition,
        gameseason=gameseason,
        week=week,
    )


@family_member_required
def tenant_scores_long(request, family_slug, pool_slug, competition, gameseason, week):
    return render_scores_page(
        request,
        tenant_context=request.tenant_context,
        competition=competition,
        gameseason=gameseason,
        week=week,
    )


def legacy_scores_long_unused(request, competition, gameseason, week):
    if competition == '0':
        competition_name='nfl-preseason'
    else:
        competition_name='nfl'

    game_list = GamesAndScores.objects.filter(competition=competition_name, gameseason=gameseason, gameWeek=week)
    
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = competition_name
    
    picks = GamePicks.objects.filter(gameseason=gameseason, gameWeek=week, competition=competition_name)
    

    points = GamePicks.objects.filter(
        gameseason=gameseason,
        gameWeek=week,
        competition=competition_name,
        pick_correct=True,
    )
    points_total = points.count()
    picks_total = picks.count()
    # user_points = points.values('uid').order_by('-uid').annotate(wins=Count('uid')).order_by('-wins')
    user_points = points.values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')
    users_w_points = user_points.values_list('uid', flat=True).distinct()
    players = GamePicks.objects.filter(gameseason=gameseason, gameWeek=week, competition=competition_name)
    players_names = players.values_list('uid', flat=True).distinct()
    players_ids = User.objects.filter(is_active=True, is_superuser=False).values_list('id', flat=True).distinct()
    wins_losses = Teams.objects.filter(gameseason=gameseason)

    winner_object = "week_{}_winner".format(week)
    week_winner = userSeasonPoints.objects.filter(**{winner_object: True},gameseason=gameseason).distinct() 

    user_weekly_stats = {}
    if request.user.is_authenticated:
        total_games_in_week = game_list.count()
        user_picks = current_user_picks(picks, request.user)

        # Base accuracy on picks made for games that are finished
        finished_games_slugs = game_list.filter(statusType='finished').values_list('slug', flat=True)
        user_picks_for_finished_games = user_picks.filter(slug__in=finished_games_slugs)
        total_graded_picks = user_picks_for_finished_games.count()
        correct_graded_picks = user_picks_for_finished_games.filter(pick_correct=True).count()

        accuracy = 0
        if total_graded_picks > 0:
            accuracy = round((correct_graded_picks / total_graded_picks) * 100, 1)

        # Get weekly points
        points_field = f"week_{week}_points"
        weekly_points = 0
        try:
            user_points_obj = userSeasonPoints.objects.get(userID=str(request.user.id), gameseason=gameseason)
            weekly_points = getattr(user_points_obj, points_field, 0)
        except userSeasonPoints.DoesNotExist:
            weekly_points = 0 # User may not have an entry yet
        
        user_weekly_stats = {
            'total_games_in_week': total_games_in_week,
            'correct_picks': correct_graded_picks, # show correct picks out of finished games
            'total_graded_picks': total_graded_picks,
            'accuracy': accuracy,
            'weekly_points': weekly_points if weekly_points is not None else 0,
        }

    template = loader.get_template('pickem/scores.html')

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition_name,
        'wins_losses': wins_losses,
        'picks': picks,
        'week': week,
        'user_points': user_points,
        'users_w_points': users_w_points,
        'players_names': players_names,
        'players_ids': players_ids,
        'week_winner': week_winner,
        'points_total': points_total,
        'show_week_stats_sidebar': picks_total > 0 or bool(players_ids),
        'game_weeks': range(1,19),
        'gameseason': gameseason,
        'user_weekly_stats': user_weekly_stats
    }
    return HttpResponse(template.render(context, request))

def submit_game_picks(request):
    if request.user.is_authenticated:
        return redirect_to_default_pool_route(request, 'family_pool_game_picks')

    return render_pick_page(request)


@family_member_required
def tenant_submit_game_picks(request, family_slug, pool_slug):
    return render_pick_page(request, tenant_context=request.tenant_context)


def render_pick_page(request, *, tenant_context=None):
    is_default_week = False
    gameseason = tenant_context.pool.season if tenant_context else get_season()
    game_week, game_competition = get_current_week_context(gameseason)
    if not GameWeeks.objects.filter(
        date=date.today(),
        weekNumber=game_week,
        competition=game_competition,
    ).exists():
        is_default_week = True
    if tenant_context:
        game_competition = tenant_context.pool.competition

    game_list = GamesAndScores.objects.filter(
        gameseason=gameseason,
        gameWeek=str(game_week),
        competition=game_competition,
    ).distinct()
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()

    # Handle unauthenticated users gracefully
    if tenant_context:
        picks = GamePicks.objects.filter(
            pool=tenant_context.pool,
            gameseason=gameseason,
            gameWeek=str(game_week),
            competition=game_competition,
        )
        picks = current_user_picks(picks, request.user)
        pick_slugs = picks.values_list('slug', flat=True).distinct()
        pick_ids = picks.values_list('id', flat=True).distinct()
    else:
        # No picks context for logged-out users
        picks = GamePicks.objects.none()
        pick_slugs = []
        pick_ids = []

    wins_losses = Teams.objects.filter(gameseason=gameseason)
    multi_family_pick_targets = []
    if tenant_context and request.user.is_authenticated:
        multi_family_pick_targets = get_multi_family_pick_target_choices(
            user=request.user,
            current_pool=tenant_context.pool,
            season=gameseason,
            competition=game_competition,
        )

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': game_competition,
        'wins_losses': wins_losses,
        'gameseason': gameseason,
        'week': game_week,
        'picks': picks,
        'pick_slugs': pick_slugs,
        'pick_ids': pick_ids,
        'is_default_week': is_default_week,
        'auth_required': not request.user.is_authenticated,
        'family': tenant_context.family if tenant_context else None,
        'pool': tenant_context.pool if tenant_context else None,
        'is_tenant_pick_page': tenant_context is not None,
        'multi_family_pick_targets': multi_family_pick_targets,
        'can_submit_to_multiple_families': len(multi_family_pick_targets) > 1,
        
    }

    if request.method == 'POST':
        if not tenant_context:
            return JsonResponse({'error': True, 'message': 'Authentication required'}, status=403)

        form = PickSubmissionForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'error': True, 'message': 'Invalid pick'}, status=400)

        game = GamesAndScores.objects.filter(
            id=form.cleaned_data['game_id'],
            gameseason=tenant_context.pool.season,
            gameWeek=str(game_week),
            competition=tenant_context.pool.competition,
        ).first()
        if not game:
            return JsonResponse({'error': True, 'message': 'Invalid pick'}, status=400)

        selected_pick = form.cleaned_data['pick']
        if selected_pick not in [game.awayTeamSlug, game.homeTeamSlug]:
            return JsonResponse({'error': True, 'message': 'Invalid pick'}, status=400)

        from pickem.utils import is_pick_locked_for_pool

        is_locked, lock_reason = is_pick_locked_for_pool(game, tenant_context.pool)
        if is_locked:
            return JsonResponse({
                'error': True,
                'message': f'Cannot submit pick: {lock_reason}',
            }, status=400)

        tiebreaker_score = form.cleaned_data.get('tieBreakerScore')
        tiebreaker_yards = form.cleaned_data.get('tieBreakerYards')
        if game.tieBreakerGame and (tiebreaker_score is None or tiebreaker_yards is None):
            return JsonResponse({
                'error': True,
                'message': 'Tiebreaker fields are required for this game',
            }, status=400)

        apply_to_all_families = request.POST.get('apply_to_all_families') == '1'
        selected_pool_ids = request.POST.getlist('target_pool_ids')
        target_pools = get_multi_family_pick_target_pools(
            user=request.user,
            current_pool=tenant_context.pool,
            game=game,
            apply_to_all_families=apply_to_all_families,
            selected_pool_ids=selected_pool_ids,
            always_include_current_when_selected=False,
        )
        saved_picks = []
        skipped_pools = []
        for target_pool in target_pools:
            target_locked, target_lock_reason = is_pick_locked_for_pool(game, target_pool)
            if target_locked:
                skipped_pools.append({
                    'pool_id': target_pool.id,
                    'family': target_pool.family.name,
                    'pool': target_pool.name,
                    'reason': target_lock_reason,
                })
                continue
            saved_picks.append(save_server_derived_pick(
                user=request.user,
                pool=target_pool,
                game=game,
                selected_pick=selected_pick,
                tiebreaker_score=tiebreaker_score if game.tieBreakerGame else None,
                tiebreaker_yards=tiebreaker_yards if game.tieBreakerGame else None,
            ))

        if not saved_picks:
            return JsonResponse({
                'error': True,
                'message': 'Cannot submit pick: all selected family pools are locked',
                'skipped_pools': skipped_pools,
            }, status=400)

        current_pick = next(
            (saved_pick for saved_pick in saved_picks if saved_pick.pool_id == tenant_context.pool.id),
            saved_picks[0],
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'pick_id': current_pick.id,
                'saved_count': len(saved_picks),
                'saved_pool_ids': [saved_pick.pool_id for saved_pick in saved_picks],
                'skipped_count': len(skipped_pools),
                'skipped_pools': skipped_pools,
            })
        return redirect(
            'family_pool_game_picks',
            family_slug=tenant_context.family.slug,
            pool_slug=tenant_context.pool.slug,
        )

    return render(request, 'pickem/picks.html', context)


@login_required
def edit_game_pick(request):
    if request.user.is_authenticated:
        return redirect_to_default_pool_route(request, 'family_pool_game_picks')


@family_member_required
def tenant_edit_game_pick(request, family_slug, pool_slug):
    """Handle editing of existing game picks"""
    from pickem.utils import is_pick_locked_for_pool
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'error': True, 'message': 'Only POST requests allowed'}, status=405)
    
    try:
        pick_id = request.POST.get('pick_id')
        new_pick = request.POST.get('pick')
        tiebreaker_score = request.POST.get('tieBreakerScore', '')
        tiebreaker_yards = request.POST.get('tieBreakerYards', '')
        
        if not pick_id or not new_pick:
            return JsonResponse({'error': True, 'message': 'Missing required fields'}, status=400)
        
        tenant_context = request.tenant_context

        # Get the existing pick through current pool and user scope before any lock/team checks.
        try:
            existing_pick = GamePicks.objects.get(
                id=pick_id,
                pool=tenant_context.pool,
                userID=str(request.user.id),
            )
        except GamePicks.DoesNotExist:
            return JsonResponse({'error': True, 'message': 'Pick not found or unauthorized'}, status=404)
        
        # Get the game to check if it's locked
        try:
            game = GamesAndScores.objects.get(
                id=existing_pick.pick_game_id,
                gameseason=tenant_context.pool.season,
                competition=tenant_context.pool.competition,
            )
        except GamesAndScores.DoesNotExist:
            return JsonResponse({'error': True, 'message': 'Game not found'}, status=404)
        
        # Check if the game is locked
        is_locked, lock_reason = is_pick_locked_for_pool(game, tenant_context.pool)
        if is_locked:
            return JsonResponse({
                'error': True, 
                'message': f'Cannot edit pick: {lock_reason}'
            }, status=400)
        
        # Validate the new pick is for the correct game
        if new_pick not in [game.awayTeamSlug, game.homeTeamSlug]:
            return JsonResponse({'error': True, 'message': 'Invalid team selection'}, status=400)
        
        # Validate tiebreaker if this is a tiebreaker game
        if game.tieBreakerGame:
            if not tiebreaker_score or not tiebreaker_yards:
                return JsonResponse({
                    'error': True, 
                    'message': 'Tiebreaker fields are required for this game'
                }, status=400)
            
            try:
                score_val = int(tiebreaker_score)
                yards_val = int(tiebreaker_yards)
                if score_val < 0 or score_val > 200 or yards_val < 0 or yards_val > 2000:
                    return JsonResponse({
                        'error': True, 
                        'message': 'Tiebreaker values out of valid range'
                    }, status=400)
            except ValueError:
                return JsonResponse({
                    'error': True, 
                    'message': 'Tiebreaker values must be numbers'
                }, status=400)
        
        apply_to_all_families = request.POST.get('apply_to_all_families') == '1'
        selected_pool_ids = request.POST.getlist('target_pool_ids')
        if apply_to_all_families and not selected_pool_ids:
            return JsonResponse({
                'error': True,
                'message': 'Choose at least one family to edit',
            }, status=400)
        target_pools = get_multi_family_pick_target_pools(
            user=request.user,
            current_pool=tenant_context.pool,
            game=game,
            apply_to_all_families=apply_to_all_families,
            selected_pool_ids=selected_pool_ids,
            always_include_current_when_selected=False,
        )

        saved_picks = []
        skipped_pools = []
        for target_pool in target_pools:
            target_locked, target_lock_reason = is_pick_locked_for_pool(game, target_pool)
            if target_locked:
                skipped_pools.append({
                    'pool_id': target_pool.id,
                    'family': target_pool.family.name,
                    'pool': target_pool.name,
                    'reason': target_lock_reason,
                })
                continue

            saved_picks.append(save_server_derived_pick(
                user=request.user,
                pool=target_pool,
                game=game,
                selected_pick=new_pick,
                tiebreaker_score=int(tiebreaker_score) if game.tieBreakerGame and tiebreaker_score else None,
                tiebreaker_yards=int(tiebreaker_yards) if game.tieBreakerGame and tiebreaker_yards else None,
            ))

        if not saved_picks:
            return JsonResponse({
                'error': True,
                'message': 'Cannot edit pick: all selected family pools are locked',
                'skipped_pools': skipped_pools,
            }, status=400)
        
        # Return success response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Pick updated successfully',
                'saved_count': len(saved_picks),
                'saved_pool_ids': [saved_pick.pool_id for saved_pick in saved_picks],
                'skipped_count': len(skipped_pools),
                'skipped_pools': skipped_pools,
            })
        else:
            # For non-AJAX requests, redirect back to picks page
            return redirect(
                'family_pool_game_picks',
                family_slug=tenant_context.family.slug,
                pool_slug=tenant_context.pool.slug,
            )
            
    except Exception as e:
        error_msg = f'Error updating pick: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': True, 'message': error_msg}, status=500)
        else:
            # For non-AJAX requests, you might want to show an error page or redirect with error
            return JsonResponse({'error': True, 'message': error_msg}, status=500)


def rules(request):
    if request.user.is_authenticated:
        return redirect_to_default_pool_route(request, 'family_pool_rules')
    return render_rules_page(request)


@login_required
def profile(request):
    gameseason = get_season()
    
    # Get or create user profile
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get all unique NFL teams for the favorite team dropdown
    teams = Teams.objects.values('teamNameSlug', 'teamNameName', 'teamLogo').distinct().order_by('teamNameName')
    
    if request.method == 'POST':
        # Handle AJAX requests for settings updates
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                data = json.loads(request.body)
                setting_name = data.get('setting')
                setting_value = data.get('value')
                
                # Update the specific setting
                if setting_name == 'email_notifications':
                    user_profile.email_notifications = setting_value
                elif setting_name == 'dark_mode':
                    user_profile.dark_mode = setting_value
                elif setting_name == 'private_profile':
                    user_profile.private_profile = setting_value
                
                user_profile.save()
                return JsonResponse({'success': True})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        # Handle form submissions for profile updates
        else:
            import re
            from django.contrib import messages
            
            username = request.POST.get('username', '').strip()
            tagline = request.POST.get('tagline', '').strip()
            favorite_team = request.POST.get('favorite_team', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            
            # Validation
            errors = []
            
            # Username validation
            if username:
                if len(username) < 3:
                    errors.append('Username must be at least 3 characters long.')
                elif len(username) > 30:
                    errors.append('Username must be less than 30 characters.')
                elif not re.match(r'^[a-zA-Z0-9._-]+$', username):
                    errors.append('Username can only contain letters, numbers, periods, underscores, and hyphens.')
                elif User.objects.filter(username=username, is_active=True).exclude(id=request.user.id).exists():
                    errors.append('This username is already taken.')
            
            # Tagline validation
            if tagline and len(tagline) > 200:
                errors.append('Tagline must be less than 200 characters.')
            
            # Phone number validation (basic)
            if phone_number:
                cleaned_phone = re.sub(r'[^\d]', '', phone_number)
                if len(cleaned_phone) < 10:
                    errors.append('Please enter a valid phone number.')
            
            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                # Update user fields
                if username:
                    request.user.username = username
                    request.user.save()
                
                # Update profile fields
                user_profile.tagline = tagline
                user_profile.favorite_team = favorite_team if favorite_team else None
                user_profile.phone_number = phone_number if phone_number else None
                user_profile.save()
                
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
    
    context = {
        'user_profile': user_profile,
        'teams': teams,
        'gameseason': gameseason,
    }
    
    return render(request, 'pickem/profile.html', context)




def user_profile(request, user_id):
    """Legacy profile route. Signed-in users are bridged into tenant context."""
    if request.user.is_authenticated:
        return redirect_to_default_pool_route(
            request,
            'family_pool_user_profile',
            user_id=user_id,
        )
    return render_user_profile(request, user_id)


@family_member_required
def tenant_user_profile(request, family_slug, pool_slug, user_id):
    return render_user_profile(request, user_id, tenant_context=request.tenant_context)


def render_user_profile(request, user_id, *, tenant_context=None):
    if tenant_context:
        profile_user = get_object_or_404(
            User,
            id=user_id,
            is_active=True,
            family_memberships__family=tenant_context.family,
            family_memberships__status=FamilyMembership.Status.ACTIVE,
        )
        gameseason = tenant_context.pool.season
        points_scope = userSeasonPoints.objects.filter(pool=tenant_context.pool)
        picks_scope = GamePicks.objects.filter(pool=tenant_context.pool)
        stats_scope = userStats.objects.filter(pool=tenant_context.pool)
        posts_scope = MessageBoardPost.objects.filter(family=tenant_context.family)
    else:
        profile_user = get_object_or_404(User, id=user_id)
        gameseason = get_season()
        points_scope = userSeasonPoints.objects.all()
        picks_scope = GamePicks.objects.all()
        stats_scope = userStats.objects.all()
        posts_scope = MessageBoardPost.objects.all()

    gameseason_display = get_season(display_name=True)
    user_profile, _created = UserProfile.objects.get_or_create(user=profile_user)

    if user_profile.private_profile and request.user != profile_user:
        teams = Teams.objects.values(
            'teamNameSlug',
            'teamNameName',
            'teamLogo',
        ).distinct().order_by('teamNameName')
        return render(request, 'pickem/user_profile_private.html', {
            'profile_user': profile_user,
            'user_profile': user_profile,
            'teams': teams,
            'family': tenant_context.family if tenant_context else None,
            'pool': tenant_context.pool if tenant_context else None,
            'gameseason': gameseason,
        })

    season_points = points_scope.filter(
        userID=str(user_id),
        gameseason=gameseason,
    ).first()
    all_season_points = points_scope.filter(userID=str(user_id))
    user_stats_obj = stats_scope.filter(userID=str(user_id)).first()

    stats = {
        'seasons_won': all_season_points.filter(year_winner=True).count(),
        'weeks_won_current_season': 0,
        'weeks_won_total': 0,
        'current_season_points': 0,
        'best_season_points': 0,
        'best_rank': None,
        'total_lifetime_points': 0,
        'pick_accuracy_current': 0,
        'pick_accuracy_lifetime': 0,
        'total_picks_made': 0,
        'correct_picks': 0,
        'favorite_team': None,
        'favorite_team_logo': None,
        'years_playing': 0,
        'current_season_rank': 'N/A',
        'perfect_weeks': 0,
    }

    if season_points:
        stats['current_season_points'] = season_points.total_points or 0
        stats['weeks_won_current_season'] = sum(
            1
            for week in range(1, 19)
            if getattr(season_points, f'week_{week}_winner', False)
        )

    if all_season_points.exists():
        stats['total_lifetime_points'] = all_season_points.aggregate(
            total=Coalesce(Sum('total_points'), 0)
        )['total']
        best_season = all_season_points.order_by('-total_points').first()
        if best_season:
            stats['best_season_points'] = best_season.total_points or 0
            season_standings = points_scope.filter(
                gameseason=best_season.gameseason,
            ).order_by('-total_points', 'userID')
            for rank, standing in enumerate(season_standings, 1):
                if standing.userID == str(user_id):
                    stats['best_rank'] = rank
                    break
        stats['weeks_won_total'] = sum(
            1
            for season in all_season_points
            for week in range(1, 19)
            if getattr(season, f'week_{week}_winner', False)
        )
        stats['years_playing'] = all_season_points.values('gameseason').distinct().count()

    if user_stats_obj:
        stats['perfect_weeks'] = user_stats_obj.perfectWeeksSeason or 0
        stats['pick_accuracy_current'] = user_stats_obj.pickPercentSeason or 0
        stats['pick_accuracy_lifetime'] = user_stats_obj.pickPercentTotal or 0
        stats['total_picks_made'] = user_stats_obj.totalPicksTotal or 0
        stats['correct_picks'] = user_stats_obj.correctPickTotalTotal or 0

    # Only reveal picks for games that have kicked off: showing not-yet-started
    # picks (e.g. a lone opening-night pick) leaks them to other players.
    started_game_slugs = GamesAndScores.objects.filter(
        gameseason=gameseason,
        startTimestamp__lte=timezone.now(),
    ).values('slug')
    user_picks = picks_scope.filter(
        userID=str(user_id),
        gameseason=gameseason,
        slug__in=started_game_slugs,
    )
    team_pick_stats = user_picks.values('pick').annotate(
        count=Count('pick')
    ).order_by('-count')
    total_picks = user_picks.count()
    modern_colors = [
        'rgba(99, 102, 241, 0.8)',
        'rgba(168, 85, 247, 0.8)',
        'rgba(236, 72, 153, 0.8)',
        'rgba(245, 158, 11, 0.8)',
        'rgba(34, 197, 94, 0.8)',
        'rgba(6, 182, 212, 0.8)',
    ]
    team_chart_data = []
    team_chart_labels = []
    team_chart_colors = []
    team_chart_slugs = []
    team_chart_logos = []
    team_abbreviations = {
        'arizona-cardinals': 'ARI',
        'atlanta-falcons': 'ATL',
        'atl': 'ATL',
        'ari': 'ARI',
    }
    for i, team_stat in enumerate(team_pick_stats):
        team_slug = team_stat['pick']
        pick_count = team_stat['count']
        percentage = round((pick_count / total_picks) * 100, 1) if total_picks else 0
        team = Teams.objects.filter(teamNameSlug=team_slug).first()
        display_name = team_abbreviations.get(team_slug, team_slug.replace('-', ' ').title())
        team_chart_data.append(percentage)
        team_chart_labels.append(display_name)
        team_chart_slugs.append(team_slug)
        team_chart_logos.append(team.teamLogo if team and team.teamLogo else '/static/images/nfl.svg')
        team_chart_colors.append(modern_colors[i % len(modern_colors)])

    most_picked_teams = []
    if team_chart_data:
        max_percentage = team_chart_data[0]
        for i, percentage in enumerate(team_chart_data):
            if percentage != max_percentage:
                break
            most_picked_teams.append({
                'slug': team_chart_slugs[i],
                'label': team_chart_labels[i],
                'percentage': percentage,
            })

    if user_profile.favorite_team:
        favorite_team = Teams.objects.filter(teamNameSlug=user_profile.favorite_team).first()
        if favorite_team:
            stats['favorite_team'] = favorite_team.teamNameName
            stats['favorite_team_logo'] = favorite_team.teamLogo

    # A rank means nothing until at least one game of the season is scored
    # (before that, everyone ties at zero and the "rank" is just row order).
    season_has_scored_games = GamesAndScores.objects.filter(
        gameseason=gameseason,
        gameScored=True,
    ).exists()
    if season_points and season_has_scored_games:
        stats['current_season_rank'] = points_scope.filter(
            gameseason=gameseason,
            total_points__gt=season_points.total_points,
        ).count() + 1

    recent_picks = user_picks.select_related().order_by('-gameWeek')[:5]
    posts_count = posts_scope.filter(user_id=user_id, is_active=True).count()

    context = {
        'profile_user': profile_user,
        'user_profile': user_profile,
        'user_stats_obj': user_stats_obj,
        'stats': stats,
        'recent_picks': recent_picks,
        'posts_count': posts_count,
        'gameseason': gameseason,
        'gameseason_display': gameseason_display,
        'is_own_profile': request.user == profile_user,
        # Raw lists; the template serialises them with |json_script (safe
        # against </script> breakouts, unlike json.dumps + |safe).
        'team_chart_data': team_chart_data,
        'team_chart_labels': team_chart_labels,
        'team_chart_colors': team_chart_colors,
        'team_chart_slugs': team_chart_slugs,
        'team_chart_logos': team_chart_logos,
        'most_picked_teams': most_picked_teams,
        'family': tenant_context.family if tenant_context else None,
        'pool': tenant_context.pool if tenant_context else None,
        'membership': tenant_context.membership if tenant_context else None,
    }

    return render(request, 'pickem/user_profile.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def check_username(request):
    """
    Check if a username is available.
    Returns JSON with availability status and message.
    """
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        
        if not username:
            return JsonResponse({
                'available': False,
                'message': 'Username is required'
            })
        
        # Check if username is taken by another user
        if User.objects.filter(username__iexact=username, is_active=True).exclude(id=request.user.id).exists():
            return JsonResponse({
                'available': False,
                'message': 'This username is already taken'
            })
        
        return JsonResponse({
            'available': True,
            'message': 'Username is available'
        })
        
    except Exception as e:
        return JsonResponse({
            'available': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def toggle_theme(request):
    """
    Dedicated endpoint for handling theme toggle requests.
    Accepts JSON with theme preference and updates user profile.
    """
    try:
        data = json.loads(request.body)
        theme = data.get('theme', 'light')
        
        # Get or create user profile
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Update dark mode setting based on theme
        user_profile.dark_mode = (theme == 'dark')
        user_profile.save()
        
        return JsonResponse({
            'success': True,
            'theme': theme,
            'dark_mode': user_profile.dark_mode
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# =============================================================================
# MESSAGE BOARD VIEWS
# =============================================================================

@login_required
# @ratelimit(key='user', rate='10/m', method='POST', block=True)  # Disabled for now
@require_http_methods(["POST"])
def create_post(request):
    return message_board_not_found()


@family_member_required
@require_http_methods(["POST"])
def tenant_create_post(request, family_slug, pool_slug):
    return create_post_for_family(request, request.tenant_context.family)


def message_board_not_found():
    return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


def create_post_for_family(request, family):
    content = request.POST.get('content', '').strip()
    title = request.POST.get('title', '').strip()

    if not title and content:
        title = content[:50] + ('...' if len(content) > 50 else '')

    if not content:
        return JsonResponse({
            'success': False,
            'errors': {'content': ['This field is required.']}
        }, status=400)

    if len(content) > 2000:
        return JsonResponse({
            'success': False,
            'errors': {'content': ['Message too long. Please keep it under 2000 characters.']}
        }, status=400)

    try:
        post = MessageBoardPost.objects.create(
            family=family,
            user=request.user,
            title=title,
            content=content
        )
        
        return JsonResponse({
            'success': True,
            'post_id': post.id,
            'message': 'Message sent successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'general': [str(e)]}
        }, status=500)


@login_required
# @ratelimit(key='user', rate='15/m', method='POST', block=True)  # Disabled for now
@require_http_methods(["POST"])
def create_comment(request):
    return message_board_not_found()


@family_member_required
@require_http_methods(["POST"])
def tenant_create_comment(request, family_slug, pool_slug):
    return create_comment_for_family(request, request.tenant_context.family)


def create_comment_for_family(request, family):
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        parent_id = data.get('parent_id')
        content = data.get('content', '').strip()

        if not content:
            return JsonResponse({
                'success': False,
                'error': 'Comment content is required'
            }, status=400)

        post = get_object_or_404(
            MessageBoardPost,
            id=post_id,
            family=family,
            is_active=True,
        )

        parent = None
        if parent_id:
            parent = get_object_or_404(
                MessageBoardComment,
                id=parent_id,
                family=family,
                post=post,
                is_active=True,
            )

        comment = MessageBoardComment.objects.create(
            family=family,
            post=post,
            user=request.user,
            parent=parent,
            content=content
        )

        avatar_url = 'https://www.wmata.com/systemimages/icons/menu-car-icon.png'
        if hasattr(request.user, 'socialaccount_set') and request.user.socialaccount_set.exists():
            avatar_url = request.user.socialaccount_set.first().get_avatar_url()

        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'user': request.user.username,
                'avatar': avatar_url,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                'score': comment.score,
                'depth': comment.depth,
                'parent_id': parent_id,
                'user_id': request.user.id,
            }
        })

    except Http404:
        return message_board_not_found()
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
# @ratelimit(key='user', rate='30/m', method='POST', block=True)  # Disabled for now
@require_http_methods(["POST"])
def vote_post(request):
    return message_board_not_found()


@family_member_required
@require_http_methods(["POST"])
def tenant_vote_post(request, family_slug, pool_slug):
    return vote_post_for_family(request, request.tenant_context.family)


def vote_post_for_family(request, family):
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        vote_type = data.get('vote_type')

        if vote_type not in [1, -1]:
            return JsonResponse({
                'success': False,
                'error': 'Invalid vote type'
            }, status=400)

        post = get_object_or_404(
            MessageBoardPost,
            id=post_id,
            family=family,
            is_active=True,
        )

        existing_vote = MessageBoardVote.objects.filter(
            family=family,
            user=request.user,
            post=post,
        ).first()

        if existing_vote:
            if existing_vote.vote_type == vote_type:
                existing_vote.delete()
                action = 'removed'
            else:
                existing_vote.vote_type = vote_type
                existing_vote.save()
                action = 'changed'
        else:
            MessageBoardVote.objects.create(
                family=family,
                user=request.user,
                post=post,
                vote_type=vote_type
            )
            action = 'added'

        post.refresh_from_db()

        return JsonResponse({
            'success': True,
            'action': action,
            'score': post.score,
            'upvotes': post.upvotes,
            'downvotes': post.downvotes
        })

    except Http404:
        return message_board_not_found()
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
# @ratelimit(key='user', rate='30/m', method='POST', block=True)  # Disabled for now
@require_http_methods(["POST"])
def vote_comment(request):
    return message_board_not_found()


@family_member_required
@require_http_methods(["POST"])
def tenant_vote_comment(request, family_slug, pool_slug):
    return vote_comment_for_family(request, request.tenant_context.family)


def vote_comment_for_family(request, family):
    try:
        data = json.loads(request.body)
        comment_id = data.get('comment_id')
        vote_type = data.get('vote_type')

        if vote_type not in [1, -1]:
            return JsonResponse({
                'success': False,
                'error': 'Invalid vote type'
            }, status=400)

        comment = get_object_or_404(
            MessageBoardComment,
            id=comment_id,
            family=family,
            is_active=True,
        )

        existing_vote = MessageBoardVote.objects.filter(
            family=family,
            user=request.user,
            comment=comment,
        ).first()

        if existing_vote:
            if existing_vote.vote_type == vote_type:
                existing_vote.delete()
                action = 'removed'
            else:
                existing_vote.vote_type = vote_type
                existing_vote.save()
                action = 'changed'
        else:
            MessageBoardVote.objects.create(
                family=family,
                user=request.user,
                comment=comment,
                vote_type=vote_type
            )
            action = 'added'

        comment.refresh_from_db()

        return JsonResponse({
            'success': True,
            'action': action,
            'score': comment.score,
            'upvotes': comment.upvotes,
            'downvotes': comment.downvotes
        })

    except Http404:
        return message_board_not_found()
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# @ratelimit(key='ip', rate='60/m', method='GET', block=True)  # Disabled for now
def get_post_comments(request, post_id):
    return message_board_not_found()


@family_member_required
def tenant_get_post_comments(request, family_slug, pool_slug, post_id):
    return get_post_comments_for_family(request, request.tenant_context.family, post_id)


def get_post_comments_for_family(request, family, post_id):
    try:
        post = get_object_or_404(
            MessageBoardPost,
            id=post_id,
            family=family,
            is_active=True,
        )
        comments = MessageBoardComment.objects.filter(
            post=post,
            family=family,
            parent=None,
            is_active=True,
        ).order_by('-created_at')

        def serialize_comment(comment):
            avatar_url = 'https://www.wmata.com/systemimages/icons/menu-car-icon.png'
            if hasattr(comment.user, 'socialaccount_set') and comment.user.socialaccount_set.exists():
                avatar_url = comment.user.socialaccount_set.first().get_avatar_url()

            replies = MessageBoardComment.objects.filter(
                parent=comment,
                family=family,
                is_active=True,
            ).order_by('created_at')
            data = {
                'id': comment.id,
                'content': comment.content,
                'user': comment.user.username,
                'user_id': comment.user_id,
                'avatar': avatar_url,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                'score': comment.score,
                'depth': comment.depth,
                'replies': [serialize_comment(reply) for reply in replies]
            }
            return data

        comments_data = [serialize_comment(comment) for comment in comments]

        return JsonResponse({
            'success': True,
            'comments': comments_data,
            'total_comments': MessageBoardComment.objects.filter(
                post=post,
                family=family,
                is_active=True,
            ).count()
        })

    except Http404:
        return message_board_not_found()
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Commissioner Views
def legacy_commissioner_json_denial(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {'success': False, 'error': 'authentication_required'},
            status=401,
        )
    return JsonResponse({'success': False, 'error': 'not_found'}, status=404)


@never_cache
def commissioners(request):
    raise Http404()


@require_http_methods(["POST"])
@csrf_exempt
def set_week_winner(request):
    return legacy_commissioner_json_denial(request)


@require_http_methods(["POST"])
def manage_banner(request):
    raise Http404()


@require_http_methods(["POST"])
def deactivate_banner(request):
    raise Http404()


def get_week_candidates(gameseason, week, competition):
    """Get candidates for week winner selection with tiebreaker info"""
    from django.db.models import Count, Max
    
    # Get all picks for the week
    week_picks = GamePicks.objects.filter(
        gameseason=gameseason,
        gameWeek=week,
        competition=competition,
        pick_correct=True
    )
    
    # Get user points for the week
    user_points = week_picks.values('uid').annotate(
        wins=Count('uid')
    ).order_by('-wins')
    
    if not user_points:
        return []
    
    # Get the highest score
    max_wins = user_points.first()['wins']
    
    # Get all users tied for the highest score
    candidates = []
    for user_data in user_points:
        if user_data['wins'] == max_wins:  # Only include top scorers
            # Get tiebreaker info
            tiebreaker_pick = GamePicks.objects.filter(
                uid=user_data['uid'],
                gameWeek=week,
                gameseason=gameseason,
                competition=competition,
                tieBreakerScore__isnull=False
            ).first()
            
            candidate = {
                'uid': user_data['uid'],
                'wins': user_data['wins'],
                'tiebreaker_score': tiebreaker_pick.tieBreakerScore if tiebreaker_pick else None,
                'tiebreaker_yards': tiebreaker_pick.tieBreakerYards if tiebreaker_pick else None
            }
            candidates.append(candidate)
    
    return candidates


@require_http_methods(["POST"])
@csrf_exempt
def submit_manual_pick(request):
    return legacy_commissioner_json_denial(request)


@require_http_methods(["GET"])
def get_user_picks(request):
    return legacy_commissioner_json_denial(request)
