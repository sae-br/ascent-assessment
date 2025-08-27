from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("overview/", views.reports_overview, name="reports_overview"),
    path("download/<int:report_id>/", views.download_report, name="download_report"),
]