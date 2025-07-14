from django.db import transaction
from .models import Game, GamePlayer, Round, CardSubmission
from .utils.api_client import cards_api
import random
import json

class GameService:
  """Service class for managing game logic"""

  @staticmethod
  @transaction.atomic
  def create_game(room):
    """Create a new game for a room with all players"""
    # Create the game
    game = Game.objects.create(room=room)

    # Add all room members as game players
    for membership in room.memberships.filter(is_active=True):
      GamePlayer.objects.create(
        game=game,
        user=membership.user,
        card_hand=[]  # Will be populated when game starts
      )

    return game

  @staticmethod
  def start_game(game):
    """Start the game by dealing cards and creating first round"""
    # Deal white cards to all players
    players = game.players.all()
    for player in players:
      GameService.deal_white_cards(player)

    # Create first round
    return GameService.create_round(game)

  @staticmethod
  def deal_white_cards(player, count=10):
    """Deal white cards to a player"""
    # Get current hand size
    current_hand = player.card_hand or []
    needed_cards = count - len(current_hand)

    if needed_cards > 0:
      # Fetch new white cards from API
      white_cards = cards_api.get_white_cards(count=needed_cards)

      # Add to player's hand
      for card in white_cards:
          current_hand.append({
            'id': str(random.randint(10000, 99999)),  # Generate unique ID
            'text': card['text'],
            'pack': card.get('pack', 'Unknown')
          })

      player.card_hand = current_hand
      player.save()

  @staticmethod
  @transaction.atomic
  def create_round(game):
    """Create a new round with a black card"""
    # Get random black card from API
    # Fetch multiple cards at once to improve caching
    black_cards = cards_api.get_black_cards(count=5)  # Get more for cache
    if not black_cards:
      raise Exception("No black cards available")

    black_card = black_cards[0]  # Use the first one

    # Determine next judge (rotate through players)
    last_round = game.rounds.order_by('-round_number').first()
    if last_round and last_round.judge:
      # Get next player after current judge
      players = list(game.players.order_by('id'))
      current_judge_index = next(
        (i for i, p in enumerate(players) if p.user.id == last_round.judge.id),
        -1
      )
      next_judge_index = (current_judge_index + 1) % len(players)
      judge = players[next_judge_index].user  # Get the User, not GamePlayer
    else:
      # First round - random judge
      judge_player = game.players.order_by('?').first()
      judge = judge_player.user if judge_player else None

    # Create the round
    round_number = (last_round.round_number + 1) if last_round else 1
    round_obj = Round.objects.create(
      game=game,
      round_number=round_number,
      black_card=black_card,
      judge=judge
    )

    return round_obj

  @staticmethod
  @transaction.atomic
  def submit_card(player, round_obj, card_id):
    """Submit a white card for the round"""
    # Check if player already submitted
    if CardSubmission.objects.filter(
      round=round_obj,
      player=player
    ).exists():
      raise Exception("Already submitted for this round")

    # Find card in player's hand
    card_hand = player.card_hand or []
    selected_card = None

    for card in card_hand:
      if card['id'] == card_id:
        selected_card = card
        break

    if not selected_card:
      raise Exception("Card not found in hand")

    # Create submission
    submission = CardSubmission.objects.create(
      round=round_obj,
      player=player,
      white_cards=[selected_card]  # Support multiple cards for pick > 1
    )

    # Remove card from hand
    card_hand = [c for c in card_hand if c['id'] != card_id]
    player.card_hand = card_hand
    player.save()

    # Deal replacement card
    GameService.deal_white_cards(player, count=10)

    return submission

  @staticmethod
  @transaction.atomic
  def select_winner(round_obj, submission_id, judge_player):
    """Judge selects the winning submission"""
    # Verify judge (compare User objects)
    if round_obj.judge.id != judge_player.user.id:
      raise Exception("Only the judge can select winner")

    # Get submission
    submission = CardSubmission.objects.get(
      id=submission_id,
      round=round_obj
    )

    # Mark as winner
    round_obj.winning_submission = submission
    round_obj.save()

    # Award point
    submission.player.score += 1
    submission.player.save()

  # Check if we've reached the round limit
    game = round_obj.game
    if round_obj.round_number >= game.room.round_limit:
      # Game is over - find player(s) with highest score
      from django.db.models import Max
      top_score = game.players.aggregate(Max('score'))['score__max']
      top_players = game.players.filter(score=top_score)
      if top_players.count() > 1:
        # Multiple winners (tie) - leave winner as None to indicate tie
        game.winner = None
      else:
        # Single winner
        game.winner = top_players.first().user
      game.status = 'ended'
      game.save()
      return game
    return None  # Continue to next round

  @staticmethod
  def end_game_early(game):
      """End game before round limit - determine winner(s) by current highest score"""
      from django.db.models import Max
      top_score = game.players.aggregate(Max('score'))['score__max']
      top_players = game.players.filter(score=top_score)

      if top_players.count() > 1:
        # Multiple winners (tie)
        game.winner = None
      else:
        # Single winner
        game.winner = top_players.first().user

      game.status = 'ended'
      game.save()
      return game