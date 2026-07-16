from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class SuperAdminAuditLog(models.Model):
    """Global audit trail for the superadmin console.

    FamilyAuditLog.family is non-null, so it structurally cannot record a global
    action (blocking a user, editing team colors, rolling the season). This table
    can. Because `changes` stores before/after, it doubles as forensics for a bad
    edit — which matters, since some repair actions are not reversible.
    """

    class Action(models.TextChoices):
        USER_BLOCKED = 'user_blocked', 'User blocked'
        USER_UNBLOCKED = 'user_unblocked', 'User unblocked'
        USER_PROFILE_UPDATED = 'user_profile_updated', 'User profile updated'
        FAMILY_UPDATED = 'family_updated', 'Family updated'
        POOL_SETTINGS_UPDATED = 'pool_settings_updated', 'Pool settings updated'
        TEAM_UPDATED = 'team_updated', 'Team updated'
        SEASON_UPDATED = 'season_updated', 'Current season updated'
        BANNER_PUBLISHED = 'banner_published', 'Site banner published'
        JOB_QUEUED = 'job_queued', 'Pipeline job queued'
        DATA_REPAIR = 'data_repair', 'Data repair action'
        SCHEDULE_UPDATED = 'schedule_updated', 'Job schedule updated'

    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='superadmin_audit_logs',
        blank=True, null=True,
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Superadmin audit log'
        verbose_name_plural = 'Superadmin audit logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='sa_audit_created_idx'),
            models.Index(fields=['action'], name='sa_audit_action_idx'),
        ]

    def __str__(self):
        return f'{self.action} by {self.actor} at {self.created_at}'


class SuperAdminLogEntry(models.Model):
    """Application log records captured to the DB so the console can show them
    without shell/kubectl access. Written by pickem_superadmin.logging.DatabaseLogHandler,
    aged out by the prune_superadmin_logs command."""

    LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    level = models.CharField(max_length=10, choices=[(l, l) for l in LEVELS])
    level_no = models.PositiveSmallIntegerField(default=0)
    logger_name = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    traceback = models.TextField(blank=True, null=True)
    pathname = models.CharField(max_length=255, blank=True, null=True)
    lineno = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['level_no', '-timestamp'], name='sa_log_level_ts_idx'),
            models.Index(fields=['-timestamp'], name='sa_log_ts_idx'),
        ]

    def __str__(self):
        return f'[{self.level}] {self.logger_name}: {self.message[:60]}'
