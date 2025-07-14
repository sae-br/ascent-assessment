from django.contrib import admin
from .models import ResultsSummary, UniformRangeSummary, PeakInsights, PeakActions

@admin.register(ResultsSummary)
class ResultsSummaryAdmin(admin.ModelAdmin):
    list_display = ("high_peak", "low_peak")
    list_filter = ("high_peak", "low_peak")

@admin.register(UniformRangeSummary)
class UniformRangeSummaryAdmin(admin.ModelAdmin):
    list_display = ("range_label",)
    list_filter = ("range_label",)

@admin.register(PeakInsights)
class PeakInsightsAdmin(admin.ModelAdmin):
    list_display = ("peak",)
    list_filter = ("peak",)

@admin.register(PeakActions)
class PeakActionsAdmin(admin.ModelAdmin):
    list_display = ("peak",)
    list_filter = ("peak",)