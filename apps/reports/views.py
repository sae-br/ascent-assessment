from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect

from apps.pdfexport.models import FinalReport
from apps.pdfexport.utils.storage import S3Uploader
from apps.pdfexport.views import build_report_filenames


@login_required
def reports_overview(request):
    """
    Show a list of reports generated for teams owned by the current user.
    Ordered by most recent first.
    """
    reports = (
        FinalReport.objects
        .filter(assessment__team__admin=request.user)
        .filter(s3_key__isnull=False).exclude(s3_key="")
        .select_related('assessment', 'assessment__team')
        .order_by('-created_at')
    )
    return render(request, 'reports/overview.html', {
        'reports': reports,
    })


@login_required
def download_report(request, report_id: int):
    """
    Redirect to a short-lived, pre-signed S3 URL for this report's PDF.
    Only the team admin who owns the assessment may access it.
    """
    fr = get_object_or_404(
        FinalReport,
        id=report_id,
        assessment__team__admin=request.user,
    )

    if not fr.s3_key:
        from django.http import Http404
        raise Http404("Report file is not available yet.")

    # Build a user-friendly filename like "Imperials – September 2025.pdf"
    pretty_name, _slug_name = build_report_filenames(fr.assessment)

    uploader = S3Uploader(
        bucket=settings.AWS_STORAGE_BUCKET_NAME,
        region=settings.AWS_S3_REGION_NAME,
        access_key=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        secret_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
    )

    url = uploader.presign_get(
        fr.s3_key,
        expires_seconds=300,
        pretty_filename=pretty_name,
        content_type="application/pdf",
    )
    return redirect(url)