from django.shortcuts import render
from apps.teams.models import Team
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    teams = Team.objects.all()
    return render(request, 'dashboard/home.html', {'teams': teams})