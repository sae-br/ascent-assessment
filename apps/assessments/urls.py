from django.urls import path
from . import views

urlpatterns = [
    path('start/<uuid:token>/', views.start_assessment, name='start_assessment'),
    path('submit/', views.submit_assessment, name='submit_assessment'),
    path('assessments/new/', views.new_assessment, name='new_assessment'),
    path('assessments/confirm/', views.confirm_launch, name='confirm_launch'),
]