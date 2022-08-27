from django.http import HttpResponse
from django.template import loader
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks
from django.shortcuts import render
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
    picks = GamePicks.objects.filter(gameWeek=game_week, competition=game_competition)

    template = loader.get_template('pickem/scores.html')

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition,
        'picks': picks,
        'week': game_week
    }
    return HttpResponse(template.render(context, request))

def scores_long(request, year, week):
    game_list = GamesAndScores.objects.filter(gameyear=year, gameWeek=week, competition='nfl')
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = 'nfl'
    picks = GamePicks.objects.filter(gameWeek=week, competition='nfl')

    template = loader.get_template('pickem/scores.html')

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition,
        'picks': picks,
        'week': week
    }
    return HttpResponse(template.render(context, request))
