from django.contrib import admin
from .models import GamePicks, GamesAndScores, GameWeeks, Teams

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

@admin.register(GameWeeks)
class GameWeekssAdmin(admin.ModelAdmin):
    list_display = ('weekNumber', 'competition', 'date')
    list_filter = ('weekNumber', 'date',)
    ordering = ('competition', 'weekNumber', 'date')

@admin.register(Teams) 
class TeamsAdmin(admin.ModelAdmin):
    list_display = ('teamNameSlug', 'teamNameName', 'teamWins', 'teamLosses')