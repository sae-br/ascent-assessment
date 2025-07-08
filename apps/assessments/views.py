from django.shortcuts import render, get_object_or_404, redirect
from .models import TeamMember, Question, Answer, Assessment
from django.contrib import messages
from django.urls import reverse
from apps.teams.models import Team
from datetime import datetime
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required

# initializing and monitoring

@login_required
def new_assessment(request):
    teams = Team.objects.all()

    if request.method == "POST":
        team_id = request.POST.get("team")
        deadline_str = request.POST.get("deadline")  # e.g. '2025-08-01'

        if not team_id or not deadline_str:
            messages.error(request, "Please select a team and a deadline.")
        else:
            try:
                # Validate date format
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()

                request.session['new_assessment'] = {
                    "team_id": team_id,
                    "deadline": deadline_str
                }

                return redirect("confirm_launch")

            except ValueError:
                messages.error(request, "Invalid deadline format. Please use the date picker.")

    return render(request, "assessments/new_assessment.html", {
        "teams": teams
    })

@login_required
def confirm_launch(request):
    session_data = request.session.get("new_assessment")
    if not session_data:
        messages.error(request, "Missing assessment setup data.")
        return redirect("new_assessment")

    team = get_object_or_404(Team, id=session_data["team_id"])
    deadline = datetime.strptime(session_data["deadline"], "%Y-%m-%d").date()

    # Create Assessment object but don't send email yet
    assessment, created = Assessment.objects.get_or_create(
        team=team,
        deadline=deadline,
    )

    if request.method == "POST":
        for member in team.members.all():
            send_mail(
                subject="You're invited to complete a team assessment",
                message=f"Hello {member.name},\n\nPlease complete your team assessment by visiting this link:\n\nhttp://127.0.0.1:8000/assessments/start/{member.unique_token}/\n\nDeadline: {assessment.deadline.strftime('%B %Y')}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.email],
                fail_silently=False,
            )
        request.session.pop("new_assessment", None)
        messages.success(request, f"Assessment for {team.name} launched!")
        return redirect("dashboard_home")

    return render(request, "assessments/confirm_launch.html", {
        "assessment": assessment,
        "members": team.members.all()
    })

# respondent submission

def start_assessment(request, token):
    member = get_object_or_404(TeamMember, unique_token=token)

    if member.has_submitted:
        return render(request, "assessments/submit.html", {"member": member})

    questions = Question.objects.all()

    if request.method == "POST":
        for question in questions:
            field_name = f"question_{question.id}"
            score = request.POST.get(field_name)
            if score:
                Answer.objects.create(
                    team_member=member,
                    question=question,
                    value=int(score)
                )
        member.has_submitted = True
        member.save()
        
        # Email confirmation to the team member
        send_mail(
            subject="Thanks for submitting your assessment",
            message=f"Hi {member.name},\n\nThanks for completing your assessment. Your input has been recorded.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member.email],
            fail_silently=True
        )
        
        # Email notification to the client user
        team = member.team
        admin_user = team.admin
        submitted_count = team.members.filter(has_submitted=True).count()
        total_count = team.members.count()
        # Find the latest assessment by deadline (in case multiple exist)
        assessment = team.assessments.order_by('-deadline').first()
        send_mail(
            subject=f"{member.name} submitted their assessment",
            message=(
                f"{member.name} has completed the assessment for team '{team.name}'.\n\n"
                f"Progress: {submitted_count} out of {total_count} team members have submitted.\n"
                f"Deadline: {assessment.deadline.strftime('%B %d, %Y') if assessment else 'N/A'}\n\n"
                f"You can check the progress or review the report in your dashboard."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_user.email],
            fail_silently=True
        )
        return render(request, "assessments/submit.html", {"member": member})

    return render(request, "assessments/start.html", {
        "member": member,
        "questions": questions
    })

# possibly don't need this or its URL pattern
def submit_assessment(request):
    return render(request, 'assessments/submit.html')