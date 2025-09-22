from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import json
import stripe
import requests
import docraptor
from docraptor.rest import ApiException

from apps.assessments.models import Assessment
from apps.pdfexport.models import FinalReport
from apps.pdfexport.views import build_report_filenames
from apps.pdfexport.utils.storage import S3Uploader
from apps.payments.models import PromoCode, Redemption
from apps.payments.utils.promos import validate_and_price, PromoInvalid, normalize_code
from apps.payments.utils.tax import compute_tax_minor

import logging
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def checkout(request, assessment_id: int):
    """
    Render the on-page checkout with Stripe Payment Element.
    Creates or reuses a PaymentIntent and passes its client_secret to the template.
    """
    assessment = get_object_or_404(
        Assessment,
        id=assessment_id,
        team__admin=request.user
    )

    # If a report file already exists, don't let them pay again.
    if FinalReport.objects.filter(assessment=assessment, s3_key__isnull=False).exists():
        messages.info(request, "A final report already exists for this assessment.")
        return redirect(f"{reverse('assessments:assessments_overview')}?assessment={assessment.id}")

    # Prices set in Stripe
    price_id = getattr(settings, "STRIPE_PRICE_FINAL_REPORT", None)
    if not price_id:
        return HttpResponseBadRequest("Price not configured. Please contact support.")

    # Retrieve the Price to get amount + currency
    price_obj = stripe.Price.retrieve(price_id)
    amount = price_obj["unit_amount"]          # integer, in the currency’s minor unit
    currency = price_obj["currency"]           # e.g. "cad"
    amount_display = f"${amount / 100:,.2f}"

    # Optional: apply promo
    promo_code_input = request.POST.get("promo_code") or request.GET.get("promo_code")
    discount_minor = 0
    final_amount = amount
    applied_code = None
    error_msg = None

    if promo_code_input:
        try:
            result = validate_and_price(
                code_str=promo_code_input,
                user=request.user,
                assessment=assessment,
                subtotal_minor=amount,
                currency=currency,
            )
            discount_minor = result["discount_minor"]
            final_amount = result["final_minor"]
            applied_code = result["promocode"].code
        except PromoInvalid as e:
            error_msg = str(e)

    # Create the PaymentIntent for the Payment Element, using the FINAL amount
    pi = stripe.PaymentIntent.create(
        amount=final_amount,
        currency=currency,
        payment_method_types=["card"],
        metadata={
            "assessment_id": str(assessment.id),
            "user_id": str(request.user.id),
            "promo_code": applied_code or "",
            "amount_before": str(amount),
            "discount_applied": str(discount_minor),
            "amount_after": str(final_amount),
        },
        receipt_email=request.user.email or None,
        description="Ascent Assessment Final Report",
    )

    # Return URL that Stripe will hit after on-page confirmation completes
    return_url = request.build_absolute_uri(reverse("payments:payment_return"))

    return render(request, "payments/checkout.html", {
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "client_secret": pi.client_secret,
        "assessment_id": assessment.id,
        "return_url": return_url,
        "amount_display": amount_display,
        "original_amount_minor": amount,
        "final_amount_minor": final_amount,
        "discount_minor": discount_minor,
        "applied_code": applied_code,
        "promo_error": error_msg,
        "success_url": request.build_absolute_uri(
            reverse("payments:payment_return") + f"?assessment={assessment.id}"
        ),
    })

@login_required
@require_POST
def reprice(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    assessment_id = payload.get('assessment_id')
    promo_code_input = (payload.get('promo_code') or '').strip()
    billing_address = payload.get('billing_address') or {}
    pi_id = (payload.get('pi_id') or '').strip()

    if not assessment_id or not pi_id:
        return HttpResponseBadRequest('Missing assessment or PI id')

    assessment = get_object_or_404(Assessment, id=assessment_id, team__admin=request.user)

    # 1) Base price from Stripe Price (controls subtotal)
    price_id = getattr(settings, 'STRIPE_PRICE_FINAL_REPORT', None)
    if not price_id:
        return HttpResponseBadRequest('Price not configured')
    price_obj = stripe.Price.retrieve(price_id)
    amount = price_obj['unit_amount']
    currency = price_obj['currency']

    # 2) Apply promo (server-side only)
    discount_minor = 0
    final_after_discount = amount
    applied_code = None
    if promo_code_input:
        try:
            res = validate_and_price(
                code_str=promo_code_input,
                user=request.user,
                assessment=assessment,
                subtotal_minor=amount,
                currency=currency,
            )
            discount_minor = res['discount_minor']
            final_after_discount = res['final_minor']
            applied_code = res['promocode'].code
        except PromoInvalid:
            discount_minor = 0
            final_after_discount = amount
            applied_code = None

    # 3) Compute tax with Stripe Tax
    tax_minor = compute_tax_minor(final_after_discount, currency, billing_address)
    final_amount_minor = final_after_discount + tax_minor

    # 4) Verify and update existing PaymentIntent
    try:
        pi = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        return HttpResponseBadRequest('Invalid PaymentIntent')

    meta = pi.metadata or {}
    if (
        str(meta.get('user_id')) != str(request.user.id)
        or str(meta.get('assessment_id')) != str(assessment.id)
        or pi.status not in ('requires_payment_method', 'requires_confirmation')
    ):
        return HttpResponseBadRequest('Invalid PaymentIntent')

    zero_due = (final_amount_minor == 0)

    if not zero_due:
        try:
            stripe.PaymentIntent.modify(
                pi_id,
                amount=int(final_amount_minor),
                metadata={
                    'assessment_id': str(assessment.id),
                    'user_id': str(request.user.id),
                    'promo_code': applied_code or '',
                    'amount_before': str(amount),
                    'discount_applied': str(discount_minor),
                    'tax_applied': str(tax_minor),
                    'amount_after': str(final_amount_minor),
                },
                description='Ascent Assessment Final Report',
                receipt_email=request.user.email or None,
            )
        except Exception as e:
            logger.error('Failed to modify PaymentIntent %s: %s', pi_id, e, exc_info=True)
            return HttpResponseBadRequest('Failed to update payment amount')
    else:
        # Optional: cancel the PI if it's still in a modifiable state
        try:
            if pi.status in ('requires_payment_method', 'requires_confirmation'):
                stripe.PaymentIntent.cancel(pi_id)
        except Exception:
            pass

    return JsonResponse({
        'original_amount_minor': amount,
        'discount_minor': discount_minor,
        'tax_minor': tax_minor,
        'final_amount_minor': final_amount_minor,
        'payment_intent_id': pi_id,
        'zero_due': zero_due,
    })

@login_required
@require_POST
def complete_zero(request):
    """
    Complete a $0 checkout without Stripe. We *recompute* totals server-side,
    and only proceed if final_amount_minor == 0. Then we mark paid_at and
    kick off DocRaptor idempotently.
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    assessment_id = payload.get('assessment_id')
    promo_code_input = (payload.get('promo_code') or '').strip()
    billing_address = payload.get('billing_address') or {}

    if not assessment_id:
        return HttpResponseBadRequest('Missing assessment id')

    assessment = get_object_or_404(Assessment, id=assessment_id, team__admin=request.user)

    # 1) Base price from Stripe Price
    price_id = getattr(settings, 'STRIPE_PRICE_FINAL_REPORT', None)
    if not price_id:
        return HttpResponseBadRequest('Price not configured')
    price_obj = stripe.Price.retrieve(price_id)
    amount = price_obj['unit_amount']
    currency = price_obj['currency']

    # 2) Promo
    final_after_discount = amount
    if promo_code_input:
        try:
            res = validate_and_price(
                code_str=promo_code_input,
                user=request.user,
                assessment=assessment,
                subtotal_minor=amount,
                currency=currency,
            )
            final_after_discount = res['final_minor']
        except PromoInvalid:
            pass

    # 3) Tax
    tax_minor = compute_tax_minor(final_after_discount, currency, billing_address)
    final_amount_minor = final_after_discount + tax_minor

    if final_amount_minor != 0:
        return HttpResponseBadRequest('Amount is not zero; cannot complete as free')

    # 4) Idempotently mark paid & enqueue DocRaptor
    fr, _ = FinalReport.objects.get_or_create(assessment=assessment)
    if not fr.paid_at:
        fr.paid_at = timezone.now()
        fr.save(update_fields=['paid_at'])

    # Kick off DocRaptor via internal endpoint (idempotent)
    try:
        base = getattr(settings, 'BASE_URL', None) or request.build_absolute_uri('/').rstrip('/')
        internal_url = f"{base}/pdfexport/{assessment.id}/docraptor/start-internal/"
        headers = {'X-Internal-Token': getattr(settings, 'INTERNAL_WEBHOOK_TOKEN', '')}
        requests.post(internal_url, headers=headers, timeout=10)
    except Exception as e:
        logger.warning('Zero-complete: failed to enqueue DocRaptor for assessment %s: %s', assessment.id, e)

    return JsonResponse({
        'ok': True,
        'redirect': request.build_absolute_uri(reverse('payments:success', args=[assessment.id]))
    })

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

        # Record redemption if a promo code was used
        promo_code = (pi.metadata or {}).get("promo_code") or ""
        amount_before = int((pi.metadata or {}).get("amount_before") or 0)
        discount_applied = int((pi.metadata or {}).get("discount_applied") or 0)
        amount_after = int((pi.metadata or {}).get("amount_after") or pi.amount or 0)

        if promo_code and discount_applied > 0:
            try:
                pc = PromoCode.objects.get(code=promo_code)
                # Guard against duplicates (e.g., refresh)
                Redemption.objects.get_or_create(
                    promocode=pc,
                    user=request.user,
                    assessment=assessment,
                    defaults={
                        "payment_intent_id": pi.id,
                        "amount_before": amount_before,
                        "discount_applied": discount_applied,
                        "amount_after": amount_after,
                    }
                )
            except PromoCode.DoesNotExist:
                logger.warning("PI %s had promo_code=%s but PromoCode not found", pi.id, promo_code)

        return redirect("payments:success", assessment_id=assessment_id)

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

    elif etype == "payment_intent.payment_failed":
        pi = event["data"]["object"]
        err = (pi.get("last_payment_error") or {}).get("message") if isinstance(pi, dict) else None
        logger.warning("Stripe PI failed: %s | error=%s", pi.get("id") if isinstance(pi, dict) else getattr(pi, "id", None), err)

    # Always 200 to avoid Stripe retries unless signature failed
    return HttpResponse(status=200)