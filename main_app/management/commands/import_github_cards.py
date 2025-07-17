from django.core.management.base import BaseCommand
from django.db import transaction
from main_app.models import CardPack, Card
import json
import os

class Command(BaseCommand):
    help = 'Import cards from GitHub CAH JSON - using same efficient pattern as import_cards.py'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default='external_cards/against-humanity/source/cards.json',
            help='Path to the cards.json file'
        )

    def handle(self, *args, **options):
        json_file = options['file']
        
        if not os.path.exists(json_file):
            self.stdout.write(self.style.ERROR(f'File not found: {json_file}'))
            return
        
        with open(json_file, 'r') as f:
            cards_data = json.load(f)
        
        self.stdout.write(f'Found {len(cards_data)} cards in JSON file')
        
        # Group cards by expansion
        expansions = {}
        for card in cards_data:
            exp_name = card.get('expansion', 'Unknown')
            if exp_name not in expansions:
                expansions[exp_name] = {'black': [], 'white': []}
            
            if card['cardType'] == 'Q':  # Question = Black card
                expansions[exp_name]['black'].append(card)
            elif card['cardType'] == 'A':  # Answer = White card
                expansions[exp_name]['white'].append(card)
        
        self.stdout.write(f'\nFound {len(expansions)} expansions')
        
        total_black = 0
        total_white = 0
        
        for idx, (exp_name, cards) in enumerate(expansions.items(), 1):
            pack_name = f'[GitHub] {exp_name}'
            self.stdout.write(f'\n[{idx}/{len(expansions)}] Processing {pack_name}')
            
            try:
                with transaction.atomic():
                    # Create or get the pack
                    pack, _ = CardPack.objects.get_or_create(
                        name=pack_name,
                        defaults={'description': f'Cards from GitHub - {exp_name}'}
                    )
                    
                    # Get existing cards for this pack (ONE QUERY)
                    existing_texts = set(
                        Card.objects.filter(pack=pack).values_list('text', flat=True)
                    )
                    
                    # Prepare cards to bulk create
                    cards_to_create = []
                    
                    # Process black cards
                    for card_data in cards['black']:
                        text = card_data.get('text', '').strip()
                        if text and text not in existing_texts:
                            pick = card_data.get('numAnswers', 1) or 1
                            cards_to_create.append(Card(
                                text=text,
                                card_type='black',
                                pack=pack,
                                pick=pick
                            ))
                            existing_texts.add(text)
                    
                    # Process white cards
                    for card_data in cards['white']:
                        text = card_data.get('text', '').strip()
                        if text and text not in existing_texts:
                            cards_to_create.append(Card(
                                text=text,
                                card_type='white',
                                pack=pack
                            ))
                            existing_texts.add(text)
                    
                    # Bulk create all cards for this pack (ONE QUERY per 500 cards)
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
        
        self.stdout.write(self.style.SUCCESS(
            f'\nImport complete! Added {total_black} black, {total_white} white cards'
        ))