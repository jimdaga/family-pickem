"""
Django Context Processors for Dark Mode Support

Provides theme preferences and user authentication status
to all templates for consistent dark mode functionality.
"""

from datetime import date
from django.conf import settings
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from pickem_api.authz import (
    AuthenticationRequired,
    PermissionDeniedForTenant,
    TenantNotFound,
    get_real_user_family_memberships,
    get_user_family_memberships,
    require_tenant_context,
)
from pickem_api.models import UserProfile, GameWeeks, GamesAndScores, GamePicks, userSeasonPoints
from pickem_api.models import Pool
from pickem_homepage.models import SiteBanner
from pickem.utils import get_season


def theme_context(request):
    """
    Context processor to inject theme preferences into all templates.
    
    Provides:
    - user_dark_mode: Boolean indicating user's dark mode preference
    - user_authenticated: Boolean indicating if user is logged in
    - user_theme_preference: String ('light', 'dark', or None for system default)
    """
    context = {
        'user_authenticated': request.user.is_authenticated,
        'user_dark_mode': None,
        'user_theme_preference': None,
        'user_is_commissioner': False,
        # Tenant-scoped owner flag derived from the current family membership.
        'user_is_commissioner_flag': False,
        # Stable per-deployment cache-buster for static assets (see settings).
        'static_version': settings.STATIC_VERSION,
        'debug_mode': settings.DEBUG,
    }
    
    if request.user.is_authenticated:
        try:
            # Get or create user profile
            user_profile, created = UserProfile.objects.get_or_create(user=request.user)
            context['user_dark_mode'] = user_profile.dark_mode
            context['user_theme_preference'] = 'dark' if user_profile.dark_mode else 'light'
            context['user_is_commissioner'] = user_profile.is_commissioner or request.user.is_superuser
            tenant_context = _tenant_context_from_request(request)
            membership = getattr(tenant_context, 'membership', None)
            context['user_is_commissioner_flag'] = bool(
                membership
                and getattr(membership, 'pk', None)
                and membership.role == 'owner'
            )
        except Exception as e:
            # Fallback to default values if there's any issue
            context['user_dark_mode'] = False
            context['user_theme_preference'] = 'light'
            context['user_is_commissioner'] = request.user.is_superuser if request.user.is_authenticated else False
    
    return context


def dark_mode_context(request):
    """
    Legacy context processor name for backwards compatibility.
    Delegates to theme_context.
    """
    return theme_context(request)


def _default_active_pool_for_family(family):
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


def _switcher_choice_for_membership(membership):
    family = membership.family
    pool = _default_active_pool_for_family(family)
    return {
        'membership': membership,
        'family': family,
        'pool': pool,
        'url': reverse(
            'family_pool_home',
            kwargs={'family_slug': family.slug, 'pool_slug': pool.slug},
        ) if pool else None,
    }


def _tenant_context_from_request(request):
    tenant_context = getattr(request, 'tenant_context', None)
    if tenant_context is not None:
        return tenant_context

    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return None

    resolver_match = getattr(request, 'resolver_match', None)
    kwargs = resolver_match.kwargs if resolver_match else {}
    family_slug = kwargs.get('family_slug')
    pool_slug = kwargs.get('pool_slug')
    if not family_slug:
        return None

    try:
        return require_tenant_context(
            request.user,
            family=family_slug,
            pool=pool_slug,
        )
    except (AuthenticationRequired, TenantNotFound, PermissionDeniedForTenant):
        return None
    except Exception:
        return None


def family_switcher_context(request):
    """
    Context processor for authenticated tenant navigation.

    Switcher choices are derived only from active memberships for the current
    authenticated user. Explicit tenant URLs are resolved through the Phase 2
    authorization helper before becoming current context.
    """
    context = {
        'current_family': None,
        'current_pool': None,
        'current_membership': None,
        'family_switcher_choices': [],
        'has_family_memberships': False,
        'current_user_can_submit_picks': False,
    }

    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return context

    try:
        choices = [
            _switcher_choice_for_membership(membership)
            for membership in get_real_user_family_memberships(request.user)
        ]
        context['family_switcher_choices'] = choices
        context['has_family_memberships'] = bool(choices)

        tenant_context = _tenant_context_from_request(request)

        if tenant_context is not None:
            context['current_family'] = tenant_context.family
            context['current_pool'] = tenant_context.pool
            context['current_membership'] = tenant_context.membership
            context['current_user_can_submit_picks'] = bool(
                getattr(tenant_context.membership, 'pk', None)
            )
    except (AuthenticationRequired, TenantNotFound, PermissionDeniedForTenant):
        pass
    except Exception:
        pass

    return context


def site_banner_context(request):
    """
    Context processor to inject active site banner into all templates.

    Provides:
    - active_banner: The currently active SiteBanner object (or None if no active banner)
    """
    try:
        tenant_context = _tenant_context_from_request(request)
        if tenant_context:
            now = timezone.now()
            active_banner = (
                SiteBanner.objects.filter(
                    is_active=True,
                    start_date__lte=now,
                )
                .filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
                .filter(Q(family=tenant_context.family) | Q(family__isnull=True))
                # Family-scoped banners (non-null family_id) must win over global
                # ones; nulls_last keeps the global banner as the fallback.
                .order_by(F('family_id').desc(nulls_last=True), '-priority', '-created_at')
                .first()
            )
        else:
            active_banner = SiteBanner.get_active_banner()
    except Exception:
        # If there's any database error (e.g., during migrations), return None
        active_banner = None

    return {
        'active_banner': active_banner
    }


def footer_stats_context(request):
    """
    Context processor to inject footer stats into all templates.

    Provides:
    - current_week: Current week number
    - user_current_rank: User's stored rank from database
    - user_correct_picks_week: Number of correct picks for current user this week
    """
    context = {
        'current_week': None,
        'user_current_rank': None,
        'user_correct_picks_week': None,
        'has_live_games': False,
    }

    try:
        # Get current week
        today = date.today()
        today_date = today.strftime("%Y-%m-%d")
        gameseason = get_season()

        try:
            week_obj = GameWeeks.objects.get(date=today_date)
            current_week = week_obj.weekNumber
            game_competition = week_obj.competition
        except GameWeeks.DoesNotExist:
            current_week = '1'
            game_competition = 'nfl'

        context['current_week'] = current_week
        context['has_live_games'] = GamesAndScores.objects.filter(
            gameseason=gameseason,
            statusType='inprogress',
        ).exists()

        # Ranks are only meaningful once at least one game has been scored;
        # before that everyone is trivially "#1" (e.g. first login of a season).
        season_has_scored_games = GamesAndScores.objects.filter(
            gameseason=gameseason,
            gameScored=True,
        ).exists()

        # Get user's stored rank and stats
        if request.user.is_authenticated:
            tenant_context = _tenant_context_from_request(request)
            if tenant_context is None or tenant_context.pool is None:
                return context

            try:
                # Get user's season points record with stored rank
                user_season = userSeasonPoints.objects.get(
                    userID=str(request.user.id),
                    gameseason=gameseason,
                    pool=tenant_context.pool,
                )
                if season_has_scored_games:
                    context['user_current_rank'] = user_season.current_rank
            except userSeasonPoints.DoesNotExist:
                context['user_current_rank'] = None

            try:
                # Get all games for current week
                game_list = GamesAndScores.objects.filter(
                    gameseason=gameseason,
                    gameWeek=current_week,
                    competition=game_competition
                )

                # Get user's picks for current week
                picks = GamePicks.objects.filter(
                    gameseason=gameseason,
                    gameWeek=current_week,
                    competition=game_competition,
                    userEmail=request.user.email,
                    pool=tenant_context.pool,
                )

                # Count correct picks for finished games only
                finished_games_slugs = game_list.filter(statusType='finished').values_list('slug', flat=True)
                user_picks_for_finished_games = picks.filter(slug__in=finished_games_slugs)
                correct_graded_picks = user_picks_for_finished_games.filter(pick_correct=True).count()

                context['user_correct_picks_week'] = correct_graded_picks
            except Exception:
                context['user_correct_picks_week'] = 0

    except Exception:
        # If there's any error, return default values
        pass

    return context 
