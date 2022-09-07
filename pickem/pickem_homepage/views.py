from django.http import HttpResponse
from django.template import loader
from django.contrib.auth.models import User
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks, Teams
from .forms import GamePicksForm

from django.shortcuts import render
from django.db.models import Sum
from django.db.models import Count

from datetime import date

from django.forms import formset_factory

def index(request):
    return render(request, 'pickem/home.html')

def standings(request):
    return render(request, 'pickem/standings.html')

def rules(request):
    return render(request, 'pickem/rules.html')

def scores(request):

    today = date.today()
    today_date = today.strftime("%Y-%m-%d")
    game_year = today.strftime("%Y") 
    game_week = GameWeeks.objects.get(date=today_date).weekNumber
    game_competition = GameWeeks.objects.get(date=today_date).competition

    game_list = GamesAndScores.objects.filter(gameyear=game_year, gameWeek=game_week, competition=game_competition)
    # game_list = GamesAndScores.objects.filter(gameyear=game_year, gameWeek='3', competition='nfl-preseason')
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()
    
    points = GamePicks.objects.filter(gameWeek=game_week, competition=game_competition, pick_correct=True)
    user_points = points.values('userID').order_by('-userID').annotate(wins=Count('userID')).order_by('-wins')
    users_w_points = user_points.values_list('userID', flat=True).distinct()
    picks = GamePicks.objects.filter(gameWeek=game_week, competition=game_competition)
    players = GamePicks.objects.filter(gameWeek=game_week, competition=game_competition)
    players_names = players.values_list('userID', flat=True).distinct()
    wins_losses = Teams.objects.all()

    # TODO: Give zero points to users that didn't win yet
    print(players)

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
        'game_weeks': range(1,19)
    }
    return HttpResponse(template.render(context, request))

def scores_long(request, competition, year, week):
    if competition == '0':
        competition_name='nfl-preseason'
    else:
        competition_name='nfl'

    print("comp: %s" % competition_name)

    game_list = GamesAndScores.objects.filter(competition=competition_name, gameyear=year, gameWeek=week)
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = competition_name
    picks = GamePicks.objects.filter(gameWeek=week, competition=competition_name)

    points = GamePicks.objects.filter(gameWeek=week, competition=competition_name, pick_correct=True)
    user_points = points.values('userID').order_by('-userID').annotate(wins=Count('userID'))
    users_w_points = user_points.values_list('userID', flat=True).distinct()
    players = GamePicks.objects.filter(gameWeek=week, competition=competition_name)
    players_names = players.values_list('userID', flat=True).distinct()
    wins_losses = Teams.objects.all()

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
        'game_weeks': range(1,19)
    }
    return HttpResponse(template.render(context, request))

def Standings(request):
    points = GamePicks.objects.values('userID').order_by('userID').annotate(wins=Count('userID'))
    print(points)

def submit_game_picks(request):
    today = date.today()
    today_date = today.strftime("%Y-%m-%d")
    game_year = today.strftime("%Y") 
    game_week = GameWeeks.objects.get(date=today_date).weekNumber
    game_competition = GameWeeks.objects.get(date=today_date).competition

    game_list = GamesAndScores.objects.filter(gameyear=game_year, gameWeek=game_week, competition=game_competition)
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()

    picks = GamePicks.objects.filter(gameyear=game_year, gameWeek=game_week, competition=game_competition, userEmail=request.user.email)

    pick_slugs = picks.values_list('slug', flat=True).distinct()
    pick_ids = picks.values_list('id', flat=True).distinct()

    wins_losses = Teams.objects.all()

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition,
        'wins_losses': wins_losses,
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