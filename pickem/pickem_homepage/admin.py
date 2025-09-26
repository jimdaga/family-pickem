from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import SiteBanner, MessageBoardPost, MessageBoardComment, MessageBoardVote

@admin.register(SiteBanner)
class SiteBannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'banner_type', 'status_display', 'priority', 'start_date', 'end_date', 'created_at']
    list_filter = ['banner_type', 'is_active', 'start_date', 'end_date']
    search_fields = ['title', 'description']
    ordering = ['-priority', '-created_at']
    
    fields = [
        'title', 
        'description', 
        'banner_type', 
        'icon', 
        'is_active', 
        'priority',
        'start_date', 
        'end_date', 
        'show_close_button'
    ]
    
    def status_display(self, obj):
        """Display current status with color coding"""
        if obj.is_currently_active():
            return format_html(
                '<span style="color: green; font-weight: bold;">● Active</span>'
            )
        elif not obj.is_active:
            return format_html(
                '<span style="color: red;">● Disabled</span>'
            )
        elif obj.start_date > timezone.now():
            return format_html(
                '<span style="color: orange;">● Scheduled</span>'
            )
        elif obj.end_date and obj.end_date < timezone.now():
            return format_html(
                '<span style="color: gray;">● Expired</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">● Inactive</span>'
            )
    
    status_display.short_description = 'Status'
    
    def get_queryset(self, request):
        """Add a note about the currently active banner"""
        qs = super().get_queryset(request)
        return qs
    
    def changelist_view(self, request, extra_context=None):
        """Add information about the currently active banner to the changelist"""
        extra_context = extra_context or {}
        active_banner = SiteBanner.get_active_banner()
        extra_context['active_banner'] = active_banner
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(MessageBoardPost)
class MessageBoardPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'score_display', 'comment_count', 'is_pinned', 'is_active', 'created_at']
    list_filter = ['is_pinned', 'is_active', 'created_at', 'user']
    search_fields = ['title', 'content', 'user__username']
    ordering = ['-is_pinned', '-created_at']
    readonly_fields = ['upvotes', 'downvotes', 'created_at', 'updated_at']
    
    fields = [
        'user', 
        'title', 
        'content', 
        'is_pinned', 
        'is_active',
        'upvotes',
        'downvotes',
        'created_at',
        'updated_at'
    ]
    
    def score_display(self, obj):
        """Display vote score with color coding"""
        score = obj.score
        if score > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">+{}</span>', score
            )
        elif score < 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">{}</span>', score
            )
        else:
            return format_html('<span style="color: gray;">0</span>')
    
    score_display.short_description = 'Score'
    score_display.admin_order_field = 'upvotes'


@admin.register(MessageBoardComment)
class MessageBoardCommentAdmin(admin.ModelAdmin):
    list_display = ['comment_preview', 'user', 'post', 'parent_comment', 'score_display', 'depth_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'user', 'post']
    search_fields = ['content', 'user__username', 'post__title']
    ordering = ['-created_at']
    readonly_fields = ['upvotes', 'downvotes', 'created_at', 'updated_at', 'depth']
    
    fields = [
        'post',
        'user', 
        'parent',
        'content', 
        'is_active',
        'upvotes',
        'downvotes',
        'depth',
        'created_at',
        'updated_at'
    ]
    
    def comment_preview(self, obj):
        """Show preview of comment content"""
        preview = obj.content[:50]
        if len(obj.content) > 50:
            preview += "..."
        return preview
    
    comment_preview.short_description = 'Comment'
    
    def parent_comment(self, obj):
        """Display parent comment if exists"""
        if obj.parent:
            preview = obj.parent.content[:30]
            if len(obj.parent.content) > 30:
                preview += "..."
            return f"Reply to: {preview}"
        return "Top-level comment"
    
    parent_comment.short_description = 'Parent'
    
    def score_display(self, obj):
        """Display vote score with color coding"""
        score = obj.score
        if score > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">+{}</span>', score
            )
        elif score < 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">{}</span>', score
            )
        else:
            return format_html('<span style="color: gray;">0</span>')
    
    score_display.short_description = 'Score'
    
    def depth_display(self, obj):
        """Display nesting depth"""
        depth = obj.depth
        if depth == 0:
            return "Top level"
        else:
            return f"Level {depth}"
    
    depth_display.short_description = 'Depth'


@admin.register(MessageBoardVote)
class MessageBoardVoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'target_display', 'vote_type_display', 'created_at']
    list_filter = ['vote_type', 'created_at']
    search_fields = ['user__username', 'post__title', 'comment__content']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    
    def target_display(self, obj):
        """Display what was voted on"""
        if obj.post:
            return f"Post: {obj.post.title}"
        elif obj.comment:
            preview = obj.comment.content[:40]
            if len(obj.comment.content) > 40:
                preview += "..."
            return f"Comment: {preview}"
        return "Unknown"
    
    target_display.short_description = 'Target'
    
    def vote_type_display(self, obj):
        """Display vote type with icons"""
        if obj.vote_type == 1:
            return format_html('<span style="color: green;">⬆️ Upvote</span>')
        else:
            return format_html('<span style="color: red;">⬇️ Downvote</span>')
    
    vote_type_display.short_description = 'Vote'
