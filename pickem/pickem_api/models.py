from time import timezone
from xmlrpc.client import Boolean
from django.db import models

# Create your models here.


class Teams(models.Model):
    id = models.IntegerField(primary_key=True)
    gameseason = models.IntegerField(blank=True, null=True)
    teamNameSlug = models.CharField(max_length=250)
    teamNameName = models.CharField(max_length=250)
    teamLogo = models.CharField(max_length=250, blank=True, null=True)
    teamWins = models.IntegerField(default=0)
    teamLosses = models.IntegerField(default=0)
    teamTies = models.IntegerField(default=0)

class GamesAndScores(models.Model):
    id = models.IntegerField(primary_key=True)
    slug = models.SlugField(max_length=250)
    competition = models.CharField(max_length=250)
    gameWeek = models.CharField(max_length=2)
    gameyear = models.CharField(max_length=4)
    gameseason = models.IntegerField(blank=True, null=True)
    startTimestamp = models.DateTimeField()
    gameWinner = models.CharField(max_length=250, blank=True, null=True)
    statusType = models.CharField(max_length=250)
    statusTitle = models.CharField(max_length=250)
    homeTeamId = models.IntegerField()
    homeTeamSlug = models.CharField(max_length=250)
    homeTeamName = models.CharField(max_length=250)
    homeTeamScore = models.IntegerField(blank=True, null=True)
    homeTeamPeriod1 = models.IntegerField(blank=True, null=True)
    homeTeamPeriod2 = models.IntegerField(blank=True, null=True)
    homeTeamPeriod3 = models.IntegerField(blank=True, null=True)
    homeTeamPeriod4 = models.IntegerField(blank=True, null=True)
    homeTeamPeriodOT = models.IntegerField(blank=True, null=True)
    awayTeamId = models.IntegerField()
    awayTeamSlug = models.CharField(max_length=250)
    awayTeamName = models.CharField(max_length=250)
    awayTeamScore = models.IntegerField(blank=True, null=True)
    awayTeamPeriod1 = models.IntegerField(blank=True, null=True)
    awayTeamPeriod2 = models.IntegerField(blank=True, null=True)
    awayTeamPeriod3 = models.IntegerField(blank=True, null=True)
    awayTeamPeriod4 = models.IntegerField(blank=True, null=True)
    awayTeamPeriodOT = models.IntegerField(blank=True, null=True)
    tieBreakerGame = models.BooleanField(default=False)
    gameAdded = models.DateTimeField(auto_now_add=True)
    gameUpdated = models.DateTimeField(auto_now=True)
    gameScored = models.BooleanField(default=False)

    class Meta:
        ordering = ['startTimestamp']


class GamePicks(models.Model):
    id = models.CharField(max_length=250, primary_key=True)
    userEmail = models.EmailField(blank=True)
    uid = models.IntegerField(blank=True, null=True)
    userID = models.CharField(max_length=250, blank=True)
    slug = models.SlugField(max_length=250, blank=True)
    competition = models.CharField(max_length=250, blank=True)
    gameWeek = models.CharField(max_length=2, blank=True)
    gameyear = models.CharField(max_length=4, blank=True)
    gameseason = models.IntegerField(blank=True, null=True)
    pick_game_id = models.IntegerField(blank=True)
    pick = models.CharField(max_length=250, blank=True)
    tieBreakerScore = models.IntegerField(blank=True, null=True)
    tieBreakerYards = models.IntegerField(blank=True, null=True)
    pick_correct = models.BooleanField(default=False, blank=True)
    pickAdded = models.DateTimeField(auto_now_add=True)
    pickUpdated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['gameWeek']


class userSeasonPoints(models.Model):
    id = models.AutoField(primary_key=True)
    userEmail = models.EmailField(blank=True)
    userID = models.CharField(max_length=250, blank=True)
    gameyear = models.CharField(max_length=4, blank=True)
    gameseason = models.IntegerField(blank=True, null=True)
    week_1_points = models.IntegerField(blank=True, null=True)
    week_1_bonus = models.IntegerField(blank=True, null=True)
    week_1_winner = models.BooleanField(default=False, blank=True)

    week_2_points = models.IntegerField(blank=True, null=True)
    week_2_bonus = models.IntegerField(blank=True, null=True)
    week_2_winner = models.BooleanField(default=False, blank=True)

    week_3_points = models.IntegerField(blank=True, null=True)
    week_3_bonus = models.IntegerField(blank=True, null=True)
    week_3_winner = models.BooleanField(default=False, blank=True)

    week_4_points = models.IntegerField(blank=True, null=True)
    week_4_bonus = models.IntegerField(blank=True, null=True)
    week_4_winner = models.BooleanField(default=False, blank=True)

    week_5_points = models.IntegerField(blank=True, null=True)
    week_5_bonus = models.IntegerField(blank=True, null=True)
    week_5_winner = models.BooleanField(default=False, blank=True)

    week_6_points = models.IntegerField(blank=True, null=True)
    week_6_bonus = models.IntegerField(blank=True, null=True)
    week_6_winner = models.BooleanField(default=False, blank=True)

    week_7_points = models.IntegerField(blank=True, null=True)
    week_7_bonus = models.IntegerField(blank=True, null=True)
    week_7_winner = models.BooleanField(default=False, blank=True)

    week_8_points = models.IntegerField(blank=True, null=True)
    week_8_bonus = models.IntegerField(blank=True, null=True)
    week_8_winner = models.BooleanField(default=False, blank=True)

    week_9_points = models.IntegerField(blank=True, null=True)
    week_9_bonus = models.IntegerField(blank=True, null=True)
    week_9_winner = models.BooleanField(default=False, blank=True)

    week_10_points = models.IntegerField(blank=True, null=True)
    week_10_bonus = models.IntegerField(blank=True, null=True)
    week_10_winner = models.BooleanField(default=False, blank=True)

    week_11_points = models.IntegerField(blank=True, null=True)
    week_11_bonus = models.IntegerField(blank=True, null=True)
    week_11_winner = models.BooleanField(default=False, blank=True)

    week_12_points = models.IntegerField(blank=True, null=True)
    week_12_bonus = models.IntegerField(blank=True, null=True)
    week_12_winner = models.BooleanField(default=False, blank=True)

    week_13_points = models.IntegerField(blank=True, null=True)
    week_13_bonus = models.IntegerField(blank=True, null=True)
    week_13_winner = models.BooleanField(default=False, blank=True)

    week_14_points = models.IntegerField(blank=True, null=True)
    week_14_bonus = models.IntegerField(blank=True, null=True)
    week_14_winner = models.BooleanField(default=False, blank=True)

    week_15_points = models.IntegerField(blank=True, null=True)
    week_15_bonus = models.IntegerField(blank=True, null=True)
    week_15_winner = models.BooleanField(default=False, blank=True)

    week_16_points = models.IntegerField(blank=True, null=True)
    week_16_bonus = models.IntegerField(blank=True, null=True)
    week_16_winner = models.BooleanField(default=False, blank=True)

    week_17_points = models.IntegerField(blank=True, null=True)
    week_17_bonus = models.IntegerField(blank=True, null=True)
    week_17_winner = models.BooleanField(default=False, blank=True)

    week_18_points = models.IntegerField(blank=True, null=True)
    week_18_bonus = models.IntegerField(blank=True, null=True)
    week_18_winner = models.BooleanField(default=False, blank=True)

    total_points = models.IntegerField(blank=True, null=True)

    year_winner = models.BooleanField(default=False, blank=True)

    playerAdded = models.DateTimeField(auto_now_add=True)
    playerUpdated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['total_points']


class userPoints(models.Model):
    id = models.CharField(max_length=250, primary_key=True)
    userEmail = models.EmailField(blank=True)
    userID = models.CharField(max_length=250, blank=True)
    gameyear = models.CharField(max_length=4, blank=True)
    gameseason = models.IntegerField(blank=True, null=True)
    week_1_points = models.IntegerField(blank=True, null=True)
    week_1_bonus = models.IntegerField(blank=True, null=True)
    week_1_winner = models.BooleanField(default=False, blank=True)

    week_2_points = models.IntegerField(blank=True, null=True)
    week_2_bonus = models.IntegerField(blank=True, null=True)
    week_2_winner = models.BooleanField(default=False, blank=True)

    week_3_points = models.IntegerField(blank=True, null=True)
    week_3_bonus = models.IntegerField(blank=True, null=True)
    week_3_winner = models.BooleanField(default=False, blank=True)

    week_4_points = models.IntegerField(blank=True, null=True)
    week_4_bonus = models.IntegerField(blank=True, null=True)
    week_4_winner = models.BooleanField(default=False, blank=True)

    week_5_points = models.IntegerField(blank=True, null=True)
    week_5_bonus = models.IntegerField(blank=True, null=True)
    week_5_winner = models.BooleanField(default=False, blank=True)

    week_6_points = models.IntegerField(blank=True, null=True)
    week_6_bonus = models.IntegerField(blank=True, null=True)
    week_6_winner = models.BooleanField(default=False, blank=True)

    week_7_points = models.IntegerField(blank=True, null=True)
    week_7_bonus = models.IntegerField(blank=True, null=True)
    week_7_winner = models.BooleanField(default=False, blank=True)

    week_8_points = models.IntegerField(blank=True, null=True)
    week_8_bonus = models.IntegerField(blank=True, null=True)
    week_8_winner = models.BooleanField(default=False, blank=True)

    week_9_points = models.IntegerField(blank=True, null=True)
    week_9_bonus = models.IntegerField(blank=True, null=True)
    week_9_winner = models.BooleanField(default=False, blank=True)

    week_10_points = models.IntegerField(blank=True, null=True)
    week_10_bonus = models.IntegerField(blank=True, null=True)
    week_10_winner = models.BooleanField(default=False, blank=True)

    week_11_points = models.IntegerField(blank=True, null=True)
    week_11_bonus = models.IntegerField(blank=True, null=True)
    week_11_winner = models.BooleanField(default=False, blank=True)

    week_12_points = models.IntegerField(blank=True, null=True)
    week_12_bonus = models.IntegerField(blank=True, null=True)
    week_12_winner = models.BooleanField(default=False, blank=True)

    week_13_points = models.IntegerField(blank=True, null=True)
    week_13_bonus = models.IntegerField(blank=True, null=True)
    week_13_winner = models.BooleanField(default=False, blank=True)

    week_14_points = models.IntegerField(blank=True, null=True)
    week_14_bonus = models.IntegerField(blank=True, null=True)
    week_14_winner = models.BooleanField(default=False, blank=True)

    week_15_points = models.IntegerField(blank=True, null=True)
    week_15_bonus = models.IntegerField(blank=True, null=True)
    week_15_winner = models.BooleanField(default=False, blank=True)

    week_16_points = models.IntegerField(blank=True, null=True)
    week_16_bonus = models.IntegerField(blank=True, null=True)
    week_16_winner = models.BooleanField(default=False, blank=True)

    week_17_points = models.IntegerField(blank=True, null=True)
    week_17_bonus = models.IntegerField(blank=True, null=True)
    week_17_winner = models.BooleanField(default=False, blank=True)

    week_18_points = models.IntegerField(blank=True, null=True)
    week_18_bonus = models.IntegerField(blank=True, null=True)
    week_18_winner = models.BooleanField(default=False, blank=True)

    total_points = models.IntegerField(blank=True, null=True)

    year_winner = models.BooleanField(default=False, blank=True)

    playerAdded = models.DateTimeField(auto_now_add=True)
    playerUpdated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['total_points']


class GameWeeks(models.Model):
    weekNumber = models.IntegerField()
    competition = models.CharField(max_length=250)
    date = models.DateField()
    season = models.IntegerField(blank=True, null=True)


def __str__(self):
    return self.slug
