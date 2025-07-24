from weasyprint import HTML
from django.template.loader import render_to_string
from django.conf import settings

# Create PDF
def render_pdf(assessment, context):
    html_string = render_to_string('pdfexport/report_pdf.html', context)
    html = HTML(string=html_string, base_url=settings.BASE_DIR)
    pdf_file = html.write_pdf()
    return pdf_file
