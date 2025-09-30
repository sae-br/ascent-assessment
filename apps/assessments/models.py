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
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE, related_name='assessments')
    deadline = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    launched_at = models.DateTimeField(null=True, blank=True)

    @property
    def pretty_name(self) -> str:
        """Human‑friendly label like "Leadership Team – September 2025" with a safe fallback.
        Uses an en dash and omits the date if it's missing.
        """
        team_name = getattr(self.team, "name", "Team") or "Team"
        if getattr(self, "deadline", None):
            return f"{team_name} – {self.deadline:%B %Y}"
        return team_name

    def __str__(self):
        return self.pretty_name
    
    @property
    def is_launched(self) -> bool:
        """Ensures assessments being created only get added to the model on launch.
        Keeps the db clean and avoids unusable assessment drafts being created.
        """
        return self.launched_at is not None


class AssessmentParticipant(models.Model):
    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="participants"
    )
    # Nullable so deleting a TeamMember won’t break running assessments
    team_member = models.ForeignKey(
        TeamMember, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assessment_links"
    )

    # Snapshots captured at launch (used for emails, labels, etc.)
    member_name = models.CharField(max_length=200, blank=True, default="")
    member_email = models.EmailField(blank=True, default="")

    has_submitted = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    last_invited_at = models.DateTimeField(null=True, blank=True, db_index=True)

    def display_name(self):
        # Prefer the snapshot; fall back to FK if present
        if self.member_name:
            return self.member_name
        return getattr(self.team_member, "name", "")

    def display_email(self):
        if self.member_email:
            return self.member_email
        return getattr(self.team_member, "email", "")

    def __str__(self):
        return f"{self.display_name() or 'Member'} for {self.assessment}"


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