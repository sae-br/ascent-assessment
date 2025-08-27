from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('home/', views.dashboard_home, name='home'),
    path('', views.dashboard_home, name='root'),
]