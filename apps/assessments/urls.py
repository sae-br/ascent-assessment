from django.urls import path
from . import views

app_name = "assessments"

urlpatterns = [
    path('overview/', views.assessments_overview, name='assessments_overview'),
    path('new/', views.new_assessment, name='new_assessment'),
    path('confirm_team/', views.confirm_team, name='confirm_team'),
    path('confirm/', views.confirm_launch, name='confirm_launch'),
    path('resend/<int:participant_id>/', views.resend_invite, name='resend_invite'),
    path('start/<uuid:token>/', views.start_assessment, name='start_assessment'),
    path("delete/<int:assessment_id>/", views.delete_assessment, name="delete_assessment"),
]