from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from .models import Room, Game, GamePlayer
from .services import GameService


class CardDeduplicationTestCase(TestCase):
  def setUp(self):
    """Set up test data"""
    # Create users
    self.host = User.objects.create_user('host', 'host@test.com', 'password')
    self.player1 = User.objects.create_user('player1', 'p1@test.com', 'password')
    self.player2 = User.objects.create_user('player2', 'p2@test.com', 'password')
    
    # Create room and game
    self.room = Room.objects.create(
      name='Test Room',
      room_code='TEST123',
      host=self.host,
      max_players=6
    )
    self.game = Game.objects.create(
      room=self.room,
      status='waiting'
    )
    
    # Add players to game
    self.game_player1 = GamePlayer.objects.create(
      game=self.game,
      user=self.player1,
      turn_order=1
    )
    self.game_player2 = GamePlayer.objects.create(
      game=self.game,
      user=self.player2,
      turn_order=2
    )

  @patch('main_app.services.cards_api.get_white_cards')
  def test_no_duplicate_cards_across_players(self, mock_get_cards):
    """Test that cards are not duplicated across players in the same game"""
    # Mock the API to return predictable cards
    mock_cards = [{'text': f'Card {i}', 'pack': 'Test Pack'} for i in range(1, 21)]
    
    # Configure mock to return different cards each time
    mock_get_cards.side_effect = [
      mock_cards[:10],  # First call for player 1
      mock_cards[10:20],  # Second call for player 2
    ]
    
    # Deal cards to both players
    GameService.deal_white_cards(self.game_player1, count=10)
    GameService.deal_white_cards(self.game_player2, count=10)
    
    # Refresh from database
    self.game_player1.refresh_from_db()
    self.game_player2.refresh_from_db()
    self.game.refresh_from_db()
    
    # Get all card texts
    player1_cards = set(card['text'] for card in self.game_player1.card_hand)
    player2_cards = set(card['text'] for card in self.game_player2.card_hand)
    
    # Assert no duplicates
    duplicates = player1_cards & player2_cards
    self.assertEqual(len(duplicates), 0, f"Found duplicate cards: {duplicates}")
    
    # Assert all dealt cards are tracked
    all_dealt = set(self.game.dealt_white_cards)
    expected_dealt = player1_cards | player2_cards
    self.assertEqual(all_dealt, expected_dealt)