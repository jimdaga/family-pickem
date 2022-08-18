from django.contrib import admin
from .models import GamesAndScores

# Register your models here.
@admin.register(GamesAndScores)
class GamesAndScoresAdmin(admin.ModelAdmin):
    list_display = ('slug', 'gameWeek', 'startTimestamp', 'statusTitle', 
        'homeTeamName', 'homeTeamScore', 'awayTeamName', 'awayTeamScore' )
    list_filter = ('startTimestamp', 'gameWeek',)
    search_fields = ('homeTeamName', 'awayTeamName')
    date_hierarchy = 'startTimestamp'
    ordering = ('gameWeek',)