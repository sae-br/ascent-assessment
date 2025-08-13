# from django.urls import path
# from .views import generate_final_report_pdf
#
# urlpatterns = [
#    path('pdf/<int:assessment_id>/', generate_final_report_pdf, name='generate_final_report_pdf'),
#]

from django.urls import path
from . import views

urlpatterns = [
    path("final-report/<int:assessment_id>/docraptor/", views.generate_final_report_pdf_docraptor, name="final_report_docraptor"),
]