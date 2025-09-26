from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class SiteBanner(models.Model):
    """Model for site-wide banners that can be displayed across the application"""
    
    BANNER_TYPES = [
        ('success', 'Success (Green)'),
        ('info', 'Info (Blue)'),
        ('warning', 'Warning (Yellow)'),
        ('danger', 'Danger (Red)'),
    ]
    
    title = models.CharField(max_length=200, help_text="Banner title/message")
    description = models.TextField(blank=True, help_text="Optional additional description")
    banner_type = models.CharField(
        max_length=20, 
        choices=BANNER_TYPES, 
        default='success',
        help_text="Visual style of the banner"
    )
    icon = models.CharField(
        max_length=50, 
        default='fas fa-trophy',
        help_text="Font Awesome icon class (e.g., 'fas fa-trophy', 'fas fa-info-circle')"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this banner should be displayed")
    start_date = models.DateTimeField(
        default=timezone.now,
        help_text="When this banner should start being displayed"
    )
    end_date = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When this banner should stop being displayed (leave blank for indefinite)"
    )
    show_close_button = models.BooleanField(
        default=True,
        help_text="Whether users can dismiss this banner"
    )
    priority = models.IntegerField(
        default=1,
        help_text="Banner priority (higher numbers shown first if multiple active)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = "Site Banner"
        verbose_name_plural = "Site Banners"
    
    def __str__(self):
        status = "Active" if self.is_currently_active() else "Inactive"
        return f"{self.title} ({status})"
    
    def is_currently_active(self):
        """Check if banner should be displayed right now"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        
        # Check if we're past the start date
        if now < self.start_date:
            return False
        
        # Check if we're past the end date (if set)
        if self.end_date and now > self.end_date:
            return False
        
        return True
    
    @classmethod
    def get_active_banner(cls):
        """Get the highest priority active banner"""
        return cls.objects.filter(
            is_active=True,
            start_date__lte=timezone.now()
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gt=timezone.now())
        ).first()


class MessageBoardPost(models.Model):
    """Model for main message board posts"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200, help_text="Post title")
    content = models.TextField(help_text="Post content")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False, help_text="Pin this post to the top")
    is_active = models.BooleanField(default=True, help_text="Hide/show this post")
    
    # Voting system
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "Message Board Post"
        verbose_name_plural = "Message Board Posts"
    
    def __str__(self):
        return f"{self.title} by {self.user.username}"
    
    @property
    def score(self):
        """Calculate Reddit-style score"""
        return self.upvotes - self.downvotes
    
    @property
    def comment_count(self):
        """Get total number of comments (including nested)"""
        return self.comments.filter(is_active=True).count()
    
    def get_top_level_comments(self):
        """Get only top-level comments (no parent)"""
        return self.comments.filter(parent=None, is_active=True).order_by('-created_at')


class MessageBoardComment(models.Model):
    """Model for nested comments on message board posts"""
    
    post = models.ForeignKey(MessageBoardPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField(help_text="Comment content")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Hide/show this comment")
    
    # Voting system
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Message Board Comment"
        verbose_name_plural = "Message Board Comments"
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title}"
    
    @property
    def score(self):
        """Calculate Reddit-style score"""
        return self.upvotes - self.downvotes
    
    @property
    def depth(self):
        """Calculate nesting depth"""
        if self.parent is None:
            return 0
        return self.parent.depth + 1
    
    def get_nested_replies(self):
        """Get all nested replies in chronological order"""
        return self.replies.filter(is_active=True).order_by('created_at')


class MessageBoardVote(models.Model):
    """Model to track user votes on posts and comments"""
    
    VOTE_CHOICES = [
        (1, 'Upvote'),
        (-1, 'Downvote'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(MessageBoardPost, on_delete=models.CASCADE, null=True, blank=True, related_name='votes')
    comment = models.ForeignKey(MessageBoardComment, on_delete=models.CASCADE, null=True, blank=True, related_name='votes')
    vote_type = models.IntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Ensure a user can only vote once per post/comment
        unique_together = [
            ['user', 'post'],
            ['user', 'comment'],
        ]
        verbose_name = "Message Board Vote"
        verbose_name_plural = "Message Board Votes"
    
    def __str__(self):
        target = self.post.title if self.post else f"comment on {self.comment.post.title}"
        vote_str = "upvote" if self.vote_type == 1 else "downvote"
        return f"{self.user.username} {vote_str} on {target}"
    
    def save(self, *args, **kwargs):
        """Update vote counts when saving"""
        # Check if this is an update to existing vote
        is_new = self.pk is None
        old_vote = None
        
        if not is_new:
            old_vote = MessageBoardVote.objects.get(pk=self.pk)
        
        super().save(*args, **kwargs)
        
        # Update vote counts on the target object
        if self.post:
            self._update_post_votes(old_vote)
        elif self.comment:
            self._update_comment_votes(old_vote)
    
    def delete(self, *args, **kwargs):
        """Update vote counts when deleting"""
        # Store reference before deletion
        target_post = self.post
        target_comment = self.comment
        vote_type = self.vote_type
        
        super().delete(*args, **kwargs)
        
        # Update vote counts
        if target_post:
            if vote_type == 1:
                target_post.upvotes = max(0, target_post.upvotes - 1)
            else:
                target_post.downvotes = max(0, target_post.downvotes - 1)
            target_post.save()
        elif target_comment:
            if vote_type == 1:
                target_comment.upvotes = max(0, target_comment.upvotes - 1)
            else:
                target_comment.downvotes = max(0, target_comment.downvotes - 1)
            target_comment.save()
    
    def _update_post_votes(self, old_vote):
        """Update vote counts for posts"""
        if old_vote and old_vote.vote_type != self.vote_type:
            # Vote changed, adjust both counters
            if old_vote.vote_type == 1:
                self.post.upvotes = max(0, self.post.upvotes - 1)
            else:
                self.post.downvotes = max(0, self.post.downvotes - 1)
        
        if not old_vote or old_vote.vote_type != self.vote_type:
            # New vote or changed vote
            if self.vote_type == 1:
                self.post.upvotes += 1
            else:
                self.post.downvotes += 1
        
        self.post.save()
    
    def _update_comment_votes(self, old_vote):
        """Update vote counts for comments"""
        if old_vote and old_vote.vote_type != self.vote_type:
            # Vote changed, adjust both counters
            if old_vote.vote_type == 1:
                self.comment.upvotes = max(0, self.comment.upvotes - 1)
            else:
                self.comment.downvotes = max(0, self.comment.downvotes - 1)
        
        if not old_vote or old_vote.vote_type != self.vote_type:
            # New vote or changed vote
            if self.vote_type == 1:
                self.comment.upvotes += 1
            else:
                self.comment.downvotes += 1
        
        self.comment.save()
