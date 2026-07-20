from functools import partial
from itertools import count
from .serializers import GameSerializer, GameWeeksSerializer, GamePicksSerializer, TeamsSerializer, UserSeasonPointsSerializer, UserSerializer, currentSeasonSerializer
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from .permissions import IsAdminOrReadOnly, tenant_authz_error_response
from django.contrib.auth.models import User
from pickem_api.authz import TenantAuthorizationError, require_tenant_context
from pickem_api.models import (
    FamilyMembership,
    GamesAndScores, GameWeeks, GamePicks, Teams, userSeasonPoints, currentSeason,
)
from django.db import IntegrityError, transaction
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
@permission_classes([AllowAny])
def get_current_season_api(request):
    """
    API endpoint to get the current configured season.
    """
    current_season = get_season()
    return JsonResponse({'current_season': current_season})


@api_view(['GET'])
@permission_classes([AllowAny])
def index(request):
    # return HttpResponse(")
    return JsonResponse({'message': 'Family Pickem API'})


@api_view(['GET'])
@permission_classes([AllowAny])
def family_pool_authz_check(request, family_slug, pool_slug):
    """
    Minimal internal proof endpoint for Phase 2 tenant authorization wiring.
    """
    minimum_role = request.query_params.get(
        'minimum_role',
        FamilyMembership.Role.MEMBER,
    )
    if minimum_role not in FamilyMembership.Role.values:
        return Response(
            {'detail': 'Invalid role.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        context = require_tenant_context(
            request.user,
            family=family_slug,
            pool=pool_slug,
            minimum_role=minimum_role,
        )
    except TenantAuthorizationError as error:
        return tenant_authz_error_response(error)

    return Response(
        {
            'family': context.family.slug,
            'pool': context.pool.slug,
            'role': context.membership.role,
        }
    )


@api_view(['GET'])
@permission_classes([IsAdminOrReadOnly])
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
@api_view(['GET'])
@permission_classes([IsAdminOrReadOnly])
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

@api_view(['GET'])
@permission_classes([IsAdminUser])
def user_info(request, pk):
    """
    GET user details from id
    """

    if request.method == 'GET':
        try:
            user_details = User.objects.get(pk=pk)
        except Exception:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)

        user_serializer = UserSerializer(user_details)
        return Response(user_serializer.data)
    

@api_view(['GET'])
@permission_classes([IsAdminOrReadOnly])
def week_list(request):
    """
    GET list of game weeks, POST a new date, DELETE all games
    """
    gameseason = get_season()

    if request.method == 'GET':
        # Get all game weeks for the current season
        game_weeks = GameWeeks.objects.filter(season=gameseason).order_by('weekNumber')
        
        if not game_weeks.exists():
            # If no game weeks exist, return empty list
            return Response([])

        game_week_serializer = GameWeeksSerializer(game_weeks, many=True)
        return Response(game_week_serializer.data)
@api_view(['GET'])
@permission_classes([AllowAny])
def week_detail(request, date):
    """
    GET / PUT / DELETE games
    find game date by date
    """
    try:
        game = GameWeeks.objects.get(date=date)
    except GameWeeks.DoesNotExist:
        # If no GameWeeks record exists for this date (e.g., before season starts),
        # default to week 1 for the current season
        current_season = get_season()
        try:
            # Try to find week 1 for the current season
            game = GameWeeks.objects.filter(
                weekNumber=1,
                season=current_season
            ).first()
            
            if not game:
                # If no week 1 exists for current season, try to find any week 1
                game = GameWeeks.objects.filter(weekNumber=1).first()
                
            if not game:
                return JsonResponse({'message': 'No GameWeeks data available'}, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return JsonResponse({'message': 'Error retrieving week data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if request.method == 'GET':
        game_week_serializer = GameWeeksSerializer(game)
        return Response(game_week_serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
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
@permission_classes([IsAdminUser])
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
@permission_classes([IsAdminUser])
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
@permission_classes([IsAdminUser])
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
        try:
            pick = GamePicks.objects.get(id=pick_id)
        except GamePicks.DoesNotExist:
            return JsonResponse({'message': 'There was an issue getting this data'}, status=status.HTTP_404_NOT_FOUND)
        picks_serializer = GamePicksSerializer(
            pick, data=request_data, partial=True)
        if picks_serializer.is_valid():
            try:
                # Savepoint: a caught IntegrityError must not poison any
                # outer transaction (e.g. Postgres ATOMIC_REQUESTS) beyond
                # this save.
                with transaction.atomic():
                    picks_serializer.save()
            except IntegrityError:
                return JsonResponse(
                    {'message': 'A pick already exists for that pool/user/game'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return JsonResponse(picks_serializer.data, status=status.HTTP_200_OK)
        return JsonResponse(picks_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAdminOrReadOnly])
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
@permission_classes([IsAdminOrReadOnly])
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
@permission_classes([AllowAny])
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
@permission_classes([IsAdminUser])
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


def _season_points_scope(request, game_season, id):
    """Season-points rows for a user+season, optionally narrowed to one pool
    via ``?pool=<id>``. Returns (queryset, error_response)."""
    queryset = userSeasonPoints.objects.filter(userID=id, gameseason=game_season)
    pool_param = request.GET.get('pool')
    if pool_param is not None:
        try:
            queryset = queryset.filter(pool_id=int(pool_param))
        except (TypeError, ValueError):
            return None, JsonResponse(
                {'message': 'pool must be an integer pool id'},
                status=status.HTTP_400_BAD_REQUEST)
    return queryset, None


def _single_season_points(request, game_season, id):
    """Resolve exactly one season-points row or an error response.

    A user can hold a row per pool per season, so an id+season lookup can be
    ambiguous; require ``?pool=<id>`` in that case instead of 500ing.
    """
    queryset, error = _season_points_scope(request, game_season, id)
    if error is not None:
        return None, error
    rows = list(queryset[:2])
    if not rows:
        return None, JsonResponse(
            {'message': 'There was an issue getting this data'},
            status=status.HTTP_404_NOT_FOUND)
    if len(rows) > 1:
        return None, JsonResponse(
            {'message': 'User has season points in multiple pools; specify ?pool=<id>'},
            status=status.HTTP_400_BAD_REQUEST)
    return rows[0], None


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_user_record(request, game_season, id):
    """
    DELETE user season points record
    """
    if request.method == 'DELETE':
        record, error = _single_season_points(request, game_season, id)
        if error is not None:
            return error
        record.delete()
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAdminUser])
def user_points(request, game_season, id):
    """
    GET user season points
    Find user points for a given year
    """
    if request.method == 'GET':
        user_points, error = _single_season_points(request, game_season, id)
        if error is not None:
            return error

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
        user_points, error = _single_season_points(request, game_season, id)
        if error is not None:
            return error

        user_point_serializer = UserSeasonPointsSerializer(
            user_points, data=request_data, partial=True)
        if user_point_serializer.is_valid():
            user_point_serializer.save()
            return JsonResponse(user_point_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(user_point_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAdminUser])
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
