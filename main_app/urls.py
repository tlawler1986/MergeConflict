from django.urls import path
from . import views

urlpatterns = [
  path('', views.home, name='home'),
  path('room/', views.dashboard, name='dashboard'),
  path('room/join/', views.join_room, name='join_room'),
  path('room/<str:room_code>/', views.room, name='room'),
  path('profile/edit/', views.edit_profile, name='edit_profile'),
  path('room/<str:room_code>/start/', views.start_game, name='start_game'),
  path('room/<str:room_code>/game/', views.game_play, name='game_play'),
  path('room/<str:room_code>/submit/', views.submit_card, name='submit_card'),
  path('room/<str:room_code>/judge/', views.select_winner, name='select_winner'),
  path('room/<str:room_code>/status/', views.game_status, name='game_status'),
  path('room/<str:room_code>/kick/<int:user_id>/', views.kick_player, name='kick_player'),
]