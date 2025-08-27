from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings

from apps.pdfexport.models import FinalReport
from apps.pdfexport.utils.storage import S3Uploader


@login_required
def reports_overview(request):
    """
    Show a list of reports generated for teams owned by the current user.
    Ordered by most recent first.
    """
    reports = (
        FinalReport.objects
        .filter(assessment__team__admin=request.user)
        .exclude(id__isnull=True)
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
        # Nothing uploaded yet — for now, show 404. (We can enhance to regenerate later.)
        from django.http import Http404
        raise Http404("Report file is not available yet.")

    uploader = S3Uploader(
        bucket=settings.AWS_STORAGE_BUCKET_NAME,
        region=settings.AWS_S3_REGION_NAME,
    )
    url = uploader.presign_get(fr.s3_key, expires_seconds=300)
    return redirect(url)