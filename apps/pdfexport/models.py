from django.db import models
from django.conf import settings
from apps.assessments.models import Assessment

class FinalReport(models.Model):
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE, related_name="final_report")
    s3_key = models.CharField(max_length=512)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def s3_url(self):
        # non-public; serve via presigned URL or through Django view
        return f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{self.s3_key}"