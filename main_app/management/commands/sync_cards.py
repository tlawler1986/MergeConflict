from django.core.management.base import BaseCommand
from django.db import transaction
import requests
from main_app.models import CardPack, Card
from main_app.utils.api_client import CardsAPIClient
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync cards from REST Against Humanity API to local database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing cards before syncing',
        )
        parser.add_argument(
            '--packs',
            nargs='+',
            help='Specific pack names to sync (default: all packs)',
        )

    def handle(self, *args, **options):
        api_client = CardsAPIClient()
        
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing all existing cards...'))
            Card.objects.all().delete()
            CardPack.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('All cards cleared.'))
        
        # Get list of packs to sync
        if options['packs']:
            pack_names = options['packs']
            self.stdout.write(f'Syncing specific packs: {pack_names}')
        else:
            # Get all available packs from API
            try:
                pack_names = api_client.get_available_packs()
                self.stdout.write(f'Found {len(pack_names)} packs from API')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to fetch pack list: {e}')
                )
                return
        
        # Process each pack
        total_cards = 0
        successful_packs = 0
        
        for pack_name in pack_names:
            try:
                self.stdout.write(f'\nProcessing pack: {pack_name}')
                
                # Create or update pack
                pack, created = CardPack.objects.get_or_create(
                    name=pack_name,
                    defaults={'description': f'Cards from {pack_name}'}
                )
                
                if created:
                    self.stdout.write(f'  Created new pack: {pack_name}')
                else:
                    self.stdout.write(f'  Updating existing pack: {pack_name}')
                
                # Fetch cards for this pack
                cards_data = api_client.get_cards([pack_name])
                
                if not cards_data:
                    self.stdout.write(
                        self.style.WARNING(f'  No cards returned for {pack_name}')
                    )
                    continue
                
                # Process cards
                black_cards = cards_data.get('black', [])
                white_cards = cards_data.get('white', [])
                
                pack_total = 0
                
                # Use transaction for better performance
                with transaction.atomic():
                    # Process black cards
                    for card_data in black_cards:
                        card, created = Card.objects.update_or_create(
                            text=card_data['text'],
                            card_type='black',
                            pack=pack,
                            defaults={
                                'pick': card_data.get('pick', 1),
                                'is_active': True
                            }
                        )
                        if created:
                            pack_total += 1
                    
                    # Process white cards
                    for card_data in white_cards:
                        card, created = Card.objects.update_or_create(
                            text=card_data['text'],
                            card_type='white',
                            pack=pack,
                            defaults={
                                'pick': 1,
                                'is_active': True
                            }
                        )
                        if created:
                            pack_total += 1
                    
                    # Update pack statistics
                    pack.black_card_count = pack.cards.filter(card_type='black').count()
                    pack.white_card_count = pack.cards.filter(card_type='white').count()
                    pack.card_count = pack.black_card_count + pack.white_card_count
                    pack.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Synced {pack_total} new cards '
                        f'(Total in pack: {pack.card_count} - '
                        f'{pack.black_card_count} black, {pack.white_card_count} white)'
                    )
                )
                
                total_cards += pack_total
                successful_packs += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  Failed to sync {pack_name}: {e}')
                )
                continue
        
        # Final summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(
                f'Sync complete! '
                f'{successful_packs}/{len(pack_names)} packs synced successfully. '
                f'{total_cards} new cards added.'
            )
        )
        
        # Overall statistics
        total_packs = CardPack.objects.count()
        total_black = Card.objects.filter(card_type='black').count()
        total_white = Card.objects.filter(card_type='white').count()
        
        self.stdout.write(
            f'\nDatabase totals: {total_packs} packs, '
            f'{total_black + total_white} cards '
            f'({total_black} black, {total_white} white)'
        )