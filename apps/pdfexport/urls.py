# from django.urls import path
# from .views import generate_final_report_pdf
#
# urlpatterns = [
#    path('pdf/<int:assessment_id>/', generate_final_report_pdf, name='generate_final_report_pdf'),
#]

from django.urls import path
from . import views

urlpatterns = [
    # start the async job
    path(
        "final-report/<int:assessment_id>/docraptor/start/",
        views.final_report_docraptor_start,
        name="final_report_docraptor_start",
    ),
    # polled by the little status page
    path(
        "docraptor/status/<str:status_id>/",
        views.docraptor_status,
        name="docraptor_status",
    ),
    # streams the finished PDF
    path(
        "docraptor/download/<str:status_id>/",
        views.docraptor_download,
        name="docraptor_download",
    ),
    # final report html page (remove once async and download version tested)
    path(
        "final-report/<int:assessment_id>/docraptor/", 
        views.generate_final_report_pdf_docraptor, 
        name="final_report_docraptor"
    ),
    # preview for simple tests (will not render like DocRaptor)  
    path(
        "final-report/<int:assessment_id>/preview/", 
        views.final_report_preview, 
        name="final_report_preview"
    ), 
]