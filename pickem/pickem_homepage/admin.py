from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import SiteBanner

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
