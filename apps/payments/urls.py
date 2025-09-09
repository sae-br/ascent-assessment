from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("checkout/<int:assessment_id>/", views.checkout, name="checkout"),
    path("return/", views.payment_return, name="payment_return"),
    path("success/<int:assessment_id>/", views.success, name="success"),
    path("status/<int:assessment_id>/", views.report_status, name="report_status"),
    path("webhook/", views.stripe_webhook_success, name="stripe_webhook_success"),
]