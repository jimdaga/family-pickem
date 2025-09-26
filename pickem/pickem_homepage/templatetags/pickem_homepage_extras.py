from django import template
from django.contrib.auth.models import User
from pickem_api.models import Teams, GamePicks, userSeasonPoints, userStats, UserProfile, GamesAndScores
from django.shortcuts import render
from allauth.socialaccount.models import SocialAccount
from datetime import date
import requests
from pickem.utils import get_season

register = template.Library()

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
        # avatar_url = None
        avatar_url = "https://www.wmata.com/systemimages/icons/menu-car-icon.png"
    
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
    stats = userStats.objects.filter(userID=str(user_id)).first()

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
