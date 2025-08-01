# apps/teams/views.py

from django.shortcuts      import render, get_object_or_404, redirect
from django.urls           import reverse
from django.contrib        import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http  import require_POST

from .models   import Team, TeamMember
from .forms    import TeamForm, TeamMemberForm


@login_required
def teams_overview(request):
    user          = request.user
    teams         = user.teams.all()
    selected_team = None
    members       = None
    member_form   = None
    editing_id    = None

    # ——————————————————————————————
    # POST: create/switch/edit/delete
    # ——————————————————————————————
    if request.method == "POST":

        # 1) Create a new team
        if "create_team" in request.POST:
            form = TeamForm(request.POST)
            if form.is_valid():
                new_team       = form.save(commit=False)
                new_team.admin = user
                new_team.save()
                messages.success(request, f"Team '{new_team.name}' created.")
                return redirect(f"{reverse('teams_overview')}?team={new_team.id}")

        # 2) Switch which team is active
        if "edit_team" in request.POST:
            sel_id = request.POST.get("selected_team")
            return redirect(f"{reverse('teams_overview')}?team={sel_id}")

        # 3) Add a new member to that team
        if "add_member" in request.POST:
            sel_id      = request.POST.get("selected_team")
            team        = get_object_or_404(Team, id=sel_id, admin=user)
            member_form = TeamMemberForm(request.POST)
            if member_form.is_valid():
                new_member      = member_form.save(commit=False)
                new_member.team = team
                new_member.save()
                messages.success(request, f"Added member: {new_member.name}")
            return redirect(f"{reverse('teams_overview')}?team={team.id}")

        # 4) Edit an existing member inline
        if "edit_member" in request.POST:
            member_id = request.POST.get("member_id")
            member    = get_object_or_404(TeamMember, id=member_id, team__admin=user)
            form      = TeamMemberForm(request.POST, instance=member)
            if form.is_valid():
                form.save()
                messages.success(request, f"Updated member: {member.name}")
            return redirect(f"{reverse('teams_overview')}?team={member.team_id}")

        # 5) Delete a member
        if "delete_member" in request.POST:
            member_id = request.POST.get("member_id")
            member    = get_object_or_404(TeamMember, id=member_id, team__admin=user)
            team_id   = member.team_id
            member.delete()
            messages.success(request, "Deleted member.")
            return redirect(f"{reverse('teams_overview')}?team={team_id}")

    # ——————————————————————————————
    # GET: check for ?team=<id>
    # ——————————————————————————————
    team_id = request.GET.get("team")
    if team_id:
        selected_team = get_object_or_404(Team, id=team_id, admin=user)
        members       = selected_team.members.all()
        member_form   = TeamMemberForm()
    
    editing_id = request.GET.get("edit")  # will be a string

    # form to create a new team
    team_form = TeamForm()

    return render(request, "teams/overview.html", {
        "teams":         teams,
        "team_form":     team_form,
        "selected_team": selected_team,
        "members":       members,
        "member_form":   member_form,
        "editing_id":    editing_id,
    })


@require_POST
@login_required
def delete_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, admin=request.user)
    team.delete()
    messages.success(request, "Team deleted.")
    return redirect("teams_overview")


@login_required
def rename_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, admin=request.user)
    if request.method == "POST":
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, f"Team renamed to “{team.name}.”")
            return redirect("teams_overview")
    else:
        form = TeamForm(instance=team)

    return render(request, "teams/rename.html", {
        "team": team,
        "form": form,
    })