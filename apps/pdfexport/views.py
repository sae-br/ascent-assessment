# DocRaptor Version
from django.http import HttpResponse, JsonResponse, Http404
from django.template.loader import get_template
from django.templatetags.static import static
from django.conf import settings
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

import logging
logger = logging.getLogger(__name__)

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
        rows = [
            {"code": s["code"], "name": s["name"], "score": s["score"], "range": s["range_label"]}
            for s in peak_sections
        ]
        DISPLAY_ORDER = [
            "Collaborative Culture",
            "Leadership Accountability",
            "Strategic Momentum",
            "Talent Magnetism",
        ]
        order_map = {name: i for i, name in enumerate(DISPLAY_ORDER)}
        peak_score_summary = sorted(rows, key=lambda r: order_map.get(r["name"], 99))
    else:
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
        summary_rows = [
            {
                "code": p["code"],
                "name": p["name"],
                "score": p.get("score"),
                "range": p.get("range_label"),
            }
            for p in peak_sections
        ]
        # Define display order for bar row
        DISPLAY_ORDER = [
            "Collaborative Culture",
            "Leadership Accountability",
            "Strategic Momentum",
            "Talent Magnetism",
        ]
        order_map = {name: i for i, name in enumerate(DISPLAY_ORDER)}
        peak_score_summary = sorted(summary_rows, key=lambda r: order_map.get(r["name"], 99))

        # Use pre-defined weighting for Results at a Glance
        scored_sort = sorted(
            [r for r in summary_rows if r["score"] is not None],
            key=lambda r: r["score"]
        )
        if scored_sort:
            lowest = scored_sort[0]["code"]
            highest = scored_sort[-1]["code"]
            rs = ResultsSummary.objects.filter(high_peak=highest, low_peak=lowest).first()
            summary_text = rs.summary_text if rs else ""

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
    peak_score_summary, summary_text = [], ""
    if stage >= 1 and peak_sections:
        rows = [
            {"code": s["code"], "name": s["name"], "score": s["score"], "range": s["range_label"]}
            for s in peak_sections
        ]
        DISPLAY_ORDER = [
            "Collaborative Culture",
            "Leadership Accountability",
            "Strategic Momentum",
            "Talent Magnetism",
        ]
        order_map = {name: i for i, name in enumerate(DISPLAY_ORDER)}
        peak_score_summary = sorted(rows, key=lambda r: order_map.get(r["name"], 99))
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
    filename = f"orghealth-ascent-{slugify(assessment.team.name)}-{assessment.deadline:%Y-%m}.pdf"

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
    if not status_id:
        return HttpResponse("Failed to start PDF job.", status=502)
    return render(request, "pdfexport/doc_status.html", {"status_id": status_id, "filename": filename})


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
    When the job is completed, fetch the file from DocRaptor’s download_url
    and stream it to the user as application/pdf.
    """
    client = docraptor.DocApi()
    client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY

    try:
        status = client.get_async_doc_status(status_id)
    except ApiException as e:
        logger.exception("DocRaptor status check (for download) failed")
        raise Http404("PDF not available")

    if getattr(status, "status", None) != "completed":
        raise Http404("PDF not ready")

    download_url = getattr(status, "download_url", None)
    if not download_url:
        raise Http404("No download URL available")

    # Stream the file
    try:
        r = requests.get(download_url, stream=True, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.exception("Fetching DocRaptor download failed")
        return HttpResponse("Could not retrieve PDF.", status=502)

    resp = HttpResponse(r.content, content_type="application/pdf")
    resp["Content-Disposition"] = 'inline; filename="report.pdf"'
    return resp