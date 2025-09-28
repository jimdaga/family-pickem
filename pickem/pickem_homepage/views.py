from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks, Teams, userSeasonPoints, userStats, UserProfile
from .forms import GamePicksForm, MessageBoardPostForm, MessageBoardCommentForm, QuickCommentForm
from .models import MessageBoardPost, MessageBoardComment, MessageBoardVote

from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Count, Q, Avg
from django.db.models.functions import Coalesce
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
# from django_ratelimit.decorators import ratelimit  # Disabled for now
import json

from datetime import date

from django.forms import formset_factory
from pickem.utils import get_season as get_season_from_api

def get_season(display_name=False):
    return get_season_from_api(display_name=display_name)

# @ratelimit(key='ip', rate='30/m', method='GET', block=True)  # Disabled for now
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
    
    # Get league statistics - only count picks for finished games
    finished_games = GamesAndScores.objects.filter(gameseason=gameseason, statusType='finished')
    finished_game_slugs = finished_games.values_list('slug', flat=True)
    total_picks = GamePicks.objects.filter(gameseason=gameseason, slug__in=finished_game_slugs).count()
    total_correct_picks = GamePicks.objects.filter(gameseason=gameseason, slug__in=finished_game_slugs, pick_correct=True).count()
    
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
        'total_players': total_players,
        'total_picks': total_picks,
        'total_correct_picks': total_correct_picks,
        'league_accuracy': league_accuracy,
        'recent_winners': recent_winners,
        'user_has_picks': user_has_picks,
        'user_picks_count': user_picks_count,
        'user_pick_status': user_pick_status,
        'gameseason': gameseason,
        # Message board data
        'message_posts': message_posts,
        'user_votes': user_votes,
        'post_form': post_form,
        'user_achievements': user_achievements,
        'user_rankings': user_rankings,
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

    # Track if we're defaulting to week 1 (before season starts)
    is_default_week = False
    try:
        week_obj = GameWeeks.objects.get(date=today_date)
        game_week = week_obj.weekNumber
        game_competition = week_obj.competition
    except GameWeeks.DoesNotExist:
        game_week = '1'
        game_competition = 'nfl'
        is_default_week = True
    
    game_list = GamesAndScores.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)

    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()
    
    picks = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)
    picks_total = picks.count()

    points = GamePicks.objects.filter(
        gameseason=gameseason,
        gameWeek=game_week,
        competition=game_competition,
        pick_correct=True,
    )
    points_total = points.count()
    
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
        'competition': game_competition,
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
        'show_week_stats_sidebar': picks_total > 0,
        'game_weeks': range(1,19),
        'gameseason': gameseason,
        'user_weekly_stats': user_weekly_stats,
        'is_default_week': is_default_week
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

    # Track if we're defaulting to week 1 (before season starts)
    is_default_week = False
    try:
        week_obj = GameWeeks.objects.get(date=today_date)
        game_week = week_obj.weekNumber
        game_competition = week_obj.competition
    except GameWeeks.DoesNotExist:
        game_week = '1'
        game_competition = 'nfl'
        is_default_week = True

    gameseason = get_season()

    game_list = GamesAndScores.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition).distinct()
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()

    # Handle unauthenticated users gracefully
    if request.user.is_authenticated:
        picks = GamePicks.objects.filter(
            gameseason=gameseason,
            gameWeek=game_week,
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
        'auth_required': not request.user.is_authenticated
        
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
                elif User.objects.filter(username=username).exclude(id=request.user.id).exists():
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
    """Public user profile page showing stats and achievements"""
    # Get the user whose profile we're viewing
    profile_user = get_object_or_404(User, id=user_id)
    gameseason = get_season()
    gameseason_display = get_season(display_name=True)
    
    # Get or create user profile
    user_profile, created = UserProfile.objects.get_or_create(user=profile_user)
    
    # Check if profile is private (only show to the owner)
    if user_profile.private_profile and request.user != profile_user:
        # Get teams data for the private profile page
        teams = Teams.objects.values('teamNameSlug', 'teamNameName', 'teamLogo').distinct().order_by('teamNameName')
        return render(request, 'pickem/user_profile_private.html', {
            'profile_user': profile_user,
            'user_profile': user_profile,
            'teams': teams
        })
    
    # Get user's season points data
    season_points = userSeasonPoints.objects.filter(userID=str(user_id), gameseason=gameseason).first()
    all_season_points = userSeasonPoints.objects.filter(userID=str(user_id))
    
    # Get user stats
    user_stats_obj = userStats.objects.filter(userID=str(user_id)).first()
    
    # Calculate fun stats
    stats = {
        'seasons_won': 0,
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
    
    # Seasons won
    seasons_won = userSeasonPoints.objects.filter(userID=str(user_id), year_winner=True).count()
    stats['seasons_won'] = seasons_won
    
    # Current season data
    if season_points:
        stats['current_season_points'] = season_points.total_points or 0
        
        # Count weeks won this season
        weeks_won_this_season = 0
        for week in range(1, 19):  # NFL has up to 18 weeks
            if hasattr(season_points, f'week_{week}_winner'):
                if getattr(season_points, f'week_{week}_winner', False):
                    weeks_won_this_season += 1
        stats['weeks_won_current_season'] = weeks_won_this_season
        
        # Get perfect weeks from userStats (authoritative source)
        if user_stats_obj:
            stats['perfect_weeks'] = user_stats_obj.perfectWeeksSeason or 0
        else:
            stats['perfect_weeks'] = 0
    
    # Lifetime stats
    if all_season_points.exists():
        # Total lifetime points
        total_points = all_season_points.aggregate(
            total=Coalesce(Sum('total_points'), 0)
        )['total']
        stats['total_lifetime_points'] = total_points
        
        # Best season
        best_season = all_season_points.order_by('-total_points').first()
        if best_season:
            stats['best_season_points'] = best_season.total_points or 0
            
            # Calculate best rank achieved
            # Get all users' points for the same season to determine ranking
            season_standings = userSeasonPoints.objects.filter(
                gameseason=best_season.gameseason
            ).order_by('-total_points')
            
            best_rank = None
            for rank, standing in enumerate(season_standings, 1):
                if standing.userID == str(user_id):
                    best_rank = rank
                    break
            
            stats['best_rank'] = best_rank
        
        # Total weeks won across all seasons
        total_weeks_won = 0
        for season in all_season_points:
            for week in range(1, 19):
                if hasattr(season, f'week_{week}_winner'):
                    if getattr(season, f'week_{week}_winner', False):
                        total_weeks_won += 1
        stats['weeks_won_total'] = total_weeks_won
        
        # Years playing
        stats['years_playing'] = all_season_points.values('gameseason').distinct().count()
    
    # Calculate team pick statistics for pie chart (current season only to match stats page)
    user_picks = GamePicks.objects.filter(userID=str(user_id), gameseason=gameseason)
    team_pick_stats = user_picks.values('pick').annotate(
        count=Count('pick')
    ).order_by('-count')
    
    # Convert to percentage and format for chart
    total_picks = user_picks.count()
    team_chart_data = []
    team_chart_labels = []
    team_chart_colors = []
    team_chart_slugs = []
    team_chart_logos = []
    
    # Debug print
    print(f"DEBUG: User {user_id} has {total_picks} total picks")
    print(f"DEBUG: Team pick stats: {list(team_pick_stats)}")
    
    # NFL team slug to abbreviation mapping
    team_abbreviations = {
        'arizona-cardinals': 'ARI',
        'atlanta-falcons': 'ATL',
        'baltimore-ravens': 'BAL',
        'buffalo-bills': 'BUF',
        'carolina-panthers': 'CAR',
        'chicago-bears': 'CHI',
        'cincinnati-bengals': 'CIN',
        'cleveland-browns': 'CLE',
        'dallas-cowboys': 'DAL',
        'denver-broncos': 'DEN',
        'detroit-lions': 'DET',
        'green-bay-packers': 'GB',
        'houston-texans': 'HOU',
        'indianapolis-colts': 'IND',
        'jacksonville-jaguars': 'JAX',
        'kansas-city-chiefs': 'KC',
        'las-vegas-raiders': 'LV',
        'los-angeles-chargers': 'LAC',
        'los-angeles-rams': 'LAR',
        'miami-dolphins': 'MIA',
        'minnesota-vikings': 'MIN',
        'new-england-patriots': 'NE',
        'new-orleans-saints': 'NO',
        'new-york-giants': 'NYG',
        'new-york-jets': 'NYJ',
        'philadelphia-eagles': 'PHI',
        'pittsburgh-steelers': 'PIT',
        'san-francisco-49ers': 'SF',
        'seattle-seahawks': 'SEA',
        'tampa-bay-buccaneers': 'TB',
        'tennessee-titans': 'TEN',
        'washington-commanders': 'WAS',
    }
    
    # NFL team colors mapping (simplified)
    team_colors = {
        'arizona-cardinals': '#97233F',
        'atlanta-falcons': '#A71930',
        'baltimore-ravens': '#241773',
        'buffalo-bills': '#00338D',
        'carolina-panthers': '#0085CA',
        'chicago-bears': '#0B162A',
        'cincinnati-bengals': '#FB4F14',
        'cleveland-browns': '#311D00',
        'dallas-cowboys': '#003594',
        'denver-broncos': '#FB4F14',
        'detroit-lions': '#0076B6',
        'green-bay-packers': '#203731',
        'houston-texans': '#03202F',
        'indianapolis-colts': '#002C5F',
        'jacksonville-jaguars': '#006778',
        'kansas-city-chiefs': '#E31837',
        'las-vegas-raiders': '#000000',
        'los-angeles-chargers': '#0080C6',
        'los-angeles-rams': '#003594',
        'miami-dolphins': '#008E97',
        'minnesota-vikings': '#4F2683',
        'new-england-patriots': '#002244',
        'new-orleans-saints': '#D3BC8D',
        'new-york-giants': '#0B2265',
        'new-york-jets': '#125740',
        'philadelphia-eagles': '#004C54',
        'pittsburgh-steelers': '#FFB612',
        'san-francisco-49ers': '#AA0000',
        'seattle-seahawks': '#002244',
        'tampa-bay-buccaneers': '#D50A0A',
        'tennessee-titans': '#0C2340',
        'washington-commanders': '#5A1414',
    }
    
    # Modern gradient color palette for glassmorphism design
    modern_colors = [
        'rgba(99, 102, 241, 0.8)',   # Indigo
        'rgba(168, 85, 247, 0.8)',   # Purple  
        'rgba(236, 72, 153, 0.8)',   # Pink
        'rgba(245, 158, 11, 0.8)',   # Amber
        'rgba(34, 197, 94, 0.8)',    # Green
        'rgba(6, 182, 212, 0.8)',    # Cyan
        'rgba(239, 68, 68, 0.8)',    # Red
        'rgba(139, 92, 246, 0.8)',   # Violet
        'rgba(14, 165, 233, 0.8)',   # Blue
        'rgba(251, 146, 60, 0.8)',   # Orange
        'rgba(16, 185, 129, 0.8)',   # Emerald
        'rgba(244, 63, 94, 0.8)',    # Rose
        'rgba(124, 58, 237, 0.8)',   # Indigo Variant
        'rgba(59, 130, 246, 0.8)',   # Blue Variant
        'rgba(34, 197, 94, 0.8)',    # Green Variant
        'rgba(249, 115, 22, 0.8)'    # Orange Variant
    ]
    
    # Corresponding border colors with full opacity
    modern_border_colors = [
        'rgb(99, 102, 241)',   # Indigo
        'rgb(168, 85, 247)',   # Purple  
        'rgb(236, 72, 153)',   # Pink
        'rgb(245, 158, 11)',   # Amber
        'rgb(34, 197, 94)',    # Green
        'rgb(6, 182, 212)',    # Cyan
        'rgb(239, 68, 68)',    # Red
        'rgb(139, 92, 246)',   # Violet
        'rgb(14, 165, 233)',   # Blue
        'rgb(251, 146, 60)',   # Orange
        'rgb(16, 185, 129)',   # Emerald
        'rgb(244, 63, 94)',    # Rose
        'rgb(124, 58, 237)',   # Indigo Variant
        'rgb(59, 130, 246)',   # Blue Variant
        'rgb(34, 197, 94)',    # Green Variant
        'rgb(249, 115, 22)'    # Orange Variant
    ]
    
    if total_picks > 0:
        for i, team_stat in enumerate(team_pick_stats):
            team_slug = team_stat['pick']
            pick_count = team_stat['count']
            percentage = round((pick_count / total_picks) * 100, 1)
            
            # Get team abbreviation from mapping, fallback to cleaned name if not found
            display_name = team_abbreviations.get(team_slug, team_slug.replace('-', ' ').title())
            
            # Get team logo URL and resize it
            try:
                team_obj = Teams.objects.get(teamNameSlug=team_slug)
                if team_obj.teamLogo:
                    # Convert ESPN 500px logos to smaller 64px versions for better performance
                    logo_url = team_obj.teamLogo.replace('/500/', '/64/') if '/500/' in team_obj.teamLogo else team_obj.teamLogo
                else:
                    logo_url = '/static/images/nfl.svg'
            except Teams.DoesNotExist:
                logo_url = '/static/images/nfl.svg'
            
            team_chart_data.append(percentage)
            team_chart_labels.append(display_name)
            team_chart_slugs.append(team_slug)
            team_chart_logos.append(logo_url)
            # Use modern colors cycling through the palette
            color_index = i % len(modern_colors)
            team_chart_colors.append(modern_colors[color_index])
    else:
        # Add sample data for testing when user has no picks yet
        print(f"DEBUG: No picks found for user {user_id}, adding sample data")
        team_chart_data = [35.2, 18.7, 15.3, 12.8, 8.5, 9.5]
        team_chart_labels = ['NE', 'DAL', 'GB', 'KC', 'BUF', 'Other']
        team_chart_slugs = ['new-england-patriots', 'dallas-cowboys', 'green-bay-packers', 'kansas-city-chiefs', 'buffalo-bills', 'other']
        team_chart_logos = ['/static/images/nfl.svg', '/static/images/nfl.svg', '/static/images/nfl.svg', '/static/images/nfl.svg', '/static/images/nfl.svg', '/static/images/nfl.svg']
        team_chart_colors = modern_colors[:6]  # Use first 6 modern colors
    
    # Find teams tied for most picked (same percentage)
    most_picked_teams = []
    if team_chart_data:
        max_percentage = team_chart_data[0]  # Highest percentage (first in sorted list)
        for i, percentage in enumerate(team_chart_data):
            if percentage == max_percentage:
                most_picked_teams.append({
                    'slug': team_chart_slugs[i],
                    'label': team_chart_labels[i],
                    'percentage': percentage
                })
            else:
                break  # Since it's sorted, we can stop at first lower percentage
    
    # User stats data
    if user_stats_obj:
        stats['pick_accuracy_current'] = user_stats_obj.pickPercentSeason or 0
        stats['pick_accuracy_lifetime'] = user_stats_obj.pickPercentTotal or 0
        stats['total_picks_made'] = user_stats_obj.totalPicksTotal or 0
        stats['correct_picks'] = user_stats_obj.correctPickTotalTotal or 0
    
    # Favorite team info
    if user_profile.favorite_team:
        try:
            favorite_team = Teams.objects.filter(teamNameSlug=user_profile.favorite_team).first()
            if favorite_team:
                stats['favorite_team'] = favorite_team.teamNameName
                stats['favorite_team_logo'] = favorite_team.teamLogo
        except Teams.DoesNotExist:
            pass
    
    # Current season ranking
    if season_points:
        current_rank = userSeasonPoints.objects.filter(
            gameseason=gameseason,
            total_points__gt=season_points.total_points
        ).count() + 1
        stats['current_season_rank'] = current_rank
    
    # Recent activity - last 5 weeks of picks
    recent_picks = GamePicks.objects.filter(
        userID=str(user_id),
        gameseason=gameseason
    ).select_related().order_by('-gameWeek')[:5]
    
    # Get user's message board posts count
    posts_count = MessageBoardPost.objects.filter(user_id=user_id).count()
    
    context = {
        'profile_user': profile_user,
        'user_profile': user_profile,
        'stats': stats,
        'recent_picks': recent_picks,
        'posts_count': posts_count,
        'gameseason': gameseason,
        'gameseason_display': gameseason_display,
        'is_own_profile': request.user == profile_user,
        'team_chart_data': team_chart_data,
        'team_chart_labels': team_chart_labels,
        'team_chart_colors': team_chart_colors,
        'team_chart_slugs': team_chart_slugs,
        'team_chart_logos': team_chart_logos,
        'most_picked_teams': most_picked_teams,
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


# =============================================================================
# MESSAGE BOARD VIEWS
# =============================================================================

@login_required
# @ratelimit(key='user', rate='10/m', method='POST', block=True)  # Disabled for now
@require_http_methods(["POST"])
def create_post(request):
    """Create a new message board post (chat-style)"""
    content = request.POST.get('content', '').strip()
    title = request.POST.get('title', '').strip()
    
    # If no title provided, auto-generate from content
    if not title and content:
        title = content[:50] + ('...' if len(content) > 50 else '')
    
    # Validate content
    if not content:
        return JsonResponse({
            'success': False,
            'errors': {'content': ['This field is required.']}
        }, status=400)
    
    if len(content) > 2000:  # Reasonable limit for chat messages
        return JsonResponse({
            'success': False,
            'errors': {'content': ['Message too long. Please keep it under 2000 characters.']}
        }, status=400)
    
    # Create the post
    try:
        post = MessageBoardPost.objects.create(
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
    """Create a new comment on a post"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        parent_id = data.get('parent_id')  # For nested comments
        content = data.get('content', '').strip()
        
        if not content:
            return JsonResponse({
                'success': False,
                'error': 'Comment content is required'
            }, status=400)
        
        # Get the post
        post = get_object_or_404(MessageBoardPost, id=post_id, is_active=True)
        
        # Get parent comment if this is a reply
        parent = None
        if parent_id:
            parent = get_object_or_404(MessageBoardComment, id=parent_id, is_active=True)
        
        # Create the comment
        comment = MessageBoardComment.objects.create(
            post=post,
            user=request.user,
            parent=parent,
            content=content
        )
        
        # Get user avatar for response
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
                'parent_id': parent_id
            }
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


@login_required
# @ratelimit(key='user', rate='30/m', method='POST', block=True)  # Disabled for now
@require_http_methods(["POST"])
def vote_post(request):
    """Vote on a post (upvote/downvote)"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        vote_type = data.get('vote_type')  # 1 for upvote, -1 for downvote
        
        if vote_type not in [1, -1]:
            return JsonResponse({
                'success': False,
                'error': 'Invalid vote type'
            }, status=400)
        
        post = get_object_or_404(MessageBoardPost, id=post_id, is_active=True)
        
        # Check if user already voted
        existing_vote = MessageBoardVote.objects.filter(user=request.user, post=post).first()
        
        if existing_vote:
            if existing_vote.vote_type == vote_type:
                # Remove vote if clicking same button
                existing_vote.delete()
                action = 'removed'
            else:
                # Change vote
                existing_vote.vote_type = vote_type
                existing_vote.save()
                action = 'changed'
        else:
            # Create new vote
            MessageBoardVote.objects.create(
                user=request.user,
                post=post,
                vote_type=vote_type
            )
            action = 'added'
        
        # Refresh post to get updated vote counts
        post.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'action': action,
            'score': post.score,
            'upvotes': post.upvotes,
            'downvotes': post.downvotes
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


@login_required
# @ratelimit(key='user', rate='30/m', method='POST', block=True)  # Disabled for now
@require_http_methods(["POST"])
def vote_comment(request):
    """Vote on a comment (upvote/downvote)"""
    try:
        data = json.loads(request.body)
        comment_id = data.get('comment_id')
        vote_type = data.get('vote_type')  # 1 for upvote, -1 for downvote
        
        if vote_type not in [1, -1]:
            return JsonResponse({
                'success': False,
                'error': 'Invalid vote type'
            }, status=400)
        
        comment = get_object_or_404(MessageBoardComment, id=comment_id, is_active=True)
        
        # Check if user already voted
        existing_vote = MessageBoardVote.objects.filter(user=request.user, comment=comment).first()
        
        if existing_vote:
            if existing_vote.vote_type == vote_type:
                # Remove vote if clicking same button
                existing_vote.delete()
                action = 'removed'
            else:
                # Change vote
                existing_vote.vote_type = vote_type
                existing_vote.save()
                action = 'changed'
        else:
            # Create new vote
            MessageBoardVote.objects.create(
                user=request.user,
                comment=comment,
                vote_type=vote_type
            )
            action = 'added'
        
        # Refresh comment to get updated vote counts
        comment.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'action': action,
            'score': comment.score,
            'upvotes': comment.upvotes,
            'downvotes': comment.downvotes
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


# @ratelimit(key='ip', rate='60/m', method='GET', block=True)  # Disabled for now
def get_post_comments(request, post_id):
    """Get all comments for a post (AJAX endpoint)"""
    try:
        post = get_object_or_404(MessageBoardPost, id=post_id, is_active=True)
        comments = post.get_top_level_comments()
        
        def serialize_comment(comment):
            """Recursively serialize comment and its replies"""
            avatar_url = 'https://www.wmata.com/systemimages/icons/menu-car-icon.png'
            if hasattr(comment.user, 'socialaccount_set') and comment.user.socialaccount_set.exists():
                avatar_url = comment.user.socialaccount_set.first().get_avatar_url()
            
            data = {
                'id': comment.id,
                'content': comment.content,
                'user': comment.user.username,
                'avatar': avatar_url,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                'score': comment.score,
                'depth': comment.depth,
                'replies': [serialize_comment(reply) for reply in comment.get_nested_replies()]
            }
            return data
        
        comments_data = [serialize_comment(comment) for comment in comments]
        
        return JsonResponse({
            'success': True,
            'comments': comments_data,
            'total_comments': post.comment_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
