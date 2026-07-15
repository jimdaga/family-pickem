from django import forms

from pickem_api.models import Family, PoolSettings, Teams

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
            'picks_lock_at_kickoff', 'allow_tiebreaker',
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
        fields = ('name', 'slug', 'logo_url', 'status')
        widgets = {
            'name': forms.TextInput(attrs={'class': CELL}),
            'slug': forms.TextInput(attrs={'class': CELL + ' font-mono'}),
            'logo_url': forms.TextInput(attrs={'class': CELL}),
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
