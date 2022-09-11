from dataclasses import fields
from django.contrib.auth.models import User, Group
from rest_framework import serializers
from pickem_api.models import GamesAndScores, GameWeeks, GamePicks, Teams, userPoints

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

class UserPointsSerializer(serializers.ModelSerializer):
    class Meta:
        model = userPoints
        fields = '__all__'