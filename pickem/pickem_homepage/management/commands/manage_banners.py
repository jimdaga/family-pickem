from django.core.management.base import BaseCommand
from django.utils import timezone
from pickem_homepage.models import SiteBanner


class Command(BaseCommand):
    help = 'Manage site banners'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all banners',
        )
        parser.add_argument(
            '--deactivate-all',
            action='store_true',
            help='Deactivate all banners',
        )
        parser.add_argument(
            '--create-sample',
            action='store_true',
            help='Create sample banners for testing',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_banners()
        elif options['deactivate_all']:
            self.deactivate_all_banners()
        elif options['create_sample']:
            self.create_sample_banners()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify an action: --list, --deactivate-all, or --create-sample')
            )

    def list_banners(self):
        banners = SiteBanner.objects.all()
        if not banners:
            self.stdout.write('No banners found.')
            return

        self.stdout.write(f'\nFound {banners.count()} banner(s):')
        self.stdout.write('-' * 80)
        
        for banner in banners:
            status = "✓ ACTIVE" if banner.is_currently_active() else "✗ Inactive"
            self.stdout.write(f'ID: {banner.id}')
            self.stdout.write(f'Title: {banner.title}')
            self.stdout.write(f'Type: {banner.banner_type}')
            self.stdout.write(f'Status: {status}')
            self.stdout.write(f'Priority: {banner.priority}')
            self.stdout.write(f'Created: {banner.created_at.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write('-' * 40)

    def deactivate_all_banners(self):
        count = SiteBanner.objects.filter(is_active=True).update(is_active=False)
        self.stdout.write(
            self.style.SUCCESS(f'Deactivated {count} banner(s).')
        )

    def create_sample_banners(self):
        sample_banners = [
            {
                'title': 'Welcome to Family Pickem 2025!',
                'description': 'New season, new champions. Make your picks and claim victory!',
                'banner_type': 'success',
                'icon': 'fas fa-trophy',
                'priority': 3
            },
            {
                'title': 'Maintenance Window Scheduled',
                'description': 'Site will be briefly unavailable on Sunday 2AM-4AM EST for updates.',
                'banner_type': 'warning',
                'icon': 'fas fa-tools',
                'priority': 2,
                'is_active': False  # Disabled by default
            },
            {
                'title': 'Week 1 Picks Due Soon!',
                'description': 'Don\'t forget to submit your picks before Thursday kickoff.',
                'banner_type': 'info',
                'icon': 'fas fa-clock',
                'priority': 1,
                'is_active': False  # Disabled by default
            }
        ]

        created_count = 0
        for banner_data in sample_banners:
            banner = SiteBanner.objects.create(**banner_data)
            created_count += 1
            status = "active" if banner.is_active else "inactive"
            self.stdout.write(f'Created {status} banner: "{banner.title}"')

        self.stdout.write(
            self.style.SUCCESS(f'\nCreated {created_count} sample banner(s).')
        )
        self.stdout.write('Use the Django admin interface to manage these banners.')
