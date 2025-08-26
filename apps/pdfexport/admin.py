from django.contrib import admin
from .models import FinalReport

@admin.register(FinalReport)
class FinalReportAdmin(admin.ModelAdmin):
    list_display = ("assessment", "s3_key", "size_bytes", "created_at")
    search_fields = ("assessment__team__name", "s3_key")