from django.urls import path
from . import views

app_name = "teams"

urlpatterns = [
    path("overview/", views.teams_overview, name="teams_overview"),
    path("delete/<int:team_id>/", views.delete_team, name="delete_team"),
    path("rename/<int:team_id>/", views.rename_team, name="rename_team"),
    # HTMX fragment endpoint (GET returns table; POST mutates + returns table)
    path("members/<int:team_id>/table/", views.member_table, name="member_table"),
]