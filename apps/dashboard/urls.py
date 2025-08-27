from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/home', views.dashboard_home, name='dashboard_home'),
]