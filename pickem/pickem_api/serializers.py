from dataclasses import fields
from django.contrib.auth.models import User, Group
from rest_framework import serializers
from pickem_api.models import GamesAndScores, GameWeeks, GamePicks, Teams, userPoints, userSeasonPoints, userStats, currentSeason


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'


class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamesAndScores
        fields = '__all__'


class GameWeeksSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameWeeks
        fields = '__all__'


class GamePicksSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamePicks
        fields = '__all__'
        extra_kwargs = {
            'name': {'validators': []},
        }


class TeamsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teams
        fields = '__all__'


class UserSeasonPointsSerializer(serializers.ModelSerializer):
    class Meta:
        model = userSeasonPoints
        fields = '__all__'


class UserPointsSerializer(serializers.ModelSerializer):
    class Meta:
        model = userPoints
        fields = '__all__'

class UserStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = userStats
        fields = '__all__'

class currentSeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = currentSeason
        fields = '__all__'