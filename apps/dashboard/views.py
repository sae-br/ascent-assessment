from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.teams.models import Team

@login_required
def dashboard_home(request):
    user_teams = Team.objects.filter(admin=request.user)
    return render(request, "dashboard/home.html", {"teams": user_teams})