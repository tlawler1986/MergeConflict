from django.core.management.base import BaseCommand
from main_app.utils.api_client import cards_api

class Command(BaseCommand):
    help = 'Warms up the card cache by pre-fetching cards from the API'

    def handle(self, *args, **options):
        self.stdout.write('Warming up card cache...')
        
        # Pre-fetch cards from the API
        try:
            # This will cache all cards for 1 hour
            all_cards = cards_api.get_cards()
            black_count = len(all_cards.get('black', []))
            white_count = len(all_cards.get('white', []))
            
            # Pre-fetch some random selections to populate the pool cache
            cards_api.get_black_cards(count=10)
            cards_api.get_white_cards(count=50)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully cached {black_count} black cards and {white_count} white cards'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to warm up cache: {e}')
            )