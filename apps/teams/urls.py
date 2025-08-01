from django.urls import path
from . import views

urlpatterns = [
    path("", views.teams_overview, name="teams_overview"),
    path("delete/<int:team_id>/", views.delete_team, name="delete_team"),
    path("rename/<int:team_id>/", views.rename_team, name="rename_team"),
]