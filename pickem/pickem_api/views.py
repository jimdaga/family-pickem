from .serializers import GameSerializer, GameWeeksSerializer, GamePicksSerializer
from rest_framework.response import Response
from rest_framework.decorators import api_view
from pickem_api.models import GamesAndScores, GameWeeks, GamePicks
from django.http import HttpResponse
from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser 
from rest_framework import status

# Create your views here.
def index(request):
    # return HttpResponse(")
    return JsonResponse({'message': 'Family Pickem API'})

@api_view(['GET', 'POST', 'DELETE'])
def game_list(request):
    """
    GET list of games, POST a new game, DELETE all games
    """
    if request.method == 'GET':
        games = GamesAndScores.objects.all()
        
        slug = request.query_params.get('slug', None)
        if slug is not None:
            games = games.filter(title__icontains=slug)
        
        games_serializer = GameSerializer(games, many=True)
        return Response(games_serializer.data)

    elif request.method == 'POST':
        games_data = JSONParser().parse(request)
        games_serializer = GameSerializer(data=games_data)
        if games_serializer.is_valid():
            games_serializer.save()
            return JsonResponse(games_serializer.data, status=status.HTTP_201_CREATED) 
        return JsonResponse(games_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

    elif request.method == 'DELETE':
        count = GamesAndScores.objects.all().delete()
        return JsonResponse({'message': '{} All games were deleted successfully!'.format(count[0])}, status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'PUT', 'DELETE'])
def game_detail(request, pk):
    """
    GET / PUT / DELETE games
    find game by pk (id) 
    """
    try: 
        game = GamesAndScores.objects.get(pk=pk)
    except GamesAndScores.DoesNotExist: 
        return JsonResponse({'message': 'This ID does not exist'}, status=status.HTTP_404_NOT_FOUND) 
 
    if request.method == 'GET': 
        games_serializer = GameSerializer(game)
        return Response(games_serializer.data)

    elif request.method == 'PUT': 
        games_data = JSONParser().parse(request) 
        games_serializer = GameSerializer(game, data=games_data) 
        if games_serializer.is_valid(): 
            games_serializer.save() 
            return JsonResponse(games_serializer.data) 
        return JsonResponse(games_serializer.errors, status=status.HTTP_400_BAD_REQUEST) 
 
    elif request.method == 'DELETE': 
        game.delete() 
        return JsonResponse({'message': 'Game was deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST', 'DELETE'])
def week_list(request):
    """
    GET list of game weeks, POST a new date, DELETE all games
    """
    if request.method == 'GET':
        game_week = GameWeeks.objects.all()
        game_week_serializer = GameWeeksSerializer(game_week, many=True)
        return Response(game_week_serializer.data)

    elif request.method == 'POST':
        game_week = JSONParser().parse(request)
        game_week_serializer = GameWeeksSerializer(data=game_week)
        print(request)
        if game_week_serializer.is_valid():
            game_week_serializer.save()
            return JsonResponse(game_week_serializer.data, status=status.HTTP_201_CREATED) 
        return JsonResponse(game_week_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        count = GameWeeks.objects.all().delete()
        return JsonResponse({'message': '{} All game week data was deleted successfully!'.format(count[0])}, status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'PUT', 'DELETE'])
def week_detail(request, date):
    """
    GET / PUT / DELETE games
    find game date by date
    """
    try: 
        game = GameWeeks.objects.get(date=date)
    except GameWeeks.DoesNotExist: 
        return JsonResponse({'message': 'This Game Date does not exist'}, status=status.HTTP_404_NOT_FOUND) 
 
    if request.method == 'GET': 
        game_week_serializer = GameWeeksSerializer(game)
        return Response(game_week_serializer.data)

@api_view(['GET'])
def games_unscored(request):
    """
    GET unscored games
    find unscored games 
    """
    try: 
        game = GamesAndScores.objects.filter(gameScored=False, statusType='finished')
    except GamesAndScores.DoesNotExist: 
        return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND) 
 
    if request.method == 'GET': 
        games_unscored_serializer = GameSerializer(game, many=True)
        return Response(games_unscored_serializer.data)

@api_view(['GET'])
def game_picks(request, pick_game_id):
    """
    GET user picks
    Find user picks mathing game ID
    """
    try: 
        picks = GamePicks.objects.filter(pick_game_id=pick_game_id)
    except GamesAndScores.DoesNotExist: 
        return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND) 
 
    if request.method == 'GET': 
        picks_serializer = GamePicksSerializer(picks, many=True)
        return Response(picks_serializer.data)