# views.py (relevant sections only)

from .models import Assessment, AssessmentParticipant, Question, Answer
from apps.teams.models import Team, TeamMember

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from datetime import datetime


@login_required
def confirm_launch(request):
    session_data = request.session.get("new_assessment")
    if not session_data:
        messages.error(request, "Missing assessment setup data.")
        return redirect("new_assessment")

    team = get_object_or_404(Team, id=session_data["team_id"], admin=request.user)
    deadline = datetime.strptime(session_data["deadline"], "%Y-%m-%d").date()

    assessment, created = Assessment.objects.get_or_create(
        team=team,
        deadline=deadline,
    )

    if created:
        for member in team.members.all():
            AssessmentParticipant.objects.create(
                assessment=assessment,
                team_member=member,
            )

    if request.method == "POST":
        for participant in assessment.participants.select_related("team_member"):
            member = participant.team_member
            send_mail(
                subject="You're invited to complete a team assessment",
                message=(
                    f"Hello {member.name},\n\nPlease complete your team assessment by visiting this link:\n\n"
                    f"http://127.0.0.1:8000/assessments/start/{member.unique_token}/\n\n"
                    f"Deadline: {assessment.deadline.strftime('%B %Y')}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.email],
                fail_silently=False,
            )
        request.session.pop("new_assessment", None)
        messages.success(request, f"Assessment for {team.name} launched!")
        return redirect("dashboard_home")

    return render(request, "assessments/confirm_launch.html", {
        "assessment": assessment,
        "members": team.members.all(),
    })


def start_assessment(request, token):
    member = get_object_or_404(TeamMember, unique_token=token)
    participant = get_object_or_404(
        AssessmentParticipant,
        team_member=member,
        assessment__deadline__gte=datetime.today(),
    )

    if participant.has_submitted:
        return render(request, "assessments/submit.html", {"member": member})

    questions = Question.objects.all()

    if request.method == "POST":
        for question in questions:
            field_name = f"question_{question.id}"
            score = request.POST.get(field_name)
            if score:
                Answer.objects.create(
                    participant=participant,
                    question=question,
                    value=int(score),
                )
        participant.has_submitted = True
        participant.save()

        # Email confirmation to the team member
        send_mail(
            subject="Thanks for submitting your assessment",
            message=f"Hi {member.name},\n\nThanks for completing your assessment. Your input has been recorded.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member.email],
            fail_silently=True,
        )

        # Email to admin
        team = member.team
        admin_user = team.admin
        total = AssessmentParticipant.objects.filter(assessment=participant.assessment).count()
        submitted = AssessmentParticipant.objects.filter(assessment=participant.assessment, has_submitted=True).count()
        send_mail(
            subject=f"{member.name} submitted their assessment",
            message=(
                f"{member.name} has completed the assessment for team '{team.name}'.\n\n"
                f"Progress: {submitted} out of {total} team members have submitted.\n"
                f"Deadline: {participant.assessment.deadline.strftime('%B %d, %Y')}\n\n"
                f"You can check the progress or review the report in your dashboard."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_user.email],
            fail_silently=True,
        )

        return render(request, "assessments/submit.html", {"member": member})

    return render(request, "assessments/start.html", {
        "member": member,
        "questions": questions,
    })