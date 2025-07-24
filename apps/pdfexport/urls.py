from django.urls import path
from .views import generate_final_report_pdf

urlpatterns = [
    path('pdf/<int:assessment_id>/', generate_final_report_pdf, name='generate_final_report_pdf'),
]