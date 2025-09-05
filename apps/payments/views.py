# apps/payments/views.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import stripe

from apps.assessments.models import Assessment
from apps.pdfexport.models import FinalReport

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
@require_POST
def create_checkout_session(request, assessment_id: int):
    """
    Creates a Stripe Checkout Session for the one-time Final Report purchase,
    then 303-redirects the user to Stripe's hosted Checkout page.
    """
    assessment = get_object_or_404(
        Assessment,
        id=assessment_id,
        team__admin=request.user
    )

    # If a report already exists (uploaded to S3), don't sell again.
    if FinalReport.objects.filter(assessment=assessment, s3_key__isnull=False).exists():
        messages.info(request, "A final report already exists for this assessment.")
        return redirect(f"{reverse('assessments:assessments_overview')}?assessment={assessment.id}")

    # Build URLs
    success_url = request.build_absolute_uri(
        reverse("payments:checkout_success")
    ) + "?session_id={CHECKOUT_SESSION_ID}"

    cancel_url = request.build_absolute_uri(
        f"{reverse('assessments:assessments_overview')}?assessment={assessment.id}"
    )

    # Create the Checkout Session
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            # Use a Price you created in Stripe and expose via env
            "price": settings.STRIPE_PRICE_FINAL_REPORT,
            "quantity": 1,
        }],
        customer_email=request.user.email or None,
        allow_promotion_codes=True,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "assessment_id": str(assessment.id),
            "user_id": str(request.user.id),
        },
    )

    # 303 redirect is Stripe's recommendation
    return redirect(session.url, code=303)


@login_required
def checkout_success(request):
    """
    Handles the return from Stripe after a successful payment.
    We fetch the session to confirm it's paid and grab assessment_id
    from metadata, then hand off to our existing DocRaptor starter view.
    """
    session_id = request.GET.get("session_id")
    if not session_id:
        return HttpResponseBadRequest("Missing session_id")

    session = stripe.checkout.Session.retrieve(session_id)

    # Sanity check: only proceed on paid sessions
    if session.get("payment_status") != "paid":
        messages.error(request, "Payment not completed.")
        return redirect("assessments:assessments_overview")

    assessment_id = (session.get("metadata") or {}).get("assessment_id")
    if not assessment_id:
        messages.error(request, "Missing assessment reference.")
        return redirect("assessments:assessments_overview")

    # If the report is already present (user reloaded), skip straight back
    if FinalReport.objects.filter(assessment_id=assessment_id, s3_key__isnull=False).exists():
        messages.success(request, "Payment received. Your report is ready to download.")
        return redirect(f"{reverse('assessments:assessments_overview')}?assessment={assessment_id}")

    # Hand off to DocRaptor async starter (it returns the polling page)
    return redirect("final_report_docraptor_start", assessment_id=assessment_id)


@csrf_exempt
def stripe_webhook_success(request):
    """
    Optional: handle Stripe events server-to-server.
    Useful to mark payments as complete even if the user never returns.
    For now we just verify and acknowledge the event.
    """
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    if not endpoint_secret:
        return HttpResponse(status=200)  # no-op if not configured

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # You could enqueue a background task here that triggers generation
        # using an internal HTTP call to final_report_docraptor_start or
        # a Celery job that renders without a request.
        # assessment_id = (session.get("metadata") or {}).get("assessment_id")
        pass

    return HttpResponse(status=200)