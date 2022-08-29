from django.http import HttpResponse
from django.template import loader
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks
from django.shortcuts import render
from django.db.models import Sum
from django.db.models import Count
from datetime import date

def index(request):
    return render(request, 'pickem/home.html')

def scores(request):

    today = date.today()
    today_date = today.strftime("%Y-%m-%d")
    game_year = today.strftime("%Y") 
    game_week = GameWeeks.objects.get(date=today_date).weekNumber
    game_competition = GameWeeks.objects.get(date=today_date).competition

    game_list = GamesAndScores.objects.filter(gameyear=game_year, gameWeek=game_week, competition=game_competition)
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()[0]
    
    points = GamePicks.objects.filter(gameWeek=game_week, competition=game_competition, pick_correct=True)
    user_points = points.values('userID').order_by('-userID').annotate(wins=Count('userID'))
    # TODO: Give zero points to users that didn't win yet

    template = loader.get_template('pickem/scores.html')

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition,
        'week': game_week,
        'user_points': user_points,
        'game_weeks': range(1,19)
    }
    return HttpResponse(template.render(context, request))

def scores_long(request, year, week):
    game_list = GamesAndScores.objects.filter(gameyear=year, gameWeek=week, competition='nfl')
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = 'nfl'
    picks = GamePicks.objects.filter(gameWeek=week, competition='nfl')

    points = GamePicks.objects.filter(gameWeek=week, competition=competition, pick_correct=True)
    user_points = points.values('userID').order_by('-userID').annotate(wins=Count('userID'))

    template = loader.get_template('pickem/scores.html')

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition,
        'picks': picks,
        'week': week,
        'user_points': user_points,
        'game_weeks': range(1,19)
    }
    return HttpResponse(template.render(context, request))

def Standings(request):
    points = GamePicks.objects.values('userID').order_by('userID').annotate(wins=Count('userID'))
    print(points)