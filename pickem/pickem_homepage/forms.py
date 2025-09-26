from django import forms
from pickem_api.models import GamePicks
from .models import MessageBoardPost, MessageBoardComment


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
