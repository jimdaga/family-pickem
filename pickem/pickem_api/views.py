from functools import partial
from itertools import count
from .serializers import GameSerializer, GameWeeksSerializer, GamePicksSerializer, TeamsSerializer, UserSeasonPointsSerializer, UserSerializer, currentSeasonSerializer
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.contrib.auth.models import User
from pickem_api.models import GamesAndScores, GameWeeks, GamePicks, Teams, userSeasonPoints, currentSeason
from django.db.models import Q
from django.http import HttpResponse
from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser
from rest_framework import status
from datetime import date
from datetime import datetime
from django.db.models import Count


# Create your views here.

def get_season():
    # Select the 'season' value directly from the currentSeason model.
    # This is more efficient as it avoids fetching the entire object.
    try:
        # Assuming there should be only one 'current' season entry.
        return currentSeason.objects.get().season
    except currentSeason.DoesNotExist:
        # Fallback to a default season if none is configured.
        return 2025
    except currentSeason.MultipleObjectsReturned:
        # If multiple entries exist, return the latest one.
        return currentSeason.objects.latest('id').season


@api_view(['GET'])
def get_current_season_api(request):
    """
    API endpoint to get the current configured season.
    """
    current_season = get_season()
    return JsonResponse({'current_season': current_season})


def index(request):
    # return HttpResponse(")
    return JsonResponse({'message': 'Family Pickem API'})


@api_view(['GET', 'POST', 'DELETE'])
def game_list(request):
    """
    GET list of games, POST a new game, DELETE all games
    """

    if request.method == 'GET':
        gameseason = get_season()

        games = GamesAndScores.objects.filter(gameseason=gameseason)

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


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
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

    elif request.method == 'PATCH':
        games_data = JSONParser().parse(request)
        game = GamesAndScores.objects.get(pk=pk)
        games_serializer = GameSerializer(game, data=games_data, partial=True)
        if games_serializer.is_valid():
            games_serializer.save()
            return JsonResponse(games_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(games_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        game.delete()
        return JsonResponse({'message': 'Game was deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def user_info(request, pk):
    """
    GET user details from id
    """

    if request.method == 'GET':
        try:
            user_details = User.objects.get(pk=pk)
        except:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        user_serializer = UserSerializer(user_details)
        return Response(user_serializer.data)
    

@api_view(['GET', 'POST', 'DELETE'])
def week_list(request):
    """
    GET list of game weeks, POST a new date, DELETE all games
    """
    gameseason = get_season()

    if request.method == 'GET':

        try:
            game_week = GameWeeks.objects.get(date=today_date).weekNumber
        except:
            game_week = '1'

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
    gameseason = get_season()

    try:
        game = GamesAndScores.objects.filter(
            gameseason=gameseason, gameScored=False, statusType='finished')
    except GamesAndScores.DoesNotExist:
        return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        games_unscored_serializer = GameSerializer(game, many=True)
        return Response(games_unscored_serializer.data)


@api_view(['GET', 'POST'])
def game_picks_week_all(request, game_season, game_week):
    """
    GET user picks
    Find user picks mathing game ID
    """
    if request.method == 'GET':
        try:
            picks = GamePicks.objects.filter(
                gameseason=game_season, gameWeek=game_week)
        except GamePicks.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        picks_serializer = GamePicksSerializer(picks, many=True)
        return Response(picks_serializer.data)


@api_view(['GET', 'POST'])
def game_picks(request, pick_game_id):
    """
    GET user picks
    Find user picks mathing game ID
    """
    if request.method == 'GET':
        try:
            picks = GamePicks.objects.filter(pick_game_id=pick_game_id)
        except GamePicks.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            picks_serializer = GamePicksSerializer(picks, many=True)
            return Response(picks_serializer.data)

    elif request.method == 'POST':
        pick_data = JSONParser().parse(request)
        picks_serializer = GamePicksSerializer(data=pick_data)
        if picks_serializer.is_valid():
            picks_serializer.save()
            return JsonResponse(picks_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(picks_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
def user_picks(request, pick_id):
    """
    GET user picks
    Find user picks mathing game ID
    """
    if request.method == 'GET':
        try:
            picks = GamePicks.objects.get(id=pick_id)
        except GamePicks.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        picks_serializer = GamePicksSerializer(picks)
        return Response(picks_serializer.data)

    elif request.method == 'PATCH':
        request_data = JSONParser().parse(request)
        pick = GamePicks.objects.get(id=pick_id)
        # picks_serializer = GamePicksSerializer(pick, data=request_data, partial=True)
        picks_serializer = GamePicksSerializer(
            pick, data={'pick_correct': 'true'}, partial=True)
        if picks_serializer.is_valid():
            picks_serializer.save()
            return JsonResponse(picks_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(picks_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
def get_teams(request):
    """
    GET team names
    Find user picks mathing game ID
    """
    if request.method == 'GET':
        teams = Teams.objects.all()

        teams_serializer = TeamsSerializer(teams, many=True)
        return Response(teams_serializer.data)

    elif request.method == 'POST':
        teams_data = JSONParser().parse(request)
        teams_serializer = TeamsSerializer(data=teams_data)
        if teams_serializer.is_valid():
            teams_serializer.save()
            return JsonResponse(teams_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(teams_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST', 'PATCH'])
def get_teams_detail(request, team_id):
    """
    GET team names by ID
    Find team details mathing game ID
    """
    if request.method == 'GET':
        try:
            team = Teams.objects.filter(id=team_id)
        except Teams.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        teams_serializer = TeamsSerializer(team, many=True)
        return Response(teams_serializer.data)

    elif request.method == 'POST':
        teams_data = JSONParser().parse(request)
        teams_serializer = TeamsSerializer(data=teams_data)
        if teams_serializer.is_valid():
            teams_serializer.save()
            return JsonResponse(teams_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(teams_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'PATCH':
        teams_data = JSONParser().parse(request)
        team_id = Teams.objects.get(id=team_id)
        teams_serializer = TeamsSerializer(
            team_id, data=teams_data, partial=True)
        if teams_serializer.is_valid():
            teams_serializer.save()
            return JsonResponse(teams_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(teams_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_active_games(request):
    """
    GET active games (bool)
    Figure out if there are any active games
    """
    gameseason = get_season()

    if request.method == 'GET':
        try:
            today = datetime.today()
            active_games = GamesAndScores.objects.filter(Q(startTimestamp__year=today.year,
                                                           startTimestamp__month=today.month,
                                                           startTimestamp__day=today.day,
                                                           startTimestamp__hour=today.hour) |
                                                         Q(statusType='inprogress', gameseason=gameseason))
        except GamesAndScores.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        games_serializer = GameSerializer(active_games, many=True)
        return Response(games_serializer.data)


@api_view(['GET', 'POST'])
def user_points_all(request):
    """
    GET user season points
    Find user points for a given year
    """
    if request.method == 'GET':
        gameseason = get_season()

        try:
            user_points = userSeasonPoints.objects.filter(gameseason=gameseason)
        except userSeasonPoints.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        user_point_serializer = UserSeasonPointsSerializer(user_points, many=True)
        return Response(user_point_serializer.data)

    elif request.method == 'POST':
        request_data = JSONParser().parse(request)
        user_point_serializer = UserSeasonPointsSerializer(data=request_data)
        if user_point_serializer.is_valid():
            user_point_serializer.save()
            return JsonResponse(user_point_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(user_point_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def delete_user_record(request, game_season, id):
    """
    GET user season points
    Find user points for a given year
    """
    if request.method == 'DELETE':
        cleanup = userSeasonPoints.objects.get(userID=id, gameseason=game_season).delete()
        return JsonResponse({'message': 'Deleted record for user id {}'.format(cleanup[0])}, status=status.HTTP_204_NO_CONTENT)
    

@api_view(['GET', 'POST', 'PATCH'])
def user_points(request, game_season, id):
    """
    GET user season points
    Find user points for a given year
    """
    if request.method == 'GET':
        try:
            user_points = userSeasonPoints.objects.get(userID=id, gameseason=game_season)
        except userSeasonPoints.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        user_point_serializer = UserSeasonPointsSerializer(user_points)
        return Response(user_point_serializer.data)

    elif request.method == 'POST':
        request_data = JSONParser().parse(request)
        
        user_point_serializer = UserSeasonPointsSerializer(data=request_data, partial=True)
        if user_point_serializer.is_valid():
            user_point_serializer.save()
            return JsonResponse(user_point_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(user_point_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    elif request.method == 'PATCH':
        request_data = JSONParser().parse(request)
        try:
            user_points = userSeasonPoints.objects.get(userID=id, gameseason=game_season)
        except userSeasonPoints.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)
        
        user_point_serializer = UserSeasonPointsSerializer(
            user_points, data=request_data, partial=True)
        if user_point_serializer.is_valid():
            user_point_serializer.save()
            return JsonResponse(user_point_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(user_point_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def correct_user_picks(request, game_season, game_week, uid):
    """
    GET user season points
    Find user points for a given year
    """
    if request.method == 'GET':
        try:
            picks = GamePicks.objects.filter(
                gameseason=game_season, gameWeek=game_week, uid=uid, pick_correct=True)

        except GamePicks.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        picks_serializer = GamePicksSerializer(picks, many=True)
        return Response(picks_serializer.data)
