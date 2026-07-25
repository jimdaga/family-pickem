from django.db import models, transaction
from django.db.models import F
from django.db.models.functions import Greatest
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
    family = models.ForeignKey(
        "pickem_api.Family",
        on_delete=models.SET_NULL,
        related_name='banners',
        blank=True,
        null=True,
        help_text="Optional family scope; blank keeps the banner site-wide",
    )
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
        indexes = [
            models.Index(fields=['family', 'is_active', 'created_at'], name='banner_family_active_idx'),
        ]
    
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


class FamilyPublication(models.Model):
    """A longer-form, auditable message shown on one pool's lobby.

    Publications deliberately keep source metadata separate from the actor.  A
    future generated weekly summary can therefore use the same review and
    publication path without acquiring commissioner privileges.
    """

    class Source(models.TextChoices):
        COMMISSIONER = 'commissioner', 'Commissioner'
        AI_WEEKLY_SUMMARY = 'ai_weekly_summary', 'Sideline'

    family = models.ForeignKey(
        'pickem_api.Family', on_delete=models.PROTECT, related_name='publications'
    )
    pool = models.ForeignKey(
        'pickem_api.Pool', on_delete=models.PROTECT, related_name='publications'
    )
    title = models.CharField(max_length=200)
    body = models.TextField(help_text='Markdown source. Raw HTML is never rendered.')
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='family_publications'
    )
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.COMMISSIONER)
    generation_reference = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['family', 'pool', 'is_published', 'published_at'], name='publication_lobby_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                # Meta cannot reference the enclosing Source class at model
                # construction time, so keep this DB-level mirror explicit.
                check=models.Q(source__in=['commissioner', 'ai_weekly_summary']),
                name='publication_source_valid',
            ),
            # Each pool has two intentional, separately managed slots: one
            # commissioner announcement and one AI recap.  A source may be a
            # draft or published, but never a growing stream of replacements.
            models.UniqueConstraint(
                fields=['pool', 'source'], name='one_publication_per_pool_source',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.pool_id and self.family_id and self.pool.family_id != self.family_id:
            raise ValidationError({'pool': 'The pool must belong to this family.'})

    def __str__(self):
        return f'{self.family.name} / {self.pool.name}: {self.title}'


class AIWeeklySummaryRun(models.Model):
    """Cost-safe operational record for one tenant-scoped recap attempt.

    Prompts and provider responses are intentionally not stored.  The reviewed
    publication is the only persisted generated content.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        DISABLED = 'disabled', 'Disabled'
        SUCCESS = 'success', 'Success'
        ERROR = 'error', 'Error'
        SKIPPED = 'skipped', 'Skipped'

    family = models.ForeignKey('pickem_api.Family', on_delete=models.PROTECT)
    pool = models.ForeignKey('pickem_api.Pool', on_delete=models.PROTECT)
    season = models.IntegerField()
    week = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    model = models.CharField(max_length=100, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    publication = models.ForeignKey(
        FamilyPublication, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ai_summary_runs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pool', 'season', 'week', 'created_at'], name='ai_summary_pool_week_idx'),
        ]

    def __str__(self):
        return f'{self.pool} week {self.week}: {self.status}'


class MessageBoardPost(models.Model):
    """Model for main message board posts"""
    
    family = models.ForeignKey(
        "pickem_api.Family",
        on_delete=models.SET_NULL,
        related_name='message_board_posts',
        blank=True,
        null=True,
    )
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
        indexes = [
            models.Index(fields=['family', 'is_active', 'created_at'], name='post_family_active_idx'),
        ]
    
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
    
    family = models.ForeignKey(
        "pickem_api.Family",
        on_delete=models.SET_NULL,
        related_name='message_board_comments',
        blank=True,
        null=True,
    )
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
        indexes = [
            models.Index(fields=['family', 'created_at'], name='comment_family_created_idx'),
        ]
    
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
    
    family = models.ForeignKey(
        "pickem_api.Family",
        on_delete=models.SET_NULL,
        related_name='message_board_votes',
        blank=True,
        null=True,
    )
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
        indexes = [
            models.Index(fields=['family', 'created_at'], name='vote_family_created_idx'),
        ]
    
    def __str__(self):
        target = self.post.title if self.post else f"comment on {self.comment.post.title}"
        vote_str = "upvote" if self.vote_type == 1 else "downvote"
        return f"{self.user.username} {vote_str} on {target}"
    
    def save(self, *args, **kwargs):
        """Update vote counts when saving"""
        is_new = self.pk is None

        if is_new:
            super().save(*args, **kwargs)
            if self.post:
                self._update_post_votes(None)
            elif self.comment:
                self._update_comment_votes(None)
            return

        # An update (vote_type flip): lock the existing row for the whole
        # read-old-value + write-new-value + adjust-counters sequence, so
        # two concurrent saves of the SAME vote (e.g. a rapid double
        # submit) can't both read the same pre-change vote_type and each
        # apply their own delta — that would double-apply one transition
        # (e.g. two decrements of upvotes for a single upvote->downvote).
        with transaction.atomic():
            old_vote = MessageBoardVote.objects.select_for_update().get(pk=self.pk)
            super().save(*args, **kwargs)
            if self.post:
                self._update_post_votes(old_vote)
            elif self.comment:
                self._update_comment_votes(old_vote)

    @staticmethod
    def _clamped_decrement(field):
        """A -1 update expression for `field` that floors at 0."""
        return Greatest(F(field) - 1, 0)

    def delete(self, *args, **kwargs):
        """Update vote counts when deleting"""
        # Lock the row for the same reason as save(): two concurrent
        # deletes of the same vote must not both decrement the aggregate.
        # select_for_update().first() (not .get()) so a vote already
        # deleted by a concurrent request resolves to None here instead of
        # raising DoesNotExist — in that case there's nothing left to
        # decrement, so skip it rather than double-counting.
        with transaction.atomic():
            locked = MessageBoardVote.objects.select_for_update().filter(pk=self.pk).first()
            if locked is None:
                return

            target_post = locked.post
            target_comment = locked.comment
            vote_type = locked.vote_type

            super().delete(*args, **kwargs)

            field = 'upvotes' if vote_type == 1 else 'downvotes'
            if target_post:
                MessageBoardPost.objects.filter(pk=target_post.pk).update(
                    **{field: self._clamped_decrement(field)}
                )
            elif target_comment:
                MessageBoardComment.objects.filter(pk=target_comment.pk).update(
                    **{field: self._clamped_decrement(field)}
                )

    def _vote_count_updates(self, old_vote):
        """Build the {field: expression} update kwargs for a vote save.

        Uses F()/Greatest() so the counter change is a single atomic UPDATE
        instead of a Python read-modify-write, which two concurrent votes
        could otherwise race (one increment silently lost).
        """
        updates = {}
        if old_vote and old_vote.vote_type != self.vote_type:
            dec_field = 'upvotes' if old_vote.vote_type == 1 else 'downvotes'
            updates[dec_field] = self._clamped_decrement(dec_field)

        if not old_vote or old_vote.vote_type != self.vote_type:
            inc_field = 'upvotes' if self.vote_type == 1 else 'downvotes'
            updates[inc_field] = F(inc_field) + 1

        return updates

    def _update_post_votes(self, old_vote):
        """Update vote counts for posts"""
        updates = self._vote_count_updates(old_vote)
        if updates:
            MessageBoardPost.objects.filter(pk=self.post.pk).update(**updates)

    def _update_comment_votes(self, old_vote):
        """Update vote counts for comments"""
        updates = self._vote_count_updates(old_vote)
        if updates:
            MessageBoardComment.objects.filter(pk=self.comment.pk).update(**updates)
