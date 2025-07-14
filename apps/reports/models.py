from django.db import models
from markdownx.models import MarkdownxField

PEAK_CHOICES = [
    ('CC', 'Collaborative Culture'),
    ('LA', 'Leadership Accountability'),
    ('SM', 'Strategic Momentum'),
    ('TM', 'Talent Magnetism'),
]

RANGE_CHOICES = [
    ("LOW", "Low"),
    ("MEDIUM", "Medium"),
    ("HIGH", "High"),
]

class ResultsSummary(models.Model):
    high_peak = models.CharField(max_length=2, choices=PEAK_CHOICES)
    low_peak = models.CharField(max_length=2, choices=PEAK_CHOICES)
    summary_text = models.TextField()

    class Meta:
        unique_together = ("high_peak", "low_peak")

    def __str__(self):
        return f"High: {self.get_high_peak_display()}, Low: {self.get_low_peak_display()}"


class UniformRangeSummary(models.Model):
    range_label = models.CharField(max_length=10, choices=RANGE_CHOICES, unique=True)
    summary_text = models.TextField()

    def __str__(self):
        return f"All {self.get_range_label_display()}"


class PeakInsights(models.Model):
    peak = models.CharField(max_length=2, choices=PEAK_CHOICES)
    range_label = models.CharField(max_length=10, choices=RANGE_CHOICES)
    insight_text = MarkdownxField()

    class Meta:
        unique_together = ("peak", "range_label")

    def __str__(self):
        return f"{self.get_peak_display()} ({self.range_label}) Insight"


class PeakActions(models.Model):
    peak = models.CharField(max_length=2, choices=PEAK_CHOICES)
    range_label = models.CharField(max_length=10, choices=RANGE_CHOICES)
    action_text = MarkdownxField()

    class Meta:
        unique_together = ("peak", "range_label")

    def __str__(self):
        return f"{self.get_peak_display()} – {self.range_label.capitalize()} Actions"