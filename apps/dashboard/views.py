from django.shortcuts import render
from apps.teams.models import Team

def home(request):
    teams = Team.objects.all()
    return render(request, 'dashboard/home.html', {'teams': teams})