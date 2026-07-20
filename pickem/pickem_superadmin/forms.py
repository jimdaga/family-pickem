from django import forms

from pickem_api.models import Family, PoolSettings, ScheduledJobConfig, Teams
from pickem_superadmin.models import AIProviderSettings, EmailNotificationCampaign, EmailProviderSettings

CELL = 'sa-select w-full !py-1'
NUM_CELL = 'sa-input w-16 !px-2 !py-1 sa-num text-center'

# Not permission-gated — unimplemented. Playoff scoring needs schema work
# (userSeasonPoints only has week_1..18) and against-the-spread has no scoring
# logic. Flipping either would silently corrupt scoring rather than enable a
# feature, so they are locked here exactly as they are in FamilyAdminSettingsForm.
LOCKED_FIELDS = ('pick_type', 'include_playoffs')


class PoolSettingsRowForm(forms.ModelForm):
    """One row of the settings matrix. Prefixed by pool id so many bind at once."""

    class Meta:
        model = PoolSettings
        fields = (
            'win_points', 'tie_points', 'weekly_winner_points',
            'picks_lock_mode', 'allow_tiebreaker',
            'primary_tiebreaker', 'secondary_tiebreaker',
            'perfect_week_bonus_enabled', 'perfect_week_bonus_amount',
            'entry_fee_enabled', 'entry_fee_amount',
            'missed_pick_policy', 'late_join_policy', 'payout_structure',
            'pick_type', 'include_playoffs',
        )
        widgets = {
            'win_points': forms.NumberInput(attrs={'class': NUM_CELL}),
            'tie_points': forms.NumberInput(attrs={'class': NUM_CELL}),
            'weekly_winner_points': forms.NumberInput(attrs={'class': NUM_CELL}),
            'perfect_week_bonus_amount': forms.NumberInput(attrs={'class': NUM_CELL}),
            'entry_fee_amount': forms.NumberInput(attrs={'class': NUM_CELL}),
            'picks_lock_mode': forms.Select(attrs={'class': CELL}),
            'primary_tiebreaker': forms.Select(attrs={'class': CELL}),
            'secondary_tiebreaker': forms.Select(attrs={'class': CELL}),
            'missed_pick_policy': forms.Select(attrs={'class': CELL}),
            'late_join_policy': forms.Select(attrs={'class': CELL}),
            'payout_structure': forms.Select(attrs={'class': CELL}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django ignores submitted data for disabled fields and falls back to the
        # initial value, which defeats a hand-crafted POST. This is the server-side
        # rejection, not just a greyed-out widget.
        for name in LOCKED_FIELDS:
            self.fields[name].disabled = True
            self.fields[name].help_text = 'Not implemented yet.'


class FamilyRowForm(forms.ModelForm):
    """One row of the families matrix. Prefixed by family id so many bind at once."""

    class Meta:
        model = Family
        fields = ('name', 'slug', 'status')
        widgets = {
            'name': forms.TextInput(attrs={'class': CELL}),
            'slug': forms.TextInput(attrs={'class': CELL + ' font-mono'}),
            'status': forms.Select(attrs={'class': CELL}),
        }


class TeamRowForm(forms.ModelForm):
    """One row of the teams matrix. Prefixed by team id so many bind at once."""

    class Meta:
        model = Teams
        fields = ('color', 'alternateColor', 'logo_contrast_preset')
        widgets = {
            'color': forms.TextInput(attrs={'class': CELL + ' font-mono w-20'}),
            'alternateColor': forms.TextInput(attrs={'class': CELL + ' font-mono w-20'}),
            'logo_contrast_preset': forms.Select(attrs={'class': CELL}),
        }


class ScheduledJobConfigForm(forms.ModelForm):
    """One editable schedule row (interval minutes + enabled), prefixed by pk."""

    class Meta:
        model = ScheduledJobConfig
        fields = ('interval_minutes', 'enabled')
        widgets = {
            'interval_minutes': forms.NumberInput(attrs={'class': NUM_CELL, 'min': 1}),
        }


class EmailProviderSettingsForm(forms.ModelForm):
    api_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={'class': 'sa-input w-full', 'autocomplete': 'new-password'},
        ),
        help_text='Leave blank to keep the existing API key. Enter a new value to rotate it.',
    )

    class Meta:
        model = EmailProviderSettings
        fields = ('provider', 'invites_enabled', 'from_email', 'reply_to_email')
        widgets = {
            'provider': forms.Select(attrs={'class': 'sa-select w-full'}),
            'from_email': forms.TextInput(attrs={'class': 'sa-input w-full'}),
            'reply_to_email': forms.TextInput(attrs={'class': 'sa-input w-full'}),
        }

    def clean(self):
        cleaned = super().clean()
        invites_enabled = cleaned.get('invites_enabled')
        from_email = (cleaned.get('from_email') or '').strip()
        api_key = (self.cleaned_data.get('api_key') or '').strip()
        if invites_enabled and not from_email:
            self.add_error('from_email', 'From email is required when invites are enabled.')
        if invites_enabled and not (self.instance.has_api_key or api_key):
            self.add_error('api_key', 'API key is required when invites are enabled.')
        return cleaned


class AIProviderSettingsForm(forms.ModelForm):
    api_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={'class': 'sa-input w-full', 'autocomplete': 'new-password'},
        ),
        help_text='Write-only. Leave blank to keep the stored key; enter a new value to rotate it.',
    )

    class Meta:
        model = AIProviderSettings
        fields = ('provider', 'enabled', 'model', 'timeout_seconds', 'retries', 'max_runs_per_pool_week')
        widgets = {
            'provider': forms.Select(attrs={'class': 'sa-select w-full'}),
            'model': forms.TextInput(attrs={'class': 'sa-input w-full'}),
            'timeout_seconds': forms.NumberInput(attrs={'class': 'sa-input w-full', 'min': 1}),
            'retries': forms.NumberInput(attrs={'class': 'sa-input w-full', 'min': 0}),
            'max_runs_per_pool_week': forms.NumberInput(attrs={'class': 'sa-input w-full', 'min': 1}),
        }

    def clean(self):
        cleaned = super().clean()
        api_key = (self.cleaned_data.get('api_key') or '').strip()
        if cleaned.get('enabled') and not (self.instance.has_api_key or api_key):
            self.add_error('api_key', 'An API key is required when AI recaps are enabled.')
        return cleaned


class EmailTestSendForm(forms.Form):
    to_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'sa-input w-full'}),
        help_text='Sends a one-off verification email using the currently saved provider settings.',
    )


class EmailNotificationCampaignForm(forms.ModelForm):
    class Meta:
        model = EmailNotificationCampaign
        fields = (
            'enabled',
            'weekday',
            'hour',
            'minute',
            'timezone_name',
            'rollout_mode',
            'allowlist_emails',
            'family_link_strategy',
        )
        widgets = {
            'timezone_name': forms.TextInput(attrs={'class': 'sa-input w-full'}),
            'rollout_mode': forms.Select(attrs={'class': 'sa-select w-full'}),
            'family_link_strategy': forms.Select(attrs={'class': 'sa-select w-full'}),
            'allowlist_emails': forms.Textarea(attrs={'class': 'sa-textarea w-full', 'rows': 3}),
        }

    WEEKDAY_CHOICES = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )

    weekday = forms.TypedChoiceField(
        choices=WEEKDAY_CHOICES,
        coerce=int,
        widget=forms.Select(attrs={'class': 'sa-select w-full'}),
    )
    hour = forms.IntegerField(
        min_value=0,
        max_value=23,
        widget=forms.NumberInput(attrs={'class': 'sa-input w-full', 'min': 0, 'max': 23}),
        help_text='24-hour clock in the configured timezone.',
    )
    minute = forms.IntegerField(
        min_value=0,
        max_value=59,
        widget=forms.NumberInput(attrs={'class': 'sa-input w-full', 'min': 0, 'max': 59}),
    )

    def clean_allowlist_emails(self):
        cleaned = [
            email.strip().lower()
            for email in (self.cleaned_data.get('allowlist_emails') or '').replace('\n', ',').split(',')
            if email.strip()
        ]
        return ', '.join(cleaned)


class WeeklyPicksPreviewForm(forms.Form):
    to_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'sa-input w-full'}),
        help_text='Where to send the preview email.',
    )
    sample_user_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'sa-input w-full'}),
        help_text='Optional: render the email as this user. Defaults to the first eligible member.',
    )
