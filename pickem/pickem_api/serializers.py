from django.contrib.auth.models import User, Group
from rest_framework import serializers
from pickem_api.models import GamesAndScores

class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamesAndScores
        fields = '__all__'