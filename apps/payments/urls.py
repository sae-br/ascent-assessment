from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("checkout/<int:assessment_id>/", views.checkout, name="checkout"),
    path("create-session/<int:assessment_id>/", views.create_checkout_session, name="create_checkout_session"),
    path("success/", views.checkout_success, name="checkout_success"),  # returns redirect to payments:success/<id> if paid
    path("success/<int:assessment_id>/", views.success, name="success"),  # the page that polls + kicks off DocRaptor
    path("report-status/<int:assessment_id>/", views.report_status, name="report_status"),  # HTMX polled partial
    path("webhook/", views.stripe_webhook_success, name="stripe_webhook"), 
]