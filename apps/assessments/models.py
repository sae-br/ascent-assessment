from django.db import models
from apps.teams.models import TeamMember, Team
from django.utils import timezone
import uuid

PEAK_CHOICES = [
    ('CC', 'Collaborative Culture'),
    ('LA', 'Leadership Accountability'),
    ('SM', 'Strategic Momentum'),
    ('TM', 'Talent Magnetism'),
]

class Peak(models.Model):
    code = models.CharField(max_length=2, unique=True, choices=PEAK_CHOICES)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Question(models.Model):
    peak = models.ForeignKey(Peak, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.peak.name}: {self.text[:60]}..."


class Assessment(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="assessments")
    deadline = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.team.name} - {self.deadline.strftime('%B %Y')}"


class AssessmentParticipant(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="participants")
    team_member = models.ForeignKey(TeamMember, on_delete=models.CASCADE, related_name="assessment_links")
    has_submitted = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"{self.team_member.name} for {self.assessment}"


class Answer(models.Model):
    participant = models.ForeignKey(AssessmentParticipant, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    value = models.IntegerField(choices=[
        (3, "Consistently true"),
        (2, "Somewhat true"),
        (1, "Somewhat untrue"),
        (0, "Consistently untrue"),
    ])
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('participant', 'question')

    def __str__(self):
        return f"{self.participant.team_member.name} → Q{self.question.id} = {self.value}"