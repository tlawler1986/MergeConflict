import requests
from django.shortcuts import render
from django.shortcuts import render, redirect
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic import DetailView, ListView
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignUpForm, ProfileEditForm

# Create your views here.
def home(request):
  return render(request, 'home.html')

@login_required
def room(request):
  return render(request, 'room.html')

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
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            if 'avatar' in request.FILES:
                user.avatar_url = request.FILES['avatar']
            user.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('edit_profile')
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'edit_profile.html', {'form': form})