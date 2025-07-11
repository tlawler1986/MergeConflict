import requests
from django.shortcuts import render
from django.shortcuts import render, redirect
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic import DetailView, ListView

# Create your views here.
def home(request):
  return render(request, 'home.html')