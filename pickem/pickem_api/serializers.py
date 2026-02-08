from dataclasses import fields
from django.contrib.auth.models import User, Group
from rest_framework import serializers
from pickem_api.models import GamesAndScores, GameWeeks, GamePicks, Teams, userPoints, userSeasonPoints, userStats, currentSeason, UserProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'is_active']


class UserProfileSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'tagline', 'favorite_team', 'phone_number', 
                 'email_notifications', 'dark_mode', 'private_profile', 
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


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
        fields = ['id', 'uid', 'userID', 'slug', 'competition', 'gameWeek',
                  'gameyear', 'gameseason', 'pick_game_id', 'pick',
                  'tieBreakerScore', 'tieBreakerYards', 'pick_correct',
                  'pickAdded', 'pickUpdated']
        extra_kwargs = {
            'name': {'validators': []},
        }


class GamePicksAdminSerializer(serializers.ModelSerializer):
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