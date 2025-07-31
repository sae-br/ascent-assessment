from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Count, Q
from datetime import date

from apps.teams.models import Team
from apps.assessments.models import Assessment, AssessmentParticipant


@login_required
def dashboard_home(request):
    user = request.user

    # Recent Assessments (limit 3, sorted by -created_at)
    recent_assessments = (
        Assessment.objects
        .filter(team__admin=user)
        .select_related("team")
        .order_by("-created_at")[:3]
    )

    assessments_data = []
    for assessment in recent_assessments:
        participants = (
            assessment.participants
            .select_related("team_member")
            .order_by("has_submitted")  # False (incomplete) first
        )
        assessments_data.append({
            "assessment": assessment,
            "team": assessment.team,
            "participants": participants,
            "total": participants.count(),
            "complete": participants.filter(has_submitted=True).count(),
        })

    # Teams (sorted by most recently created)
    teams = Team.objects.filter(admin=user).order_by("-created_at")

    # Reports (assessments where all participants have submitted)
    report_ready_assessments = (
        Assessment.objects
        .filter(team__admin=user)
        .annotate(incomplete_count=Count("participants", filter=Q(participants__has_submitted=False)))
        .filter(incomplete_count=0)
        .order_by("-created_at")
    )

    return render(request, "dashboard/home.html", {
        "assessments_data": assessments_data,
        "teams": teams,
        "reports": report_ready_assessments,
    })