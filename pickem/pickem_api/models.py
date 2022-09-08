from time import timezone
from xmlrpc.client import Boolean
from django.db import models

# Create your models here.
class Teams(models.Model):
    id = models.IntegerField(primary_key=True)
    teamNameSlug = models.CharField(max_length=250)
    teamNameName = models.CharField(max_length=250)
    teamWins =  models.IntegerField(default=0)
    teamLosses =  models.IntegerField(default=0)

class GamesAndScores(models.Model):
    id = models.IntegerField(primary_key=True)
    slug = models.SlugField(max_length=250)
    competition = models.CharField(max_length=250)
    gameWeek = models.CharField(max_length=2)
    gameyear = models.CharField(max_length=4)
    startTimestamp = models.DateTimeField()
    gameWinner = models.CharField(max_length=250)
    statusType = models.CharField(max_length=250)
    statusTitle = models.CharField(max_length=250)
    homeTeamId = models.IntegerField()
    homeTeamSlug = models.CharField(max_length=250)
    homeTeamName = models.CharField(max_length=250)
    homeTeamScore = models.IntegerField()
    homeTeamPeriod1 = models.IntegerField(default=0)
    homeTeamPeriod2 = models.IntegerField(default=0)
    homeTeamPeriod3 = models.IntegerField(default=0)
    homeTeamPeriod4 = models.IntegerField(default=0)
    awayTeamId = models.IntegerField()
    awayTeamSlug = models.CharField(max_length=250)
    awayTeamName = models.CharField(max_length=250)
    awayTeamScore = models.IntegerField()
    awayTeamPeriod1 = models.IntegerField(default=0)
    awayTeamPeriod2 = models.IntegerField(default=0)
    awayTeamPeriod3 = models.IntegerField(default=0)
    awayTeamPeriod4 = models.IntegerField(default=0)
    tieBreakerGame = models.BooleanField(default=False)
    gameAdded = models.DateTimeField(auto_now_add=True)
    gameUpdated = models.DateTimeField(auto_now=True)
    gameScored = models.BooleanField(default=False)

    class Meta:
        ordering = ['startTimestamp']

class GamePicks(models.Model):
    id = models.CharField(max_length=250,primary_key=True)
    userEmail = models.EmailField(blank=True)
    userID = models.CharField(max_length=250, blank=True)
    slug = models.SlugField(max_length=250, blank=True)
    competition = models.CharField(max_length=250, blank=True)
    gameWeek = models.CharField(max_length=2, blank=True)
    gameyear = models.CharField(max_length=4, blank=True)
    pick_game_id = models.IntegerField(blank=True)
    pick = models.CharField(max_length=250, blank=True) 
    tieBreakerScore = models.IntegerField(blank=True, null=True)
    pick_correct = models.BooleanField(default=False, blank=True)
    pickAdded = models.DateTimeField(auto_now_add=True)
    pickUpdated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['gameWeek']

class GameWeeks(models.Model):
    weekNumber = models.IntegerField()
    competition = models.CharField(max_length=250)
    date = models.DateField()

def __str__(self):
    return self.slug