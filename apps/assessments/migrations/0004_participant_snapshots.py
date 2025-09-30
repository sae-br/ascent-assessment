from django.db import migrations, models
from django.db.models import F

def backfill_participant_snapshots(apps, schema_editor):
    Participant = apps.get_model("assessments", "AssessmentParticipant")
    for p in Participant.objects.select_related("team_member"):
        if p.team_member and not p.member_name:
            p.member_name = p.team_member.name or ""
        if p.team_member and not p.member_email:
            p.member_email = p.team_member.email or ""
        p.save(update_fields=["member_name", "member_email"])

class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0003_assessment_launched_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessmentparticipant",
            name="member_name",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="assessmentparticipant",
            name="member_email",
            field=models.EmailField(max_length=254, blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="assessmentparticipant",
            name="team_member",
            field=models.ForeignKey(
                to="teams.teammember",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name="assessment_links",
            ),
        ),
        migrations.RunPython(backfill_participant_snapshots, migrations.RunPython.noop),
    ]