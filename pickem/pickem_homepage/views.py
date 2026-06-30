from django.http import Http404, HttpResponse, JsonResponse
from django.template import loader
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks, Teams, userSeasonPoints, userStats, UserProfile
from .forms import (
    CreateFamilyForm,
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
import hashlib
import json
import secrets

from datetime import date, timedelta

from django.forms import formset_factory
from django.utils import timezone
from pickem.utils import get_season as get_season_from_api
from pickem_api.authz import get_user_family_memberships
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


def get_invite_audit_context(request):
    return {
        'ip_address': request.META.get('REMOTE_ADDR'),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
    }


def get_valid_invitation_for_code(raw_code):
    if not normalize_invite_code(raw_code):
        return None

    invitation = (
        FamilyInvitation.objects.select_for_update()
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
                name='Main Pickem',
                slug=generate_unique_slug(
                    Pool,
                    'Main Pickem',
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
    top_standings = list(standings_qs[:5])
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

    current_games = GamesAndScores.objects.filter(
        gameseason=gameseason,
        gameWeek=current_week,
        competition=current_competition,
    ).count()
    user_picks_count = GamePicks.objects.filter(
        pool=pool,
        gameseason=gameseason,
        gameWeek=current_week,
        competition=current_competition,
        userEmail=request.user.email,
    ).count()
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
        'recent_winners': recent_winners,
        'current_games': current_games,
        'user_picks_count': user_picks_count,
        'user_pick_status': user_pick_status,
        'message_posts': message_posts,
        'active_members': active_members,
    }
    return render(request, 'pickem/family_pool_home.html', context)


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

    context = {
        'players': players,
        'player_points': player_points,
        'season_winner': season_winner,
        'weekly_winners': weekly_winners,
        'all_seasons': formatted_seasons,
        'selected_season': selected_season,
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
    players_ids_qs = User.objects.filter(is_active=True, is_superuser=False)
    if tenant_context:
        member_user_ids = FamilyMembership.objects.filter(
            family=tenant_context.family,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
        ).values_list('user_id', flat=True)
        players_ids_qs = players_ids_qs.filter(id__in=member_user_ids)
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
        user_picks = picks.filter(userEmail=request.user.email)

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
        'show_week_stats_sidebar': picks_total > 0,
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
        user_picks = picks.filter(userEmail=request.user.email)

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
        'show_week_stats_sidebar': picks_total > 0,
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
            userEmail=request.user.email,
        )
        pick_slugs = picks.values_list('slug', flat=True).distinct()
        pick_ids = picks.values_list('id', flat=True).distinct()
    else:
        # No picks context for logged-out users
        picks = GamePicks.objects.none()
        pick_slugs = []
        pick_ids = []

    wins_losses = Teams.objects.filter(gameseason=gameseason)

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

        from pickem.utils import is_pick_locked

        is_locked, lock_reason = is_pick_locked(game)
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

        pick = save_server_derived_pick(
            user=request.user,
            pool=tenant_context.pool,
            game=game,
            selected_pick=selected_pick,
            tiebreaker_score=tiebreaker_score if game.tieBreakerGame else None,
            tiebreaker_yards=tiebreaker_yards if game.tieBreakerGame else None,
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'pick_id': pick.id})
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
    from pickem.utils import is_pick_locked
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
        is_locked, lock_reason = is_pick_locked(game)
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
        
        save_server_derived_pick(
            user=request.user,
            pool=tenant_context.pool,
            game=game,
            selected_pick=new_pick,
            tiebreaker_score=int(tiebreaker_score) if game.tieBreakerGame and tiebreaker_score else None,
            tiebreaker_yards=int(tiebreaker_yards) if game.tieBreakerGame and tiebreaker_yards else None,
        )
        
        # Return success response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Pick updated successfully'})
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


def home_view(request):
    gameseason = get_season()
    context = {
        'banner_message': 'Week 15 picks are due by Sunday at 1 PM EST!',
        'banner_type': 'warning',
        'banner_icon': 'fas fa-clock',
        'banner_dismissible': True,
        'gameseason': gameseason
    }
    return render(request, 'pickem/home.html', context)


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

    user_picks = picks_scope.filter(userID=str(user_id), gameseason=gameseason)
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

    if season_points:
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
        'team_chart_data': json.dumps(team_chart_data),
        'team_chart_labels': json.dumps(team_chart_labels),
        'team_chart_colors': json.dumps(team_chart_colors),
        'team_chart_slugs': json.dumps(team_chart_slugs),
        'team_chart_logos': json.dumps(team_chart_logos),
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
@commissioner_required
@never_cache
def commissioners(request):
    """Main commissioners dashboard"""
    from .forms import WeekWinnerForm, SiteBannerForm
    
    today = date.today()
    gameseason = get_season()
    
    # Get current week info
    try:
        week_obj = GameWeeks.objects.get(date=today.strftime("%Y-%m-%d"))
        current_week = week_obj.weekNumber
        current_competition = week_obj.competition
    except GameWeeks.DoesNotExist:
        current_week = '1'
        current_competition = 'nfl'
    
    # Get current week candidates for week winner selection
    week_candidates = get_week_candidates(gameseason, current_week, current_competition)
    
    # Check if current week already has a winner
    winner_field = f"week_{current_week}_winner"
    current_week_winner = userSeasonPoints.objects.filter(
        gameseason=gameseason, 
        **{winner_field: True}
    ).first()
    
    # Get active banner info
    active_banner = SiteBanner.get_active_banner()
    
    # Get data for manual pick submission
    # Get all active users for the dropdown
    User = get_user_model()
    active_users = User.objects.filter(is_active=True).order_by('username')
    
    # Get current week games
    current_week_games = GamesAndScores.objects.filter(
        gameseason=gameseason, 
        gameWeek=current_week, 
        competition=current_competition
    ).order_by('startTimestamp')
    
    # Get team records for display
    team_records = Teams.objects.filter(gameseason=gameseason)
    
    # Initialize forms
    week_winner_form = WeekWinnerForm(week_candidates) if week_candidates else None
    banner_form = SiteBannerForm(instance=active_banner) if active_banner else SiteBannerForm()
    
    context = {
        'current_week': current_week,
        'gameseason': gameseason,
        'current_competition': current_competition,
        'week_candidates': week_candidates,
        'current_week_winner': current_week_winner,
        'active_banner': active_banner,
        'week_winner_form': week_winner_form,
        'banner_form': banner_form,
        'active_users': active_users,
        'current_week_games': current_week_games,
        'team_records': team_records,
    }
    
    return render(request, 'pickem/commissioners.html', context)


@commissioner_required
@require_http_methods(["POST"])
@csrf_exempt
def set_week_winner(request):
    """Set the winner for a specific week"""
    from .forms import WeekWinnerForm
    
    try:
        data = json.loads(request.body)
        week_number = data.get('week_number')
        winner_uid = data.get('winner_uid')
        gameseason = data.get('gameseason')
        
        if not all([week_number, winner_uid, gameseason]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        # Clear any existing winners for this week
        winner_field = f"week_{week_number}_winner"
        userSeasonPoints.objects.filter(gameseason=gameseason).update(**{winner_field: False})
        
        # Set the new winner
        winner_record = userSeasonPoints.objects.filter(
            userEmail=User.objects.get(id=winner_uid).email,
            gameseason=gameseason
        ).first()
        
        if not winner_record:
            return JsonResponse({
                'success': False,
                'error': 'User season record not found'
            }, status=404)
        
        # Set winner and add bonus points
        setattr(winner_record, winner_field, True)
        bonus_field = f"week_{week_number}_bonus"
        setattr(winner_record, bonus_field, 2)  # 2 bonus points for winning
        
        # Recalculate total points
        total_points = 0
        for week in range(1, 19):  # Weeks 1-18
            points_field = f"week_{week}_points"
            bonus_field = f"week_{week}_bonus"
            week_points = getattr(winner_record, points_field, 0) or 0
            week_bonus = getattr(winner_record, bonus_field, 0) or 0
            total_points += week_points + week_bonus
        
        winner_record.total_points = total_points
        winner_record.save()
        
        winner_user = User.objects.get(id=winner_uid)
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully set {winner_user.username} as Week {week_number} winner with 2 bonus points!'
        })
        
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


@commissioner_required
@require_http_methods(["POST"])
def manage_banner(request):
    """Create or update a site banner"""
    from .forms import SiteBannerForm
    
    # Deactivate all current banners first (only one active at a time)
    SiteBanner.objects.filter(is_active=True).update(is_active=False)
    
    # Get existing banner if editing
    banner_id = request.POST.get('banner_id')
    if banner_id:
        banner = get_object_or_404(SiteBanner, id=banner_id)
        form = SiteBannerForm(request.POST, instance=banner)
    else:
        form = SiteBannerForm(request.POST)
    
    if form.is_valid():
        banner = form.save(commit=False)
        banner.is_active = True  # Make this the active banner
        banner.save()
        
        messages.success(request, f'Successfully {"updated" if banner_id else "created"} site banner!')
        return redirect('commissioners')
    else:
        messages.error(request, 'Please correct the errors below.')
        
        # Re-render the commissioners page with form errors
        return commissioners(request)


@commissioner_required
@require_http_methods(["POST"])
def deactivate_banner(request):
    """Deactivate the current site banner"""
    try:
        active_banner = SiteBanner.get_active_banner()
        if active_banner:
            active_banner.is_active = False
            active_banner.save()
            messages.success(request, 'Site banner has been deactivated.')
        else:
            messages.info(request, 'No active banner to deactivate.')
    except Exception as e:
        messages.error(request, f'Error deactivating banner: {str(e)}')
    
    return redirect('commissioners')


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


@commissioner_required
@require_http_methods(["POST"])
@csrf_exempt
def submit_manual_pick(request):
    """Submit a pick on behalf of a user"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        game_id = data.get('game_id')
        pick = data.get('pick')
        tiebreaker_score = data.get('tiebreaker_score', '')
        tiebreaker_yards = data.get('tiebreaker_yards', '')
        
        if not all([user_id, game_id, pick]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        # Get the user and game
        try:
            User = get_user_model()
            user = User.objects.get(id=user_id)
            game = GamesAndScores.objects.get(id=game_id)
        except (User.DoesNotExist, GamesAndScores.DoesNotExist):
            return JsonResponse({
                'success': False,
                'error': 'User or game not found'
            }, status=404)
        
        # Create the pick ID (same format as regular picks)
        pick_id = f"{user.id}-{game.id}"
        
        # Check if pick already exists and update or create
        pick_obj, created = GamePicks.objects.update_or_create(
            id=pick_id,
            defaults={
                'userEmail': user.email,
                'uid': user.id,
                'userID': str(user.id),
                'slug': game.slug,
                'competition': game.competition,
                'gameWeek': game.gameWeek,
                'gameyear': game.gameyear,
                'gameseason': game.gameseason,
                'pick_game_id': game.id,
                'pick': pick,
                'tieBreakerScore': int(tiebreaker_score) if tiebreaker_score else None,
                'tieBreakerYards': int(tiebreaker_yards) if tiebreaker_yards else None,
            }
        )
        
        action = "created" if created else "updated"
        return JsonResponse({
            'success': True,
            'message': f'Successfully {action} pick for {user.username}: {pick}',
            'pick_id': pick_id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid data: {str(e)}'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@commissioner_required
@require_http_methods(["GET"])
def get_user_picks(request):
    """Get existing picks for a user for the current week"""
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'User ID required'}, status=400)
    
    try:
        User = get_user_model()
        user = User.objects.get(id=user_id)
        
        # Get current week info
        today = date.today()
        gameseason = get_season()
        
        try:
            week_obj = GameWeeks.objects.get(date=today.strftime("%Y-%m-%d"))
            current_week = week_obj.weekNumber
            current_competition = week_obj.competition
        except GameWeeks.DoesNotExist:
            current_week = '1'
            current_competition = 'nfl'
        
        # Get user's picks for current week
        picks = GamePicks.objects.filter(
            userEmail=user.email,
            gameWeek=current_week,
            gameseason=gameseason,
            competition=current_competition
        )
        
        picks_data = {}
        for pick in picks:
            picks_data[str(pick.pick_game_id)] = {
                'pick': pick.pick,
                'tiebreaker_score': pick.tieBreakerScore,
                'tiebreaker_yards': pick.tieBreakerYards,
                'pick_id': pick.id
            }
        
        return JsonResponse({
            'success': True,
            'picks': picks_data,
            'username': user.username
        })
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
