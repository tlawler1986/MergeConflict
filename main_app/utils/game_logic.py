from .api_client import cards_api
from ..models import Game, GamePlayer, Round, CardSubmission
from django.utils import timezone

class GameManager:

    def start_game(self, game):
        """Initialize game with cards for all players"""
        # Deal cards to all players
        for player in game.players.all():
            white_cards = cards_api.get_white_cards(10)
            player.white_card_ids = [card['id'] for card in white_cards]
            player.save()
        
        # Start first round
        self.start_round(game, 1)
        
        game.status = 'active'
        game.started_at = timezone.now()
        game.save()

    def start_round(self, game, round_number):
        """Start a new round with black card and judge"""
        # Get judge (rotate based on turn_order)
        players = list(game.players.filter(is_active=True).order_by('turn_order'))
        judge_index = (round_number - 1) % len(players)
        judge = players[judge_index].user
        
        # Get black card
        black_cards = cards_api.get_black_cards(1)
        black_card = black_cards[0]
        
        # Create round
        round_obj = Round.objects.create(
            game=game,
            round_number=round_number,
            black_card_id=black_card['id'],
            black_card_text=black_card['text'],
            judge=judge,
            started_at=timezone.now()
        )
        
        return round_obj

    def submit_card(self, round_obj, player, white_card_id):
        """Player submits white card for round"""
        # Get card text from player's hand or API
        player_obj = GamePlayer.objects.get(game=round_obj.game, user=player)
        
        if white_card_id not in player_obj.white_card_ids:
            raise ValueError("Player doesn't have this card")
        
        # Get card text (could cache this)
        white_cards = cards_api.get_white_cards(1)  # Would need better lookup
        card_text = "Card text placeholder"  # Simplified for now
        
        submission = CardSubmission.objects.create(
            round=round_obj,
            player=player,
            white_card_id=white_card_id,
            white_card_text=card_text
        )
        
        # Remove card from player's hand and deal new one
        player_obj.white_card_ids.remove(white_card_id)
        new_cards = cards_api.get_white_cards(1)
        player_obj.white_card_ids.append(new_cards[0]['id'])
        player_obj.save()
        
        return submission

    def judge_round(self, round_obj, winning_submission_id):
        """Judge selects winning card"""
        winning_submission = CardSubmission.objects.get(
            id=winning_submission_id, 
            round=round_obj
        )
        
        # Mark winner
        winning_submission.is_winner = True
        winning_submission.save()
        
        # Update player score
        winner_player = GamePlayer.objects.get(
            game=round_obj.game, 
            user=winning_submission.player
        )
        winner_player.score += 1
        winner_player.save()
        
        # Update round
        round_obj.winner = winning_submission.player
        round_obj.status = 'completed'
        round_obj.ended_at = timezone.now()
        round_obj.save()
        
        # Check if game should end
        if round_obj.round_number >= round_obj.game.room.round_limit:
            self.end_game(round_obj.game)
        else:
            self.start_round(round_obj.game, round_obj.round_number + 1)

# Global instance
game_manager = GameManager()