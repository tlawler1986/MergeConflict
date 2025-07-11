from django.urls import path
from . import views

urlpatterns = [
  path('', views.home, name='home'),
  path('room/', views.room, name='room'),
  path('profile/edit/', views.edit_profile, name='edit_profile'),
]