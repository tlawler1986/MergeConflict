from django.core.management.base import BaseCommand
from main_app.models import Card, CardPack
import json
import os

class Command(BaseCommand):
    help = 'Find cards that exist in the API but not in the database'

    def handle(self, *args, **options):
        # Load the API data
        data_file = os.path.join('card_data', 'cards_final.json')
        with open(data_file, 'r') as f:
            api_data = json.load(f)

        self.stdout.write("Checking for missing cards...\n")

        missing_black = []
        missing_white = []
        duplicate_cards = []

        for pack_data in api_data:
            pack_name = pack_data.get('name', '').strip()
            if not pack_name:
                continue
            
            try:
                pack = CardPack.objects.get(name=pack_name)
            except CardPack.DoesNotExist:
                self.stdout.write(f"Pack not found in DB: {pack_name}")
                continue
            
            # Get all cards for this pack from DB
            db_cards = set(Card.objects.filter(pack=pack).values_list('text', flat=True))
            
            # Check black cards
            for card in pack_data.get('black', []):
                text = card.get('text', '').strip()
                if text and text not in db_cards:
                    # Check if this card exists in another pack
                    other_pack = Card.objects.filter(text=text).exclude(pack=pack).first()
                    if other_pack:
                        duplicate_cards.append({
                            'text': text,
                            'type': 'black',
                            'api_pack': pack_name,
                            'db_pack': other_pack.pack.name
                        })
                    else:
                        missing_black.append({
                            'pack': pack_name,
                            'text': text
                        })
            
            # Check white cards
            for card in pack_data.get('white', []):
                text = card.get('text', '').strip()
                if text and text not in db_cards:
                    # Check if this card exists in another pack
                    other_pack = Card.objects.filter(text=text).exclude(pack=pack).first()
                    if other_pack:
                        duplicate_cards.append({
                            'text': text,
                            'type': 'white',
                            'api_pack': pack_name,
                            'db_pack': other_pack.pack.name
                        })
                    else:
                        missing_white.append({
                            'pack': pack_name,
                            'text': text
                        })

        # Report findings
        self.stdout.write(f"\nMissing black cards: {len(missing_black)}")
        self.stdout.write(f"Missing white cards: {len(missing_white)}")
        self.stdout.write(f"Duplicate cards (in different packs): {len(duplicate_cards)}")

        if missing_black:
            self.stdout.write("\nMissing Black Cards:")
            self.stdout.write("-" * 50)
            for card in missing_black:
                self.stdout.write(f"Pack: {card['pack']}")
                self.stdout.write(f"Text: {card['text']}")
                self.stdout.write("")

        if missing_white:
            self.stdout.write("\nMissing White Cards:")
            self.stdout.write("-" * 50)
            for card in missing_white:
                self.stdout.write(f"Pack: {card['pack']}")
                self.stdout.write(f"Text: {card['text']}")
                self.stdout.write("")

        if duplicate_cards:
            self.stdout.write("\nDuplicate Cards (exist in different packs):")
            self.stdout.write("-" * 50)
            for card in duplicate_cards[:20]:  # Show first 20
                self.stdout.write(f"Type: {card['type']}")
                self.stdout.write(f"Text: {card['text']}")
                self.stdout.write(f"API says it's in: {card['api_pack']}")
                self.stdout.write(f"DB has it in: {card['db_pack']}")
                self.stdout.write("")
            
            if len(duplicate_cards) > 20:
                self.stdout.write(f"... and {len(duplicate_cards) - 20} more duplicates")

        # Summary of unique texts
        all_texts_db = set(Card.objects.values_list('text', flat=True))
        self.stdout.write("\nSummary:")
        self.stdout.write(f"Total unique card texts in database: {len(all_texts_db)}")
        self.stdout.write(f"Total card records in database: {Card.objects.count()}")