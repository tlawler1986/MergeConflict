from django.urls import path
from . import views

urlpatterns = [
  path('', views.home, name='home'),
  path('room/<str:room_code>/', views.room, name='room'),
  path('profile/edit/', views.edit_profile, name='edit_profile'),
  path('room/<str:room_code>/start/', views.start_game, name='start_game'),
  path('room/<str:room_code>/game/', views.game_play, name='game_play'),
  path('room/<str:room_code>/submit/', views.submit_card, name='submit_card'),
  path('room/<str:room_code>/judge/', views.select_winner, name='select_winner'),
  path('room/<str:room_code>/status/', views.game_status, name='game_status'),
]