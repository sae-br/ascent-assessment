# # WeasyPrint Version
# from django.template.loader import get_template
# from django.conf import settings
# from django.http import HttpResponse
# from weasyprint import HTML, CSS
# from apps.reports.models import PeakActions, PeakInsights, ResultsSummary
# from apps.assessments.models import Peak, Question, Answer, Assessment
# from apps.pdfexport.utils.context import get_report_context_data
# from apps.pdfexport.utils.charts import (
#     get_peak_rating_distribution,
#     generate_peak_distribution_chart,
#     generate_question_bar_chart
# )
# import tempfile
# import os

# def generate_final_report_pdf(request, assessment_id):
#     # Get base context (assessment and peaks)
#     base_context = get_report_context_data(assessment_id)
#     assessment = base_context["assessment"]
#     peaks = base_context["peaks"]

#     peak_sections = []
#     temp_chart_paths = []

#     # Create a section for each peak
#     for peak in peaks:
#         # Get rating distribution data
#         percentages = get_peak_rating_distribution(assessment, peak.code)

#         # Create a temporary PNG path for the chart
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
#             output_path = tmpfile.name

#         # Generate chart and save to output_path
#         generate_peak_distribution_chart(peak.name, percentages, output_path)

#         # Score is the average of the answers in this peak (already calculated)
#         score = sum((i * p) for i, p in enumerate(percentages)) / 100  # weighted average
#         percentage_score = round(score * 100 / 3)  # Converts 0–3 scale to 0–100

#         # Determine range label based on thresholds
#         if percentage_score < 34:
#             range_label = "LOW"
#         elif percentage_score < 67:
#             range_label = "MEDIUM"
#         else:
#             range_label = "HIGH"

#         # Fetch insights for this peak and range
#         try:
#             insight_entry = PeakInsights.objects.get(peak=peak.code, range_label=range_label)
#             insights = insight_entry.insight_text
#         except PeakInsights.DoesNotExist:
#             insights = "No insights available."
        
#         # Fetch data for questions and bar charts
#         question_data = []
#         questions = Question.objects.filter(peak=peak)

#         # Get all participants for this assessment
#         participants = assessment.participants.all()
#         answers = Answer.objects.filter(participant__in=participants)

#         for q in questions:
#             # Get all answers for this question from this assessment
#             question_answers = answers.filter(question=q)

#             # Count responses per rating (0 to 3)
#             rating_counts = [0, 0, 0, 0]
#             for answer in question_answers:
#                 if 0 <= answer.value <= 3:
#                     rating_counts[answer.value] += 1

#             # Calculate health percentage
#             total = sum(rating_counts)
#             if total > 0:
#                 weighted = sum(i * count for i, count in enumerate(rating_counts))
#                 health_pct = round((weighted / total) * 100 / 3)
#             else:
#                 health_pct = 0

#             # Generate bar chart image
#             with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as chart_file:
#                 chart_path = chart_file.name
#             generate_question_bar_chart(q.text, rating_counts, chart_path)
#             temp_chart_paths.append(chart_path)  

#             question_data.append({
#                 "text": q.text,
#                 "health_percentage": health_pct,
#                 "chart_path": chart_path
#             })

#         # Fetch suggested actions for this peak and range
#         actions = PeakActions.objects.filter(peak=peak.code, range_label=range_label).first()

#         # Gather the dynamic elements
#         peak_sections.append({
#             "name": peak.name,
#             "code": peak.code,
#             "chart_path": output_path,
#             "range_label": range_label,
#             "score": percentage_score,
#             "insights": insights,
#             "actions": actions.action_text if actions else "No actions available.",
#             "ascent_image": os.path.join(settings.BASE_DIR, "apps/pdfexport/static/images", f"ascent-{peak.code.lower()}-focus.png"),
#             "questions": question_data,
#         })
#         peak_score_summary = sorted(
#             [{"code": p["code"], "name": p["name"], "score": p["score"], "range": p["range_label"]} for p in peak_sections],
#             key=lambda x: x["score"]
#         )
#         temp_chart_paths.append(output_path)

#         # Get Highest and Lowest peaks and related Results Summary
#         lowest_peak_code = peak_score_summary[0]["code"]
#         highest_peak_code = peak_score_summary[-1]["code"]

#         try:
#             results_summary = ResultsSummary.objects.get(high_peak=highest_peak_code, low_peak=lowest_peak_code)
#             summary_text = results_summary.summary_text
#         except ResultsSummary.DoesNotExist:
#             summary_text = "No summary available for this combination."

#     # Assemble context
#     context = {
#         "assessment": assessment,
#         "team_name": assessment.team.name,
#         "deadline": assessment.deadline,
#         "peak_sections": peak_sections,
#         "peak_score_summary": peak_score_summary,
#         "summary_text": summary_text,
#     }

#     # Load HTML template
#     template = get_template("pdfexport/finalreport.html")
#     html_string = template.render(context)

#     # Load CSS
#     css_path = os.path.join(settings.STATIC_ROOT, 'pdfexport/finalreport.css')
#     css = CSS(filename=css_path)

#     # Render PDF
#     html = HTML(string=html_string, base_url=request.build_absolute_uri())
#     with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as output:
#         html.write_pdf(output.name, stylesheets=[css])
#         output.seek(0)
#         pdf = output.read()

#     # Clean up chart image files
#     for path in temp_chart_paths:
#         try:
#             os.remove(path)
#         except OSError:
#             pass

#     response = HttpResponse(pdf, content_type="application/pdf")
#     response["Content-Disposition"] = "inline; filename=team-report.pdf"
#     return response


# DocRaptor Version
from django.http import HttpResponse
from django.template.loader import get_template
from django.templatetags.static import static
from django.conf import settings
from django.utils.text import slugify

import os
import tempfile

from apps.reports.models import PeakActions, PeakInsights, ResultsSummary
from apps.assessments.models import Peak, Question, Answer, Assessment
from apps.pdfexport.utils.context import get_report_context_data
from apps.pdfexport.utils.charts import (
    get_peak_rating_distribution,
    generate_peak_distribution_chart,
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
    base = get_report_context_data(assessment_id)
    assessment = base["assessment"]
    ctx = {
        "STATIC_ABS": request.build_absolute_uri(static("")),
        "assessment": assessment,
        "team_name": assessment.team.name,
        "deadline": assessment.deadline,
        "peak_sections": [],
        "peak_score_summary": [],
        "summary_text": "",
    }
    return HttpResponse(get_template("pdfexport/finalreport_docraptor.html").render(ctx))


# TEMP BAREBONES DOCRAPTOR VIEW FOR TIMEOUT ISSUE
def generate_final_report_pdf_docraptor(request, assessment_id):
    t0_total = time.monotonic()
    logger.info("[PDF] Start render for assessment_id=%s", assessment_id)

    base = get_report_context_data(assessment_id)
    assessment = base["assessment"]
    STATIC_ABS = request.build_absolute_uri(static(""))

    # For now, skip the heavy peak loop — just pass empty lists
    ctx = {
        "STATIC_ABS": STATIC_ABS,
        "assessment": assessment,
        "team_name": assessment.team.name,
        "deadline": assessment.deadline,
        "peak_sections": [],
        "peak_score_summary": [],
        "summary_text": "",
    }

    html = get_template("pdfexport/finalreport_docraptor.html").render(ctx)
    html_len = len(html)
    img_count = html.count("<img")
    logger.info("[PDF] HTML size=%s bytes, img_count=%s", html_len, img_count)

    client = docraptor.DocApi()
    client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY
    baseurl = request.build_absolute_uri("/")

    t0_docraptor = time.monotonic()
    logger.info("[PDF] Calling DocRaptor...")
    try:
        result = client.create_doc({
            "test": True,
            "document_type": "pdf",
            "name": f"{slugify(assessment.team.name)}-{assessment.deadline:%Y-%m}.pdf",
            "document_content": html,
            "prince_options": {
                "media": "print",
                "baseurl": baseurl,
            },
        },
        _request_timeout=(10, 700)  # MEASURING: (connect_timeout, read_timeout) in seconds
        )
    except ApiException as e:
        logger.exception("DocRaptor API error")
        return HttpResponse(f"DocRaptor error: {e}", status=502)

    docraptor_dt = time.monotonic() - t0_docraptor
    logger.info("[PDF] DocRaptor returned in %.2f seconds", docraptor_dt)

    total_dt = time.monotonic() - t0_total
    logger.info("[PDF] Total view time %.2f seconds", total_dt)

    return HttpResponse(result, content_type="application/pdf")

# def generate_final_report_pdf_docraptor(request, assessment_id):
#     # MEASURING: Start logging size and time used, to find bottleneck areas
#     t0_total = time.monotonic()
#     logger.info("[PDF] Start render for assessment_id=%s", assessment_id)
    
#     # 0) Base context
#     base = get_report_context_data(assessment_id)
#     assessment = base["assessment"]
#     peaks = base["peaks"]

#     # absolute static base (e.g. https://orghealthascent.com/static/)
#     STATIC_ABS = request.build_absolute_uri(static(""))

#     peak_sections = []
#     temp_paths = []

#     # MEASURING: Log how large HTML payload is and how many img tags it has
#     html = get_template("pdfexport/finalreport_docraptor.html").render(ctx)
#     html_len = len(html)
#     img_count = html.count("<img")
#     logger.info("[PDF] HTML size=%s bytes, img_count=%s", html_len, img_count)

#     # 1) Build each peak section 
#     for peak in peaks:
#         # — rating spread chart —
#         percents = get_peak_rating_distribution(assessment, peak.code)
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
#             spread_png = tmp.name
#         generate_peak_distribution_chart(peak.name, percents, spread_png)
#         temp_paths.append(spread_png)
#         spread_data_uri = png_path_to_data_uri(spread_png)

#         # score on 0–100
#         score0_3 = sum((i * p) for i, p in enumerate(percents)) / 100.0  # weighted avg on 0–3
#         percentage_score = round(score0_3 * 100 / 3)
#         if percentage_score < 34:
#             range_label = "LOW"
#         elif percentage_score < 67:
#             range_label = "MEDIUM"
#         else:
#             range_label = "HIGH"

#         # insights/actions
#         insight = PeakInsights.objects.filter(peak=peak.code, range_label=range_label).first()
#         actions = PeakActions.objects.filter(peak=peak.code, range_label=range_label).first()

#         # questions + per-question chart
#         q_rows = []
#         participants = assessment.participants.all()
#         answers = Answer.objects.filter(participant__in=participants)
#         for q in Question.objects.filter(peak=peak):
#             qa = answers.filter(question=q)
#             counts = [0, 0, 0, 0]
#             for a in qa:
#                 if 0 <= a.value <= 3:
#                     counts[a.value] += 1
#             total = sum(counts)
#             if total:
#                 weighted = sum(i * c for i, c in enumerate(counts))
#                 health_pct = round((weighted / total) * 100 / 3)
#             else:
#                 health_pct = 0

#             with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as qtmp:
#                 qpng = qtmp.name
#             generate_question_bar_chart(q.text, counts, qpng)
#             temp_paths.append(qpng)
#             q_rows.append({
#                 "text": q.text,
#                 "health_percentage": health_pct,
#                 "chart_data_uri": png_path_to_data_uri(qpng),
#             })

#         # focus image (absolute URL)
#         ascent_image_abs = f"{STATIC_ABS}images/ascent-{peak.code.lower()}-focus.png"

#         peak_sections.append({
#             "name": peak.name,
#             "code": peak.code,
#             "chart_data_uri": spread_data_uri,
#             "range_label": range_label,
#             "score": percentage_score,
#             "insights": insight.insight_text if insight else "No insights available.",
#             "actions": actions.action_text if actions else "No actions available.",
#             "ascent_image_abs": ascent_image_abs,
#             "questions": q_rows,
#         })

#     # order + summary
#     peak_score_summary = sorted(
#         [{"code": p["code"], "name": p["name"], "score": p["score"], "range": p["range_label"]} for p in peak_sections],
#         key=lambda x: x["score"]
#     )
#     lowest = peak_score_summary[0]["code"]
#     highest = peak_score_summary[-1]["code"]
#     rs = ResultsSummary.objects.filter(high_peak=highest, low_peak=lowest).first()
#     summary_text = rs.summary_text if rs else "No summary available for this combination."

#     # 2) Render HTML
#     ctx = {
#         "STATIC_ABS": STATIC_ABS,
#         "assessment": assessment,
#         "team_name": assessment.team.name,
#         "deadline": assessment.deadline,
#         "peak_sections": peak_sections,
#         "peak_score_summary": peak_score_summary,
#         "summary_text": summary_text,
#     }
#     html = get_template("pdfexport/finalreport_docraptor.html").render(ctx)

#     # MEASURING: Marking start of DocRaptor call
#     t0_docraptor = time.monotonic()
#     logger.info("[PDF] Calling DocRaptor...")

#     # 3) Call DocRaptor 
#     client = docraptor.DocApi()
#     client.api_client.configuration.username = settings.DOCRAPTOR_API_KEY

#     baseurl = request.build_absolute_uri("/")  # https://orghealthascent.com/

#     try:
#         # Can also pass "document_url" if you expose the HTML at a route; here we send content directly
#         result = client.create_doc({
#             "test": True,  # Change when done testing
#             "document_type": "pdf",
#             "name": f"{slugify(assessment.team.name)}-{assessment.deadline:%Y-%m}.pdf",
#             "document_content": html,
#             "prince_options": {
#                 "media": "print",
#                 "baseurl": baseurl,
#                 # Turn on JS later if/when we move to Chart.js:
#                 # "javascript": True,
#             },
#         })
#         # MEASURING: remote render duration
#         docraptor_dt = time.monotonic() - t0_docraptor
#         logger.info("[PDF] DocRaptor returned in %.2f seconds", docraptor_dt)
#     except ApiException as e:
#         logger.exception("DocRaptor API error")
#         return HttpResponse(
#             f"DocRaptor error {getattr(e, 'status', '')}: {getattr(e, 'body', e)}",
#             status=502
#         )
#     except Exception as e:
#         logger.exception("Unexpected error generating DocRaptor PDF")
#         return HttpResponse(f"Unexpected error: {e}", status=500)
#     finally:
#         # 4) cleanup temp PNGs
#         for p in temp_paths:
#             try:
#                 os.remove(p)
#             except OSError:
#                 pass

#     # MEASURING: get total wall-clock for inside this view
#     total_dt = time.monotonic() - t0_total
#     logger.info("[PDF] Total view time %.2f seconds", total_dt)

#     return HttpResponse(result, content_type="application/pdf")