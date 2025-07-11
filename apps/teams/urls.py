from django.urls import path
from . import views

urlpatterns = [
    path('', views.team_list, name='team_list'),
    path('teams/<int:team_id>/', views.team_detail, name='team_detail'),
    path('delete/<int:team_id>/', views.delete_team, name='delete_team'),
]