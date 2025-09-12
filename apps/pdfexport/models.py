from django.db import models
from django.conf import settings
from apps.assessments.models import Assessment
from django.utils.text import slugify

class FinalReport(models.Model):
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE, related_name="final_report")
    docraptor_status_id = models.CharField(max_length=64, blank=True, null=True)
    s3_key = models.CharField(max_length=512, blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, default="")
    size_bytes = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def s3_url(self):
        # non-public; serve via presigned URL or through Django view
        return f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{self.s3_key}"