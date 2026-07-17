import uuid
from datetime import timedelta
from django.core.validators import MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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

    # Site-wide block. Distinct from FamilyMembership.status, which only removes a
    # user from one family. Blocking sets User.is_active = False (which Django's
    # auth backend already refuses to log in) and records who/why/when here.
    blocked_at = models.DateTimeField(
        blank=True, null=True, help_text="When this user was blocked site-wide",
    )
    blocked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='blocked_users',
        blank=True, null=True, help_text="Superadmin who blocked this user",
    )
    blocked_reason = models.TextField(
        blank=True, default='', help_text="Why this user was blocked",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['user__username']


class Family(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    name = models.CharField(max_length=200, help_text="Family display name")
    slug = models.SlugField(max_length=80, unique=True, help_text="Stable family URL slug")
    logo_url = models.CharField(max_length=500, null=True, blank=True, help_text="URL or static path to family logo (e.g. /static/images/logo.png or https://...)")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Family lifecycle status",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Family"
        verbose_name_plural = "Families"
        ordering = ['name', 'slug']
        indexes = [
            models.Index(fields=['slug'], name='family_slug_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=['active', 'inactive']),
                name='family_status_valid',
            ),
        ]


class Pool(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        ARCHIVED = 'archived', 'Archived'

    family = models.ForeignKey(Family, on_delete=models.PROTECT, related_name='pools')
    name = models.CharField(max_length=200, help_text="Pool display name")
    slug = models.SlugField(max_length=80, help_text="Stable pool slug within a family")
    season = models.IntegerField(help_text="Season in YYZZ format, e.g. 2526")
    competition = models.CharField(max_length=50, default='nfl', help_text="Competition identifier")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Pool lifecycle status",
    )
    is_default = models.BooleanField(default=False, help_text="Default pool for this family")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.family.name} - {self.name}"

    @property
    def display_season(self):
        """Format the YYZZ season for display, e.g. 2627 -> '2026-2027'."""
        season_str = str(self.season)
        if len(season_str) == 4:
            return f"20{season_str[:2]}-20{season_str[2:]}"
        return season_str

    class Meta:
        verbose_name = "Pool"
        verbose_name_plural = "Pools"
        ordering = ['family__name', 'season', 'name']
        indexes = [
            models.Index(fields=['family', 'slug', 'status'], name='pool_family_slug_status_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['family', 'slug'], name='unique_pool_family_slug'),
            models.CheckConstraint(
                check=models.Q(status__in=['active', 'inactive', 'archived']),
                name='pool_status_valid',
            ),
        ]


class FamilyMembership(models.Model):
    class Role(models.TextChoices):
        # DB value stays 'owner' (pre-rebrand); the family-facing name is Commissioner.
        OWNER = 'owner', 'Commissioner'
        ADMIN = 'admin', 'Admin'
        MEMBER = 'member', 'Member'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    family = models.ForeignKey(Family, on_delete=models.PROTECT, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='family_memberships')
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
        help_text="Family-level role",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Membership lifecycle status",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} in {self.family.name} ({self.role})"

    class Meta:
        verbose_name = "Family Membership"
        verbose_name_plural = "Family Memberships"
        ordering = ['family__name', 'user__username']
        indexes = [
            models.Index(fields=['family', 'user', 'status'], name='member_family_user_status_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['family', 'user'], name='unique_family_membership_user'),
            models.CheckConstraint(
                check=models.Q(role__in=['owner', 'admin', 'member']),
                name='family_membership_role_valid',
            ),
            models.CheckConstraint(
                check=models.Q(status__in=['active', 'inactive']),
                name='family_membership_status_valid',
            ),
        ]


class PoolSettings(models.Model):
    class PrimaryTiebreaker(models.TextChoices):
        TOTAL_SCORE = 'total_score', 'Closest total score'
        TOTAL_SCORE_NO_OVER = 'total_score_no_over', 'Closest total score without going over'
        COMBINED_YARDS = 'combined_yards', 'Closest combined yards'

    class SecondaryTiebreaker(models.TextChoices):
        COMBINED_YARDS = 'combined_yards', 'Closest combined yards'
        TOTAL_SCORE = 'total_score', 'Closest total score'
        SPLIT_POINTS = 'split_points', 'Split the points'
        COIN_FLIP = 'coin_flip', 'Coin flip'

    class PickType(models.TextChoices):
        STRAIGHT_UP = 'straight_up', 'Straight up (pick the winner)'
        AGAINST_SPREAD = 'against_spread', 'Against the spread (coming soon)'

    class MissedPickPolicy(models.TextChoices):
        ZERO_POINTS = 'zero_points', 'No points for missed picks'
        AUTO_HOME = 'auto_home', 'Auto-pick the home team'
        AUTO_FAVORITE = 'auto_favorite', 'Auto-pick the favorite'

    class LateJoinPolicy(models.TextChoices):
        OPEN = 'open', 'Members can join all season'
        LOCK_AFTER_WEEK_1 = 'lock_after_week_1', 'Entries lock after Week 1'

    class PayoutStructure(models.TextChoices):
        WINNER_TAKES_ALL = 'winner_takes_all', '1st place takes the whole pool'
        NINETY_TEN = 'ninety_ten', '1st gets 90%, 2nd gets 10%'
        SEVENTY_TWENTY_TEN = 'seventy_twenty_ten', '1st 70%, 2nd 20%, 3rd 10%'
        SECOND_GETS_FEE_BACK = 'second_gets_fee_back', '1st takes the pool, 2nd gets their entry fee back'

    pool = models.OneToOneField(Pool, on_delete=models.PROTECT, related_name='settings')
    picks_lock_at_kickoff = models.BooleanField(
        default=True,
        help_text="Lock picks when each game starts",
    )
    allow_tiebreaker = models.BooleanField(
        default=True,
        help_text="Allow tiebreaker predictions",
    )

    # Scoring rules (display/config now; automated scoring reads these later)
    win_points = models.PositiveSmallIntegerField(
        default=1,
        help_text="Points awarded per correct pick",
    )
    tie_points = models.PositiveSmallIntegerField(
        default=0,
        help_text="Points awarded when a picked game ends in a tie",
    )
    weekly_winner_points = models.PositiveSmallIntegerField(
        default=2,
        help_text="Bonus points awarded to the weekly winner",
    )
    primary_tiebreaker = models.CharField(
        max_length=32,
        choices=PrimaryTiebreaker.choices,
        default=PrimaryTiebreaker.TOTAL_SCORE,
        help_text="First tiebreaker used to settle weekly ties",
    )
    secondary_tiebreaker = models.CharField(
        max_length=32,
        choices=SecondaryTiebreaker.choices,
        default=SecondaryTiebreaker.COMBINED_YARDS,
        help_text="Second tiebreaker if the primary is also tied",
    )
    perfect_week_bonus_enabled = models.BooleanField(
        default=False,
        help_text="Award a cash bonus for picking every game correctly in a week",
    )
    perfect_week_bonus_amount = models.PositiveIntegerField(
        default=10,
        help_text="Perfect week bonus, in whole dollars",
    )
    entry_fee_enabled = models.BooleanField(
        default=False,
        help_text="Whether this pool collects an entry fee",
    )
    entry_fee_amount = models.PositiveIntegerField(
        default=0,
        help_text="Entry fee per player, in whole dollars",
    )
    pick_type = models.CharField(
        max_length=32,
        choices=PickType.choices,
        default=PickType.STRAIGHT_UP,
        help_text="How picks are made (against-the-spread is not yet available)",
    )
    missed_pick_policy = models.CharField(
        max_length=32,
        choices=MissedPickPolicy.choices,
        default=MissedPickPolicy.ZERO_POINTS,
        help_text="What happens when a member doesn't submit a pick",
    )
    include_playoffs = models.BooleanField(
        default=False,
        help_text="Continue the pool through the playoffs (scoring logic coming later)",
    )
    late_join_policy = models.CharField(
        max_length=32,
        choices=LateJoinPolicy.choices,
        default=LateJoinPolicy.OPEN,
        help_text="Whether members can join after the season starts",
    )
    payout_structure = models.CharField(
        max_length=32,
        choices=PayoutStructure.choices,
        default=PayoutStructure.WINNER_TAKES_ALL,
        help_text="How the pot is split when an entry fee is collected",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.pool}"

    class Meta:
        verbose_name = "Pool Settings"
        verbose_name_plural = "Pool Settings"
        ordering = ['pool__family__name', 'pool__name']


class FamilyInvitation(models.Model):
    family = models.ForeignKey(Family, on_delete=models.PROTECT, related_name='invitations')
    pool = models.ForeignKey(
        Pool,
        on_delete=models.SET_NULL,
        related_name='invitations',
        blank=True,
        null=True,
    )
    code_hash = models.CharField(max_length=128, unique=True, help_text="Hashed invite code")
    recipient_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Optional recipient email that must match the redeemer's account",
    )
    role = models.CharField(
        max_length=20,
        choices=FamilyMembership.Role.choices,
        default=FamilyMembership.Role.MEMBER,
        help_text="Role assigned when invite is accepted",
    )
    expires_at = models.DateTimeField(blank=True, null=True)
    is_revoked = models.BooleanField(default=False)
    max_uses = models.PositiveIntegerField(blank=True, null=True)
    use_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='created_family_invitations',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invitation for {self.family.name}"

    class Meta:
        verbose_name = "Family Invitation"
        verbose_name_plural = "Family Invitations"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code_hash'], name='invitation_code_hash_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(role__in=['owner', 'admin', 'member']),
                name='family_invitation_role_valid',
            ),
        ]


class FamilyAuditLog(models.Model):
    class Action(models.TextChoices):
        INVITATION_CREATED = 'invitation_created', 'Invitation created'
        INVITATION_REVOKED = 'invitation_revoked', 'Invitation revoked'
        MEMBERSHIP_CREATED = 'membership_created', 'Membership created'
        MEMBERSHIP_UPDATED = 'membership_updated', 'Membership updated'
        POOL_SETTINGS_UPDATED = 'pool_settings_updated', 'Pool settings updated'
        MANUAL_PICK_UPDATED = 'manual_pick_updated', 'Manual pick updated'
        WEEK_WINNER_UPDATED = 'week_winner_updated', 'Week winner updated'

    family = models.ForeignKey(Family, on_delete=models.PROTECT, related_name='audit_logs')
    pool = models.ForeignKey(
        Pool,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
        blank=True,
        null=True,
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='family_audit_logs',
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.family.name}: {self.action} at {self.created_at}"

    class Meta:
        verbose_name = "Family Audit Log"
        verbose_name_plural = "Family Audit Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['family', 'created_at'], name='audit_family_created_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(action__in=[
                    'invitation_created',
                    'invitation_revoked',
                    'membership_created',
                    'membership_updated',
                    'pool_settings_updated',
                    'manual_pick_updated',
                    'week_winner_updated',
                ]),
                name='family_audit_log_action_valid',
            ),
        ]


class Teams(models.Model):
    class LogoContrastPreset(models.TextChoices):
        DEFAULT = 'default', 'Default'
        REVERSE_GRADIENT = 'reverse-gradient', 'Reverse gradient'
        WHITE_BURST = 'white-burst', 'White burst'

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
    logo_contrast_preset = models.CharField(
        max_length=32,
        choices=LogoContrastPreset.choices,
        default=LogoContrastPreset.DEFAULT,
        help_text="Controls the admin-selected logo contrast treatment for scorecards and other branded surfaces.",
    )

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
    pool = models.ForeignKey(
        Pool,
        on_delete=models.SET_NULL,
        related_name='game_picks',
        blank=True,
        null=True,
    )
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
    auto_pick = models.BooleanField(
        default=False,
        help_text="Pick was generated by the pool's missed-pick policy, not the user",
    )
    pickAdded = models.DateTimeField(auto_now_add=True, db_column='pickadded')
    pickUpdated = models.DateTimeField(auto_now=True, db_column='pickupdated')

    class Meta:
        ordering = ['gameWeek']
        indexes = [
            models.Index(fields=['pool', 'gameseason'], name='gp_pool_season_idx'),
            models.Index(fields=['pool', 'gameseason', 'gameWeek'], name='gp_pool_season_week_idx'),
            models.Index(fields=['pool', 'userID'], name='gp_pool_userid_idx'),
        ]


class userSeasonPoints(models.Model):
    id = models.AutoField(primary_key=True)
    pool = models.ForeignKey(
        Pool,
        on_delete=models.SET_NULL,
        related_name='season_points',
        blank=True,
        null=True,
    )
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
        indexes = [
            models.Index(fields=['pool', 'gameseason'], name='usp_pool_season_idx'),
            models.Index(fields=['pool', 'userID'], name='usp_pool_userid_idx'),
        ]


class userPoints(models.Model):
    id = models.CharField(max_length=250, primary_key=True)
    pool = models.ForeignKey(
        Pool,
        on_delete=models.SET_NULL,
        related_name='legacy_user_points',
        blank=True,
        null=True,
    )
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
        indexes = [
            models.Index(fields=['pool', 'gameseason'], name='up_pool_season_idx'),
            models.Index(fields=['pool', 'userID'], name='up_pool_userid_idx'),
        ]


class GameWeeks(models.Model):
    weekNumber = models.IntegerField(db_column='weeknumber')
    competition = models.CharField(max_length=250)
    date = models.DateField()
    season = models.IntegerField(blank=True, null=True)

class userStats(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pool = models.ForeignKey(
        Pool,
        on_delete=models.SET_NULL,
        related_name='user_stats',
        blank=True,
        null=True,
    )
    userEmail = models.EmailField(blank=True, db_column='useremail')
    userID = models.CharField(max_length=250, blank=True, db_column='userid')
    # Number of Weeks Won (Season / All Time)
    weeksWonSeason = models.IntegerField(blank=True, null=True, db_column='weekswonseason')
    weeksWonTotal = models.IntegerField(blank=True, null=True, db_column='weekswontotal')
    # Correct Pick Percentage (Season / All Time)
    pickPercentSeason = models.IntegerField(blank=True, null=True, db_column='pickpercentseason')
    pickPercentTotal = models.IntegerField(blank=True, null=True, db_column='pickpercenttotal')
    # Total Number of Correct Picks (Season / All Time)
    correctPickTotalSeason = models.IntegerField(blank=True, null=True, db_column='correctpicktotalseason')
    correctPickTotalTotal = models.IntegerField(blank=True, null=True, db_column='correctpicktotaltotal')
    # Total Number of Picks (Season / All Time)
    totalPicksSeason = models.IntegerField(blank=True, null=True, db_column='totalpicksseason')
    totalPicksTotal = models.IntegerField(blank=True, null=True, db_column='totalpickstotal')
    # Most Picked Team (Season / All Time)
    mostPickedSeason = models.TextField(blank=True, null=True, db_column='mostpickedseason')
    mostPickedTotal = models.TextField(blank=True, null=True, db_column='mostpickedtotal')
    # Least Picked Team (Season / All Time)
    leastPickedSeason = models.TextField(blank=True, null=True, db_column='leastpickedseason')
    leastPickedTotal = models.TextField(blank=True, null=True, db_column='leastpickedtotal')
    # Number of seasons won (All Time)
    seasonsWon = models.IntegerField(blank=True, null=True, db_column='seasonswon')
    # Missed Picks (Season / All Time)
    missedPicksSeason = models.IntegerField(blank=True, null=True, db_column='missedpicksseason')
    missedPicksTotal = models.IntegerField(blank=True, null=True, db_column='missedpickstotal')
    # Perfect Weeks (Season / All Time)
    perfectWeeksSeason = models.IntegerField(blank=True, null=True, db_column='perfectweeksseason')
    perfectWeeksTotal = models.IntegerField(blank=True, null=True, db_column='perfectweekstotal')

    class Meta:
        indexes = [
            models.Index(fields=['pool', 'userID'], name='us_pool_userid_idx'),
        ]

class currentSeason(models.Model):
    season = models.IntegerField(blank=True, null=True)
    display_name = models.CharField(max_length=20, blank=True, null=True, help_text="User-friendly season name (e.g., '2025-2026')")

    class Meta:
        # This table is a singleton in practice. Deterministic ordering keeps the
        # ubiquitous `.first()` reads stable even if a stray second row ever
        # appears; the superadmin season-update path collapses duplicates.
        ordering = ['id']

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


class ScheduledJobConfig(models.Model):
    """Editable cadence for one orchestrated job (a pipeline step or a standalone
    evaluator — see scheduler.ORCHESTRATED_JOBS).

    The scheduler's single orchestrator tick reads these every minute and runs
    each job whose row is enabled and due (now - last_run_at >= interval). The
    superadmin console edits interval/enabled; last_run_at is bookkeeping the
    orchestrator writes.
    """
    job_id = models.CharField(max_length=100, unique=True)
    interval_minutes = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
    )
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['job_id']

    def __str__(self):
        state = 'on' if self.enabled else 'off'
        return f'{self.job_id}: every {self.interval_minutes}m ({state})'

    def is_due(self, now):
        if self.last_run_at is None:
            return True
        return (now - self.last_run_at) >= timedelta(minutes=self.interval_minutes)

    @classmethod
    def seed_from_pipeline(cls):
        """Create a config row for any orchestrated job that has none. Never
        overwrites an existing (possibly edited) row."""
        from pickem_api.scheduler import JOB_DEFAULT_MINUTES  # local: scheduler imports models

        for job_id, default_minutes in JOB_DEFAULT_MINUTES.items():
            cls.objects.get_or_create(
                job_id=job_id,
                defaults={'interval_minutes': default_minutes},
            )


class RunningJobMarker(models.Model):
    """A row exists while an APScheduler job is executing. Written by scheduler
    event listeners, read by the superadmin jobs status endpoint. DB-backed (not
    in-memory) because a console request may run in a different worker than the
    scheduler."""
    job_id = models.CharField(max_length=100, unique=True)
    started_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['started_at']

    def __str__(self):
        return f'{self.job_id} running since {self.started_at}'


class JobRun(models.Model):
    """One execution of an orchestrated job. Its `run_id` is stamped onto every
    SuperAdminLogEntry written during the run, so the jobs page can link a run to
    its exact logs."""

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        SUCCESS = 'success', 'Success'
        ERROR = 'error', 'Error'

    run_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    job_id = models.CharField(max_length=100, db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.RUNNING,
    )
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    exception = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['job_id', '-started_at'], name='jobrun_job_started_idx'),
            models.Index(fields=['-started_at'], name='jobrun_started_idx'),
        ]

    def __str__(self):
        return f'{self.job_id} {self.status} @ {self.started_at:%Y-%m-%d %H:%M:%S}'
