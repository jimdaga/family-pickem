from django import forms
from django.contrib.auth.models import User
from pickem_api.models import GamePicks, userSeasonPoints
from .models import MessageBoardPost, MessageBoardComment, SiteBanner


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
