from time import timezone
import uuid
from xmlrpc.client import Boolean
from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Personal Information
    tagline = models.CharField(max_length=200, blank=True, null=True, help_text="A short personal tagline or bio")
    favorite_team = models.CharField(max_length=250, blank=True, null=True, help_text="User's favorite NFL team slug")
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Contact phone number")
    
    # Site Settings
    email_notifications = models.BooleanField(default=True, help_text="Receive email notifications")
    dark_mode = models.BooleanField(default=False, help_text="Use dark mode theme")
    private_profile = models.BooleanField(default=False, help_text="Make profile private to other users")
    
    # Role Settings
    is_commissioner = models.BooleanField(default=False, help_text="User has commissioner privileges")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['user__username']


class Teams(models.Model):
    id = models.IntegerField(primary_key=True)
    gameseason = models.IntegerField(blank=True, null=True)
    teamNameSlug = models.CharField(max_length=250)
    teamNameName = models.CharField(max_length=250)
    teamLogo = models.CharField(max_length=250, blank=True, null=True)
    teamWins = models.IntegerField(default=0)
    teamLosses = models.IntegerField(default=0)
    teamTies = models.IntegerField(default=0)
    color = models.CharField(max_length=6, blank=True, null=True)
    alternateColor = models.CharField(max_length=6, blank=True, null=True)

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
    
    # Betting and Odds Information
    homeTeamWinProbability = models.FloatField(blank=True, null=True, help_text="Home team win probability as percentage (0-100)")
    awayTeamWinProbability = models.FloatField(blank=True, null=True, help_text="Away team win probability as percentage (0-100)")
    spread = models.FloatField(blank=True, null=True, help_text="Point spread (positive favors home team)")
    overUnder = models.FloatField(blank=True, null=True, help_text="Over/under total points line")
    
    # Weather and Venue Information
    temperature = models.IntegerField(blank=True, null=True, help_text="Game temperature in Fahrenheit")
    weatherCondition = models.CharField(max_length=100, blank=True, null=True, help_text="Weather condition description")
    venueIndoor = models.BooleanField(default=False, help_text="Whether the game is played indoors")

    # Broadcast and Links
    broadcast = models.CharField(max_length=50, blank=True, null=True, help_text="TV network broadcasting the game (e.g., CBS, FOX, ESPN)")
    gamecastUrl = models.URLField(max_length=500, blank=True, null=True, help_text="ESPN Gamecast URL for the game")

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
    current_rank = models.IntegerField(blank=True, null=True, help_text='Current ranking position (handles ties)')

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

class userStats(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    userEmail = models.EmailField(blank=True)
    userID = models.CharField(max_length=250, blank=True)
    # Number of Weeks Won (Season / All Time)
    weeksWonSeason = models.IntegerField(max_length=250, blank=True, null=True)
    weeksWonTotal = models.IntegerField(max_length=250, blank=True, null=True)
    # Correct Pick Percentage (Season / All Time)
    pickPercentSeason = models.IntegerField(max_length=250, blank=True, null=True)
    pickPercentTotal = models.IntegerField(max_length=250, blank=True, null=True)
    # Total Number of Correct Picks (Season / All Time)
    correctPickTotalSeason = models.IntegerField(max_length=250, blank=True, null=True)
    correctPickTotalTotal = models.IntegerField(max_length=250, blank=True, null=True)
    # Total Number of Picks (Season / All Time)
    totalPicksSeason = models.IntegerField(max_length=250, blank=True, null=True)
    totalPicksTotal = models.IntegerField(max_length=250, blank=True, null=True)
    # Most Picked Team (Season / All Time)
    mostPickedSeason = models.TextField(blank=True, null=True)
    mostPickedTotal = models.TextField(blank=True, null=True)
    # Least Picked Team (Season / All Time)
    leastPickedSeason = models.TextField(blank=True, null=True)
    leastPickedTotal = models.TextField(blank=True, null=True)
    # Number of seasons won (All Time)
    seasonsWon = models.IntegerField(max_length=250, blank=True, null=True)
    # Missed Picks (Season / All Time)
    missedPicksSeason = models.IntegerField(max_length=250, blank=True, null=True)
    missedPicksTotal = models.IntegerField(max_length=250, blank=True, null=True)
    # Perfect Weeks (Season / All Time)
    perfectWeeksSeason = models.IntegerField(max_length=250, blank=True, null=True)
    perfectWeeksTotal = models.IntegerField(max_length=250, blank=True, null=True)

class currentSeason(models.Model):
    season = models.IntegerField(blank=True, null=True)
    display_name = models.CharField(max_length=20, blank=True, null=True, help_text="User-friendly season name (e.g., '2025-2026')")

    def __str__(self):
        return self.display_name or str(self.season)

    def get_display_season(self):
        """Return the display name if available, otherwise format the season number"""
        if self.display_name:
            return self.display_name
        if self.season:
            # Convert season number like 2526 to "2025-2026"
            season_str = str(self.season)
            if len(season_str) == 4:
                year1 = season_str[:2]
                year2 = season_str[2:]
                return f"20{year1}-20{year2}"
        return str(self.season)
