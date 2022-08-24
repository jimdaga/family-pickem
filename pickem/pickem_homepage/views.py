from django.http import HttpResponse
from django.template import loader
from pickem_api.models import GamesAndScores, GameWeeks

def index(request):
    game_list = GamesAndScores.objects.filter(gameWeek=1, competition='nfl-preseason')
    game_days = game_list.values_list('startTimestamp', flat=True).distinct()
    competition = game_list.values_list('competition', flat=True).distinct()[0]
    print(competition)
    template = loader.get_template('pickem/home.html')
    context = {
        'game_list': game_list,
        'game_days': game_days,
        'competition': competition,
    }
    return HttpResponse(template.render(context, request))