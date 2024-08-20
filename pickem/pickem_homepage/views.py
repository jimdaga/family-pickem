from django.http import HttpResponse
from django.template import loader
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks, Teams, userSeasonPoints
from .forms import GamePicksForm

from django.shortcuts import render
from django.db.models import Sum
from django.db.models import Count
from django.db.models.functions import Coalesce

from datetime import date

from django.forms import formset_factory

def get_season():
    # I'll probably hate myself in the future for hardcoding this :) 
    today = date.today()
    today_datestamp = date(today.year, today.month, today.day)

    if today_datestamp > date(2022, 4, 1) and today_datestamp < date(2023, 4, 1):
        return '2223'
    elif today_datestamp > date(2023, 4, 1) and today_datestamp < date(2024, 4, 1):
        return '2324'
    elif today_datestamp > date(2024, 4, 1):
        return '2425'

def index(request):

    season_winner = userSeasonPoints.objects.filter(year_winner=True).distinct() 
    template = loader.get_template('pickem/home.html')

    context = {
        'season_winner': season_winner
    }
    return HttpResponse(template.render(context, request))


def standings(request):
    return render(request, 'pickem/standings.html')

def rules(request):
    return render(request, 'pickem/rules.html')

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
    
    user_points = points.values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')
    # user_points = points.filter(gameseason=gameseason).values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')

    users_w_points = user_points.values_list('uid', flat=True).distinct()
    #users_w_points = user_points.filter(gameseason=gameseason).values_list('uid', flat=True).distinct()
    
    
    
    players = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)
    players_names = players.values_list('uid', flat=True).distinct()
    players_ids = User.objects.values_list('id', flat=True).distinct().exclude(username='admin')
    wins_losses = Teams.objects.filter(gameseason=gameseason)

    winner_object = "week_{}_winner".format(game_week)
    week_winner = userSeasonPoints.objects.filter(**{winner_object: True},gameseason=gameseason).distinct() 

    # TODO: Give zero points to users that didn't win yet

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
        'game_weeks': range(1,19)
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
    players_ids = User.objects.values_list('id', flat=True).distinct().exclude(username='admin')
    wins_losses = Teams.objects.filter(gameseason=gameseason)

    winner_object = "week_{}_winner".format(week)
    week_winner = userSeasonPoints.objects.filter(**{winner_object: True},gameseason=gameseason).distinct() 

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
        'game_weeks': range(1,19)
    }
    return HttpResponse(template.render(context, request))

def standings(request):
    today = date.today()
    gameseason = get_season()
    
    User = get_user_model()
    players = User.objects.all()

    player_points = userSeasonPoints.objects.filter(gameseason=gameseason).order_by('-total_points')

    template = loader.get_template('pickem/standings.html')

    context = {
        'players': players,
        'player_points': player_points
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