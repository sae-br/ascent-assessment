from django.template.loader import get_template
from django.conf import settings
from django.http import HttpResponse
from weasyprint import HTML, CSS
from apps.reports.models import PeakActions, PeakInsights, ResultsSummary
from apps.assessments.models import Peak, Question, Answer, Assessment
from apps.pdfexport.utils.context import get_report_context_data
from apps.pdfexport.utils.charts import (
    get_peak_rating_distribution,
    generate_peak_distribution_chart,
    generate_question_bar_chart
)
import tempfile
import os

def generate_final_report_pdf(request, assessment_id):
    # Get base context (assessment and peaks)
    base_context = get_report_context_data(assessment_id)
    assessment = base_context["assessment"]
    peaks = base_context["peaks"]

    peak_sections = []
    temp_chart_paths = []

    # Create a section for each peak
    for peak in peaks:
        # Get rating distribution data
        percentages = get_peak_rating_distribution(assessment, peak.code)

        # Create a temporary PNG path for the chart
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
            output_path = tmpfile.name

        # Generate chart and save to output_path
        generate_peak_distribution_chart(peak.name, percentages, output_path)

        # Score is the average of the answers in this peak (already calculated)
        score = sum((i * p) for i, p in enumerate(percentages)) / 100  # weighted average
        percentage_score = round(score * 100 / 3)  # Converts 0–3 scale to 0–100

        # Determine range label based on thresholds
        if percentage_score < 34:
            range_label = "LOW"
        elif percentage_score < 67:
            range_label = "MEDIUM"
        else:
            range_label = "HIGH"

        # Fetch insights for this peak and range
        try:
            insight_entry = PeakInsights.objects.get(peak=peak.code, range_label=range_label)
            insights = insight_entry.insight_text
        except PeakInsights.DoesNotExist:
            insights = "No insights available."
        
        # Fetch data for questions and bar charts
        question_data = []
        questions = Question.objects.filter(peak=peak)

        # Get all participants for this assessment
        participants = assessment.participants.all()
        answers = Answer.objects.filter(participant__in=participants)

        for q in questions:
            # Get all answers for this question from this assessment
            question_answers = answers.filter(question=q)

            # Count responses per rating (0 to 3)
            rating_counts = [0, 0, 0, 0]
            for answer in question_answers:
                if 0 <= answer.value <= 3:
                    rating_counts[answer.value] += 1

            # Calculate health percentage
            total = sum(rating_counts)
            if total > 0:
                weighted = sum(i * count for i, count in enumerate(rating_counts))
                health_pct = round((weighted / total) * 100 / 3)
            else:
                health_pct = 0

            # Generate bar chart image
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as chart_file:
                chart_path = chart_file.name
            generate_question_bar_chart(q.text, rating_counts, chart_path)
            temp_chart_paths.append(chart_path)  

            question_data.append({
                "text": q.text,
                "health_percentage": health_pct,
                "chart_path": chart_path
            })

        # Fetch suggested actions for this peak and range
        actions = PeakActions.objects.filter(peak=peak.code, range_label=range_label).first()

        # Gather the dynamic elements
        peak_sections.append({
            "name": peak.name,
            "code": peak.code,
            "chart_path": output_path,
            "range_label": range_label,
            "score": percentage_score,
            "insights": insights,
            "actions": actions.action_text if actions else "No actions available.",
            "ascent_image": os.path.join(settings.BASE_DIR, "apps/pdfexport/static/images", f"ascent-{peak.code}-focus.png"),
            "questions": question_data,
        })
        peak_score_summary = sorted(
            [{"code": p["code"], "name": p["name"], "score": p["score"], "range": p["range_label"]} for p in peak_sections],
            key=lambda x: x["score"]
        )
        temp_chart_paths.append(output_path)

        # Get Highest and Lowest peaks and related Results Summary
        lowest_peak_code = peak_score_summary[0]["code"]
        highest_peak_code = peak_score_summary[-1]["code"]

        try:
            results_summary = ResultsSummary.objects.get(high_peak=highest_peak_code, low_peak=lowest_peak_code)
            summary_text = results_summary.summary_text
        except ResultsSummary.DoesNotExist:
            summary_text = "No summary available for this combination."

    # Assemble context
    context = {
        "assessment": assessment,
        "team_name": assessment.team.name,
        "deadline": assessment.deadline,
        "peak_sections": peak_sections,
        "peak_score_summary": peak_score_summary,
        "summary_text": summary_text,
    }

    # Load HTML template
    template = get_template("pdfexport/finalreport.html")
    html_string = template.render(context)

    # Load CSS
    css_path = os.path.join(settings.STATIC_ROOT, 'pdfexport/finalreport.css')
    css = CSS(filename=css_path)

    # Render PDF
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as output:
        html.write_pdf(output.name, stylesheets=[css])
        output.seek(0)
        pdf = output.read()

    # Clean up chart image files
    for path in temp_chart_paths:
        try:
            os.remove(path)
        except OSError:
            pass

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "inline; filename=team-report.pdf"
    return response