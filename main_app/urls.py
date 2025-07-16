from django.urls import path
from . import views

urlpatterns = [
  path('', views.home, name='home'),
  path('room/', views.dashboard, name='dashboard'),
  path('room/join/', views.join_room, name='join_room'),
  path('room/<str:room_code>/', views.room, name='room'),
  path('profile/edit/', views.edit_profile, name='edit_profile'),
  path('profile/change-password/', views.change_password, name='change_password'),
  path('profile/delete-confirm/', views.delete_account_confirm, name='delete_account_confirm'),
  path('profile/delete/', views.delete_account, name='delete_account'),
  path('room/<str:room_code>/start/', views.start_game, name='start_game'),
  path('room/<str:room_code>/game/', views.game_play, name='game_play'),
  path('room/<str:room_code>/submit/', views.submit_card, name='submit_card'),
  path('room/<str:room_code>/judge/', views.select_winner, name='select_winner'),
  path('room/<str:room_code>/status/', views.game_status, name='game_status'),
  path('room/<str:room_code>/kick/<int:user_id>/', views.kick_player, name='kick_player'),
  path('room/<str:room_code>/lobby-status/', views.lobby_status, name='lobby_status'),
  path('room/<str:room_code>/results/', views.game_results, name='game_results'),
  path('room/<str:room_code>/end/', views.end_game, name='end_game'),
  path('room/<str:room_code>/timer/', views.check_timer, name='check_timer'),
]