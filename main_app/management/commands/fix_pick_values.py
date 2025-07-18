from django.core.management.base import BaseCommand
from django.db import transaction
from main_app.models import Card
import re


class Command(BaseCommand):
    help = 'Fix pick values for cards based on actual number of blanks in text'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Find all black cards
        black_cards = Card.objects.filter(card_type='black')
        total_cards = black_cards.count()
        
        self.stdout.write(f'Checking {total_cards} black cards...')
        
        cards_to_update = []
        
        for card in black_cards:
            # Count blanks - any sequence of 1 or more underscores
            blanks = re.findall(r'_+', card.text)
            actual_blank_count = len(blanks)
            
            # Check if pick value needs updating
            if actual_blank_count != card.pick:
                cards_to_update.append({
                    'card': card,
                    'old_pick': card.pick,
                    'new_pick': actual_blank_count,
                    'text': card.text[:80]
                })
        
        if not cards_to_update:
            self.stdout.write(self.style.SUCCESS('All cards have correct pick values!'))
            return
        
        # Group by change type for summary
        by_change = {}
        for update in cards_to_update:
            key = f"{update['old_pick']} -> {update['new_pick']}"
            if key not in by_change:
                by_change[key] = []
            by_change[key].append(update)
        
        # Show summary
        self.stdout.write(f'\nFound {len(cards_to_update)} cards needing updates:')
        for change_type, updates in sorted(by_change.items()):
            self.stdout.write(f'  {change_type}: {len(updates)} cards')
        
        # Show examples
        self.stdout.write('\nExample cards to be updated:')
        for update in cards_to_update[:5]:
            self.stdout.write(
                f'  [{update["card"].pack.name}] "{update["text"]}..." '
                f'(pick: {update["old_pick"]} -> {update["new_pick"]})'
            )
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))
            return
        
        # Confirm before making changes
        confirm = input(f'\nUpdate {len(cards_to_update)} cards? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('Cancelled'))
            return
        
        # Update cards
        with transaction.atomic():
            updated = 0
            for update in cards_to_update:
                card = update['card']
                card.pick = update['new_pick']
                card.save()
                updated += 1
            
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully updated {updated} cards!')
            )
        
        # Show final summary
        self.stdout.write('\nUpdate summary:')
        for change_type, updates in sorted(by_change.items()):
            self.stdout.write(f'  {change_type}: {len(updates)} cards updated')