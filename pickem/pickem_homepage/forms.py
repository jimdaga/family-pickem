from django import forms
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from pickem_api.models import FamilyMembership, GamePicks, PoolSettings, userSeasonPoints
from .models import MessageBoardPost, MessageBoardComment, SiteBanner


class CreateFamilyForm(forms.Form):
    name = forms.CharField(
        label="Family name",
        max_length=200,
        min_length=2,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-lg border border-border-light dark:border-border-subtle bg-white dark:bg-surface px-4 py-3 text-slate-900 dark:text-text-primary placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20',
            'placeholder': 'Smith Family',
            'autocomplete': 'organization',
        }),
    )

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Family name is required.")
        return " ".join(name.split())


class JoinFamilyForm(forms.Form):
    code = forms.CharField(
        label="Invite code",
        max_length=200,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-lg border border-border-light dark:border-border-subtle bg-white dark:bg-surface px-4 py-3 text-slate-900 dark:text-text-primary placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20',
            'placeholder': 'Invite code',
            'autocomplete': 'off',
        }),
    )

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if not code:
            raise forms.ValidationError("Invite code is required.")
        return code


class GamePicksForm(forms.ModelForm):

    class Meta:
        model = GamePicks
        fields = (
            'id',
            'userEmail',
            'userID',
            'uid',
            'slug',
            'competition',
            'gameseason',
            'gameWeek',
            'gameyear',
            'pick_game_id',
            'pick',
            'pick_correct',
            'tieBreakerScore',
            'tieBreakerYards'
        )


class PickSubmissionForm(forms.Form):
    game_id = forms.IntegerField(required=True)
    pick = forms.CharField(max_length=250, required=True, strip=True)
    tieBreakerScore = forms.IntegerField(required=False, min_value=0, max_value=200)
    tieBreakerYards = forms.IntegerField(required=False, min_value=0, max_value=2000)


ADMIN_TEXT_INPUT_CLASSES = (
    'w-full rounded-lg border border-border-light dark:border-border-subtle '
    'bg-white dark:bg-surface px-4 py-3 text-slate-900 dark:text-text-primary '
    'placeholder-slate-500 focus:border-primary focus:outline-none '
    'focus:ring-2 focus:ring-primary/20'
)


class DisabledOptionSelect(forms.Select):
    """Select widget that renders specific option values as disabled
    (greyed out and unselectable) — used for "coming soon" choices."""

    def __init__(self, *args, disabled_choices=(), **kwargs):
        self.disabled_choices = set(disabled_choices)
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, *args, **kwargs):
        option = super().create_option(name, value, *args, **kwargs)
        if value in self.disabled_choices:
            option['attrs']['disabled'] = True
        return option


class FamilyAdminSettingsForm(forms.Form):
    family_name = forms.CharField(
        label="Family display name",
        max_length=200,
        min_length=2,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': ADMIN_TEXT_INPUT_CLASSES,
            'autocomplete': 'organization',
        }),
    )
    pool_name = forms.CharField(
        label="Pool display name",
        max_length=200,
        min_length=2,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': ADMIN_TEXT_INPUT_CLASSES,
            'autocomplete': 'off',
        }),
    )
    logo_url = forms.CharField(
        label="Family logo URL",
        max_length=500,
        required=False,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': ADMIN_TEXT_INPUT_CLASSES,
            'placeholder': 'https://example.com/logo.png or /static/images/logo.png',
            'autocomplete': 'off',
        }),
        help_text="Shown at the top of your family's lobby. Leave blank to use the default Pick'em logo.",
    )

    def clean_logo_url(self):
        value = (self.cleaned_data.get('logo_url') or '').strip()
        if not value:
            return value
        # Site-relative paths are fine, but '//' is protocol-relative (an
        # arbitrary external host) and browsers normalize '\' to '/', so
        # '/\evil.com/...' would resolve protocol-relative too — both must go
        # through the URL validator instead of the fast path.
        if (
            value.startswith('/')
            and not value.startswith('//')
            and '\\' not in value
        ):
            return value
        try:
            URLValidator(schemes=['http', 'https'])(value)
        except forms.ValidationError:
            raise forms.ValidationError(
                "Enter a full URL (https://...) or a site-relative path starting with /."
            )
        return value

    picks_lock_at_kickoff = forms.BooleanField(
        label="Pick Locking",
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-5 w-5 rounded border-border-light text-primary focus:ring-primary/20',
        }),
    )
    allow_tiebreaker = forms.BooleanField(
        label="Tiebreakers",
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-5 w-5 rounded border-border-light text-primary focus:ring-primary/20',
        }),
    )

    # Scoring rules
    win_points = forms.IntegerField(
        label="Points per win",
        min_value=0,
        max_value=99,
        widget=forms.NumberInput(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    tie_points = forms.IntegerField(
        label="Points per tie",
        min_value=0,
        max_value=99,
        widget=forms.NumberInput(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    weekly_winner_points = forms.IntegerField(
        label="Weekly winner bonus",
        min_value=0,
        max_value=99,
        widget=forms.NumberInput(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    primary_tiebreaker = forms.ChoiceField(
        label="Primary tiebreaker",
        choices=PoolSettings.PrimaryTiebreaker.choices,
        widget=forms.Select(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    secondary_tiebreaker = forms.ChoiceField(
        label="Secondary tiebreaker",
        choices=PoolSettings.SecondaryTiebreaker.choices,
        widget=forms.Select(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    perfect_week_bonus_enabled = forms.BooleanField(
        label="Perfect week bonus",
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-5 w-5 rounded border-border-light text-primary focus:ring-primary/20',
        }),
    )
    perfect_week_bonus_amount = forms.IntegerField(
        label="Perfect week bonus ($)",
        min_value=0,
        max_value=100000,
        widget=forms.NumberInput(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    entry_fee_enabled = forms.BooleanField(
        label="Entry fee",
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-5 w-5 rounded border-border-light text-primary focus:ring-primary/20',
        }),
    )
    entry_fee_amount = forms.IntegerField(
        label="Entry fee (whole dollars)",
        min_value=0,
        max_value=100000,
        widget=forms.NumberInput(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    pick_type = forms.ChoiceField(
        label="Pick type",
        choices=PoolSettings.PickType.choices,
        widget=DisabledOptionSelect(
            disabled_choices={PoolSettings.PickType.AGAINST_SPREAD},
            attrs={'class': ADMIN_TEXT_INPUT_CLASSES},
        ),
    )
    missed_pick_policy = forms.ChoiceField(
        label="Missed pick policy",
        choices=PoolSettings.MissedPickPolicy.choices,
        widget=forms.Select(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    include_playoffs = forms.BooleanField(
        label="Include playoffs",
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-5 w-5 rounded border-border-light text-primary focus:ring-primary/20',
        }),
    )
    late_join_policy = forms.ChoiceField(
        label="Late join policy",
        choices=PoolSettings.LateJoinPolicy.choices,
        widget=forms.Select(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
    payout_structure = forms.ChoiceField(
        label="Payout structure",
        choices=PoolSettings.PayoutStructure.choices,
        widget=forms.Select(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )

    def clean_pick_type(self):
        pick_type = self.cleaned_data['pick_type']
        if pick_type == PoolSettings.PickType.AGAINST_SPREAD:
            raise forms.ValidationError(
                "Against-the-spread pools are coming soon and can't be selected yet."
            )
        return pick_type

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('perfect_week_bonus_enabled') and not cleaned.get('perfect_week_bonus_amount'):
            self.add_error(
                'perfect_week_bonus_amount',
                "Set a bonus value (at least $1) when the perfect week bonus is enabled.",
            )
        if cleaned.get('entry_fee_enabled') and not cleaned.get('entry_fee_amount'):
            self.add_error(
                'entry_fee_amount',
                "Set an entry fee amount (at least $1) when the entry fee is enabled.",
            )
        return cleaned

    def clean_family_name(self):
        name = self.cleaned_data.get('family_name', '').strip()
        if not name:
            raise forms.ValidationError("Family display name is required.")
        return " ".join(name.split())

    def clean_pool_name(self):
        name = self.cleaned_data.get('pool_name', '').strip()
        if not name:
            raise forms.ValidationError("Pool display name is required.")
        return " ".join(name.split())


class FamilyMembershipUpdateForm(forms.Form):
    membership_id = forms.IntegerField(required=True, min_value=1)
    role = forms.ChoiceField(
        choices=FamilyMembership.Role.choices,
        required=True,
    )
    status = forms.ChoiceField(
        choices=FamilyMembership.Status.choices,
        required=True,
    )


class FamilyManualPickForm(forms.Form):
    target_user_id = forms.IntegerField(required=True, min_value=1)
    week = forms.IntegerField(required=True, min_value=1, max_value=18)
    game_id = forms.IntegerField(required=True, min_value=1)
    pick = forms.CharField(max_length=250, required=True, strip=True)
    tieBreakerScore = forms.IntegerField(required=False, min_value=0, max_value=200)
    tieBreakerYards = forms.IntegerField(required=False, min_value=0, max_value=2000)


class FamilyWeekWinnerForm(forms.Form):
    week_number = forms.IntegerField(required=True, min_value=1, max_value=18)
    winner_uid = forms.IntegerField(required=True, min_value=1)


class FamilyInviteCreateForm(forms.Form):
    role = forms.ChoiceField(required=True)
    expires_in_days = forms.IntegerField(
        label="Expires after",
        min_value=1,
        max_value=365,
        initial=14,
        widget=forms.NumberInput(attrs={
            'class': ADMIN_TEXT_INPUT_CLASSES,
        }),
    )
    max_uses = forms.IntegerField(
        label="Max uses",
        min_value=1,
        max_value=1000,
        initial=20,
        widget=forms.NumberInput(attrs={
            'class': ADMIN_TEXT_INPUT_CLASSES,
        }),
    )

    def __init__(self, *args, allowed_roles=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_roles = allowed_roles or [FamilyMembership.Role.MEMBER]
        role_labels = dict(FamilyMembership.Role.choices)
        self.fields['role'].choices = [
            (role, role_labels[role])
            for role in allowed_roles
            if role in role_labels
        ]
        self.fields['role'].widget.attrs.update({
            'class': (
                'w-full rounded-lg border border-border-light dark:border-border-subtle '
                'bg-white dark:bg-surface px-4 py-3 text-slate-900 dark:text-text-primary '
                'focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20'
            ),
        })


class MessageBoardPostForm(forms.ModelForm):
    """Form for creating and editing message board posts"""
    
    class Meta:
        model = MessageBoardPost
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter post title...',
                'maxlength': 200
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What\'s on your mind?',
                'rows': 4,
                'style': 'resize: vertical;'
            })
        }
        labels = {
            'title': 'Title',
            'content': 'Content'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes and attributes
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': f"{field.widget.attrs.get('class', '')} form-control".strip()
            })


class MessageBoardCommentForm(forms.ModelForm):
    """Form for creating and editing comments"""
    
    class Meta:
        model = MessageBoardComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control comment-textarea',
                'placeholder': 'Write a comment...',
                'rows': 3,
                'style': 'resize: vertical; min-height: 80px;'
            })
        }
        labels = {
            'content': ''  # No label for comments
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        self.fields['content'].widget.attrs.update({
            'class': 'form-control comment-textarea'
        })


class QuickCommentForm(forms.Form):
    """Simplified form for quick comment posting via AJAX"""
    
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control quick-comment-textarea',
            'placeholder': 'Write a comment...',
            'rows': 2,
            'style': 'resize: vertical; min-height: 60px;'
        }),
        max_length=2000,
        required=True,
        strip=True
    )
    post_id = forms.IntegerField(widget=forms.HiddenInput())
    parent_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    
    def clean_content(self):
        """Validate comment content"""
        content = self.cleaned_data.get('content')
        if not content or not content.strip():
            raise forms.ValidationError("Comment cannot be empty.")
        
        # Basic content filtering
        if len(content.strip()) < 2:
            raise forms.ValidationError("Comment must be at least 2 characters long.")
        
        return content.strip()


class WeekWinnerForm(forms.Form):
    """Form for selecting week winners"""
    
    def __init__(self, week_candidates, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Create choices from week candidates with tiebreaker info
        choices = [(None, "-- Select Week Winner --")]
        for candidate in week_candidates:
            user = User.objects.get(id=candidate['uid'])
            display_name = f"{user.username} ({candidate['wins']} correct picks"
            if candidate.get('tiebreaker_score') is not None:
                display_name += f", Tiebreaker: {candidate['tiebreaker_score']}"
            display_name += ")"
            choices.append((candidate['uid'], display_name))
        
        self.fields['winner'] = forms.ChoiceField(
            choices=choices,
            required=True,
            widget=forms.Select(attrs={
                'class': 'form-select',
                'id': 'week-winner-select'
            }),
            label="Select Week Winner"
        )
        
        self.fields['week_number'] = forms.CharField(
            widget=forms.HiddenInput()
        )
        
        self.fields['gameseason'] = forms.CharField(
            widget=forms.HiddenInput()
        )


class SiteBannerForm(forms.ModelForm):
    """Form for managing site banners"""
    
    class Meta:
        model = SiteBanner
        fields = [
            'title', 'description', 'banner_type', 'icon', 
            'start_date', 'end_date', 'show_close_button', 'priority'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter banner title...',
                'maxlength': 200
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Optional additional description...',
                'rows': 3,
                'style': 'resize: vertical;'
            }),
            'banner_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., fas fa-trophy, fas fa-info-circle'
            }),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'show_close_button': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 100
            })
        }
        labels = {
            'title': 'Banner Title',
            'description': 'Description (Optional)',
            'banner_type': 'Banner Style',
            'icon': 'Font Awesome Icon Class',
            'start_date': 'Start Date & Time',
            'end_date': 'End Date & Time (Optional)',
            'show_close_button': 'Allow Users to Dismiss',
            'priority': 'Priority (Higher = Shown First)'
        }
        help_texts = {
            'title': 'Main banner message that will be displayed to users',
            'description': 'Additional details (leave blank if not needed)',
            'banner_type': 'Visual style and color of the banner',
            'icon': 'Font Awesome icon class (e.g., "fas fa-trophy" for a trophy icon)',
            'start_date': 'When should this banner start being displayed?',
            'end_date': 'When should this banner stop being displayed? (leave blank for indefinite)',
            'show_close_button': 'Allow users to close/dismiss this banner',
            'priority': 'If multiple banners are active, higher priority banners are shown first'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default values for new banners
        if not self.instance.pk:
            self.fields['priority'].initial = 1
            self.fields['show_close_button'].initial = True


class FamilyBannerForm(forms.ModelForm):
    """Lightweight form for family admins to publish a pool banner."""

    class Meta:
        model = SiteBanner
        fields = ['title', 'description', 'banner_type', 'icon', 'show_close_button']
        labels = {
            'title': 'Message',
            'description': 'Details (optional)',
            'banner_type': 'Style',
            'icon': 'Icon',
            'show_close_button': 'Let members dismiss it',
        }
        help_texts = {
            'title': 'The headline members will see across the site.',
            'description': 'Optional supporting text shown beneath the message.',
            'icon': 'Font Awesome class, e.g. fas fa-bullhorn.',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'class': ADMIN_TEXT_INPUT_CLASSES,
                'placeholder': 'e.g. Picks lock Sunday at 1pm!',
            }),
            'description': forms.Textarea(attrs={
                'class': ADMIN_TEXT_INPUT_CLASSES,
                'rows': 2,
                'placeholder': 'Optional details…',
            }),
            'banner_type': forms.Select(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
            'icon': forms.TextInput(attrs={
                'class': ADMIN_TEXT_INPUT_CLASSES,
                'placeholder': 'fas fa-bullhorn',
            }),
            'show_close_button': forms.CheckboxInput(attrs={
                'class': 'h-5 w-5 rounded border-border-light text-primary focus:ring-primary/20',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        self.fields['description'].required = False
        if not self.instance.pk:
            self.fields['icon'].initial = 'fas fa-bullhorn'
            self.fields['show_close_button'].initial = True
