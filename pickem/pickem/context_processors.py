"""
Django Context Processors for Dark Mode Support

Provides theme preferences and user authentication status
to all templates for consistent dark mode functionality.
"""

from datetime import date
from pickem_api.models import UserProfile, GameWeeks, GamesAndScores, GamePicks, userSeasonPoints
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
    }
    
    if request.user.is_authenticated:
        try:
            # Get or create user profile
            user_profile, created = UserProfile.objects.get_or_create(user=request.user)
            context['user_dark_mode'] = user_profile.dark_mode
            context['user_theme_preference'] = 'dark' if user_profile.dark_mode else 'light'
            context['user_is_commissioner'] = user_profile.is_commissioner or request.user.is_superuser
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


def site_banner_context(request):
    """
    Context processor to inject active site banner into all templates.

    Provides:
    - active_banner: The currently active SiteBanner object (or None if no active banner)
    """
    try:
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

        # Get user's stored rank and stats
        if request.user.is_authenticated:
            try:
                # Get user's season points record with stored rank
                user_season = userSeasonPoints.objects.get(
                    userID=str(request.user.id),
                    gameseason=gameseason
                )
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
                    userEmail=request.user.email
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