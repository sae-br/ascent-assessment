from django.urls import path
from . import views

urlpatterns = [
    path('reports/overview/', views.reports_overview, name='reports_overview'),
    path('reports/download/<int:report_id>/', views.download_report, name='download_report'),
    path('generate/', views.generate_report, name='generate_report'),
]