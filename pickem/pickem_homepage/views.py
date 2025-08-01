from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks, Teams, userSeasonPoints, userStats, UserProfile
from .forms import GamePicksForm

from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from django.db.models import Count
from django.db.models.functions import Coalesce
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from datetime import date

from django.forms import formset_factory
from pickem.utils import get_season as get_season_from_api

def get_season():
    return get_season_from_api()

def index(request):
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
    
    # Get total players count
    total_players = User.objects.filter(is_active=True, is_superuser=False).count()
    
    # Get league statistics
    total_picks = GamePicks.objects.filter(gameseason=gameseason).count()
    total_correct_picks = GamePicks.objects.filter(gameseason=gameseason, pick_correct=True).count()
    
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

    context = {
        'season_winner': season_winner,
        'current_week': current_week,
        'current_competition': current_competition,
        'top_players': top_players,
        'current_week_winner': current_week_winner,
        'current_games': current_games,
        'total_players': total_players,
        'total_picks': total_picks,
        'total_correct_picks': total_correct_picks,
        'league_accuracy': league_accuracy,
        'recent_winners': recent_winners,
        'user_has_picks': user_has_picks,
        'user_picks_count': user_picks_count,
        'user_pick_status': user_pick_status,
        'gameseason': gameseason
    }
    return HttpResponse(template.render(context, request))


def standings(request):
    # Get all unique seasons from the database
    all_seasons = GamesAndScores.objects.values_list('gameseason', flat=True).distinct().order_by('-gameseason')
    
    # Determine the selected season
    selected_season = str(request.GET.get('season', get_season()))
    
    # Filter player points based on the selected season
    player_points = userSeasonPoints.objects.filter(gameseason=selected_season).order_by('-total_points')
    
    # Get season winner for the selected season
    season_winner = userSeasonPoints.objects.filter(year_winner=True, gameseason=selected_season).first()
    
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
    players = User.objects.all()

    context = {
        'players': players,
        'player_points': player_points,
        'season_winner': season_winner,
        'all_seasons': formatted_seasons,
        'selected_season': selected_season,
        'gameseason': selected_season
    }
    return render(request, 'pickem/standings.html', context)


def rules(request):
    gameseason = get_season()
    context = {'gameseason': gameseason}
    return render(request, 'pickem/rules.html', context)


def scores(request):

    today = date.today()
    today_date = today.strftime("%Y-%m-%d")
    gameseason = get_season()

    try:
        game_week = GameWeeks.objects.get(date=today_date).weekNumber
    except GameWeeks.DoesNotExist:
        game_week = '1'

    try:
        game_competition = GameWeeks.objects.get(date=today_date).competition
    except GameWeeks.DoesNotExist:
        game_competition = 'nfl'
    
    game_list = GamesAndScores.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)

    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()
    
    picks = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)

    points = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition, pick_correct=True)
    points_total = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition, pick_correct=True).count
    
    # user_points = points.values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')
    user_points = points.filter(gameseason=gameseason).values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')

    # users_w_points = user_points.values_list('uid', flat=True).distinct()
    users_w_points = user_points.filter(gameseason=gameseason).values_list('uid', flat=True).distinct()
    
    
    
    players = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)
    players_names = players.values_list('uid', flat=True).distinct()
    players_ids = User.objects.filter(is_active=True, is_superuser=False).values_list('id', flat=True).distinct()
    wins_losses = Teams.objects.filter(gameseason=gameseason)

    winner_object = "week_{}_winner".format(game_week)
    week_winner = userSeasonPoints.objects.filter(**{winner_object: True},gameseason=gameseason).distinct() 

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
        'competition': competition,
        'wins_losses': wins_losses,
        'picks': picks,
        'week': game_week,
        'user_points': user_points,
        'users_w_points': users_w_points,
        'players_names': players_names,
        'players_ids': players_ids,
        'week_winner': week_winner,
        'current_week': True,
        'points_total': points_total,
        'game_weeks': range(1,19),
        'gameseason': gameseason,
        'user_weekly_stats': user_weekly_stats
    }
    return HttpResponse(template.render(context, request))

def scores_long(request, competition, gameseason, week):
    if competition == '0':
        competition_name='nfl-preseason'
    else:
        competition_name='nfl'

    game_list = GamesAndScores.objects.filter(competition=competition_name, gameseason=gameseason, gameWeek=week)
    
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = competition_name
    
    picks = GamePicks.objects.filter(gameseason=gameseason, gameWeek=week, competition=competition_name)

    points = GamePicks.objects.filter(gameseason=gameseason, gameWeek=week, competition=competition_name, pick_correct=True)
    points_total = GamePicks.objects.filter(gameseason=gameseason, gameWeek=week, competition=competition_name, pick_correct=True).count
    # user_points = points.values('uid').order_by('-uid').annotate(wins=Count('uid')).order_by('-wins')
    user_points = points.values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')
    users_w_points = user_points.values_list('uid', flat=True).distinct()
    players = GamePicks.objects.filter(gameWeek=week, competition=competition_name)
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
        'game_weeks': range(1,19),
        'gameseason': gameseason,
        'user_weekly_stats': user_weekly_stats
    }
    return HttpResponse(template.render(context, request))

def stats(request):
    today = date.today()
    gameseason = get_season()
    
    User = get_user_model()

    # Get list of players and their rankings
    players = User.objects.all()
    player_points = userSeasonPoints.objects.filter(gameseason=gameseason).order_by('-total_points')
    
    # Get players with stats entries for Player Performance Analysis
    # Order by season accuracy (descending), then by weeks won (descending)
    player_stats = userStats.objects.all().order_by(
        '-pickPercentSeason', 
        '-weeksWonSeason',
        '-correctPickTotalSeason'
    )

    template = loader.get_template('pickem/stats.html')

    context = {
        'players': players,
        'player_points': player_points,
        'player_stats': player_stats,
        'gameseason': gameseason
    }
    return HttpResponse(template.render(context, request))

def submit_game_picks(request):
    today = date.today()
    today_date = today.strftime("%Y-%m-%d")

    try:
        game_week = GameWeeks.objects.get(date=today_date).weekNumber
    except GameWeeks.DoesNotExist:
        game_week = '1'

    try:
        game_competition = GameWeeks.objects.get(date=today_date).competition
    except GameWeeks.DoesNotExist:
        game_competition = 'nfl'

    gameseason = get_season()

    game_list = GamesAndScores.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition).distinct()
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()

    picks = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition, userEmail=request.user.email)

    pick_slugs = picks.values_list('slug', flat=True).distinct()
    pick_ids = picks.values_list('id', flat=True).distinct()

    wins_losses = Teams.objects.filter(gameseason=gameseason)

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition,
        'wins_losses': wins_losses,
        'gameseason': gameseason,
        'week': game_week,
        'picks': picks,
        'pick_slugs': pick_slugs,
        'pick_ids': pick_ids
        
    }

    if request.method == 'POST':
       form = GamePicksForm(request.POST)
       if form.is_valid():
           form.save()
           return render(request, 'pickem/picks.html', context)
    else:
        form = GamePicksForm()

    return render(request, 'pickem/picks.html', context)


@login_required
def edit_game_pick(request):
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
        
        # Get the existing pick
        try:
            existing_pick = GamePicks.objects.get(id=pick_id, userEmail=request.user.email)
        except GamePicks.DoesNotExist:
            return JsonResponse({'error': True, 'message': 'Pick not found or unauthorized'}, status=404)
        
        # Get the game to check if it's locked
        try:
            game = GamesAndScores.objects.get(id=existing_pick.pick_game_id)
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
        
        # Update the pick
        existing_pick.pick = new_pick
        if game.tieBreakerGame:
            existing_pick.tieBreakerScore = int(tiebreaker_score) if tiebreaker_score else None
            existing_pick.tieBreakerYards = int(tiebreaker_yards) if tiebreaker_yards else None
        
        existing_pick.save()
        
        # Return success response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Pick updated successfully'})
        else:
            # For non-AJAX requests, redirect back to picks page
            return redirect('game_picks')
            
    except Exception as e:
        error_msg = f'Error updating pick: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': True, 'message': error_msg}, status=500)
        else:
            # For non-AJAX requests, you might want to show an error page or redirect with error
            return JsonResponse({'error': True, 'message': error_msg}, status=500)


def rules(request):
    gameseason = get_season()
    template = loader.get_template('pickem/rules.html')
    context = {
        'gameseason': gameseason,
    }
    return HttpResponse(template.render(context, request))


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
            
            # Validate and update username if changed
            if username and username != request.user.username:
                # Server-side username validation
                if len(username) < 3 or len(username) > 20:
                    messages.error(request, 'Username must be between 3 and 20 characters.')
                elif not re.match(r'^[a-zA-Z0-9_]+$', username):
                    messages.error(request, 'Username can only contain letters, numbers, and underscores.')
                elif username.startswith('_') or username.endswith('_'):
                    messages.error(request, 'Username cannot start or end with an underscore.')
                elif '__' in username:
                    messages.error(request, 'Username cannot contain consecutive underscores.')
                elif User.objects.filter(username__iexact=username).exclude(id=request.user.id).exists():
                    messages.error(request, 'This username is already taken.')
                else:
                    # Username is valid, update it
                    request.user.username = username
                    request.user.save()
                    messages.success(request, 'Username updated successfully!')
            
            # Update profile fields
            user_profile.tagline = tagline if tagline else None
            user_profile.favorite_team = favorite_team if favorite_team else None
            user_profile.phone_number = phone_number if phone_number else None
            user_profile.save()
            
            # Success message for profile fields if no username errors
            if not messages.get_messages(request):
                messages.success(request, 'Profile updated successfully!')
            
    context = {
        'gameseason': gameseason,
        'user_profile': user_profile,
        'teams': teams,
    }
    return render(request, 'pickem/profile.html', context)


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
        if User.objects.filter(username__iexact=username).exclude(id=request.user.id).exists():
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