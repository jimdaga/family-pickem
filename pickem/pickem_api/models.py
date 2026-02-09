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
    teamNameSlug = models.CharField(max_length=250, db_column='teamnameslug')
    teamNameName = models.CharField(max_length=250, db_column='teamnamename')
    teamLogo = models.CharField(max_length=250, blank=True, null=True, db_column='teamlogo')
    teamWins = models.IntegerField(default=0, db_column='teamwins')
    teamLosses = models.IntegerField(default=0, db_column='teamlosses')
    teamTies = models.IntegerField(default=0, db_column='teamties')
    color = models.CharField(max_length=6, blank=True, null=True)
    alternateColor = models.CharField(max_length=6, blank=True, null=True, db_column='alternatecolor')

class GamesAndScores(models.Model):
    id = models.IntegerField(primary_key=True)
    slug = models.SlugField(max_length=250)
    competition = models.CharField(max_length=250)
    gameWeek = models.CharField(max_length=2, db_column='gameweek')
    gameyear = models.CharField(max_length=4)
    gameseason = models.IntegerField(blank=True, null=True)
    startTimestamp = models.DateTimeField(db_column='starttimestamp')
    gameWinner = models.CharField(max_length=250, blank=True, null=True, db_column='gamewinner')
    statusType = models.CharField(max_length=250, db_column='statustype')
    statusTitle = models.CharField(max_length=250, db_column='statustitle')
    homeTeamId = models.IntegerField(db_column='hometeamid')
    homeTeamSlug = models.CharField(max_length=250, db_column='hometeamslug')
    homeTeamName = models.CharField(max_length=250, db_column='hometeamname')
    homeTeamScore = models.IntegerField(blank=True, null=True, db_column='hometeamscore')
    homeTeamPeriod1 = models.IntegerField(blank=True, null=True, db_column='hometeamperiod1')
    homeTeamPeriod2 = models.IntegerField(blank=True, null=True, db_column='hometeamperiod2')
    homeTeamPeriod3 = models.IntegerField(blank=True, null=True, db_column='hometeamperiod3')
    homeTeamPeriod4 = models.IntegerField(blank=True, null=True, db_column='hometeamperiod4')
    homeTeamPeriodOT = models.IntegerField(blank=True, null=True, db_column='hometeamperiodot')
    awayTeamId = models.IntegerField(db_column='awayteamid')
    awayTeamSlug = models.CharField(max_length=250, db_column='awayteamslug')
    awayTeamName = models.CharField(max_length=250, db_column='awayteamname')
    awayTeamScore = models.IntegerField(blank=True, null=True, db_column='awayteamscore')
    awayTeamPeriod1 = models.IntegerField(blank=True, null=True, db_column='awayteamperiod1')
    awayTeamPeriod2 = models.IntegerField(blank=True, null=True, db_column='awayteamperiod2')
    awayTeamPeriod3 = models.IntegerField(blank=True, null=True, db_column='awayteamperiod3')
    awayTeamPeriod4 = models.IntegerField(blank=True, null=True, db_column='awayteamperiod4')
    awayTeamPeriodOT = models.IntegerField(blank=True, null=True, db_column='awayteamperiodot')
    tieBreakerGame = models.BooleanField(default=False, db_column='tiebreakergame')
    gameAdded = models.DateTimeField(auto_now_add=True, db_column='gameadded')
    gameUpdated = models.DateTimeField(auto_now=True, db_column='gameupdated')
    gameScored = models.BooleanField(default=False, db_column='gamescored')

    # Betting and Odds Information
    homeTeamWinProbability = models.FloatField(blank=True, null=True, help_text="Home team win probability as percentage (0-100)", db_column='hometeamwinprobability')
    awayTeamWinProbability = models.FloatField(blank=True, null=True, help_text="Away team win probability as percentage (0-100)", db_column='awayteamwinprobability')
    spread = models.FloatField(blank=True, null=True, help_text="Point spread (positive favors home team)")
    overUnder = models.FloatField(blank=True, null=True, help_text="Over/under total points line", db_column='overunder')

    # Weather and Venue Information
    temperature = models.IntegerField(blank=True, null=True, help_text="Game temperature in Fahrenheit")
    weatherCondition = models.CharField(max_length=100, blank=True, null=True, help_text="Weather condition description", db_column='weathercondition')
    venueIndoor = models.BooleanField(default=False, help_text="Whether the game is played indoors", db_column='venueindoor')

    # Broadcast and Links
    broadcast = models.CharField(max_length=50, blank=True, null=True, help_text="TV network broadcasting the game (e.g., CBS, FOX, ESPN)")
    gamecastUrl = models.URLField(max_length=500, blank=True, null=True, help_text="ESPN Gamecast URL for the game", db_column='gamecasturl')

    class Meta:
        ordering = ['startTimestamp']


class GamePicks(models.Model):
    id = models.CharField(max_length=250, primary_key=True)
    userEmail = models.EmailField(blank=True, db_column='useremail')
    uid = models.IntegerField(blank=True, null=True)
    userID = models.CharField(max_length=250, blank=True, db_column='userid')
    slug = models.SlugField(max_length=250, blank=True)
    competition = models.CharField(max_length=250, blank=True)
    gameWeek = models.CharField(max_length=2, blank=True, db_column='gameweek')
    gameyear = models.CharField(max_length=4, blank=True)
    gameseason = models.IntegerField(blank=True, null=True)
    pick_game_id = models.IntegerField(blank=True)
    pick = models.CharField(max_length=250, blank=True)
    tieBreakerScore = models.IntegerField(blank=True, null=True, db_column='tiebreakerscore')
    tieBreakerYards = models.IntegerField(blank=True, null=True, db_column='tiebreakeryards')
    pick_correct = models.BooleanField(default=False, blank=True)
    pickAdded = models.DateTimeField(auto_now_add=True, db_column='pickadded')
    pickUpdated = models.DateTimeField(auto_now=True, db_column='pickupdated')

    class Meta:
        ordering = ['gameWeek']


class userSeasonPoints(models.Model):
    id = models.AutoField(primary_key=True)
    userEmail = models.EmailField(blank=True, db_column='useremail')
    userID = models.CharField(max_length=250, blank=True, db_column='userid')
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

    playerAdded = models.DateTimeField(auto_now_add=True, db_column='playeradded')
    playerUpdated = models.DateTimeField(auto_now=True, db_column='playerupdated')

    class Meta:
        ordering = ['total_points']


class userPoints(models.Model):
    id = models.CharField(max_length=250, primary_key=True)
    userEmail = models.EmailField(blank=True, db_column='useremail')
    userID = models.CharField(max_length=250, blank=True, db_column='userid')
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

    playerAdded = models.DateTimeField(auto_now_add=True, db_column='playeradded')
    playerUpdated = models.DateTimeField(auto_now=True, db_column='playerupdated')

    class Meta:
        ordering = ['total_points']


class GameWeeks(models.Model):
    weekNumber = models.IntegerField(db_column='weeknumber')
    competition = models.CharField(max_length=250)
    date = models.DateField()
    season = models.IntegerField(blank=True, null=True)

class userStats(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    userEmail = models.EmailField(blank=True, db_column='useremail')
    userID = models.CharField(max_length=250, blank=True, db_column='userid')
    # Number of Weeks Won (Season / All Time)
    weeksWonSeason = models.IntegerField(max_length=250, blank=True, null=True, db_column='weekswonseason')
    weeksWonTotal = models.IntegerField(max_length=250, blank=True, null=True, db_column='weekswontotal')
    # Correct Pick Percentage (Season / All Time)
    pickPercentSeason = models.IntegerField(max_length=250, blank=True, null=True, db_column='pickpercentseason')
    pickPercentTotal = models.IntegerField(max_length=250, blank=True, null=True, db_column='pickpercenttotal')
    # Total Number of Correct Picks (Season / All Time)
    correctPickTotalSeason = models.IntegerField(max_length=250, blank=True, null=True, db_column='correctpicktotalseason')
    correctPickTotalTotal = models.IntegerField(max_length=250, blank=True, null=True, db_column='correctpicktotaltotal')
    # Total Number of Picks (Season / All Time)
    totalPicksSeason = models.IntegerField(max_length=250, blank=True, null=True, db_column='totalpicksseason')
    totalPicksTotal = models.IntegerField(max_length=250, blank=True, null=True, db_column='totalpickstotal')
    # Most Picked Team (Season / All Time)
    mostPickedSeason = models.TextField(blank=True, null=True, db_column='mostpickedseason')
    mostPickedTotal = models.TextField(blank=True, null=True, db_column='mostpickedtotal')
    # Least Picked Team (Season / All Time)
    leastPickedSeason = models.TextField(blank=True, null=True, db_column='leastpickedseason')
    leastPickedTotal = models.TextField(blank=True, null=True, db_column='leastpickedtotal')
    # Number of seasons won (All Time)
    seasonsWon = models.IntegerField(max_length=250, blank=True, null=True, db_column='seasonswon')
    # Missed Picks (Season / All Time)
    missedPicksSeason = models.IntegerField(max_length=250, blank=True, null=True, db_column='missedpicksseason')
    missedPicksTotal = models.IntegerField(max_length=250, blank=True, null=True, db_column='missedpickstotal')
    # Perfect Weeks (Season / All Time)
    perfectWeeksSeason = models.IntegerField(max_length=250, blank=True, null=True, db_column='perfectweeksseason')
    perfectWeeksTotal = models.IntegerField(max_length=250, blank=True, null=True, db_column='perfectweekstotal')

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
