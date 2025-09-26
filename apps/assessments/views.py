from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from .models import TeamMember, Question, Answer, Assessment, AssessmentParticipant
from apps.teams.models import Team
from datetime import datetime
from anymail.message import AnymailMessage

import logging
logger = logging.getLogger(__name__)


# main assessment overview page
@login_required
def assessments_overview(request):
    user = request.user
    teams = Team.objects.filter(admin=user)

    assessments = (
        Assessment.objects
        .filter(team__in=teams, launched_at__isnull=False)
        .select_related("team", "final_report")
        .order_by("-deadline")
    )

    selected_assessment_id = request.GET.get("assessment")
    selected_assessment = (
        assessments.filter(id=selected_assessment_id).first()
        if selected_assessment_id else assessments.first()
    )

    if not selected_assessment:
        logger.debug("assessments_overview: no assessments for user", extra={"user_id": user.id})
        participants = []
    else:
        participants = (
            AssessmentParticipant.objects
            .filter(assessment=selected_assessment)
            .select_related("team_member")
            .order_by("team_member__name")
        )

    return render(request, "assessments/overview.html", {
        "teams": teams,
        "assessments": assessments,
        "selected_assessment": selected_assessment,
        "participants": participants,
    })


# initializing and monitoring new assessment
@login_required
def new_assessment(request):
    user = request.user
    teams = Team.objects.filter(admin=request.user)
    selected_team = None

    # 1) If coming from Step 3 with ?assessment=<id>, prefill and seed session
    assessment_id = request.GET.get("assessment")
    if assessment_id:
        existing = (
            Assessment.objects
            .filter(id=assessment_id, team__admin=user)
            .select_related("team")
            .first()
        )
        if existing:
            selected_team = existing.team
            deadline_str = existing.deadline.strftime("%Y-%m-%d")
            request.session["new_assessment"] = {
                "team_id": existing.team_id,
                "deadline": deadline_str,
            }

    # 2) Or fall back to session if present
    session_data = request.session.get("new_assessment")
    if not selected_team and session_data:
        pre_team_id = session_data.get("team_id")
        if pre_team_id:
            selected_team = Team.objects.filter(id=pre_team_id, admin=user).first()

    if request.method == "POST":
        team_id = request.POST.get("team")
        deadline_str = request.POST.get("deadline")
        new_team_name = request.POST.get("new_team_name")

        if new_team_name:
            selected_team = Team.objects.create(name=new_team_name, admin=request.user)
            team_id = selected_team.id  # Treat new team as selected
            logger.info("team.created", extra={"user_id": user.id, "team_id": team_id})
        elif team_id:
            selected_team = Team.objects.filter(id=team_id, admin=request.user).first()
            if selected_team:
                logger.info("team.selected", extra={"user_id": user.id, 
                                                    "team_id": selected_team.id})

        if not selected_team or not deadline_str:
            logger.warning("new_assessment: missing team or deadline", 
                           extra={"user_id": user.id})
            messages.error(request, "Please select a team and a deadline.")
        else:
            try:
                _ = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                request.session['new_assessment'] = {
                    "team_id": team_id,
                    "deadline": deadline_str
                }
                logger.debug("new_assessment: session primed", 
                             extra={"user_id": user.id, "team_id": team_id})
                return redirect("assessments:confirm_team")

            except ValueError:
                logger.warning("new_assessment: invalid deadline format", 
                               extra={"user_id": user.id, "deadline": deadline_str})
                messages.error(request, "Invalid deadline format.")

    return render(request, "assessments/new_assessment.html", {
        "teams": teams,
        "selected_team": selected_team,
        "initial_team_id": selected_team.id if selected_team else None,
        "initial_deadline": (request.session.get("new_assessment") or {}).get("deadline"),
    })

@login_required
@require_http_methods(["GET", "POST"])
def confirm_team(request):
    user = request.user
    logger.debug("confirm_team: entered", extra={"user_id": user.id})
    if "back_to_new" in request.POST:
        return redirect("assessments:new_assessment")
    session_data = request.session.get("new_assessment")

    if not session_data:
        logger.warning("confirm_team: missing session data", extra={"user_id": user.id})
        messages.error(request, "Assessment setup data missing.")
        return redirect("assessments:new_assessment")

    team = get_object_or_404(Team, id=session_data["team_id"], admin=request.user)
    try:
        deadline = datetime.strptime(session_data["deadline"], "%Y-%m-%d").date()
    except Exception:
        deadline = None

    if request.method == "POST":
        logger.debug("confirm_team: POST received", 
                     extra={"user_id": user.id, "team_id": team.id})

        if "add_member" in request.POST:
            name = request.POST.get("new_member_name")
            email = request.POST.get("new_member_email")
            if name and email:
                member = TeamMember.objects.create(team=team, name=name, email=email)
                logger.info("member.added", extra={"user_id": user.id, 
                                                   "team_id": team.id, 
                                                   "member_id": member.id})
                messages.success(request, f"Added {name} to the team.")
            else:
                logger.warning("member.add: missing fields", 
                               extra={"user_id": user.id, "team_id": team.id})
                messages.error(request, "Name and email are required to add a new member.")

        elif "edit_member" in request.POST:
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
                logger.warning("member.edit: missing fields", 
                               extra={"user_id": user.id, "team_id": team.id})
                messages.error(request, "All fields are required to edit a member.")

        elif "delete_member" in request.POST:
            member_id = request.POST.get("member_id")
            if member_id:
                member = get_object_or_404(TeamMember, id=member_id, team=team)
                member.delete()
                logger.info("member.deleted", 
                            extra={"user_id": user.id, 
                                   "team_id": team.id, 
                                   "member_id": member_id})
                messages.success(request, "Team member deleted.")

        elif "confirm_team_done" in request.POST:
            logger.info("confirm_team: proceed to confirm_launch", 
                        extra={"user_id": user.id, "team_id": team.id})
            return redirect("assessments:confirm_launch")

        else:
            logger.warning("confirm_team: unknown POST action", 
                           extra={"user_id": user.id, "keys": list(request.POST.keys())})
            messages.error(request, "Unknown action submitted.")

    return render(request, "assessments/confirm_team.html", {
        "team": team,
        "deadline": deadline,
    })

@login_required
def confirm_launch(request):
    user = request.user
    session_data = request.session.get("new_assessment")
    if not session_data:
        messages.error(request, "Missing assessment setup data.")
        return redirect("assessments:new_assessment")

    team = get_object_or_404(Team, id=session_data["team_id"], admin=user)
    deadline = datetime.strptime(session_data["deadline"], "%Y-%m-%d").date()

    # IMPORTANT: no database writes here on GET — just show a preview card
    if request.method == "POST":
        if "edit_basics" in request.POST:
            messages.info(request, "You can adjust the basics and continue.")
            return redirect("assessments:new_assessment")

        if "edit_team_members" in request.POST:
            messages.info(request, "You can update team members and continue.")
            return redirect("assessments:confirm_team")

        if "launch_assessment" in request.POST:
            # Create the real Assessment now
            assessment = Assessment.objects.create(
                team=team,
                deadline=deadline,
                launched_at=timezone.now(),
            )

            # Seed participants from current team members
            for m in team.members.all():
                AssessmentParticipant.objects.create(assessment=assessment, team_member=m)

            # Send invites (unchanged from your code, just swap in the new `assessment`)
            sent = failed = 0
            for m in team.members.all():
                participant = AssessmentParticipant.objects.get(team_member=m, assessment=assessment)
                invite_url = request.build_absolute_uri(
                    reverse("assessments:start_assessment", args=[participant.token])
                )
                try:
                    msg = AnymailMessage(from_email=settings.DEFAULT_FROM_EMAIL, to=[m.email])
                    msg.template_id = "assessment-invite"
                    msg.merge_global_data = {
                        "member_name": m.name,
                        "team_name": team.name,
                        "invite_url": invite_url,
                        "deadline_month_day_year": deadline.strftime("%B %d, %Y"),
                        "currentyear": timezone.now().year,
                    }
                    msg.tags = ["assessment-invite"]
                    msg.metadata = {
                        "assessment_id": str(assessment.id),
                        "team_id": str(team.id),
                        "template": "assessment-invite",
                    }
                    msg.send()
                    sent += 1
                    participant.last_invited_at = timezone.now()
                    participant.save(update_fields=["last_invited_at"])
                except Exception:
                    failed += 1
                    logger.exception("invite.send_failed", extra={
                        "user_id": user.id, "assessment_id": assessment.id, "member_id": m.id
                    })

            logger.info("invite.batch_complete", extra={
                "user_id": user.id, "assessment_id": assessment.id, "sent": sent, "failed": failed
            })
            request.session.pop("new_assessment", None)
            messages.success(request, f"Assessment for {team.name} launched!")
            return redirect("dashboard:home")

    # GET render — preview only
    return render(request, "assessments/confirm_launch.html", {
        "assessment_preview": {"team_name": team.name, "deadline": deadline},
        "members": team.members.all(),
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
        
        # Email confirmation to the team member respondent
        try:
            msg_thanks = AnymailMessage(
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[member.email],
            )
            msg_thanks.template_id = "assessment-thanks"  # Mailgun template name/ID
            msg_thanks.merge_global_data = {
                "member_name": member.name,
                "team_name": member.team.name,
                "currentyear": datetime.datetime.now().year,
            }
            msg_thanks.tags = ["assessment-thanks"]
            msg_thanks.metadata = {
                "assessment_id": str(assessment.id),
                "team_id": str(member.team.id),
                "participant_id": str(participant.id),
                "template": "assessment-thanks",
            }
            msg_thanks.send()
        except Exception:
            logger.exception("start_assessment: member_thanks_failed", 
                             extra={"participant_id": participant.id, 
                                    "assessment_id": assessment.id})
        
        # Email notification to the user administrating assessment
        team = member.team
        admin_user = team.admin
        submitted_count = assessment.participants.filter(has_submitted=True).count()
        total_count = assessment.participants.count()
        try:
            msg_admin = AnymailMessage(
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin_user.email],
            )
            msg_admin.template_id = "assessment-admin-submitted"  # Mailgun template name/ID
            msg_admin.merge_global_data = {
                "admin_name": getattr(admin_user, "first_name", "") or admin_user.email,
                "member_name": member.name,
                "team_name": team.name,
                "submitted_count": str(submitted_count),
                "total_count": str(total_count),
                "deadline_month_day_year": assessment.deadline.strftime("%B %d, %Y"),
                "currentyear": datetime.datetime.now().year,
            }
            msg_admin.tags = ["assessment-admin-submitted"]
            msg_admin.metadata = {
                "assessment_id": str(assessment.id),
                "team_id": str(team.id),
                "template": "assessment-admin-submitted",
            }
            msg_admin.send()
        except Exception:
            logger.exception("start_assessment: admin_notify_failed", 
                             extra={"participant_id": participant.id, 
                                    "assessment_id": assessment.id, 
                                    "admin_id": admin_user.id})
        return render(request, "assessments/submit.html", {"member": member})

    return render(request, "assessments/start.html", {
        "member": member,
        "questions": questions
    })


@login_required
@require_http_methods(["POST"])
def resend_invite(request, participant_id):
    participant = get_object_or_404(
        AssessmentParticipant,
        id=participant_id,
        assessment__team__admin=request.user
    )
    member = participant.team_member
    assessment = participant.assessment

    # Permission check (defense in depth)
    if member.team.admin != request.user:
        if request.headers.get("HX-Request"):
            return HttpResponse("Permission denied.", status=403)
        messages.error(request, "You don't have permission to do that.")
        return redirect("assessments:assessments_overview")

    invite_url = request.build_absolute_uri(
        reverse("assessments:start_assessment", args=[participant.token])
    )

    try:
        msg = AnymailMessage(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[member.email],
        )
        msg.template_id = "assessment-invite"
        msg.merge_global_data = {
            "member_name": member.name,
            "team_name": member.team.name,
            "invite_url": invite_url,
            "deadline_month_day_year": assessment.deadline.strftime("%B %d, %Y"),
        }
        msg.tags = ["assessment-invite", "resend"]
        msg.metadata = {
            "assessment_id": str(assessment.id),
            "team_id": str(member.team.id),
            "participant_id": str(participant.id),
            "template": "assessment-invite",
            "resend": "true",
        }
        msg.send()
        # Stamp the participant to show on the table
        now = timezone.now()
        participant.last_invited_at = now
        participant.save(update_fields=["last_invited_at"])

        # HTMX response: return fragment HTML that replaces the form
        if request.headers.get("HX-Request"):
            html = render_to_string(
                "assessments/_resend_invite_fragment.html",
                {"participant": participant, "assessment": assessment},
                request=request,
            )
            return HttpResponse(html)

        messages.success(request, f"Resent invite to {member.name}.")

    except Exception:
        logger.exception(
            "resend_invite: send_failed",
            extra={
                "user_id": request.user.id,
                "assessment_id": assessment.id,
                "participant_id": participant.id,
            },
        )
        if request.headers.get("HX-Request"):
            return HttpResponse("Send failed.", status=500)
        messages.error(request, "Could not send invite. Please try again later.")
    
    return redirect(f"{reverse('assessments:assessments_overview')}?assessment={assessment.id}")



# Delete an assessment view
@login_required
@require_http_methods(["POST"])
def delete_assessment(request, assessment_id: int):
    # Delete an assessment the current user owns, then return to overview
    assessment = get_object_or_404(
        Assessment,
        id=assessment_id,
        team__admin=request.user,
    )

    team_name = assessment.team.name
    deadline_str = assessment.deadline.strftime("%B %Y") if assessment.deadline else ""

    # Deleting the Assessment should cascade to participants/answers via models
    assessment.delete()

    logger.info(
        "assessment.deleted",
        extra={
            "user_id": request.user.id,
            "team": team_name,
            "deadline": deadline_str,
        },
    )
    messages.success(request, f"Deleted assessment for {team_name} ({deadline_str}).")
    return redirect("assessments:assessments_overview")
