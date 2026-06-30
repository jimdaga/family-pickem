import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0071_userseasonpoints_current_rank'),
    ]

    operations = [
        # -------------------------------------------------------
        # Teams (7 fields)
        # -------------------------------------------------------
        migrations.AlterField(
            model_name='teams',
            name='teamNameSlug',
            field=models.CharField(db_column='teamnameslug', max_length=250),
        ),
        migrations.AlterField(
            model_name='teams',
            name='teamNameName',
            field=models.CharField(db_column='teamnamename', max_length=250),
        ),
        migrations.AlterField(
            model_name='teams',
            name='teamLogo',
            field=models.CharField(blank=True, db_column='teamlogo', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='teams',
            name='teamWins',
            field=models.IntegerField(db_column='teamwins', default=0),
        ),
        migrations.AlterField(
            model_name='teams',
            name='teamLosses',
            field=models.IntegerField(db_column='teamlosses', default=0),
        ),
        migrations.AlterField(
            model_name='teams',
            name='teamTies',
            field=models.IntegerField(db_column='teamties', default=0),
        ),
        migrations.AlterField(
            model_name='teams',
            name='alternateColor',
            field=models.CharField(blank=True, db_column='alternatecolor', max_length=6, null=True),
        ),

        # -------------------------------------------------------
        # GamesAndScores (32 fields, statusType already done but included for completeness)
        # -------------------------------------------------------
        migrations.AlterField(
            model_name='gamesandscores',
            name='gameWeek',
            field=models.CharField(db_column='gameweek', max_length=2),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='startTimestamp',
            field=models.DateTimeField(db_column='starttimestamp'),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='gameWinner',
            field=models.CharField(blank=True, db_column='gamewinner', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='statusType',
            field=models.CharField(db_column='statustype', max_length=250),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='statusTitle',
            field=models.CharField(db_column='statustitle', max_length=250),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamId',
            field=models.IntegerField(db_column='hometeamid'),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamSlug',
            field=models.CharField(db_column='hometeamslug', max_length=250),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamName',
            field=models.CharField(db_column='hometeamname', max_length=250),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamScore',
            field=models.IntegerField(blank=True, db_column='hometeamscore', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamPeriod1',
            field=models.IntegerField(blank=True, db_column='hometeamperiod1', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamPeriod2',
            field=models.IntegerField(blank=True, db_column='hometeamperiod2', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamPeriod3',
            field=models.IntegerField(blank=True, db_column='hometeamperiod3', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamPeriod4',
            field=models.IntegerField(blank=True, db_column='hometeamperiod4', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamPeriodOT',
            field=models.IntegerField(blank=True, db_column='hometeamperiodot', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamId',
            field=models.IntegerField(db_column='awayteamid'),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamSlug',
            field=models.CharField(db_column='awayteamslug', max_length=250),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamName',
            field=models.CharField(db_column='awayteamname', max_length=250),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamScore',
            field=models.IntegerField(blank=True, db_column='awayteamscore', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamPeriod1',
            field=models.IntegerField(blank=True, db_column='awayteamperiod1', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamPeriod2',
            field=models.IntegerField(blank=True, db_column='awayteamperiod2', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamPeriod3',
            field=models.IntegerField(blank=True, db_column='awayteamperiod3', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamPeriod4',
            field=models.IntegerField(blank=True, db_column='awayteamperiod4', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamPeriodOT',
            field=models.IntegerField(blank=True, db_column='awayteamperiodot', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='tieBreakerGame',
            field=models.BooleanField(db_column='tiebreakergame', default=False),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='gameAdded',
            field=models.DateTimeField(auto_now_add=True, db_column='gameadded'),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='gameUpdated',
            field=models.DateTimeField(auto_now=True, db_column='gameupdated'),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='gameScored',
            field=models.BooleanField(db_column='gamescored', default=False),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='homeTeamWinProbability',
            field=models.FloatField(blank=True, db_column='hometeamwinprobability', help_text='Home team win probability as percentage (0-100)', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='awayTeamWinProbability',
            field=models.FloatField(blank=True, db_column='awayteamwinprobability', help_text='Away team win probability as percentage (0-100)', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='overUnder',
            field=models.FloatField(blank=True, db_column='overunder', help_text='Over/under total points line', null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='weatherCondition',
            field=models.CharField(blank=True, db_column='weathercondition', help_text='Weather condition description', max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='venueIndoor',
            field=models.BooleanField(db_column='venueindoor', default=False, help_text='Whether the game is played indoors'),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='gamecastUrl',
            field=models.URLField(blank=True, db_column='gamecasturl', help_text='ESPN Gamecast URL for the game', max_length=500, null=True),
        ),

        # -------------------------------------------------------
        # GamePicks (7 fields)
        # -------------------------------------------------------
        migrations.AlterField(
            model_name='gamepicks',
            name='userEmail',
            field=models.EmailField(blank=True, db_column='useremail', max_length=254),
        ),
        migrations.AlterField(
            model_name='gamepicks',
            name='userID',
            field=models.CharField(blank=True, db_column='userid', max_length=250),
        ),
        migrations.AlterField(
            model_name='gamepicks',
            name='gameWeek',
            field=models.CharField(blank=True, db_column='gameweek', max_length=2),
        ),
        migrations.AlterField(
            model_name='gamepicks',
            name='tieBreakerScore',
            field=models.IntegerField(blank=True, db_column='tiebreakerscore', null=True),
        ),
        migrations.AlterField(
            model_name='gamepicks',
            name='tieBreakerYards',
            field=models.IntegerField(blank=True, db_column='tiebreakeryards', null=True),
        ),
        migrations.AlterField(
            model_name='gamepicks',
            name='pickAdded',
            field=models.DateTimeField(auto_now_add=True, db_column='pickadded'),
        ),
        migrations.AlterField(
            model_name='gamepicks',
            name='pickUpdated',
            field=models.DateTimeField(auto_now=True, db_column='pickupdated'),
        ),

        # -------------------------------------------------------
        # userSeasonPoints (4 fields)
        # -------------------------------------------------------
        migrations.AlterField(
            model_name='userseasonpoints',
            name='userEmail',
            field=models.EmailField(blank=True, db_column='useremail', max_length=254),
        ),
        migrations.AlterField(
            model_name='userseasonpoints',
            name='userID',
            field=models.CharField(blank=True, db_column='userid', max_length=250),
        ),
        migrations.AlterField(
            model_name='userseasonpoints',
            name='playerAdded',
            field=models.DateTimeField(auto_now_add=True, db_column='playeradded'),
        ),
        migrations.AlterField(
            model_name='userseasonpoints',
            name='playerUpdated',
            field=models.DateTimeField(auto_now=True, db_column='playerupdated'),
        ),

        # -------------------------------------------------------
        # userPoints (4 fields)
        # -------------------------------------------------------
        migrations.AlterField(
            model_name='userpoints',
            name='userEmail',
            field=models.EmailField(blank=True, db_column='useremail', max_length=254),
        ),
        migrations.AlterField(
            model_name='userpoints',
            name='userID',
            field=models.CharField(blank=True, db_column='userid', max_length=250),
        ),
        migrations.AlterField(
            model_name='userpoints',
            name='playerAdded',
            field=models.DateTimeField(auto_now_add=True, db_column='playeradded'),
        ),
        migrations.AlterField(
            model_name='userpoints',
            name='playerUpdated',
            field=models.DateTimeField(auto_now=True, db_column='playerupdated'),
        ),

        # -------------------------------------------------------
        # GameWeeks (1 field)
        # -------------------------------------------------------
        migrations.AlterField(
            model_name='gameweeks',
            name='weekNumber',
            field=models.IntegerField(db_column='weeknumber'),
        ),

        # -------------------------------------------------------
        # userStats (19 fields)
        # -------------------------------------------------------
        migrations.AlterField(
            model_name='userstats',
            name='userEmail',
            field=models.EmailField(blank=True, db_column='useremail', max_length=254),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='userID',
            field=models.CharField(blank=True, db_column='userid', max_length=250),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='weeksWonSeason',
            field=models.IntegerField(blank=True, db_column='weekswonseason', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='weeksWonTotal',
            field=models.IntegerField(blank=True, db_column='weekswontotal', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='pickPercentSeason',
            field=models.IntegerField(blank=True, db_column='pickpercentseason', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='pickPercentTotal',
            field=models.IntegerField(blank=True, db_column='pickpercenttotal', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='correctPickTotalSeason',
            field=models.IntegerField(blank=True, db_column='correctpicktotalseason', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='correctPickTotalTotal',
            field=models.IntegerField(blank=True, db_column='correctpicktotaltotal', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='totalPicksSeason',
            field=models.IntegerField(blank=True, db_column='totalpicksseason', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='totalPicksTotal',
            field=models.IntegerField(blank=True, db_column='totalpickstotal', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='mostPickedSeason',
            field=models.TextField(blank=True, db_column='mostpickedseason', null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='mostPickedTotal',
            field=models.TextField(blank=True, db_column='mostpickedtotal', null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='leastPickedSeason',
            field=models.TextField(blank=True, db_column='leastpickedseason', null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='leastPickedTotal',
            field=models.TextField(blank=True, db_column='leastpickedtotal', null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='seasonsWon',
            field=models.IntegerField(blank=True, db_column='seasonswon', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='missedPicksSeason',
            field=models.IntegerField(blank=True, db_column='missedpicksseason', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='missedPicksTotal',
            field=models.IntegerField(blank=True, db_column='missedpickstotal', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='perfectWeeksSeason',
            field=models.IntegerField(blank=True, db_column='perfectweeksseason', max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='perfectWeeksTotal',
            field=models.IntegerField(blank=True, db_column='perfectweekstotal', max_length=250, null=True),
        ),
    ]
