from .serializers import GameSerializer
from rest_framework.response import Response
from rest_framework.decorators import api_view
from pickem_api.models import GamesAndScores
from django.http import HttpResponse

# Create your views here.
def index(request):
    return HttpResponse("Family Pickem API")

@api_view(['GET'])
def getGames(request):
    """
    API endpoint that allows listing all games.
    """
    games = GamesAndScores.objects.all()
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)

@api_view(['POST'])
def addGame(request):
    """
    API endpoint that allows adding a new game score.
    """
    serializer = GameSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    else:
        return Response(serializer.errors)
    