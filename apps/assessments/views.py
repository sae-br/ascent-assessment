from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Prefetch
from django.utils.timezone import now
from .models import TeamMember, Question, Answer, Assessment, AssessmentParticipant
from apps.teams.models import Team
from datetime import datetime

# main assessment page

@login_required
def assessments_overview(request):
    # Step 1: Get all teams managed by the user
    teams = Team.objects.filter(admin=request.user)

    # Step 2: Get all assessments for those teams
    assessments = Assessment.objects.filter(team__in=teams).order_by('-deadline')

    selected_assessment_id = request.GET.get("assessment")
    selected_assessment = None
    participants = []

    if selected_assessment_id:
        selected_assessment = assessments.filter(id=selected_assessment_id).first()
    elif assessments.exists():
        selected_assessment = assessments.first()

    if selected_assessment:
        participants = AssessmentParticipant.objects.filter(
            assessment=selected_assessment
        ).select_related("team_member").order_by("team_member__name")

    return render(request, "assessments/overview.html", {
        "teams": teams,
        "assessments": assessments,
        "selected_assessment": selected_assessment,
        "participants": participants
    })


# initializing and monitoring new assessment

@login_required
def new_assessment(request):
    teams = Team.objects.filter(admin=request.user)
    selected_team = None

    if request.method == "POST":
        team_id = request.POST.get("team")
        deadline_str = request.POST.get("deadline")
        new_team_name = request.POST.get("new_team_name")

        if new_team_name:
            # Create new team if name provided
            selected_team = Team.objects.create(name=new_team_name, admin=request.user)
            team_id = selected_team.id  # Treat new team as selected
        elif team_id:
            selected_team = Team.objects.filter(id=team_id, admin=request.user).first()

        if not selected_team or not deadline_str:
            messages.error(request, "Please select a team and a deadline.")
        else:
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()

                request.session['new_assessment'] = {
                    "team_id": team_id,
                    "deadline": deadline_str
                }
                return redirect("confirm_team")

            except ValueError:
                messages.error(request, "Invalid deadline format.")

    return render(request, "assessments/new_assessment.html", {
        "teams": teams,
        "selected_team": selected_team,
    })

@login_required
@require_http_methods(["GET", "POST"])
def confirm_team(request):
    print("🟡 Entered confirm_team view")
    session_data = request.session.get("new_assessment")

    if not session_data:
        print("⚠️ No session data found in session")
        messages.error(request, "Assessment setup data missing.")
        return redirect("new_assessment")

    team = get_object_or_404(Team, id=session_data["team_id"], admin=request.user)
    try:
        deadline = datetime.strptime(session_data["deadline"], "%Y-%m-%d").date()
    except Exception:
        deadline = None

    if request.method == "POST":
        print("🔵 POST request received")
        print("🔘 POST keys:", list(request.POST.keys()))

        if "add_member" in request.POST:
            print("➕ Adding member...")
            name = request.POST.get("new_member_name")
            email = request.POST.get("new_member_email")
            if name and email:
                TeamMember.objects.create(team=team, name=name, email=email)
                messages.success(request, f"Added {name} to the team.")
            else:
                messages.error(request, "Name and email are required to add a new member.")

        elif "edit_member" in request.POST:
            print("✏️ Editing member...")
            member_id = request.POST.get("member_id")
            name = request.POST.get("edit_member_name")
            email = request.POST.get("edit_member_email")
            if member_id and name and email:
                member = get_object_or_404(TeamMember, id=member_id, team=team)
                member.name = name
                member.email = email
                member.save()
                messages.success(request, f"Updated member {name}.")
            else:
                messages.error(request, "All fields are required to edit a member.")

        elif "delete_member" in request.POST:
            print("🗑️ Deleting member...")
            member_id = request.POST.get("member_id")
            if member_id:
                member = get_object_or_404(TeamMember, id=member_id, team=team)
                member.delete()
                messages.success(request, "Team member deleted.")

        elif "confirm_team_done" in request.POST:
            print("✅ Confirm team done — redirecting to confirm_launch")
            return redirect("confirm_launch")

        else:
            print("❓ Unknown POST action:", request.POST)
            messages.error(request, "Unknown action submitted.")

    return render(request, "assessments/confirm_team.html", {
        "team": team,
        "deadline": deadline,
    })

@login_required
def confirm_launch(request):
    print("🟡 Entered confirm_launch view")
    session_data = request.session.get("new_assessment")
    print("📦 session_data:", session_data)

    if not session_data:
        print("❌ No session data — redirecting to new_assessment")
        messages.error(request, "Missing assessment setup data.")
        return redirect("new_assessment")

    team = get_object_or_404(Team, id=session_data["team_id"])
    deadline = datetime.strptime(session_data["deadline"], "%Y-%m-%d").date()

    # Create Assessment object but don't send email yet
    assessment, created = Assessment.objects.get_or_create(
        team=team,
        deadline=deadline,
    )
    for member in team.members.all():
        AssessmentParticipant.objects.get_or_create(
            assessment=assessment,
            team_member=member
        )

        if request.method == "POST":
            for member in team.members.all():
                participant = AssessmentParticipant.objects.get(team_member=member, assessment=assessment)
                send_mail(
                    subject="You're invited to complete a team assessment",
                    message=(
                        f"Hello {member.name},\n\n"
                        f"Please complete your team assessment by visiting this link:\n\n"
                        f"http://127.0.0.1:8000/assessments/start/{participant.token}/\n\n"
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
        "members": team.members.all()
    })

# respondent submission

def start_assessment(request, token):
    participant = get_object_or_404(AssessmentParticipant, token=token)
    member = participant.team_member
    assessment = participant.assessment

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
                    value=int(score)
                )
        participant.has_submitted = True
        participant.save()
        
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
        submitted_count = assessment.participants.filter(has_submitted=True).count()
        total_count = assessment.participants.count()
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


@login_required
@require_http_methods(["POST"])
def resend_invite(request, participant_id):
    participant = get_object_or_404(AssessmentParticipant, id=participant_id)
    member = participant.team_member
    assessment = participant.assessment

    if member.team.admin != request.user:
        messages.error(request, "You don't have permission to do that.")
        return redirect("assessments_home")

    send_mail(
        subject="You're invited to complete a team assessment",
        message=(
            f"Hello {member.name},\n\n"
            f"Please complete your team assessment by visiting this link:\n\n"
            f"http://127.0.0.1:8000/assessments/start/{participant.token}/\n\n"
            f"Deadline: {assessment.deadline.strftime('%B %Y')}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member.email],
        fail_silently=False,
    )

    messages.success(request, f"Resent invite to {member.name}.")
    return redirect(f"{reverse('assessments_home')}?assessment={assessment.id}")