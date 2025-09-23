from django.db import models
from django.utils import timezone

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
