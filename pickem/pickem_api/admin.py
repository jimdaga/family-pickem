from django.contrib import admin
from .models import GamesAndScores, GameWeeks

# Register your models here.
@admin.register(GamesAndScores)
class GamesAndScoresAdmin(admin.ModelAdmin):
    list_display = ('slug', 'competition', 'gameWeek', 'startTimestamp', 'statusTitle', 
        'homeTeamName', 'homeTeamScore', 'awayTeamName', 'awayTeamScore', 'gameWinner' )
    list_filter = ('startTimestamp', 'gameWeek',)
    search_fields = ('homeTeamName', 'awayTeamName')
    date_hierarchy = 'startTimestamp'
    ordering = ('gameWeek',)

@admin.register(GameWeeks)
class GameWeekssAdmin(admin.ModelAdmin):
    list_display = ('weekNumber', 'competition', 'date')
    list_filter = ('weekNumber', 'date',)
    ordering = ('competition', 'weekNumber', 'date')