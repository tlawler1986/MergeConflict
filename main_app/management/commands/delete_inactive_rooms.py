from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from main_app.models import Room


class Command(BaseCommand):
    help = 'Delete rooms that have been inactive for more than 14 days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=14,
            help='Number of days of inactivity before deletion (default: 14)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find inactive rooms
        # For now, use created_at since we don't have last_activity field yet
        # After Task 11 is implemented, change this to use last_activity
        inactive_rooms = Room.objects.filter(
            created_at__lt=cutoff_date,
            is_active=True
        )
        
        count = inactive_rooms.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'No rooms older than {days} days found.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would delete {count} rooms:')
            )
            for room in inactive_rooms[:10]:  # Show first 10
                self.stdout.write(
                    f'  - {room.name} ({room.room_code}) - '
                    f'Created: {room.created_at}'
                )
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            # Actually delete the rooms
            self.stdout.write(
                self.style.WARNING(f'Deleting {count} inactive rooms...')
            )
            
            # Delete in batches to avoid memory issues
            deleted = 0
            batch_size = 100
            
            while inactive_rooms.exists():
                batch_ids = list(inactive_rooms.values_list('id', flat=True)[:batch_size])
                Room.objects.filter(id__in=batch_ids).delete()
                deleted += len(batch_ids)
                self.stdout.write(f'  Deleted {deleted}/{count} rooms...')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {deleted} rooms older than {days} days.'
                )
            )