import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic import DetailView, ListView
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .forms import SignUpForm, ProfileEditForm
from .services import GameService
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Room, Game, GamePlayer, CardSubmission, RoomMembership, CardPack
from django.db.models import Max
from django.core.cache import cache

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
        selected_pack_ids = request.POST.getlist('selected_packs')
        
        room = Room.objects.create(
            name=room_name,
            creator=request.user,
            max_players=max_players,
            round_limit=round_limit,
            turn_time_limit=turn_timer
        )
        
        # Add selected packs to the room
        if selected_pack_ids:
            room.selected_packs.set(selected_pack_ids)
        
        # Add creator as member
        RoomMembership.objects.create(
            user=request.user,
            room=room
        )
        return redirect('room', room_code=room.room_code)
    
    # Get available card packs from database, organized by source
    # Use a single query with proper ordering
    from django.db.models import Q, Case, When, Value, IntegerField
    
    # Define default pack names (these specific 4 packs)
    default_pack_names = [
        'Geek Pack',
        'Nerd Bundle: A Few More Cards For You Nerds (Target Exclusive)', 
        'Science Pack',
        'World Wide Web Pack'
    ]
    
    # Fetch all packs in one optimized query
    all_packs = CardPack.objects.filter(is_active=True)
    
    # Separate packs by category
    default_packs = list(all_packs.filter(name__in=default_pack_names).order_by('name'))
    github_packs = list(all_packs.filter(name__startswith='[GitHub]').order_by('name'))
    
    # Default packs already have clean names, no need for display_name
    
    # REST Against Humanity packs (exclude default packs and GitHub packs)
    api_packs = list(all_packs.exclude(
        Q(name__in=default_pack_names) | Q(name__startswith='[GitHub]')
    ).order_by('name'))
    
    # Add display_name for GitHub packs
    for pack in github_packs:
        pack.display_name = pack.name.replace('[GitHub] ', '')
    
    # Add display_name for API packs (remove "CAH" prefix)
    for pack in api_packs:
        pack.display_name = pack.name.replace('CAH: ', '').replace('CAH ', '')
    
    context = {
        'user_rooms': user_rooms,
        'default_packs': default_packs,
        'api_packs': api_packs,
        'github_packs': github_packs,
    }
    return render(request, 'dashboard.html', context)

@login_required
def room_list(request):
    """Display all rooms with search and filter"""
    # Get query parameters
    search_query = request.GET.get('search', '')
    filter_type = request.GET.get('filter', 'all')  # all, mine, active
    
    # Base queryset
    rooms = Room.objects.filter(is_active=True).annotate(
        player_count=Count('memberships', filter=Q(memberships__is_active=True))
    ).select_related('creator')
    
    # Apply filters
    if search_query:
        rooms = rooms.filter(
            Q(name__icontains=search_query) | 
            Q(room_code__icontains=search_query) |
            Q(creator__username__icontains=search_query)
        )
    
    if filter_type == 'mine':
        rooms = rooms.filter(
            memberships__user=request.user,
            memberships__is_active=True
        )
    elif filter_type == 'active':
        rooms = rooms.filter(game__status='active')
    
    # Order by most recent
    rooms = rooms.order_by('-created_at')
    
    # Paginate
    paginator = Paginator(rooms, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get user's recent rooms
    recent_rooms = Room.objects.filter(
        memberships__user=request.user,
        memberships__is_active=True,
        is_active=True
    ).order_by('-memberships__joined_at')[:5]
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filter_type': filter_type,
        'recent_rooms': recent_rooms,
    }
    
    return render(request, 'room_list.html', context)

@login_required
def join_room(request):
    """Join an existing room by code"""
    if request.method == 'POST':
        room_code = request.POST.get('room_code', '').upper()
        
        try:
            room = Room.objects.get(room_code=room_code, is_active=True)
            
            # Check if already a member
            existing_membership = room.memberships.filter(user=request.user).first()
            if existing_membership:
                if existing_membership.is_active:
                    messages.info(request, "You are already a member of this room")
                else:
                    # Reactivate membership for previously kicked user
                    existing_membership.is_active = True
                    existing_membership.save()
                    messages.success(request, f"Successfully rejoined {room.name}!")
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
    
    # Ensure user has stats
    from .models import UserStats
    UserStats.objects.get_or_create(user=request.user)
    
    # Clear any stale messages (temporary fix - remove after deployment)
    storage = messages.get_messages(request)
    for _ in storage:
        pass  # This consumes and clears all messages
    
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
    invalidate_game_status_cache(room_code)

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
        return redirect('dashboard')

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

    # Calculate remaining time if there's an active round
    remaining_time = None
    if current_round and current_round.status in ['card_selection', 'judging']:
      elapsed = (timezone.now() - current_round.phase_start_time).total_seconds()
      remaining_time = max(0, room.turn_time_limit - int(elapsed))

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
        'remaining_time': remaining_time, 
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
            current_round.phase_start_time = timezone.now()
            current_round.save()
            invalidate_game_status_cache(room_code)

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
        invalidate_game_status_cache(room_code)

        if game_winner:
             # Game is over
            messages.success(request, "Game complete!")
            return redirect('game_results', room_code=room_code)
        else:
            # Start next round
            messages.success(request, "Round complete! Starting next round...")
            GameService.create_round(game)
            invalidate_game_status_cache(room_code)

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
        try:
            if hasattr(room, 'game') and room.game.status == 'active':
                game_player = room.game.players.get(user_id=user_id)
                game_player.is_active = False
                game_player.save()
                invalidate_game_status_cache(room_code)
        except (Game.DoesNotExist, GamePlayer.DoesNotExist):
            pass
        
        kicked_user = membership.user
        messages.success(request, f"{kicked_user.username} has been removed from the room")
        
    except RoomMembership.DoesNotExist:
        messages.error(request, "Player not found in this room")
    
    return redirect('room', room_code=room_code)

@login_required
def lobby_status(request, room_code):
    """Get lobby status for AJAX polling"""
    room = get_object_or_404(Room, room_code=room_code, is_active=True)
    
    # Check if user is still a member
    if not room.memberships.filter(user=request.user, is_active=True).exists():
        return JsonResponse({'error': 'Not a member', 'redirect': 'dashboard'})
    
    # Check if game started
    try:
        game = room.game
        if game.status == 'active':
            return JsonResponse({
                'game_status': 'active',
                'redirect': f'/room/{room_code}/game/'
            })
    except Game.DoesNotExist:
        pass
    
    # Get current players
    players = []
    for membership in room.memberships.filter(is_active=True).select_related('user'):
        players.append({
            'id': membership.user.id,
            'username': membership.user.username,
            'is_creator': membership.user == room.creator,
            'avatar_url': membership.user.avatar_url.url if membership.user.avatar_url else None
        })
    
    return JsonResponse({
        'player_count': len(players),
        'players': players,
        'game_status': 'waiting'
    })

def game_status(request, room_code):
    """Get current game status for polling"""
    # Create cache key
    cache_key = f'game_status_{room_code}'
    
    # Try to get from cache first
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return JsonResponse(cached_data)
    
    # If not in cache, fetch from database
    room = get_object_or_404(Room, room_code=room_code)
    try:
        game = Game.objects.get(room=room)
        current_round = game.rounds.order_by('-round_number').first() if game else None
        # Count submissions
        submissions_count = 0
        if current_round:
            submissions_count = current_round.submissions.count()
        data = {
            'game_status': game.status,
            'round_status': current_round.status if current_round else None,
            'round_number': current_round.round_number if current_round else 0,
            'submissions_count': submissions_count,
            'total_players': game.players.filter(is_active=True).count() if game else 0,
        }
    except Game.DoesNotExist:
        # No game exists
        data = {
            'game_status': None,
            'round_status': None,
            'round_number': 0,
            'submissions_count': 0,
            'total_players': 0,
        }
    
    # Cache the result for 30 seconds to reduce database hits
    cache.set(cache_key, data, timeout=30)
    
    return JsonResponse(data)

def invalidate_game_status_cache(room_code):
    """Invalidate the game status cache for a specific room"""
    cache_key = f'game_status_{room_code}'
    cache.delete(cache_key)

@login_required
def check_timer(request, room_code):
  """Check remaining time and auto-advance if expired"""
  room = get_object_or_404(Room, room_code=room_code)
  game = get_object_or_404(Game, room=room, status='active')
  current_round = game.rounds.order_by('-round_number').first()

  if not current_round:
    return JsonResponse({'remaining': 0, 'phase_changed': False})

  elapsed = (timezone.now() - current_round.phase_start_time).total_seconds()
  remaining = max(0, room.turn_time_limit - int(elapsed))

  phase_changed = False

# Auto-advance if time expired
  if remaining == 0:
    if current_round.status == 'card_selection':
      # Force advance to judging
      current_round.status = 'judging'
      current_round.phase_start_time = timezone.now()
      current_round.save()
      invalidate_game_status_cache(room_code)
      phase_changed = True
    elif current_round.status == 'judging':
      # Auto-select random winner or skip round
      submissions = current_round.submissions.all()
      if submissions:
        import random
        winner = random.choice(submissions)
        judge_player = game.players.get(user=current_round.judge)
        GameService.select_winner(current_round, str(winner.id), judge_player)
      else:
        # No submissions, start next round
        GameService.create_round(game)
      phase_changed = True

  return JsonResponse({
    'remaining': remaining,
    'phase_changed': phase_changed,
    'current_phase': current_round.status
  })    

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
        request.user.room_memberships.update(is_active=False)
        # Delete the user
        request.user.delete()
        messages.success(request, 'Your account has been deleted.')
        return redirect('home')
    else:
        messages.error(request, 'Incorrect password. Account not deleted.')
        return redirect('edit_profile')

@login_required
def game_results(request, room_code):
    #"""Display game results with winner(s)"""
    room = get_object_or_404(Room, room_code=room_code)
    game = get_object_or_404(Game, room=room, status='ended')
    # Get all players with scores
    players = game.players.all().order_by('-score', 'user__username')
    # Find winner(s) - handle ties
    top_score = game.players.aggregate(Max('score'))['score__max']
    winners = game.players.filter(score=top_score)
    context = {
      'room': room,
      'game': game,
      'players': players,
      'winners': winners,
      'top_score': top_score,
      'is_creator': room.creator == request.user,
    }
    return render(request, 'game_results.html', context)



@login_required
@require_POST
def end_game(request, room_code):
    """End game early (host only)"""
    room = get_object_or_404(Room, room_code=room_code)
    game = get_object_or_404(Game, room=room, status='active')
    # Only room creator can end game
    if request.user != room.creator:
        messages.error(request, "Only the room creator can end the game")
        return redirect('game_play', room_code=room_code)
    # End the game using the service
    GameService.end_game_early(game)
    invalidate_game_status_cache(room_code)
    messages.success(request, "Game ended early!")
    return redirect('game_results', room_code=room_code)
