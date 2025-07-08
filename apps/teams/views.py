from django.shortcuts import render

def team_list(request):
    return render(request, 'teams/list.html')

def team_detail(request):
    return render(request, 'teams/details.html')