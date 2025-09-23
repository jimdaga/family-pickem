"""
Django Context Processors for Dark Mode Support

Provides theme preferences and user authentication status
to all templates for consistent dark mode functionality.
"""

from pickem_api.models import UserProfile
from pickem_homepage.models import SiteBanner


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
    }
    
    if request.user.is_authenticated:
        try:
            # Get or create user profile
            user_profile, created = UserProfile.objects.get_or_create(user=request.user)
            context['user_dark_mode'] = user_profile.dark_mode
            context['user_theme_preference'] = 'dark' if user_profile.dark_mode else 'light'
        except Exception as e:
            # Fallback to default values if there's any issue
            context['user_dark_mode'] = False
            context['user_theme_preference'] = 'light'
    
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