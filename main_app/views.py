import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic import DetailView, ListView
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignUpForm, ProfileEditForm
from .services import GameService
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Room, Game, GamePlayer, CardSubmission, RoomMembership

# Create your views here.
def home(request):
  return render(request, 'home.html')

@login_required
def dashboard(request):
    """Display dashboard with room list and create room functionality"""
    # Get rooms where user is a member
    user_rooms = Room.objects.filter(
        memberships__user=request.user,
        memberships__is_active=True,
        is_active=True
    ).distinct()
    
    # Handle room creation if POST
    if request.method == 'POST':
        room_name = request.POST.get('room_name', 'New Room')
        max_players = int(request.POST.get('max-players', 8))
        round_limit = int(request.POST.get('round-limit', 10))
        turn_timer = int(request.POST.get('turn-timer', 3)) * 60  # Convert minutes to seconds
        
        room = Room.objects.create(
            name=room_name,
            creator=request.user,
            max_players=max_players,
            round_limit=round_limit,
            turn_time_limit=turn_timer
        )
        # Add creator as member
        RoomMembership.objects.create(
            user=request.user,
            room=room
        )
        return redirect('room', room_code=room.room_code)
    
    context = {
        'user_rooms': user_rooms,
    }
    return render(request, 'dashboard.html', context)

@login_required
def join_room(request):
    """Join an existing room by code"""
    if request.method == 'POST':
        room_code = request.POST.get('room_code', '').upper()
        
        try:
            room = Room.objects.get(room_code=room_code, is_active=True)
            
            # Check if already a member
            if room.memberships.filter(user=request.user, is_active=True).exists():
                messages.info(request, "You are already a member of this room")
            else:
                # Add user to room
                RoomMembership.objects.create(
                    user=request.user,
                    room=room
                )
                messages.success(request, f"Successfully joined {room.name}!")
            
            return redirect('room', room_code=room.room_code)
            
        except Room.DoesNotExist:
            messages.error(request, "Invalid room code. Please check and try again.")
            return redirect('dashboard')
    
    return redirect('dashboard')

@login_required
def room(request, room_code):
    """Display room details with Start Game button for creator"""
    room = get_object_or_404(Room, room_code=room_code, is_active=True)
    
    # Check if user is a member of this room
    if not room.memberships.filter(user=request.user, is_active=True).exists():
        messages.error(request, "You are not a member of this room")
        return redirect('home')
    
    player_count = room.memberships.filter(is_active=True).count()
    
    context = {
        'room': room,
        'player_count': player_count,
        'players': room.memberships.filter(is_active=True).select_related('user'),
        'is_creator': room.creator == request.user,
    }
    
    return render(request, 'game-lobby.html', context)

class Login(LoginView):
    template_name = 'registration/login.html'

def signup(request):
    error_message = ''
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
        else:
            error_message = 'Invalid sign up - try again'
    else:
        form = SignUpForm()
    context = {'form': form, 'error_message': error_message}
    return render(request, 'registration/signup.html', context)

@login_required
def edit_profile(request):
    if request.method == 'POST':
        # Store the original email before form processing
        original_email = request.user.email
        
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            # Check if email is being changed BEFORE saving
            new_email = form.cleaned_data.get('email')
            
            user = form.save(commit=False)
            
            if new_email and new_email != original_email:
                # Don't update email in User model yet - let allauth handle it
                user.email = original_email  # Keep old email for now
                
                # Use allauth's email management
                from allauth.account.models import EmailAddress
                
                try:
                    # First, check if this email already exists for ANY user
                    existing = EmailAddress.objects.filter(email__iexact=new_email).first()
                    if existing:
                        if existing.user == request.user:
                            if existing.verified:
                                # This email is already verified for this user
                                messages.info(request, f'{new_email} is already verified. Making it your primary email.')
                                EmailAddress.objects.filter(user=request.user, primary=True).update(primary=False)
                                existing.set_as_primary()
                                user.email = new_email
                            else:
                                # Resend verification
                                existing.send_confirmation(request)
                                messages.info(request, f'A verification email has been sent to {new_email}. Please check your email to confirm the change.')
                        else:
                            messages.error(request, f'The email {new_email} is already in use by another account.')
                    else:
                        # Add the new email address
                        email_address = EmailAddress.objects.add_email(
                            request,
                            request.user,
                            new_email,
                            confirm=True  # This sends the confirmation email
                        )
                        
                        if email_address:
                            messages.info(request, f'A verification email has been sent to {new_email}. Please check your email to confirm the change.')
                        else:
                            messages.error(request, 'Could not add email address. It may already be in use.')
                except Exception as e:
                    messages.error(request, f'Error adding email: {str(e)}')
            
            if 'avatar' in request.FILES:
                user.avatar_url = request.FILES['avatar']
            user.save()
            
            if new_email == original_email:
                messages.success(request, 'Profile updated successfully!')
            
            return redirect('edit_profile')
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'edit_profile.html', {'form': form})

@login_required
def start_game(request, room_code):
    """Start a new game in the room"""
    room = get_object_or_404(Room, room_code=room_code, is_active=True)

 # Only room creator can start game
    if request.user != room.creator:
        messages.error(request, "Only the room creator can start the game")
        return redirect('room', room_code=room_code)

    # Check if enough players (minimum 2)
    if room.memberships.filter(is_active=True).count() < 2:
        messages.error(request, "Need at least 2 players to start")
        return redirect('room', room_code=room_code)

    # Check if a game already exists for this room
    try:
        game = room.game
        if game.status == 'active':
            # Game is already active, redirect to it
            messages.info(request, "Game is already in progress")
            return redirect('game_play', room_code=room_code)
        elif game.status == 'ended':
            # Previous game ended, delete it and create new one
            game.delete()
            game = GameService.create_game(room)
    except Game.DoesNotExist:
        # No game exists, create one
        game = GameService.create_game(room)
    
    # Start the game
    GameService.start_game(game)
    game.status = 'active'
    game.save()

    return redirect('game_play', room_code=room_code)

@login_required
def game_play(request, room_code):
    """Main game interface"""
    room = get_object_or_404(Room, room_code=room_code, is_active=True)
    game = get_object_or_404(Game, room=room)

    # Get current player
    try:
        player = game.players.get(user=request.user)
    except GamePlayer.DoesNotExist:
        messages.error(request, "You are not in this game")
        return redirect('room_list')

    # Get current round
    current_round = game.rounds.order_by('-round_number').first()

    # Check if player already submitted
    has_submitted = False
    if current_round:
        has_submitted = CardSubmission.objects.filter(
            round=current_round,
            player=player
        ).exists()

    # Get all submissions
    submissions = []
    if current_round:
        submissions = current_round.submissions.all()

    context = {
        'room': room,
        'game': game,
        'player': player,
        'current_round': current_round,
        'is_judge': current_round and current_round.judge == request.user,
        'is_creator': room.creator == request.user,
        'has_submitted': has_submitted,
        'submissions': submissions,
        'players': game.players.all(),
    }

    return render(request, 'game-play.html', context)

@login_required
@require_POST
def submit_card(request, room_code):
    """Player submits a white card"""
    room = get_object_or_404(Room, room_code=room_code)
    game = get_object_or_404(Game, room=room, status='active')
    player = get_object_or_404(GamePlayer, game=game, user=request.user)

    current_round = game.rounds.order_by('-round_number').first()
    if not current_round or current_round.status != 'card_selection':
        messages.error(request, "Cannot submit cards right now")
        return redirect('game_play', room_code=room_code)

    card_id = request.POST.get('card_id')
    if not card_id:
        messages.error(request, "Please select a card")
        return redirect('game_play', room_code=room_code)

    try:
        GameService.submit_card(player, current_round, card_id)
        messages.success(request, "Card submitted!")

        # Check if all players submitted
        expected_submissions = game.players.filter(is_active=True).exclude(
            user=current_round.judge
        ).count()
        actual_submissions = current_round.submissions.count()

        if actual_submissions >= expected_submissions:
            # Move to judging phase
            current_round.status = 'judging'
            current_round.save()

    except Exception as e:
        messages.error(request, str(e))

    return redirect('game_play', room_code=room_code)

@login_required
@require_POST
def select_winner(request, room_code):
    """Judge selects winning submission"""
    room = get_object_or_404(Room, room_code=room_code)
    game = get_object_or_404(Game, room=room, status='active')

    current_round = game.rounds.order_by('-round_number').first()
    if not current_round or current_round.status != 'judging':
        messages.error(request, "Cannot judge right now")
        return redirect('game_play', room_code=room_code)

    if current_round.judge != request.user:
        messages.error(request, "Only the judge can select a winner")
        return redirect('game_play', room_code=room_code)

    submission_id = request.POST.get('submission_id')
    if not submission_id:
        messages.error(request, "Please select a winner")
        return redirect('game_play', room_code=room_code)

    try:
        # Debug logging
        print(f"DEBUG select_winner: submission_id={submission_id}, type={type(submission_id)}")
        
        judge_player = game.players.get(user=request.user)
        game_winner = GameService.select_winner(
            current_round,
            submission_id,
            judge_player
        )

        if game_winner:
            # Game is over
            messages.success(request, f"{game_winner.winner.username} wins the game!")
            return redirect('room', room_code=room_code)
        else:
            # Start next round
            messages.success(request, "Round complete! Starting next round...")
            GameService.create_round(game)

    except GamePlayer.DoesNotExist:
        messages.error(request, "Judge player not found")
    except Exception as e:
        print(f"DEBUG select_winner error: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error selecting winner: {str(e)}")

    return redirect('game_play', room_code=room_code)

@login_required
@require_POST
def kick_player(request, room_code, user_id):
    """Room creator can kick players from the room"""
    room = get_object_or_404(Room, room_code=room_code, is_active=True)
    
    # Only room creator can kick players
    if request.user != room.creator:
        messages.error(request, "Only the room creator can kick players")
        return redirect('room', room_code=room_code)
    
    # Can't kick yourself
    if user_id == request.user.id:
        messages.error(request, "You cannot kick yourself from the room")
        return redirect('room', room_code=room_code)
    
    # Find the membership to deactivate
    try:
        membership = RoomMembership.objects.get(
            room=room,
            user_id=user_id,
            is_active=True
        )
        membership.is_active = False
        membership.save()
        
        # Also deactivate them from any active game
        active_game = room.games.filter(status='active').first()
        if active_game:
            try:
                game_player = active_game.players.get(user_id=user_id)
                game_player.is_active = False
                game_player.save()
            except GamePlayer.DoesNotExist:
                pass
        
        kicked_user = membership.user
        messages.success(request, f"{kicked_user.username} has been removed from the room")
        
    except RoomMembership.DoesNotExist:
        messages.error(request, "Player not found in this room")
    
    return redirect('room', room_code=room_code)

def game_status(request, room_code):
    """Get current game status for polling"""
    room = get_object_or_404(Room, room_code=room_code)
    game = get_object_or_404(Game, room=room)
    current_round = game.rounds.order_by('-round_number').first()

    # Count submissions
    submissions_count = 0
    if current_round:
        submissions_count = current_round.submissions.count()

    data = {
        'game_status': game.status,
        'round_status': current_round.status if current_round else None,
        'round_number': current_round.round_number if current_round else 0,
        'submissions_count': submissions_count,
        'total_players': game.players.filter(is_active=True).count(),
    }

    return JsonResponse(data)

@login_required
def change_password(request):
    """Allow users to change their password"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Check current password is correct
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match')
        elif len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long')
        else:
            # Set new password
            request.user.set_password(new_password)
            request.user.save()
            # Keep user logged in after password change
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully!')
            return redirect('edit_profile')
    
    return render(request, 'change_password.html')

@login_required
def delete_account_confirm(request):
    """Show confirmation page for account deletion"""
    return render(request, 'delete_account_confirm.html')

@login_required
@require_POST
def delete_account(request):
    """Delete user account"""
    # Verify password before deletion
    password = request.POST.get('password')
    
    if request.user.check_password(password):
        # Deactivate all room memberships
        request.user.roommembership_set.update(is_active=False)
        # Delete the user
        request.user.delete()
        messages.success(request, 'Your account has been deleted.')
        return redirect('home')
    else:
        messages.error(request, 'Incorrect password. Account not deleted.')
        return redirect('edit_profile')




