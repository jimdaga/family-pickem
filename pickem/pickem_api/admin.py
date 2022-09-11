from django.contrib import admin
from .models import GamePicks, GamesAndScores, GameWeeks, Teams, userPoints

# Register your models here.
@admin.register(GamesAndScores)
class GamesAndScoresAdmin(admin.ModelAdmin):
    list_display = ('slug', 'competition', 'gameWeek', 'startTimestamp', 'statusTitle', 
        'homeTeamName', 'homeTeamScore', 'awayTeamName', 'awayTeamScore', 'gameWinner' )
    list_filter = ('startTimestamp', 'gameWeek',)
    search_fields = ('homeTeamName', 'awayTeamName')
    date_hierarchy = 'startTimestamp'
    ordering = ('gameWeek',)

@admin.register(GamePicks)
class GamesPicksAdmin(admin.ModelAdmin):
    list_display = ('userEmail', 'slug', 'competition', 'gameWeek', 'gameyear', 
        'pick_game_id', 'pick', 'pick_correct', 'pickAdded', 'pickUpdated' )
    list_filter = ('userEmail', 'slug', 'gameWeek', 'gameyear')
    search_fields = ('userEmail',)
    date_hierarchy = 'pickAdded'
    ordering = ('pickAdded',)

@admin.register(userPoints)
class UserPointsAdmin(admin.ModelAdmin):
    list_display = ('userEmail', 'gameyear', 'week_1_points', 'week_1_winner', 'week_2_points', 'week_2_winner',
    'week_3_points', 'week_3_winner', 'week_4_points', 'week_4_winner', 'week_5_points', 'week_5_winner', 'week_6_points', 'week_6_winner',
    'week_7_points', 'week_7_winner', 'week_8_points', 'week_8_winner', 'week_9_points', 'week_9_winner', 'week_10_points', 'week_10_winner',
    'week_11_points', 'week_11_winner', 'week_12_points', 'week_12_winner', 'week_13_points', 'week_13_winner', 'week_14_points', 'week_14_winner',
    'week_15_points', 'week_15_winner', 'week_16_points', 'week_16_winner', 'week_17_points', 'week_17_winner', 'week_18_points', 'week_18_winner', 
    'total_points')
    search_fields = ('userEmail',)
    date_hierarchy = 'playerUpdated'

@admin.register(GameWeeks)
class GameWeekssAdmin(admin.ModelAdmin):
    list_display = ('weekNumber', 'competition', 'date')
    list_filter = ('weekNumber', 'date',)
    ordering = ('competition', 'weekNumber', 'date')

@admin.register(Teams) 
class TeamsAdmin(admin.ModelAdmin):
    list_display = ('teamNameSlug', 'teamNameName', 'teamWins', 'teamLosses')