from django.contrib import admin
from .models import (
    Family, FamilyAuditLog, FamilyInvitation, FamilyMembership, GamePicks,
    GamesAndScores, GameWeeks, Pool, PoolSettings, Teams, userPoints,
    userSeasonPoints, userStats, currentSeason, UserProfile,
)

# Register your models here.
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'tagline', 'favorite_team', 'phone_number', 'email_notifications', 'dark_mode', 'private_profile', 'is_commissioner', 'created_at', 'updated_at')
    list_filter = ('email_notifications', 'dark_mode', 'private_profile', 'is_commissioner', 'favorite_team', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'tagline', 'phone_number')
    date_hierarchy = 'created_at'
    ordering = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Personal Information', {
            'fields': ('tagline', 'favorite_team', 'phone_number')
        }),
        ('Site Settings', {
            'fields': ('email_notifications', 'dark_mode', 'private_profile')
        }),
        ('Role Settings', {
            'fields': ('is_commissioner',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'status', 'logo_url', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'slug')
    date_hierarchy = 'created_at'
    ordering = ('name', 'slug')
    readonly_fields = ('created_at', 'updated_at')
    fields = ('name', 'slug', 'logo_url', 'status', 'created_at', 'updated_at')


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'slug', 'season', 'competition', 'status', 'is_default', 'created_at', 'updated_at')
    list_filter = ('status', 'competition', 'season', 'is_default', 'created_at')
    search_fields = ('name', 'slug', 'family__name', 'family__slug')
    date_hierarchy = 'created_at'
    ordering = ('family__name', 'season', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FamilyMembership)
class FamilyMembershipAdmin(admin.ModelAdmin):
    list_display = ('family', 'user', 'role', 'status', 'created_at', 'updated_at')
    list_filter = ('role', 'status', 'created_at')
    search_fields = ('family__name', 'family__slug', 'user__username', 'user__email', 'user__first_name', 'user__last_name')
    date_hierarchy = 'created_at'
    ordering = ('family__name', 'user__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PoolSettings)
class PoolSettingsAdmin(admin.ModelAdmin):
    list_display = ('pool', 'picks_lock_mode', 'allow_tiebreaker', 'created_at', 'updated_at')
    list_filter = ('picks_lock_mode', 'allow_tiebreaker', 'created_at')
    search_fields = ('pool__name', 'pool__slug', 'pool__family__name', 'pool__family__slug')
    date_hierarchy = 'created_at'
    ordering = ('pool__family__name', 'pool__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FamilyInvitation)
class FamilyInvitationAdmin(admin.ModelAdmin):
    list_display = ('family', 'pool', 'recipient_email', 'code_hash', 'role', 'expires_at', 'is_revoked', 'max_uses', 'use_count', 'created_by', 'created_at')
    list_filter = ('role', 'is_revoked', 'expires_at', 'created_at')
    search_fields = ('family__name', 'family__slug', 'pool__name', 'pool__slug', 'recipient_email', 'code_hash', 'created_by__username', 'created_by__email')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FamilyAuditLog)
class FamilyAuditLogAdmin(admin.ModelAdmin):
    list_display = ('family', 'pool', 'actor', 'action', 'target_type', 'target_id', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('family__name', 'family__slug', 'pool__name', 'pool__slug', 'actor__username', 'actor__email', 'target_type', 'target_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = (
        'family', 'pool', 'actor', 'action', 'target_type', 'target_id',
        'metadata', 'ip_address', 'user_agent', 'created_at',
    )


@admin.register(GamesAndScores)
class GamesAndScoresAdmin(admin.ModelAdmin):
    list_display = ('slug', 'competition', 'gameseason', 'gameWeek', 'gameyear', 'startTimestamp', 'statusTitle',
        'homeTeamName', 'homeTeamScore', 'awayTeamName', 'awayTeamScore', 'gameWinner', 'broadcast', 'gamecastUrl')
    list_filter = ('startTimestamp', 'gameseason', 'gameWeek', 'broadcast')
    search_fields = ('homeTeamName', 'awayTeamName', 'broadcast')
    date_hierarchy = 'startTimestamp'
    ordering = ('gameWeek', 'startTimestamp' )

@admin.register(GamePicks)
class GamesPicksAdmin(admin.ModelAdmin):
    list_display = ('pool', 'userEmail', 'uid', 'slug', 'competition', 'gameseason', 'gameWeek', 'gameyear', 
        'pick_game_id', 'pick', 'pick_correct', 'tieBreakerScore', 'tieBreakerYards', 'pickAdded', 'pickUpdated' )
    list_filter = ('pool', 'userEmail', 'gameseason', 'gameWeek', 'gameyear')
    search_fields = ('userEmail',)
    date_hierarchy = 'pickAdded'
    ordering = ('pickAdded',)

@admin.register(userSeasonPoints)
class UserSeasonPointsAdmin(admin.ModelAdmin):
    list_display = ('id', 'pool', 'userID', 'userEmail', 'gameseason', 'gameyear', 'week_1_points', 'week_1_bonus', 'week_1_winner', 'week_2_points', 'week_2_bonus', 'week_2_winner',
    'week_3_points', 'week_3_bonus', 'week_3_winner', 'week_4_points', 'week_4_bonus', 'week_4_winner', 'week_5_points', 'week_5_bonus', 'week_5_winner', 'week_6_points', 'week_6_bonus', 'week_6_winner',
    'week_7_points', 'week_7_bonus', 'week_7_winner', 'week_8_points', 'week_8_bonus', 'week_8_winner', 'week_9_points', 'week_9_bonus', 'week_9_winner', 'week_10_points', 'week_10_bonus', 'week_10_winner',
    'week_11_points', 'week_11_bonus', 'week_11_winner', 'week_12_points', 'week_12_bonus', 'week_12_winner', 'week_13_points', 'week_13_bonus', 'week_13_winner', 'week_14_points', 'week_14_bonus','week_14_winner',
    'week_15_points', 'week_15_bonus', 'week_15_winner', 'week_16_points', 'week_16_bonus', 'week_16_winner', 'week_17_points', 'week_17_bonus', 'week_17_winner', 'week_18_points', 'week_18_bonus', 'week_18_winner', 
    'total_points', 'year_winner')
    list_filter = ('pool', 'gameseason', 'userEmail')
    search_fields = ('userEmail', 'gameseason')
    date_hierarchy = 'playerUpdated'

@admin.register(userPoints)
class UserPointsAdmin(admin.ModelAdmin):
    list_display = ('id', 'pool', 'userID', 'userEmail', 'gameseason', 'gameyear', 'week_1_points', 'week_1_bonus', 'week_1_winner', 'week_2_points', 'week_2_bonus', 'week_2_winner',
    'week_3_points', 'week_3_bonus', 'week_3_winner', 'week_4_points', 'week_4_bonus', 'week_4_winner', 'week_5_points', 'week_5_bonus', 'week_5_winner', 'week_6_points', 'week_6_bonus', 'week_6_winner',
    'week_7_points', 'week_7_bonus', 'week_7_winner', 'week_8_points', 'week_8_bonus', 'week_8_winner', 'week_9_points', 'week_9_bonus', 'week_9_winner', 'week_10_points', 'week_10_bonus', 'week_10_winner',
    'week_11_points', 'week_11_bonus', 'week_11_winner', 'week_12_points', 'week_12_bonus', 'week_12_winner', 'week_13_points', 'week_13_bonus', 'week_13_winner', 'week_14_points', 'week_14_bonus','week_14_winner',
    'week_15_points', 'week_15_bonus', 'week_15_winner', 'week_16_points', 'week_16_bonus', 'week_16_winner', 'week_17_points', 'week_17_bonus', 'week_17_winner', 'week_18_points', 'week_18_bonus', 'week_18_winner', 
    'total_points', 'year_winner')
    list_filter = ('pool', 'gameseason', 'userEmail')
    search_fields = ('userEmail', 'gameseason')
    date_hierarchy = 'playerUpdated'

@admin.register(GameWeeks)
class GameWeekssAdmin(admin.ModelAdmin):
    list_display = ('weekNumber', 'competition', 'date', 'season')
    list_filter = ('weekNumber', 'date', 'season')
    ordering = ('competition', 'weekNumber', 'date')

@admin.register(Teams)
class TeamsAdmin(admin.ModelAdmin):
    list_display = (
        'teamNameSlug',
        'teamNameName',
        'gameseason',
        'teamWins',
        'teamLosses',
        'teamTies',
        'color',
        'alternateColor',
        'logo_contrast_preset',
    )
    list_filter = ('gameseason', 'logo_contrast_preset')
    search_fields = ('teamNameSlug', 'teamNameName', 'teamLogo')
    ordering = ('teamNameName',)
    fields = (
        'id',
        'gameseason',
        'teamNameSlug',
        'teamNameName',
        'teamLogo',
        'teamWins',
        'teamLosses',
        'teamTies',
        'color',
        'alternateColor',
        'logo_contrast_preset',
    )

@admin.register(userStats)
class userStatsAdmin(admin.ModelAdmin):
    list_display = ('id', 'pool', 'userEmail', 'userID', 'weeksWonSeason', 'weeksWonTotal', 'weeksWonSeason', 'weeksWonTotal', 'weeksWonSeason', 'pickPercentTotal', 'correctPickTotalSeason', 'correctPickTotalTotal', 'totalPicksSeason', 'mostPickedSeason', 'totalPicksTotal', 'mostPickedTotal', 'leastPickedSeason', 'leastPickedTotal', 'seasonsWon')
    list_filter = ('pool', 'userEmail', 'userID')
    search_fields = ('userEmail', 'userID')

@admin.register(currentSeason)
class currentSeasonAdmin(admin.ModelAdmin):
    list_display = ('season', 'display_name', 'get_display_season')
    list_filter = ('season',)
    search_fields = ('season', 'display_name')
    ordering = ('season',)
    fields = ('season', 'display_name')
    
    def get_display_season(self, obj):
        """Show the computed display season"""
        return obj.get_display_season()
    get_display_season.short_description = 'Computed Display Name'
