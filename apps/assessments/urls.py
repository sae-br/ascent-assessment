from django.urls import path
from . import views

urlpatterns = [
    path('start/<uuid:token>/', views.start_assessment, name='start_assessment'),
    path('assessments/overview/', views.assessments_overview, name='assessments_overview'),
    path('assessments/new/', views.new_assessment, name='new_assessment'),
    path('assessments/confirm_team/', views.confirm_team, name='confirm_team'),
    path('assessments/confirm/', views.confirm_launch, name='confirm_launch'),
    path('resend/<int:participant_id>/', views.resend_invite, name='resend_invite'),
]