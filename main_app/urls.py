from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
  path('', views.home, name='home'),
  path('room/', views.room, name='room'),
  path('accounts/signup/', views.signup, name='signup'),
  path('accounts/login/', views.Login.as_view(), name='login'),
  path('accounts/logout/', LogoutView.as_view(next_page='home'), name='logout'),
]