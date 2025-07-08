from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Team

@login_required
def team_list(request):
    return render(request, 'teams/list.html')

@login_required
def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id, admin=request.user)
    return render(request, "teams/detail.html", {"team": team})