# DocRaptor Version
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseBadRequest
from django.template.loader import get_template
from django.templatetags.static import static
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify

import os
import tempfile
import requests

from apps.reports.models import PeakActions, PeakInsights, ResultsSummary
from apps.assessments.models import Peak, Question, Answer, Assessment
from apps.pdfexport.utils.context import get_report_context_data
from apps.pdfexport.utils.charts import (
    get_peak_rating_distribution,
    generate_peak_mountain_chart,
    generate_question_bar_chart,
)
from apps.pdfexport.utils.images import png_path_to_data_uri
from apps.pdfexport.utils.storage import S3Uploader
from apps.pdfexport.models import FinalReport

import logging
import boto3
logger = logging.getLogger(__name__)

# ---- Canonical peak order and names (for display + tiebreaks) -----------
ORDER = ["CC", "LA", "SM", "TM"]
NAMES = {
    "CC": "Collaborative Culture",
    "LA": "Leadership Accountability",
    "SM": "Strategic Momentum",
    "TM": "Talent Magnetism",
}

def compute_summary_and_display_rows(peak_sections):
    """
    Given peak_sections (each has at least code, name, and maybe score/range_label),
    return:
      - peak_score_summary (always in canonical display order),
      - summary_text derived from lowest/highest scores with deterministic tiebreaks,
      - lowest and highest row dicts (for logging / future needs).
    """
    # Normalize into a dict keyed by code
    rows_by_code = {}
    for s in peak_sections:
        code = s.get("code")
        if not code:
            continue
        rows_by_code[code] = {
            "code": code,
            "name": s.get("name") or NAMES.get(code, code),
            "score": s.get("score"),
            "range": s.get("range_label"),
        }

    # Always display in the fixed canonical order
    peak_score_summary = [rows_by_code[c] for c in ORDER if c in rows_by_code]

    # Pick lowest/highest with deterministic tie-breaks using ORDER
    scored = [r for r in peak_score_summary if r.get("score") is not None]
    lowest = highest = None
    summary_text = ""
    if scored:
        lowest = min(scored, key=lambda r: (r["score"], ORDER.index(r["code"])))
        highest = max(scored, key=lambda r: (r["score"], -ORDER.index(r["code"])))
        from apps.reports.models import ResultsSummary  # local import to avoid cycles

        rs = ResultsSummary.objects.filter(high_peak=highest["code"], low_peak=lowest["code"]).first()
        summary_text = rs.summary_text if rs else ""

    return peak_score_summary, summary_text, lowest, highest


import time
import docraptor
from docraptor.rest import ApiException


# A TEMP TEST FOR TROUBLESHOOTING
def final_report_preview(request, assessment_id):
    stage = int(request.GET.get("stage", "1") or 1)
    stage = max(1, min(stage, 6))

    assessment = get_object_or_404(Assessment, id=assessment_id)
    peaks = list(Peak.objects.all().values("name", "code"))
    STATIC_ABS = request.build_absolute_uri(static(""))

    # flags for the template
    show_scores = stage >= 1
    show_insights_actions = stage >= 2
    show_peak_charts = stage >= 3   # we won't actually render charts in preview, but flag stays consistent
    show_question_rows = stage >= 4
    show_question_charts = stage >= 5

    # helper for LOW/MEDIUM/HIGH
    def range_for(pct):
        if pct < 34: return "LOW"
        if pct < 67: return "MEDIUM"
        return "HIGH"

    # Preload answers once (cheap enough) to compute basic scores
    participants = assessment.participants.all()
    answers_qs = Answer.objects.filter(participant__in=participants)

    peak_sections = []
    for p in peaks:
        section = {"name": p["name"], "code": p["code"]}

        # (1) score/range
        if show_scores:
            # percentages for ratings 0..3
            percents = get_peak_rating_distribution(assessment, p["code"])  # [p0,p1,p2,p3] sums to 100
            score0_3 = sum((i * pct) for i, pct in enumerate(percents)) / 100.0
            percentage_score = round(score0_3 * 100 / 3)
            section["score"] = percentage_score
            section["range_label"] = range_for(percentage_score)

        # (2) insights/actions
        if show_insights_actions:
            rl = section.get("range_label")
            insight = PeakInsights.objects.filter(peak=p["code"], range_label=rl).first() if rl else None
            action  = PeakActions.objects.filter(peak=p["code"], range_label=rl).first() if rl else None
            section["insights"] = insight.insight_text if insight else ""
            section["actions"]  = action.action_text  if action  else ""

        # (3) focus image (absolute URL)
        if stage >= 3:
            section["ascent_image"] = f"{STATIC_ABS}images/ascent-{p['code'].lower()}-focus.png"

        # leave these empty in preview to keep it light
        section.setdefault("questions", [])
        section.setdefault("chart_path", "")

        peak_sections.append(section)

    # Basic summary table when scores are shown
    if show_scores and peak_sections:
        peak_score_summary, summary_text, low_row, high_row = compute_summary_and_display_rows(peak_sections)
        logger.info("PREVIEW summary order=%s low=%s high=%s",
                    [r["code"] for r in peak_score_summary],
                    getattr(low_row, "code", 
                            getattr(low_row, "get", lambda k=None: None)("code") 
                            if isinstance(low_row, dict) else None),
                    getattr(high_row, "code", 
                            getattr(high_row, "get", lambda k=None: None)("code") 
                            if isinstance(high_row, dict) else None))
    else:
        summary_text = ""
        peak_score_summary = [{"name": p["name"], "score": 0, "range": "—"} for p in peaks]

    ctx = {
        "STATIC_ABS": STATIC_ABS,
        "team_name": assessment.team.name,
        "deadline": assessment.deadline,
        "peak_score_summary": peak_score_summary,
        "peak_sections": peak_sections,
        "show_scores": show_scores,
        "show_insights_actions": show_insights_actions,
        "show_peak_charts": show_peak_charts,
        "show_question_rows": show_question_rows,
        "show_question_charts": show_question_charts,
        "stage": stage,
        "summary_text": summary_text,
    }
    logger.info("PREVIEW stage=%s sections=%s", stage, len(peak_sections))
    return render(request, "pdfexport/finalreport_docraptor.html", ctx)


def generate_final_report_pdf_docraptor(request, assessment_id):
    """
    Flags in place to incrementally build the PDF payload. 
    Control with ?stage=N while testing/troubleshooting:
      1: scores/range/summary only
      2: + insights/actions text
      3: + focus images
      4: + peak distribution chart (data URI)
      5: + per-question health % rows (no charts)
      6: + per-question bar charts (data URIs)
    """
    stage = int(request.GET.get("stage", 1))
    # Clamp stage to [1, 6]
    if stage < 1:
        stage = 1
    elif stage > 6:
        stage = 6
    show_scores = stage >= 2
    show_insights_actions = stage >= 3
    show_peak_charts = stage >= 4
    show_question_rows = stage >= 5
    show_question_charts = stage >= 6
    t0_total = time.monotonic()
    logger.info("[PDF] Start render for assessment_id=%s stage=%s", assessment_id, stage)

    # --- Base context --------------------------------------------------------
    base = get_report_context_data(assessment_id)
    assessment = base["assessment"]
    peaks = base["peaks"]
    STATIC_ABS = request.build_absolute_uri(static(""))

    peak_sections = []
    temp_paths = []  # for generated PNGs to clean up

    def range_for(pct):
        if pct < 34:
            return "LOW"
        elif pct < 67:
            return "MEDIUM"
        return "HIGH"

    # --- Build per-peak blocks, gated by stage -------------------------------
    for peak in peaks:
        section = {
            "name": peak.name,
            "code": peak.code,
        }

        # (1) score/range (no images)
        if stage >= 1:
            percents = get_peak_rating_distribution(assessment, peak.code)  # list of 4 percentages for 0..3
            # weighted avg (0..3)
            score0_3 = sum((i * p) for i, p in enumerate(percents)) / 100.0
            percentage_score = round(score0_3 * 100 / 3)
            section["score"] = percentage_score
            section["range_label"] = range_for(percentage_score)

        # (2) insights/actions text
        if stage >= 2:
            rl = section.get("range_label")
            insight = PeakInsights.objects.filter(peak=peak.code, range_label=rl).first() if rl else None
            action =  PeakActions.objects.filter(peak=peak.code, range_label=rl).first() if rl else None
            section["insights"] = insight.insight_text if insight else None
            section["actions"]  = action.action_text  if action  else None

        # (3) focus image (absolute URL)
        if stage >= 3:
            section["ascent_image_abs"] = f"{STATIC_ABS}images/ascent-{peak.code.lower()}-focus.png"

        # (4) peak distribution chart (PNG → data URI)
        if stage >= 4:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                spread_png = tmp.name
            generate_peak_mountain_chart(peak.name, get_peak_rating_distribution(assessment, peak.code), spread_png)
            temp_paths.append(spread_png)
            section["chart_data_uri"] = png_path_to_data_uri(spread_png)

        # (5/6) per-question rows
        if stage >= 5:
            q_rows = []
            participants = assessment.participants.all()
            answers = Answer.objects.filter(participant__in=participants)
            for q in Question.objects.filter(peak=peak):
                qa = answers.filter(question=q)
                counts = [0, 0, 0, 0]
                for a in qa:
                    if 0 <= a.value <= 3:
                        counts[a.value] += 1
                total = sum(counts)
                if total:
                    weighted = sum(i * c for i, c in enumerate(counts))
                    health_pct = round((weighted / total) * 100 / 3)
                else:
                    health_pct = 0

                row = {"text": q.text, "health_percentage": health_pct}

                if stage >= 6:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as qtmp:
                        qpng = qtmp.name
                    generate_question_bar_chart(q.text, counts, qpng)
                    temp_paths.append(qpng)
                    row["chart_data_uri"] = png_path_to_data_uri(qpng)

                q_rows.append(row)

            section["questions"] = q_rows

        peak_sections.append(section)

    # Score summary (stage >= 1)
    peak_score_summary = []
    summary_text = ""
    if stage >= 1 and peak_sections:
        peak_score_summary, summary_text, low_row, high_row = compute_summary_and_display_rows(peak_sections)
        logger.info("[PDF] summary order=%s low=%s high=%s",
                    [r["code"] for r in peak_score_summary],
                    low_row and low_row.get("code"),
                    high_row and high_row.get("code"))

    # --- Render HTML for DocRaptor ------------------------------------------
    ctx = {
        "STATIC_ABS": STATIC_ABS,
        "assessment": assessment,
        "team_name": assessment.team.name,
        "deadline": assessment.deadline,
        "peak_sections": peak_sections,
        "peak_score_summary": peak_score_summary,
        "summary_text": summary_text,
        "stage": stage,
        "show_scores": show_scores,
        "show_insights_actions": show_insights_actions,
        "show_peak_charts": show_peak_charts,
        "show_question_rows": show_question_rows,
        "show_question_charts": show_question_charts,
    }
    html = get_template("pdfexport/finalreport_docraptor.html").render(ctx)
    logger.info("[PDF] HTML size=%s bytes, img_count=%s", len(html), html.count("<img"))

    # --- DocRaptor call ------------------------------------------------------
    client = docraptor.DocApi()
    client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY
    baseurl = request.build_absolute_uri("/")

    t0_docraptor = time.monotonic()
    logger.info("[PDF] Calling DocRaptor...")
    try:
        result = client.create_doc({
            "test": True,  # keep True while testing
            "document_type": "pdf",
            "name": f"{slugify(assessment.team.name)}-{assessment.deadline:%Y-%m}.pdf",
            "document_content": html,  
            "prince_options": {
                "media": "print",
                "baseurl": baseurl,
            },
        },
        _request_timeout=(10, 700))
        logger.info("[PDF] DocRaptor returned in %.2fs", time.monotonic() - t0_docraptor)
        return HttpResponse(result, content_type="application/pdf")
    except ApiException as e:
        logger.exception("DocRaptor API error")
        return HttpResponse(f"DocRaptor error {getattr(e, 'status', '')}: {getattr(e, 'body', e)}", status=502)
    except Exception as e:
        logger.exception("Unexpected error during DocRaptor render")
        return HttpResponse(f"Unexpected error: {e}", status=500)
    finally:
        for p in temp_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        logger.info("[PDF] Total view time %.2fs", time.monotonic() - t0_total)


# --- Async DocRaptor flow ---
    """
    PDF load too high for synchronous generation.
    Use async flow to:
      1: Start the report generation 
      2: Display a JS status page to the client while job works
      3: Load the completed download file for the client
    """
def start_final_report_job(request, assessment_id):
    assessment = get_object_or_404(Assessment, pk=assessment_id)

    # hard gate: do not regenerate if a report exists
    if hasattr(assessment, "final_report"):
        return HttpResponseBadRequest("A final report already exists for this assessment.")

    # enqueue the async job (Celery) with assessment_id
    # enqueue_generate_report.delay(assessment_id)
    return JsonResponse({"ok": True, "queued": True})

def final_report_docraptor_start(request, assessment_id):
    stage = int(request.GET.get("stage", "1") or 1)
    stage = max(1, min(stage, 6))

    # Build the SAME context as the sync view does for the chosen stage
    base = get_report_context_data(assessment_id)
    assessment = base["assessment"]
    peaks = base["peaks"]
    STATIC_ABS = request.build_absolute_uri(static(""))

    def range_for(pct):
        if pct < 34: return "LOW"
        if pct < 67: return "MEDIUM"
        return "HIGH"

    peak_sections, temp_paths = [], []

    # Build per-peak blocks just like in generate_final_report_pdf_docraptor
    for peak in peaks:
        section = {"name": peak.name, "code": peak.code}

        # scores/range
        if stage >= 1:
            perc = get_peak_rating_distribution(assessment, peak.code)
            score0_3 = sum((i * p) for i, p in enumerate(perc)) / 100.0
            pct_score = round(score0_3 * 100 / 3)
            section["score"] = pct_score
            section["range_label"] = range_for(pct_score)

        # insights/actions
        if stage >= 2:
            rl = section.get("range_label")
            insight = PeakInsights.objects.filter(peak=peak.code, range_label=rl).first() if rl else None
            action  = PeakActions.objects.filter(peak=peak.code, range_label=rl).first() if rl else None
            section["insights"] = insight.insight_text if insight else None
            section["actions"]  = action.action_text  if action  else None

        # focus image
        if stage >= 3:
            section["ascent_image_abs"] = f"{STATIC_ABS}images/ascent-{peak.code.lower()}-focus.png"

        # peak distribution chart
        if stage >= 4:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                path = tmp.name
            generate_peak_mountain_chart(peak.name, get_peak_rating_distribution(assessment, peak.code), path)
            temp_paths.append(path)
            from apps.pdfexport.utils.images import png_path_to_data_uri
            section["chart_data_uri"] = png_path_to_data_uri(path)

        # per-question rows
        if stage >= 5:
            q_rows = []
            participants = assessment.participants.all()
            answers = Answer.objects.filter(participant__in=participants)
            for q in Question.objects.filter(peak=peak):
                qa = answers.filter(question=q)
                counts = [0,0,0,0]
                for a in qa:
                    if 0 <= a.value <= 3:
                        counts[a.value] += 1
                total = sum(counts)
                if total:
                    weighted = sum(i*c for i,c in enumerate(counts))
                    hp = round((weighted / total) * 100 / 3)
                else:
                    hp = 0
                row = {"text": q.text, "health_percentage": hp}
                if stage >= 6:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as qtmp:
                        qpath = qtmp.name
                    generate_question_bar_chart(q.text, counts, qpath)
                    temp_paths.append(qpath)
                    row["chart_data_uri"] = png_path_to_data_uri(qpath)
                q_rows.append(row)
            section["questions"] = q_rows

        peak_sections.append(section)

    # summary (only when scores exist)
    summary_text = ""
    if stage >= 1 and peak_sections:
        peak_score_summary, summary_text, low_row, high_row = compute_summary_and_display_rows(peak_sections)
        logger.info("[ASYNC] summary order=%s low=%s high=%s",
                    [r["code"] for r in peak_score_summary],
                    low_row and low_row.get("code"),
                    high_row and high_row.get("code"))
    else:
        peak_score_summary = [{"name": p["name"], "score": 0, "range": "—"} for p in peaks]

    # flags consumed by the template
    ctx = {
        "STATIC_ABS": STATIC_ABS,
        "assessment": assessment,
        "team_name": assessment.team.name,
        "deadline": assessment.deadline,
        "peak_sections": peak_sections,
        "peak_score_summary": peak_score_summary,
        "summary_text": summary_text,
        "stage": stage,
        "show_scores": (stage >= 2),
        "show_insights_actions": (stage >= 3),
        "show_peak_charts": (stage >= 4),
        "show_question_rows": (stage >= 5),
        "show_question_charts": (stage >= 6),
    }

    html = get_template("pdfexport/finalreport_docraptor.html").render(ctx)
    filename = f"orghealth-ascent-{slugify(assessment.team.name)}-{assessment.deadline:%Y-%m}__aid-{assessment.id}.pdf"

    client = docraptor.DocApi()
    client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY
    baseurl = request.build_absolute_uri("/")

    try:
        job = client.create_async_doc({
            "test": True,
            "document_type": "pdf",
            "name": filename,
            "document_content": html, 
            "prince_options": {
                "media": "print",
                "baseurl": baseurl,
            },
        })
    finally:
        # cleanup temp PNGs
        for p in temp_paths:
            try: os.remove(p)
            except OSError: pass

    status_id = getattr(job, "status_id", None)
    cache.set(
        f"docraptor:{status_id}",
        {"assessment_id": assessment.id, "filename": filename},
        timeout=60 * 60, 
    )

    # --- Return a tiny self-contained status page that polls until ready ---
    if not status_id:
        return HttpResponse("Failed to start DocRaptor job.", status=502)

    status_poll_url = request.build_absolute_uri(f"/pdfexport/docraptor/status/{status_id}/")

    html_poll = f"""
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
    <title>Generating report…</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif; margin: 2rem; }}
      .muted {{ color: #666; }}
      code {{ background: #f6f8fa; padding: 0.2rem 0.4rem; border-radius: 4px; }}
    </style>
  </head>
  <body>
    <h1>Generating your PDF…</h1>
    <p class=\"muted\">This page will refresh automatically. You can leave it open.</p>
    <p class=\"muted\">Status ID: <code>{status_id}</code></p>
    <div id=\"status\" class=\"muted\">Starting…</div>
    <script>
      const statusUrl = {status_poll_url!r};
      async function poll() {{
        try {{
          const res = await fetch(statusUrl, {{credentials: 'same-origin'}});
          if (!res.ok) throw new Error('HTTP ' + res.status);
          const data = await res.json();
          document.getElementById('status').textContent = 'Status: ' + (data.status || 'unknown');
          if (data.status === 'completed' && data.download) {{
            window.location.replace(data.download);
            return;
          }}
          if (data.status === 'failed') {{
            document.getElementById('status').textContent = 'Failed: ' + (data.message || 'DocRaptor failed');
            return;
          }}
        }} catch (e) {{
          document.getElementById('status').textContent = 'Error: ' + e.message;
        }}
        setTimeout(poll, 2000);
      }}
      poll();
    </script>
  </body>
</html>
"""
    return HttpResponse(html_poll)


def docraptor_status(request, status_id):
    """
    JSON endpoint the browser polls every couple seconds to check progress.
    """
    client = docraptor.DocApi()
    client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY

    try:
        status = client.get_async_doc_status(status_id)
    except ApiException as e:
        logger.exception("DocRaptor status check failed")
        return JsonResponse({"status": "error", "message": str(e)}, status=502)

    # status.status is one of: queued / processing / completed / failed
    state = getattr(status, "status", "unknown")

    if state == "completed":
        download_url = getattr(status, "download_url", None)
        return JsonResponse({
            "status": "completed",
            "download": request.build_absolute_uri(
                # route that will stream the PDF back through the app
                # (safer than sending DocRaptor URL directly to the browser)
                f"/pdfexport/docraptor/download/{status_id}/"
            )
        })

    if state == "failed":
        return JsonResponse({
            "status": "failed",
            "message": getattr(status, "message", "DocRaptor failed")
        }, status=500)

    # queued / processing (or unknown)
    return JsonResponse({"status": state})


def docraptor_download(request, status_id):
    """
    Resolve the PDF by status_id using cache metadata, upload once to S3 if needed,
    then redirect to a short-lived signed S3 URL. 
    No FinalReport.status_id/is_ready usage.
    """
    # Pull assessment + filename from cache where we stored it in final_report_docraptor_start
    meta = cache.get(f"docraptor:{status_id}")
    if not meta:
        raise Http404("Unknown or expired job")

    assessment_id = meta.get("assessment_id")
    filename = meta.get("filename") or f"final-report-{assessment_id}.pdf"

    # Use a stable S3 key (avoid relying on fields that don't exist on FinalReport)
    key = f"reports/assessments/{assessment_id}/final-report-{assessment_id}.pdf"

    # Prefer explicit reports bucket setting but fall back to the standard storage bucket
    bucket = getattr(settings, "AWS_S3_REPORTS_BUCKET", getattr(settings, "AWS_STORAGE_BUCKET_NAME", None))
    if not bucket:
        return HttpResponse("S3 bucket not configured", status=500)

    uploader = S3Uploader(
        bucket=bucket,
        region=getattr(settings, "AWS_S3_REGION_NAME", None),
        access_key=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        secret_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
    )

    # If we've already uploaded a FinalReport for this assessment, just presign and return
    fr, _ = FinalReport.objects.get_or_create(assessment_id=assessment_id)
    if fr.s3_key:
        return redirect(uploader.presign_get(fr.s3_key, expires_seconds=300))

    # Otherwise fetch the finished bytes from DocRaptor and upload
    client = docraptor.DocApi()
    client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY

    try:
        status = client.get_async_doc_status(status_id)
    except ApiException:
        logger.exception("DocRaptor status check (for download) failed")
        raise Http404("PDF not available")

    if getattr(status, "status", None) != "completed":
        raise Http404("PDF not ready")

    download_url = getattr(status, "download_url", None)
    if not download_url:
        raise Http404("No download URL available")

    try:
        r = requests.get(download_url, stream=True, timeout=30)
        r.raise_for_status()
        pdf_bytes = r.content
    except requests.RequestException:
        logger.exception("Fetching DocRaptor download failed")
        return HttpResponse("Could not retrieve PDF.", status=502)

    uploaded_key, size_bytes = uploader.upload_bytes(
        pdf_bytes, key, content_type="application/pdf"
    )

    # Persist the S3 location/size on FinalReport (no is_ready field on model)
    fr.s3_key = uploaded_key
    fr.size_bytes = size_bytes
    fr.save(update_fields=["s3_key", "size_bytes"]) 

    return redirect(uploader.presign_get(uploaded_key, expires_seconds=300))