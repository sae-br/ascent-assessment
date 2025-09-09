from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.templatetags.static import static
from django.utils.text import slugify
from django.views.decorators.http import require_POST

import os
import tempfile
import time
import docraptor
from docraptor.rest import ApiException

from apps.reports.models import PeakActions, PeakInsights
from apps.assessments.models import Question, Answer, Assessment
from apps.pdfexport.utils.context import get_report_context_data
from apps.pdfexport.utils.charts import (
    get_peak_rating_distribution,
    generate_peak_mountain_chart,
    generate_question_bar_chart,
)
from apps.pdfexport.utils.images import png_path_to_data_uri
from apps.pdfexport.models import FinalReport

import logging
logger = logging.getLogger(__name__)


# --- Helper: build consistent filenames for PDFs ---
def build_report_filenames(assessment):
    """Return (pretty_filename, slug_filename) for a report.
    pretty: human friendly, used for download header.
    slug: safe for S3 object key and DocRaptor name.
    """
    team_name = getattr(getattr(assessment, "team", None), "name", None) or str(getattr(assessment, "team", "team"))
    deadline = getattr(assessment, "deadline", None)
    if deadline:
        pretty = f"{team_name} – {deadline:%B %Y}.pdf"
        slug_part = f"{slugify(team_name)}-{deadline:%Y-%m}"
    else:
        pretty = f"{team_name} – report.pdf"
        slug_part = f"{slugify(team_name)}-report"
    return pretty, f"{slug_part}.pdf"

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


@require_POST
@login_required
def final_report_docraptor_start(request, assessment_id):
    """
    Kick off an asynchronous DocRaptor job to generate the final report PDF
    for this assessment. Returns JSON with a docraptor_status_id if a new job is queued,
    or a simple ok/already_ready/in_progress signal otherwise.

    The HTML/PDF building mirrors the synchronous renderer but we only
    enqueue an async job here; no bytes are returned.
    """
    assessment = get_object_or_404(Assessment, pk=assessment_id, team__admin=request.user)

    # Ensure we have a FinalReport row to hold state
    fr, _ = FinalReport.objects.get_or_create(assessment=assessment)

    # If a report already finished, nothing to do
    if fr.s3_key:
        return JsonResponse({"ok": True, "already_ready": True}, status=200)

    # If a job is already in-flight, don't queue another
    if fr.docraptor_status_id:
        return JsonResponse({"ok": True, "in_progress": True, "docraptor_status_id": fr.docraptor_status_id}, status=200)

    # -----------------------------
    # Build the HTML payload
    # -----------------------------
    stage = int(request.GET.get("stage", "6") or 6)
    stage = max(1, min(stage, 6))

    t0_total = time.monotonic()
    logger.info("[PDF] Start async render for assessment_id=%s stage=%s", assessment_id, stage)

    base = get_report_context_data(assessment_id)
    assessment = base["assessment"]
    peaks = base["peaks"]
    STATIC_ABS = request.build_absolute_uri(static(""))

    def range_for(pct):
        if pct < 34: return "LOW"
        if pct < 67: return "MEDIUM"
        return "HIGH"

    peak_sections, temp_paths = [], []

    for peak in peaks:
        section = {"name": peak.name, "code": peak.code}

        # (1) score/range
        if stage >= 1:
            perc = get_peak_rating_distribution(assessment, peak.code)
            score0_3 = sum((i * p) for i, p in enumerate(perc)) / 100.0
            pct_score = round(score0_3 * 100 / 3)
            section["score"] = pct_score
            section["range_label"] = range_for(pct_score)

        # (2) insights/actions
        if stage >= 2:
            rl = section.get("range_label")
            insight = PeakInsights.objects.filter(peak=peak.code, range_label=rl).first() if rl else None
            action  = PeakActions.objects.filter(peak=peak.code, range_label=rl).first() if rl else None
            section["insights"] = insight.insight_text if insight else None
            section["actions"]  = action.action_text  if action  else None

        # (3) focus image
        if stage >= 3:
            section["ascent_image_abs"] = f"{STATIC_ABS}images/ascent-{peak.code.lower()}-focus.png"

        # (4) peak distribution chart
        if stage >= 4:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                path = tmp.name
            generate_peak_mountain_chart(peak.name, get_peak_rating_distribution(assessment, peak.code), path)
            temp_paths.append(path)
            section["chart_data_uri"] = png_path_to_data_uri(path)

        # (5/6) per-question rows (+ charts at 6)
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

    # Summary (when scores exist)
    summary_text = ""
    if stage >= 1 and peak_sections:
        peak_score_summary, summary_text, low_row, high_row = compute_summary_and_display_rows(peak_sections)
        logger.info("[ASYNC] summary order=%s low=%s high=%s",
                    [r["code"] for r in peak_score_summary],
                    low_row and low_row.get("code"),
                    high_row and high_row.get("code"))
    else:
        peak_score_summary = [{"name": p["name"], "score": 0, "range": "—"} for p in peaks]

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
    # Keep if some downstream helper expects it; otherwise fine to remove.
    request._docraptor_ctx = ctx

    html = get_template("pdfexport/finalreport_docraptor.html").render(ctx)
    logger.info("[PDF] HTML size=%s bytes, img_count=%s", len(html), html.count("<img"))

    # -----------------------------
    # Queue async DocRaptor job
    # -----------------------------
    pretty_name, slug_name = build_report_filenames(assessment)
    filename = slug_name

    client = docraptor.DocApi()
    client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY
    baseurl = request.build_absolute_uri("/")

    try:
        t0_docraptor = time.monotonic()
        job = client.create_async_doc({
            "test": bool(getattr(settings, "DOCRAPTOR_TEST", True)),
            "document_type": "pdf",
            "name": filename,
            "document_content": html,
            "prince_options": {
                "media": "print",
                "baseurl": baseurl,
            },
        }, _request_timeout=(10, 700))
        logger.info("[PDF] DocRaptor job queued in %.2fs", time.monotonic() - t0_docraptor)

        docraptor_status_id = getattr(job, "docraptor_status_id", None)
        if not docraptor_status_id:
            logger.error("DocRaptor returned no docraptor_status_id")
            return JsonResponse({"ok": False, "error": "docraptor_status_id"}, status=502)

        # Cache meta so /pdfexport/docraptor/download/<docraptor_status_id>/ knows how to upload/name
        cache.set(
            f"docraptor:{docraptor_status_id}",
            {"assessment_id": assessment.id, "filename": filename, "pretty_name": pretty_name},
            timeout=60 * 60,
        )

        # Persist state on FinalReport so your polling view can check progress
        fr.docraptor_status_id = docraptor_status_id
        fr.size_bytes = None
        fr.save(update_fields=["docraptor_status_id", "size_bytes"])

        return JsonResponse({"ok": True, "docraptor_status_id": docraptor_status_id}, status=200)

    except ApiException as e:
        logger.exception("DocRaptor API error")
        return JsonResponse({"ok": False, "error": "docraptor_api", "detail": str(e)}, status=502)
    except Exception as e:
        logger.exception("Unexpected error during DocRaptor enqueue")
        return JsonResponse({"ok": False, "error": "unexpected", "detail": str(e)}, status=500)
    finally:
        for p in temp_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        logger.info("[PDF] final_report_docraptor_start total time %.2fs", time.monotonic() - t0_total)

