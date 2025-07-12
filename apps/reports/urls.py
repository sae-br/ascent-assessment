from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_report, name='generate_report'),
    path('team_report/', views.review_team_report_redirect, name='review_team_report_redirect'),
    path('team_report/<int:assessment_id>/', views.review_team_report, name='review_team_report'),
]