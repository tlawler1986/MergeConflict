from django.db import models
from django.contrib.auth.models import AbstractUser
import string
import random

class User(AbstractUser):
    """Custom User model to replace date_joined with created_at/updated_at"""
    # Remove date_joined field
    date_joined = None
    
    # Add our custom fields from ERD
    avatar_url = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.username

class Room(models.Model):
    room_code = models.CharField(max_length=6, unique=True)
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    max_players = models.IntegerField(default=8)
    round_limit = models.IntegerField(default=10)
    turn_time_limit = models.IntegerField(default=120)  # seconds
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.room_code:
            self.room_code = self.generate_room_code()
        super().save(*args, **kwargs)

    def generate_room_code(self):
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not Room.objects.filter(room_code=code).exists():
                return code

class RoomMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'room')

class Game(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting for Players'),
        ('active', 'Game in Progress'),
        ('ended', 'Game Ended'),
    ]
    
    room = models.OneToOneField(Room, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    current_round_number = models.IntegerField(default=0)
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

class GamePlayer(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    turn_order = models.IntegerField(default=0)
    card_hand = models.JSONField(default=list)  # Store full card objects
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('game', 'user')
        ordering = ['turn_order']

class Round(models.Model):
    STATUS_CHOICES = [
        ('card_selection', 'Players Selecting Cards'),
        ('judging', 'Judge Reviewing Submissions'),
        ('completed', 'Round Complete'),
    ]
    
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='rounds')
    round_number = models.IntegerField()
    black_card = models.JSONField(default=dict)  # Full black card object
    judge = models.ForeignKey(User, on_delete=models.CASCADE, related_name='judged_rounds')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='card_selection')
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_rounds')
    winning_submission = models.ForeignKey('CardSubmission', on_delete=models.SET_NULL, null=True, blank=True, related_name='won_round')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('game', 'round_number')

class CardSubmission(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='submissions')
    player = models.ForeignKey(GamePlayer, on_delete=models.CASCADE)
    white_cards = models.JSONField(default=list)  # List of white card objects
    is_winner = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('round', 'player')