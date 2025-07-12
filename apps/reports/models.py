from django.db import models
from apps.assessments.models import Peak

PEAK_CHOICES = [
    ('CC', 'Collaborative Culture'),
    ('LA', 'Leadership Accountability'),
    ('SM', 'Strategic Momentum'),
    ('TM', 'Talent Magnetism'),
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
    RANGE_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    ]
    range_label = models.CharField(max_length=10, choices=RANGE_CHOICES, unique=True)
    summary_text = models.TextField()

    def __str__(self):
        return f"All {self.get_range_label_display()}"


class PeakRange(models.Model):
    peak = models.ForeignKey(Peak, on_delete=models.CASCADE)
    low_threshold = models.PositiveIntegerField()
    medium_threshold = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.get_peak_display()} thresholds"


class PeakInsight(models.Model):
    peak = models.CharField(max_length=2, choices=PEAK_CHOICES, unique=True)
    insight_text = models.TextField()

    def __str__(self):
        return f"{self.get_peak_display()} Insight"


class PeakAction(models.Model):
    peak = models.CharField(max_length=2, choices=PEAK_CHOICES, unique=True)
    action_text = models.TextField()

    def __str__(self):
        return f"{self.get_peak_display()} Action"