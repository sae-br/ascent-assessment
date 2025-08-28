from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .models import Team, TeamMember
from .forms import TeamForm, TeamMemberForm

import logging
logger = logging.getLogger(__name__)


@login_required
def teams_overview(request):
    user = request.user
    teams = user.teams.all()
    selected_team = None
    members = None
    member_form = None
    editing_id = None

    # ——————————————————————————————
    # POST: create/switch/edit/delete
    # ——————————————————————————————
    if request.method == "POST":
        logger.debug("teams_overview POST", extra={"post_keys": list(request.POST.keys())})

        # 1) Create a new team
        if "create_team" in request.POST:
            form = TeamForm(request.POST)
            if form.is_valid():
                new_team = form.save(commit=False)
                new_team.admin = user
                new_team.save()
                messages.success(request, f"Team '{new_team.name}' created.")
                return redirect(f"{reverse('teams:teams_overview')}?team={new_team.id}")

        # 2) Switch which team is active
        if "edit_team" in request.POST:
            sel_id = request.POST.get("selected_team")
            return redirect(f"{reverse('teams:teams_overview')}?team={sel_id}")

        # 3) Add a new member to that team
        if "add_member" in request.POST:
            sel_id = request.POST.get("selected_team") or request.GET.get("team")
            team = get_object_or_404(Team, id=sel_id, admin=user)
            # Normalize form fields coming from either the include or teams page
            data = request.POST.copy()
            if not data.get("name"):
                data["name"] = request.POST.get("new_member_name", "")
            if not data.get("email"):
                data["email"] = request.POST.get("new_member_email", "")

            member_form = TeamMemberForm(data)
            if member_form.is_valid():
                new_member = member_form.save(commit=False)
                new_member.team = team
                new_member.save()
                messages.success(request, f"Added member: {new_member.name}")
            else:
                logger.warning("add_member invalid", extra={"errors": member_form.errors.as_json()})
                messages.error(request, "Please provide a valid name and email.")
            return redirect(f"{reverse('teams:teams_overview')}?team={team.id}")

        # 4) Edit an existing member inline
        if "edit_member" in request.POST:
            member_id = request.POST.get("member_id")
            member = get_object_or_404(TeamMember, id=member_id, team__admin=user)
            # Normalize edit field names from partials
            data = request.POST.copy()
            if not data.get("name"):
                data["name"] = request.POST.get("edit_member_name", member.name)
            if not data.get("email"):
                data["email"] = request.POST.get("edit_member_email", member.email)

            form = TeamMemberForm(data, instance=member)
            if form.is_valid():
                form.save()
                messages.success(request, f"Updated member: {member.name}")
            else:
                logger.warning("edit_member invalid", extra={"errors": form.errors.as_json(), "member_id": member_id})
                messages.error(request, "Could not update member. Please check the fields.")
            return redirect(f"{reverse('teams:teams_overview')}?team={member.team_id}")

        # 5) Delete a member
        if "delete_member" in request.POST:
            member_id = request.POST.get("member_id")
            member = get_object_or_404(TeamMember, id=member_id, team__admin=user)
            team_id = member.team_id
            member.delete()
            messages.success(request, "Deleted member.")
            return redirect(f"{reverse('teams:teams_overview')}?team={team_id}")


    # ——————————————————————————————
    # GET: check for ?team=<id>
    # ——————————————————————————————
    team_id = request.GET.get("team")
    if team_id:
        selected_team = get_object_or_404(Team, id=team_id, admin=user)
    else:
        selected_team = teams.first()  # optional: default to first team

    if selected_team:
        members = selected_team.members.all().order_by("name")
        member_form = TeamMemberForm()
    
    editing_id = request.GET.get("edit")  # will be a string

    # form to create a new team
    team_form = TeamForm()

    return render(request, "teams/overview.html", {
        "teams": teams,
        "team_form": team_form,
        "selected_team": selected_team,
        "members": members,
        "member_form": member_form,
        "editing_id": editing_id,
    })


@require_POST
@login_required
def delete_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, admin=request.user)
    team.delete()
    messages.success(request, "Team deleted.")
    return redirect("teams:teams_overview")


@require_POST
@login_required
def rename_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, admin=request.user)
    form = TeamForm(request.POST, instance=team)
    if form.is_valid():
        form.save()
        messages.success(request, f"Team renamed to “{team.name}.”")
    else:
        messages.error(request, "Please provide a valid team name.")
    return redirect(f"{reverse('teams:teams_overview')}?team={team.id}")