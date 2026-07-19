from django import template
from django.contrib.auth.models import User
from django.utils.text import capfirst
from pickem_api.models import Teams, GamePicks, userSeasonPoints, userStats, UserProfile, GamesAndScores
from django.shortcuts import render
from allauth.socialaccount.models import SocialAccount
from datetime import date
from django.utils import timezone
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
import requests
import re
from pickem.utils import get_season

register = template.Library()


@register.filter(is_safe=True)
def safe_markdown(value):
    """Render a small, deliberately safe Markdown subset.

    Escaping happens before any Markdown transforms, so raw HTML (including
    scripts and event attributes) is always text. Links only allow http(s),
    mailto, and local paths. This avoids granting lobby authors an HTML
    execution surface while supporting the useful message-writing basics.
    """
    import re
    from urllib.parse import urlparse

    text = conditional_escape(value or '')

    def link(match):
        label, url = match.group(1), match.group(2)
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {'http', 'https', 'mailto', ''}:
            return label
        if not parsed.scheme and not url.startswith(('/', '#')):
            return label
        return f'<a href="{url}" rel="nofollow noopener noreferrer" class="text-primary underline">{label}</a>'

    text = re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', link, text)
    text = re.sub(r'`([^`]+)`', r'<code class="rounded bg-black/5 px-1 py-0.5 dark:bg-white/10">\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*|__([^_]+)__', lambda m: f'<strong>{m.group(1) or m.group(2)}</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)|(?<!_)_([^_]+)_(?!_)', lambda m: f'<em>{m.group(1) or m.group(2)}</em>', text)

    blocks, list_items, ordered_list_items = [], [], []
    def flush_list():
        if list_items:
            blocks.append('<ul class="my-3 list-disc space-y-1 pl-5">' + ''.join(f'<li>{item}</li>' for item in list_items) + '</ul>')
            list_items.clear()
        if ordered_list_items:
            blocks.append('<ol class="my-3 list-decimal space-y-1 pl-5">' + ''.join(f'<li>{item}</li>' for item in ordered_list_items) + '</ol>')
            ordered_list_items.clear()
    for line in text.splitlines():
        heading = re.match(r'^(#{1,3})\s+(.+)$', line)
        bullet = re.match(r'^[-*]\s+(.+)$', line)
        numbered = re.match(r'^\d+[.)]\s+(.+)$', line)
        if heading:
            flush_list()
            level = len(heading.group(1))
            blocks.append(f'<h{level} class="mt-4 font-bold text-text-dark dark:text-white">{heading.group(2)}</h{level}>')
        elif bullet:
            list_items.append(bullet.group(1))
        elif numbered:
            ordered_list_items.append(numbered.group(1))
        elif line.strip():
            flush_list()
            blocks.append(f'<p class="my-2">{line}</p>')
        else:
            flush_list()
    flush_list()
    return mark_safe('\n'.join(blocks))

@register.filter
def display_name(user):
    """Return a consistent display name for a Django user-like object."""
    if not user:
        return ""

    name = ""
    try:
        social_account = user.socialaccount_set.first()
        if social_account:
            name = social_account.extra_data.get("given_name") or ""
    except Exception:
        name = ""

    if not name:
        name = getattr(user, "first_name", "") or getattr(user, "username", "") or ""

    # capfirst uppercases only the first character, leaving the rest intact so
    # names like "McCoy" are not mangled while "smith-player" reads as "Smith-player".
    return capfirst(str(name).strip())

@register.filter
def season_year_range(value):
    """Format YYZZ season values like 2627 as 2026 - 2027."""
    if value in (None, ""):
        return ""

    raw = str(value).strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    if not raw.isdigit():
        return value

    raw = raw.zfill(4)
    if len(raw) != 4:
        return value

    return f"20{raw[:2]} - 20{raw[2:]}"

@register.filter
def addstr(arg1, arg2):
    """concatenate arg1 & arg2"""
    return str(arg1) + str(arg2)

@register.filter
def lookupname(id):
    user = User.objects.get(id=id)
    return user

@register.filter
def lookupavatar(user_id):
    try:
        social_account = SocialAccount.objects.get(user_id=user_id)
        avatar_url = social_account.get_avatar_url()
    except SocialAccount.DoesNotExist:
        # Try to get user email for Gravatar fallback
        try:
            from django.contrib.auth.models import User
            import hashlib
            user = User.objects.get(id=user_id)
            email_hash = hashlib.md5(user.email.lower().encode('utf-8')).hexdigest()
            avatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=64"
        except User.DoesNotExist:
            avatar_url = "https://www.gravatar.com/avatar/?d=identicon&s=64"
    
    return avatar_url

@register.filter
def lookuplogo(slug):
    if slug != None:
        # Handle comma-separated team names (ties) by taking the first team
        if ',' in slug:
            first_team_slug = slug.split(',')[0].strip()
            try:
                logo = Teams.objects.get(teamNameSlug=first_team_slug)
            except Teams.DoesNotExist:
                logo = {
                    'teamLogo': None
                }
        else:
            try:
                logo = Teams.objects.get(teamNameSlug=slug)
            except Teams.DoesNotExist:
                logo = {
                    'teamLogo': None
                }
    else:
        logo = {
            'teamLogo': None
        }
    return logo


def _team_brand_value(team, key, default=None):
    if isinstance(team, dict):
        return team.get(key, default)
    return getattr(team, key, default)


def _normalize_team_hex_color(value, fallback):
    color = str(value or "").strip().lstrip("#")
    if len(color) == 3 and re.fullmatch(r"[0-9a-fA-F]{3}", color):
        color = "".join(character * 2 for character in color)

    if re.fullmatch(r"[0-9a-fA-F]{6}", color):
        return color.upper()
    return fallback


@register.filter
def team_brand_presentation(team):
    primary_color = _normalize_team_hex_color(
        _team_brand_value(team, "color"),
        "333333",
    )
    alternate_color = _normalize_team_hex_color(
        _team_brand_value(team, "alternateColor"),
        "666666",
    )
    preset = (
        _team_brand_value(team, "logo_contrast_preset")
        or Teams.LogoContrastPreset.DEFAULT
    )

    gradient_primary = primary_color
    gradient_alternate = alternate_color
    if preset == Teams.LogoContrastPreset.REVERSE_GRADIENT:
        gradient_primary, gradient_alternate = alternate_color, primary_color

    background_style = (
        "background: linear-gradient("
        f"135deg, #{gradient_alternate}40 0%, #{gradient_primary} 50%, #{gradient_primary} 100%);"
    )
    show_white_burst = preset == Teams.LogoContrastPreset.WHITE_BURST
    logo_style = ""
    if show_white_burst:
        logo_style = (
            "filter: drop-shadow(0 0 18px rgba(255, 255, 255, 0.55)) "
            "drop-shadow(0 0 8px rgba(255, 255, 255, 0.35));"
        )

    return {
        "preset": preset,
        "background_style": background_style,
        "show_white_burst": show_white_burst,
        "logo_style": logo_style,
    }

@register.filter
def has_multiple_teams(team_string):
    """Check if a team string contains multiple teams (comma-separated)"""
    if not team_string:
        return False
    return ',' in str(team_string)

@register.filter
def count_teams(team_string):
    """Count the number of teams in a comma-separated team string"""
    if not team_string:
        return 0
    return len([team.strip() for team in str(team_string).split(',') if team.strip()])

@register.filter
def get_team_names(team_string):
    """Get the team names from a comma-separated team slug string"""
    if not team_string:
        return ""
    
    team_slugs = [team.strip() for team in str(team_string).split(',') if team.strip()]
    if len(team_slugs) <= 1:
        # Single team - look up the name
        try:
            team = Teams.objects.get(teamNameSlug=str(team_string).strip())
            return team.teamNameName
        except Teams.DoesNotExist:
            return str(team_string)
    
    # Multiple teams - look up all names
    team_names = []
    for slug in team_slugs:
        try:
            team = Teams.objects.get(teamNameSlug=slug)
            team_names.append(team.teamNameName)
        except Teams.DoesNotExist:
            team_names.append(slug)  # Fallback to slug if not found
    
    return ", ".join(team_names)

@register.filter
def lookuppick(id):
    pick = GamePicks.objects.filter(id=id).distinct()
    return pick.count


@register.filter
def contains(collection, value):
    """True if value is in collection (set/list/dict). Used to flag missing
    picks on the scores page from a precomputed set of picked keys."""
    if collection is None:
        return False
    return value in collection


@register.filter(name='times')
def times(number):
    return range(1, number+1)

@register.filter
def lookweekwinner(weekno, gameseason):
    if not gameseason:
        gameseason=get_season()
    winner_object = "week_{}_winner".format(weekno)
    week_winner = userSeasonPoints.objects.filter(**{winner_object: True},gameseason=gameseason).distinct() 
    return week_winner

@register.filter
def get_week_points(player, week_num):
    """Get points for a specific week dynamically"""
    if not player or not week_num:
        return None
    field_name = f'week_{week_num}_points'
    return getattr(player, field_name, None)

@register.filter
def get_week_winner(player, week_num):
    """Check if player won a specific week dynamically"""
    if not player or not week_num:
        return False
    field_name = f'week_{week_num}_winner'
    return getattr(player, field_name, False)

@register.filter
def safe_username(user_id):
    """Safely get username with fallback"""
    try:
        user = User.objects.get(id=user_id)
        return user.username if hasattr(user, 'username') and user.username else user.email.split('@')[0] if user.email else f"User {user_id}"
    except User.DoesNotExist:
        return f"Unknown User"
    except Exception:
        return f"User {user_id}"

@register.filter
def lookupStats(user_id):
    # The global all-time stats row is the pool-null one. Per-pool rows (written
    # by a superadmin pool recompute) must not shadow it here.
    stats = userStats.objects.filter(userID=str(user_id), pool__isnull=True).first()

    weeksWonSeason = stats.weeksWonSeason if stats else '0'
    weeksWonTotal = stats.weeksWonTotal if stats else '0'
    pickPercentSeason = stats.pickPercentSeason if stats else '0'
    pickPercentTotal = stats.pickPercentTotal if stats else '0'
    correctPickTotalSeason = stats.correctPickTotalSeason if stats else '0'
    correctPickTotalTotal = stats.correctPickTotalTotal if stats else '0'
    totalPicksSeason = stats.totalPicksSeason if stats else '0'
    totalPicksTotal = stats.totalPicksTotal if stats else '0'
    mostPickedSeason = stats.mostPickedSeason if stats else None
    mostPickedTotal = stats.mostPickedTotal if stats else None
    leastPickedSeason = stats.leastPickedSeason if stats else None
    leastPickedTotal = stats.leastPickedTotal if stats else None
    seasonsWon = stats.seasonsWon if stats else None
    missedPicksSeason = stats.missedPicksSeason if stats else '0'
    missedPicksTotal = stats.missedPicksTotal if stats else '0'
    perfectWeeksSeason = stats.perfectWeeksSeason if stats else '0'
    perfectWeeksTotal = stats.perfectWeeksTotal if stats else '0'


    data = {
        'weeksWonSeason': weeksWonSeason,
        'weeksWonTotal': weeksWonTotal,
        'pickPercentSeason': pickPercentSeason,
        'pickPercentTotal': pickPercentTotal,
        'correctPickTotalSeason': correctPickTotalSeason,
        'correctPickTotalTotal': correctPickTotalTotal,
        'totalPicksSeason': totalPicksSeason,
        'totalPicksTotal': totalPicksTotal,
        'mostPickedSeason': mostPickedSeason,
        'mostPickedTotal': mostPickedTotal,
        'leastPickedSeason': leastPickedSeason,
        'leastPickedTotal': leastPickedTotal,
        'seasonsWon': seasonsWon,
        'missedPicksSeason': missedPicksSeason,
        'missedPicksTotal': missedPicksTotal,
        'perfectWeeksSeason': perfectWeeksSeason,
        'perfectWeeksTotal': perfectWeeksTotal,
    }

    return data

@register.filter
def mul(value, arg):
    """Multiply the value by the argument"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """Subtract the argument from the value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def lookuptagline(user_id):
    """Get user's tagline from UserProfile, default to 'League Member' if not set"""
    try:
        user = User.objects.get(id=user_id)
        profile = UserProfile.objects.get(user=user)
        return profile.tagline if profile.tagline else "League Member"
    except (User.DoesNotExist, UserProfile.DoesNotExist):
        return "League Member"

@register.filter
def is_game_locked(game):
    """Check if picks are locked for a specific game using new Sunday 1PM EST logic"""
    try:
        from pickem.utils import is_pick_locked
        # Get all games in the same week
        week_games = GamesAndScores.objects.filter(
            gameseason=game.gameseason,
            gameWeek=game.gameWeek,
            competition=game.competition
        )
        is_locked, lock_reason = is_pick_locked(game, week_games)
        return is_locked
    except:
        # Fallback to old logic if there's an error
        return game.statusType != 'notstarted'

@register.filter
def is_game_locked_for_pool(game, pool):
    """Check if picks are locked for a game using the current pool settings."""
    try:
        from pickem.utils import is_pick_locked_for_pool
        week_games = GamesAndScores.objects.filter(
            gameseason=game.gameseason,
            gameWeek=game.gameWeek,
            competition=game.competition
        )
        is_locked, _lock_reason = is_pick_locked_for_pool(game, pool, week_games)
        return is_locked
    except ImportError:
        return is_game_locked(game)

@register.filter
def game_lock_reason(game):
    """Get the reason why picks are locked for a specific game"""
    try:
        from pickem.utils import is_pick_locked
        # Get all games in the same week
        week_games = GamesAndScores.objects.filter(
            gameseason=game.gameseason,
            gameWeek=game.gameWeek,
            competition=game.competition
        )
        is_locked, lock_reason = is_pick_locked(game, week_games)
        return lock_reason if is_locked else "Available"
    except:
        # Fallback to old logic if there's an error
        return "Game has started" if game.statusType != 'notstarted' else "Available"

@register.filter
def game_lock_reason_for_pool(game, pool):
    """Get the lock reason for a game using the current pool settings."""
    try:
        from pickem.utils import is_pick_locked_for_pool
        week_games = GamesAndScores.objects.filter(
            gameseason=game.gameseason,
            gameWeek=game.gameWeek,
            competition=game.competition
        )
        is_locked, lock_reason = is_pick_locked_for_pool(game, pool, week_games)
        return lock_reason if is_locked else "Available"
    except ImportError:
        return game_lock_reason(game)


@register.filter
def game_start_label(game):
    """Render a friendly game start label for scheduled games."""
    try:
        start_timestamp = getattr(game, 'startTimestamp', game)
        status_type = getattr(game, 'statusType', 'notstarted')
        start_local = timezone.localtime(start_timestamp)
        if status_type == 'notstarted' and start_local.hour == 0 and start_local.minute == 0:
            return "Upcoming"
        return start_local.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return "Upcoming" if getattr(game, 'statusType', 'notstarted') == 'notstarted' else ""

@register.filter
def block_is_stale_final(games, kickoff):
    """True when every game in a kickoff block is final and roughly two hours
    have passed since the last one ended, so the block can collapse by default.

    Game end times aren't stored, so the end is estimated as kickoff plus an
    average NFL game length (~3h20m); two hours after that is kickoff + 5h20m.
    """
    from datetime import timedelta

    try:
        games = list(games)
        if not games:
            return False
        if any(getattr(g, 'statusType', '') != 'finished' for g in games):
            return False
        return timezone.now() >= kickoff + timedelta(hours=5, minutes=20)
    except Exception:
        return False


@register.simple_tag
def week_lock_status(games):
    """Get the overall locking status for a week of games"""
    try:
        from pickem.utils import are_picks_locked_for_week
        return are_picks_locked_for_week(games)
    except:
        return {
            'any_locked': False,
            'sunday_cutoff_passed': False,
            'sunday_cutoff_time': None,
            'individual_locks': {}
        }

@register.filter
def lookup(dictionary, key):
    """Look up a value in a dictionary using a key"""
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None


@register.filter
def message_icon(tag):
    """Return Font Awesome icon for message tags"""
    icon_map = {
        'success': 'check-circle',
        'info': 'info-circle', 
        'warning': 'exclamation-triangle',
        'error': 'times-circle',
        'danger': 'times-circle',
    }
    return icon_map.get(tag, 'info-circle')
