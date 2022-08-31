from django import forms
from pickem_api.models import GamePicks

class GamePicksForm(forms.ModelForm):

    class Meta:
        model = GamePicks
        fields = (
            'id',
            'userEmail',
            'userID',
            'slug',
            'competition',
            'gameWeek',
            'gameyear',
            'pick_game_id',
            'pick',
            'pick_correct'
        )
