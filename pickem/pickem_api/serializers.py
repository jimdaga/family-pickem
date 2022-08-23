from dataclasses import fields
from django.contrib.auth.models import User, Group
from rest_framework import serializers
from pickem_api.models import GamesAndScores, GameWeeks

class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamesAndScores
        fields = '__all__'

class GameWeeksSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameWeeks
        fields = '__all__'