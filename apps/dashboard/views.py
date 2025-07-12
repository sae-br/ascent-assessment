from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.teams.models import Team
from apps.assessments.models import Assessment
from datetime import date

@login_required
def dashboard_home(request):
    user_teams = Team.objects.filter(admin=request.user)
    assessments_data = []

    for team in user_teams:
        assessments = team.assessments.filter(deadline__gte=date.today())
        for assessment in assessments:
            participants = assessment.participants.select_related('team_member')
            assessments_data.append({
                "team": team,
                "assessment": assessment,
                "participants": participants,
            })

    return render(request, "dashboard/home.html", {
        "assessments_data": assessments_data
    })