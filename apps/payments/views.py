from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import stripe
import requests
import docraptor
from docraptor.rest import ApiException

from apps.assessments.models import Assessment
from apps.pdfexport.models import FinalReport
from apps.pdfexport.views import build_report_filenames
from apps.pdfexport.utils.storage import S3Uploader

import logging
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def checkout(request, assessment_id: int):
    assessment = get_object_or_404(Assessment, id=assessment_id, team__admin=request.user)

    if FinalReport.objects.filter(assessment=assessment, s3_key__isnull=False).exists():
        messages.info(request, "A final report already exists for this assessment.")
        return redirect(f"{reverse('assessments:assessments_overview')}?assessment={assessment.id}")

    price_id = getattr(settings, "STRIPE_PRICE_FINAL_REPORT", None)
    price = stripe.Price.retrieve(price_id)
    amount_minor = price["unit_amount"]
    currency = price["currency"]

    return render(request, "payments/checkout.html", {
        "assessment": assessment,
        "amount_display": f"${amount_minor/100:,.2f}",
        "currency": currency.upper(),
    })


@login_required
@require_POST
def create_checkout_session(request, assessment_id: int):
    assessment = get_object_or_404(
        Assessment, id=assessment_id, team__admin=request.user
    )

    # If already has a report, don’t sell twice
    if FinalReport.objects.filter(assessment=assessment, s3_key__isnull=False).exists():
        return JsonResponse({"redirect": f"{reverse('assessments:assessments_overview')}?assessment={assessment.id}"})

    price_id = getattr(settings, "STRIPE_PRICE_FINAL_REPORT", None)
    if not price_id:
        return JsonResponse({"error": "Price not configured."}, status=400)

    success_url = request.build_absolute_uri(
        reverse("payments:checkout_success")
    ) + "?session_id={CHECKOUT_SESSION_ID}&assessment=" + str(assessment.id)

    cancel_url = request.build_absolute_uri(
        reverse("assessments:assessments_overview")
    ) + f"?assessment={assessment.id}"

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            allow_promotion_codes=True,
            automatic_tax={"enabled": True},
            billing_address_collection="required",
            customer_email=request.user.email or None,
            metadata={
                "assessment_id": str(assessment.id),
                "user_id": str(request.user.id),
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return JsonResponse({"id": session.id, "url": session.url})
    except Exception as e:
        logger.error("Failed to create Checkout Session: %s", e, exc_info=True)
        return JsonResponse({"error": "Could not start checkout"}, status=400)

@login_required
def checkout_success(request):
    session_id = request.GET.get("session_id")
    assessment_id = request.GET.get("assessment")

    if not session_id or not assessment_id:
        messages.error(request, "Missing checkout confirmation.")
        return redirect("assessments:assessments_overview")

    # Optional: verify the session (not strictly required if webhook is authoritative)
    try:
        sess = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
    except Exception:
        sess = None

    # If Stripe already shows paid here, feel free to redirect to your existing success page.
    if sess and getattr(sess, "payment_status", "") == "paid":
        return redirect("payments:success", assessment_id=int(assessment_id))

    # Otherwise show your existing "processing" experience:
    return redirect(f"{reverse('assessments:assessments_overview')}?assessment={assessment_id}")

@login_required
def payment_return(request):
    """
    After Stripe confirmation. If paid, go to success page where we kick off
    DocRaptor and poll for report generation completion.
    """
    pi_id = (
        request.GET.get("payment_intent")
        or request.GET.get("pi")
    )
    client_secret = request.GET.get("payment_intent_client_secret")

    if not pi_id and not client_secret:
        messages.error(request, "Missing payment confirmation info.")
        return redirect("assessments:assessments_overview")

    try:
        pi = stripe.PaymentIntent.retrieve(pi_id) if pi_id else stripe.PaymentIntent.retrieve(client_secret)
    except Exception:
        messages.error(request, "Could not verify your payment.")
        return redirect("assessments:assessments_overview")

    status = pi.get("status")
    meta = pi.get("metadata") or {}
    assessment_id = meta.get("assessment_id")

    if not assessment_id:
        messages.error(request, "Missing assessment reference.")
        return redirect("assessments:assessments_overview")

    if status == "succeeded":
        assessment = Assessment.objects.get(id=assessment_id, team__admin=request.user)
        fr, _ = FinalReport.objects.get_or_create(assessment=assessment)
        if not fr.paid_at:
            fr.paid_at = timezone.now()
            fr.save(update_fields=["paid_at"])

    elif status in ("requires_payment_method", "canceled"):
        messages.error(request, "Payment was not completed. Please try again.")
        return redirect("payments:checkout", assessment_id=assessment_id)

    else:
        messages.info(request, "Your payment is processing. Please check back shortly.")
        return redirect(f"{reverse('assessments:assessments_overview')}?assessment={assessment_id}")


@login_required
def success(request, assessment_id: int):
    """
    Show a 'payment successful' page. On load:
      1) POST (via htmx) to start DocRaptor generation
      2) Poll a tiny status endpoint until the report is ready
    """
    assessment = get_object_or_404(
        Assessment, id=assessment_id, team__admin=request.user
    )

    # If a finished report is *already* present (e.g., user refreshed),
    # we can show the download button immediately.
    fr = FinalReport.objects.filter(assessment=assessment, s3_key__isnull=False).first()

    return render(request, "payments/success.html", {
        "assessment": assessment,
        "final_report": fr,
    })


@login_required
def report_status(request, assessment_id: int):
    """
    HTMX polled endpoint:
    - returns not-ready while queueing/processing
    - when DocRaptor completes, downloads bytes, uploads to S3, marks FinalReport ready
    - resilient to transient DocRaptor/S3 errors and double-writes
    """
    assessment = get_object_or_404(
        Assessment, pk=assessment_id, team__admin=request.user
    )
    fr = FinalReport.objects.filter(assessment=assessment).first()

    # Default context
    ctx = {
        "assessment": assessment,
        "final_report": fr,
        "ready": False,
        "status_text": None,
        "error": None,
    }

    # No FinalReport row yet (e.g., kickoff hasn’t persisted it); keep polling quietly.
    if not fr:
        ctx["status_text"] = "Starting…"
        return render(request, "payments/_report_status.html", ctx)

    # Already finalized
    if fr.s3_key:
        ctx["ready"] = True
        return render(request, "payments/_report_status.html", ctx)
    
    # Job id from DocRaptor
    job_id = fr.docraptor_status_id

    # We have a FinalReport row but no job id yet (kickoff in flight); keep polling.
    if not job_id:
        ctx["status_text"] = "Queuing…"
        return render(request, "payments/_report_status.html", ctx)

    # Ask DocRaptor for job status
    client = docraptor.DocApi()
    client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY

    try:
        status = client.get_async_doc_status(job_id)
    except ApiException as e:
        # Hard failures: treat as error (let UI offer retry)
        if getattr(e, "status", None) in (404, 422):
            logger.error("DocRaptor status hard error for job %s (assessment %s): %s",
                         job_id, assessment.id, e, exc_info=True)
            ctx["error"] = "The PDF job could not be found or failed to initialize. Please try again."
            return render(request, "payments/_report_status.html", ctx)
        # Transient failures: keep polling
        logger.warning("DocRaptor status transient error for job %s: %s", job_id, e)
        ctx["status_text"] = "Still working…"
        return render(request, "payments/_report_status.html", ctx)

    st = getattr(status, "status", None)
    if st in (None, "queued", "processing"):
        ctx["status_text"] = "Generating your report…"
        return render(request, "payments/_report_status.html", ctx)

    if st == "failed":
        # Log as much detail as possible, but don’t leak it to users.
        detail = getattr(status, "message", None) or getattr(status, "validation_errors", None)
        logger.error("DocRaptor job failed for assessment %s (job %s): %r", assessment.id, job_id, detail)
        ctx["error"] = "PDF generation failed. Please try again."
        return render(request, "payments/_report_status.html", ctx)

    if st == "completed":
        # Another poller could have just finished the upload
        if fr.s3_key:
            ctx["ready"] = True
            return render(request, "payments/_report_status.html", ctx)

        download_url = getattr(status, "download_url", None)
        if not download_url:
            # Rare but harmless; wait for DocRaptor to expose the URL.
            ctx["status_text"] = "Finalizing…"
            return render(request, "payments/_report_status.html", ctx)

        # Fetch PDF
        try:
            r = requests.get(download_url, stream=True, timeout=60)
            r.raise_for_status()
            pdf_bytes = r.content
        except requests.RequestException as e:
            logger.warning("DocRaptor download transient error for job %s: %s", job_id, e)
            ctx["status_text"] = "Finalizing…"
            return render(request, "payments/_report_status.html", ctx)

        # Upload to S3 (private)
        try:
            pretty_name, slug_name = build_report_filenames(assessment)
            s3_key = f"reports/assessments/{assessment.id}/{slug_name}"

            uploader = S3Uploader(
                bucket=settings.AWS_STORAGE_BUCKET_NAME,
                region=settings.AWS_S3_REGION_NAME,
                access_key=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                secret_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
            )
            uploaded_key, size_bytes = uploader.upload_bytes(
                pdf_bytes, s3_key, content_type="application/pdf"
            )
        except Exception as e:
            logger.error("S3 upload failed for assessment %s: %s", assessment.id, e, exc_info=True)
            ctx["error"] = "We generated the PDF but couldn’t store it. Please retry in a moment."
            return render(request, "payments/_report_status.html", ctx)

        # Persist and return ready
        fr.s3_key = uploaded_key
        fr.size_bytes = size_bytes
        fr.save(update_fields=["s3_key", "size_bytes"])

        ctx["final_report"] = fr
        ctx["ready"] = True
        return render(request, "payments/_report_status.html", ctx)

    # Unknown status: keep polling conservatively
    logger.warning("DocRaptor returned unexpected status %r for job %s", st, job_id)
    ctx["status_text"] = "Working…"
    return render(request, "payments/_report_status.html", ctx)


@csrf_exempt
def stripe_webhook_success(request):
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    if not endpoint_secret:
        return HttpResponse(status=200)  # no-op if not configured

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        logger.warning("Stripe webhook signature verify failed: %s", e)
        return HttpResponse(status=400)

    etype = event.get("type")

    if etype == "payment_intent.succeeded":
        pi = event["data"]["object"]
        meta = (pi.get("metadata") or {}) if isinstance(pi, dict) else (getattr(pi, "metadata", {}) or {})
        assessment_id = str(meta.get("assessment_id") or "")
        promo_code = (meta.get("promo_code") or "").strip().upper()
        user_id = str(meta.get("user_id") or "")

        if not assessment_id:
            return HttpResponse(status=200)

        try:
            assessment = Assessment.objects.get(id=assessment_id)
        except Assessment.DoesNotExist:
            return HttpResponse(status=200)

        fr, _ = FinalReport.objects.get_or_create(assessment=assessment)
        if not fr.paid_at:
            fr.paid_at = timezone.now()
            fr.save(update_fields=["paid_at"])

        # Kick off async PDF generation via internal endpoint (idempotent)
        try:
            base = getattr(settings, "BASE_URL", None) or request.build_absolute_uri("/").rstrip("/")
            internal_url = f"{base}/pdfexport/{assessment.id}/docraptor/start-internal/"
            headers = {"X-Internal-Token": getattr(settings, "INTERNAL_WEBHOOK_TOKEN", "")}
            requests.post(internal_url, headers=headers, timeout=10)
        except Exception as e:
            logger.warning("Failed to trigger internal DocRaptor enqueue for assessment %s: %s", assessment_id, e)

        # Resolve user for redemption (metadata user_id preferred; fallback to assessment owner)
        User = get_user_model()
        user_obj = None
        if user_id:
            try:
                user_obj = User.objects.get(id=user_id)
            except User.DoesNotExist:
                user_obj = None
        if user_obj is None:
            user_obj = getattr(assessment.team, 'admin', None)

    elif etype == "payment_intent.payment_failed":
        pi = event["data"]["object"]
        err = (pi.get("last_payment_error") or {}).get("message") if isinstance(pi, dict) else None
        logger.warning("Stripe PI failed: %s | error=%s", pi.get("id") if isinstance(pi, dict) else getattr(pi, "id", None), err)

    # Always 200 to avoid Stripe retries unless signature failed
    return HttpResponse(status=200)