from django.db import models
from django.contrib.auth.models import User
import uuid

class Team(models.Model):
    name = models.CharField(max_length=100)
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teams')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class TeamMember(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    unique_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    has_submitted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.email})"