from django.http import HttpResponse
from django.template import loader
from pickem_api.models import GamePicks
from pickem_api.models import GamesAndScores, GameWeeks
from django.shortcuts import render

def index(request):
    return render(request, 'pickem/home.html')

def scores(request):
    game_list = GamesAndScores.objects.filter(gameWeek=1, competition='nfl-preseason')
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()[0]
    picks = GamePicks.objects.filter(gameWeek=1, competition='nfl-preseason')

    template = loader.get_template('pickem/scores.html')

    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition,
        'picks': picks
    }
    return HttpResponse(template.render(context, request))
