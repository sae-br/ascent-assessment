from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Team, TeamMember
from .forms import TeamForm, TeamMemberForm

# Delete a team
@require_POST
def delete_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, admin=request.user)
    team.delete()
    messages.success(request, "Team deleted.")
    return redirect('team_list')

# Manage Teams
@login_required
def team_list(request):
    user_teams = request.user.teams.all()
    form = TeamForm()

    if request.method == "POST":
        if "create_team" in request.POST:
            form = TeamForm(request.POST)
            if form.is_valid():
                new_team = form.save(commit=False)
                new_team.admin = request.user
                new_team.save()
                messages.success(request, f"Team '{new_team.name}' created.")
                return redirect('team_detail', team_id=new_team.id)

        elif "delete_team" in request.POST:
            team_id = request.POST.get("selected_team")
            team = get_object_or_404(Team, id=team_id, admin=request.user)
            team.delete()
            messages.success(request, f"Team '{team.name}' deleted.")
            return redirect('team_list')

        elif "edit_team" in request.POST:
            team_id = request.POST.get("selected_team")
            return redirect('team_detail', team_id=team_id)

    return render(request, "teams/list.html", {
        "teams": user_teams,
        "form": form
    })

# Manage Team Members
@login_required
def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id, admin=request.user)
    members = team.members.all()
    teams = request.user.teams.all()  # For dropdown
    member_form = TeamMemberForm()

    if request.method == "POST":
        if "add_member" in request.POST:
            member_form = TeamMemberForm(request.POST)
            if member_form.is_valid():
                new_member = member_form.save(commit=False)
                new_member.team = team
                new_member.save()
                messages.success(request, f"Added member: {new_member.name}")
                return redirect("team_detail", team_id=team.id)

        elif "delete_members" in request.POST:
            ids_to_delete = request.POST.getlist("selected_members")
            TeamMember.objects.filter(id__in=ids_to_delete, team=team).delete()
            messages.success(request, "Selected member(s) deleted.")
            return redirect("team_detail", team_id=team.id)

        elif "change_team" in request.POST:
            selected_id = request.POST.get("selected_team")
            return redirect("team_detail", team_id=selected_id)

    return render(request, "teams/detail.html", {
        "team": team,
        "teams": teams,
        "members": members,
        "member_form": member_form,
    })