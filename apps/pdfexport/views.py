from django.template.loader import get_template
from django.conf import settings
from django.http import HttpResponse
from weasyprint import HTML, CSS
from apps.pdfexport.utils.context import get_report_context_data
from apps.pdfexport.utils.charts import (
    get_peak_rating_distribution,
    generate_peak_distribution_chart
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

    for peak in peaks:
        # Get rating distribution data
        percentages = get_peak_rating_distribution(assessment, peak.code)

        # Create a temporary PNG path for the chart
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
            output_path = tmpfile.name

        # Generate chart and save to output_path
        generate_peak_distribution_chart(peak.name, percentages, output_path)

        peak_sections.append({
            "name": peak.name,
            "code": peak.code,
            "chart_path": output_path,
        })
        temp_chart_paths.append(output_path)

    # Assemble context
    context = {
        "assessment": assessment,
        "team_name": assessment.team.name,
        "deadline": assessment.deadline,
        "peak_sections": peak_sections,
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