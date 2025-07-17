from django.core.management.base import BaseCommand
from django.db import transaction
from main_app.models import CardPack, Card
import json
import os

class Command(BaseCommand):
    help = 'Import card data from JSON file'

    def handle(self, *args, **options):
        data_file = os.path.join('card_data', 'cards_final.json')
        
        self.stdout.write(f'Looking for file: {data_file}')
        
        if not os.path.exists(data_file):
            self.stdout.write(self.style.ERROR(f'File not found: {data_file}'))
            return
        
        self.stdout.write('File found, loading JSON...')
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        self.stdout.write(f'Found {len(data)} packs in cards_final.json')
        
        total_black = 0
        total_white = 0
        
        for idx, pack_data in enumerate(data, start=1):
            pack_name = pack_data.get('name', '').strip()
            if not pack_name:
                continue
            
            self.stdout.write(f'\n[{idx}/{len(data)}] {pack_name}')
            
            try:
                # Get or create pack
                pack, pack_created = CardPack.objects.get_or_create(name=pack_name)
                
                # Get existing cards for this pack to avoid duplicates
                existing_texts = set(
                    Card.objects.filter(pack=pack).values_list('text', flat=True)
                )
                
                # Prepare cards to bulk create
                cards_to_create = []
                
                # Process black cards
                black_cards = pack_data.get('black', [])
                for card_data in black_cards:
                    text = card_data.get('text', '').strip()
                    if text and text not in existing_texts:
                        cards_to_create.append(Card(
                            text=text,
                            card_type='black',
                            pack=pack
                        ))
                        existing_texts.add(text)
                
                # Process white cards
                white_cards = pack_data.get('white', [])
                for card_data in white_cards:
                    text = card_data.get('text', '').strip()
                    if text and text not in existing_texts:
                        cards_to_create.append(Card(
                            text=text,
                            card_type='white',
                            pack=pack
                        ))
                        existing_texts.add(text)
                
                # Bulk create all cards for this pack
                if cards_to_create:
                    Card.objects.bulk_create(cards_to_create, batch_size=500)
                    black_created = sum(1 for c in cards_to_create if c.card_type == 'black')
                    white_created = sum(1 for c in cards_to_create if c.card_type == 'white')
                    total_black += black_created
                    total_white += white_created
                    self.stdout.write(f'  Added: {black_created}B/{white_created}W')
                else:
                    self.stdout.write(f'  No new cards to add')
                
                # Update pack counts
                pack.black_card_count = Card.objects.filter(pack=pack, card_type='black').count()
                pack.white_card_count = Card.objects.filter(pack=pack, card_type='white').count()
                pack.card_count = pack.black_card_count + pack.white_card_count
                pack.save()
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))
        
        # Final summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'Import complete!'))
        self.stdout.write(f'New cards: {total_black} black, {total_white} white')
        
        total_packs = CardPack.objects.count()
        total_db_black = Card.objects.filter(card_type='black').count()
        total_db_white = Card.objects.filter(card_type='white').count()
        
        self.stdout.write(f'\nDatabase totals:')
        self.stdout.write(f'  Packs: {total_packs}')
        self.stdout.write(f'  Black cards: {total_db_black}')
        self.stdout.write(f'  White cards: {total_db_white}')