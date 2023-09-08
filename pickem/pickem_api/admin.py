from django.contrib import admin
from .models import GamePicks, GamesAndScores, GameWeeks, Teams, userPoints, userSeasonPoints

# Register your models here.
@admin.register(GamesAndScores)
class GamesAndScoresAdmin(admin.ModelAdmin):
    list_display = ('slug', 'competition', 'gameseason', 'gameWeek', 'gameyear', 'startTimestamp', 'statusTitle', 
        'homeTeamName', 'homeTeamScore', 'awayTeamName', 'awayTeamScore', 'gameWinner' )
    list_filter = ('startTimestamp', 'gameseason', 'gameWeek',)
    search_fields = ('homeTeamName', 'awayTeamName')
    date_hierarchy = 'startTimestamp'
    ordering = ('gameWeek', 'startTimestamp' )

@admin.register(GamePicks)
class GamesPicksAdmin(admin.ModelAdmin):
    list_display = ('userEmail', 'uid', 'slug', 'competition', 'gameseason', 'gameWeek', 'gameyear', 
        'pick_game_id', 'pick', 'pick_correct', 'tieBreakerScore', 'tieBreakerYards', 'pickAdded', 'pickUpdated' )
    list_filter = ('userEmail', 'gameseason', 'gameWeek', 'gameyear')
    search_fields = ('userEmail',)
    date_hierarchy = 'pickAdded'
    ordering = ('pickAdded',)

@admin.register(userSeasonPoints)
class UserPointsAdmin(admin.ModelAdmin):
    list_display = ('id', 'userID', 'userEmail', 'gameseason', 'gameyear', 'week_1_points', 'week_1_bonus', 'week_1_winner', 'week_2_points', 'week_2_bonus', 'week_2_winner',
    'week_3_points', 'week_3_bonus', 'week_3_winner', 'week_4_points', 'week_4_bonus', 'week_4_winner', 'week_5_points', 'week_5_bonus', 'week_5_winner', 'week_6_points', 'week_6_bonus', 'week_6_winner',
    'week_7_points', 'week_7_bonus', 'week_7_winner', 'week_8_points', 'week_8_bonus', 'week_8_winner', 'week_9_points', 'week_9_bonus', 'week_9_winner', 'week_10_points', 'week_10_bonus', 'week_10_winner',
    'week_11_points', 'week_11_bonus', 'week_11_winner', 'week_12_points', 'week_12_bonus', 'week_12_winner', 'week_13_points', 'week_13_bonus', 'week_13_winner', 'week_14_points', 'week_14_bonus','week_14_winner',
    'week_15_points', 'week_15_bonus', 'week_15_winner', 'week_16_points', 'week_16_bonus', 'week_16_winner', 'week_17_points', 'week_17_bonus', 'week_17_winner', 'week_18_points', 'week_18_bonus', 'week_18_winner', 
    'total_points', 'year_winner')
    list_filter = ('gameseason', 'userEmail')
    search_fields = ('userEmail', 'gameseason')
    date_hierarchy = 'playerUpdated'

@admin.register(userPoints)
class UserPointsAdmin(admin.ModelAdmin):
    list_display = ('id', 'userID', 'userEmail', 'gameseason', 'gameyear', 'week_1_points', 'week_1_bonus', 'week_1_winner', 'week_2_points', 'week_2_bonus', 'week_2_winner',
    'week_3_points', 'week_3_bonus', 'week_3_winner', 'week_4_points', 'week_4_bonus', 'week_4_winner', 'week_5_points', 'week_5_bonus', 'week_5_winner', 'week_6_points', 'week_6_bonus', 'week_6_winner',
    'week_7_points', 'week_7_bonus', 'week_7_winner', 'week_8_points', 'week_8_bonus', 'week_8_winner', 'week_9_points', 'week_9_bonus', 'week_9_winner', 'week_10_points', 'week_10_bonus', 'week_10_winner',
    'week_11_points', 'week_11_bonus', 'week_11_winner', 'week_12_points', 'week_12_bonus', 'week_12_winner', 'week_13_points', 'week_13_bonus', 'week_13_winner', 'week_14_points', 'week_14_bonus','week_14_winner',
    'week_15_points', 'week_15_bonus', 'week_15_winner', 'week_16_points', 'week_16_bonus', 'week_16_winner', 'week_17_points', 'week_17_bonus', 'week_17_winner', 'week_18_points', 'week_18_bonus', 'week_18_winner', 
    'total_points', 'year_winner')
    list_filter = ('gameseason', 'userEmail')
    search_fields = ('userEmail', 'gameseason')
    date_hierarchy = 'playerUpdated'

@admin.register(GameWeeks)
class GameWeekssAdmin(admin.ModelAdmin):
    list_display = ('weekNumber', 'competition', 'date', 'season')
    list_filter = ('weekNumber', 'date', 'season')
    ordering = ('competition', 'weekNumber', 'date')

@admin.register(Teams) 
class TeamsAdmin(admin.ModelAdmin):
    list_display = ('teamNameSlug', 'teamNameName', 'teamWins', 'teamLosses', 'teamTies')