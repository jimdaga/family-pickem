from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
import base64
import hashlib
import logging

from cryptography.fernet import Fernet
from django.conf import settings


logger = logging.getLogger(__name__)


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
        EMAIL_SETTINGS_UPDATED = 'email_settings_updated', 'Email settings updated'
        EMAIL_TEST_SENT = 'email_test_sent', 'Email test sent'
        EMAIL_CAMPAIGN_UPDATED = 'email_campaign_updated', 'Email campaign updated'
        EMAIL_CAMPAIGN_SENT = 'email_campaign_sent', 'Email campaign sent'
        EMAIL_PREVIEW_SENT = 'email_preview_sent', 'Email preview sent'

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


def _superadmin_secret_fernet():
    secret = settings.SECRET_KEY.encode('utf-8')
    digest = hashlib.sha256(b'pickem-superadmin-secrets:' + secret).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class EmailProviderSettings(models.Model):
    class Provider(models.TextChoices):
        RESEND = 'resend', 'Resend'

    singleton = models.CharField(max_length=20, unique=True, default='default')
    provider = models.CharField(
        max_length=30,
        choices=Provider.choices,
        default=Provider.RESEND,
    )
    invites_enabled = models.BooleanField(default=False)
    from_email = models.CharField(max_length=255, blank=True, default='')
    reply_to_email = models.CharField(max_length=255, blank=True, default='')
    api_key_ciphertext = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Email provider settings'
        verbose_name_plural = 'Email provider settings'

    def __str__(self):
        return f'{self.get_provider_display()} email settings'

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(singleton='default')
        return obj

    @classmethod
    def current(cls):
        return cls.objects.filter(singleton='default').first()

    def set_api_key(self, raw_api_key):
        raw_api_key = (raw_api_key or '').strip()
        if not raw_api_key:
            self.api_key_ciphertext = ''
            return
        self.api_key_ciphertext = _superadmin_secret_fernet().encrypt(
            raw_api_key.encode('utf-8')
        ).decode('utf-8')

    def get_api_key(self):
        if not self.api_key_ciphertext:
            return ''
        try:
            return _superadmin_secret_fernet().decrypt(
                self.api_key_ciphertext.encode('utf-8')
            ).decode('utf-8')
        except Exception:
            logger.warning('Failed to decrypt stored email provider API key.')
            return ''

    @property
    def has_api_key(self):
        return bool(self.get_api_key())

    @property
    def masked_api_key(self):
        if not self.has_api_key:
            return ''
        raw = self.get_api_key()
        if len(raw) <= 8:
            return '•' * len(raw)
        return f"{raw[:4]}{'•' * max(len(raw) - 8, 4)}{raw[-4:]}"


class EmailNotificationCampaign(models.Model):
    WEEKDAY_LABELS = {
        0: 'Monday',
        1: 'Tuesday',
        2: 'Wednesday',
        3: 'Thursday',
        4: 'Friday',
        5: 'Saturday',
        6: 'Sunday',
    }
    class CampaignKey(models.TextChoices):
        WEEKLY_PICKS_AVAILABLE = 'weekly_picks_available', 'Weekly picks available'

    class RolloutMode(models.TextChoices):
        ALLOWLIST = 'allowlist', 'Allowlist only'
        ALL_ENABLED_USERS = 'all_enabled_users', 'All eligible users'

    class FamilyLinkStrategy(models.TextChoices):
        EARLIEST_MEMBERSHIP = 'earliest_membership', 'Earliest joined family'

    campaign_key = models.CharField(
        max_length=50,
        unique=True,
        choices=CampaignKey.choices,
    )
    enabled = models.BooleanField(default=False)
    weekday = models.PositiveSmallIntegerField(default=2)
    hour = models.PositiveSmallIntegerField(default=9)
    minute = models.PositiveSmallIntegerField(default=0)
    timezone_name = models.CharField(max_length=64, default='America/New_York')
    rollout_mode = models.CharField(
        max_length=50,
        choices=RolloutMode.choices,
        default=RolloutMode.ALLOWLIST,
    )
    allowlist_emails = models.TextField(
        blank=True,
        default='jdagostino2@gmail.com',
        help_text='Comma-separated email allowlist for safe rollout and testing.',
    )
    family_link_strategy = models.CharField(
        max_length=50,
        choices=FamilyLinkStrategy.choices,
        default=FamilyLinkStrategy.EARLIEST_MEMBERSHIP,
    )
    last_sent_season = models.IntegerField(blank=True, null=True)
    last_sent_week = models.PositiveSmallIntegerField(blank=True, null=True)
    last_sent_at = models.DateTimeField(blank=True, null=True)
    last_sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['campaign_key']
        verbose_name = 'Email notification campaign'
        verbose_name_plural = 'Email notification campaigns'

    def __str__(self):
        return self.get_campaign_key_display()

    @classmethod
    def load_weekly_picks(cls):
        obj, _created = cls.objects.get_or_create(
            campaign_key=cls.CampaignKey.WEEKLY_PICKS_AVAILABLE,
        )
        return obj

    @property
    def allowlist(self):
        return [
            email.strip().lower()
            for email in (self.allowlist_emails or '').split(',')
            if email.strip()
        ]

    @property
    def weekday_label(self):
        return self.WEEKDAY_LABELS.get(self.weekday, str(self.weekday))
