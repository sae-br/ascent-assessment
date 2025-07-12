from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.teams.models import Team
from apps.assessments.models import Assessment
from datetime import date

@login_required
def dashboard_home(request):
    teams = Team.objects.filter(admin=request.user).prefetch_related("assessments", "members")

    assessments = []
    for team in teams:
        team.assessments.filter(deadline__gte=date.today())
        for assessment in team.assessments.all():
            members = team.members.all()
            assessments.append({
                "team": team,
                "assessment": assessment,
                "members": members
            })

    return render(request, "dashboard/home.html", {
        "teams": teams,
        "assessments": assessments
    })