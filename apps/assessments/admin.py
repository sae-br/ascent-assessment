from django.contrib import admin
from .models import Peak, Question, Answer, Assessment, AssessmentParticipant

@admin.register(Peak)
class PeakAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'peak', 'order',)
    list_filter = ('peak',)
    ordering = ('peak', 'order',)

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('participant', 'question', 'value', 'submitted_at')
    list_filter = ('participant__assessment', 'question__peak')
    search_fields = ('participant__team_member__name',)

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        'team', 'deadline', 'created_at',
        'created_by__user', 'responses', 'has_report',
        'id',
    )
    list_filter = ('team',)
    search_fields = ('team__name',)

    list_select_related = (
        "team",
        "team__admin",
    )

    @admin.display(description="Created by (email)", ordering="team__admin__email")
    def created_by__user(self, obj):
        team_admin = getattr(obj.team, "admin", None)
        return getattr(team_admin, "email", "—")

    @admin.display(description="Responses")
    def responses(self, obj):
        qs = obj.participants.all()
        total = qs.count()
        submitted = qs.filter(has_submitted=True).count()
        return f"{submitted} / {total}"

    @admin.display(boolean=True, description="Report")
    def has_report(self, obj):
        """True if a FinalReport exists for this assessment."""
        try:
            from apps.pdfexport.models import FinalReport
            return FinalReport.objects.filter(assessment=obj).exists()
        except Exception:
            # Fallback if related name is available but import path changes
            rel = getattr(obj, "final_reports", None) or getattr(obj, "finalreport_set", None)
            return bool(rel and rel.exists())

@admin.register(AssessmentParticipant)
class AssessmentParticipantAdmin(admin.ModelAdmin):
    list_display = ('team_member', 'assessment', 'has_submitted', 'token',)
    readonly_fields = ('token',)
    list_filter = ('assessment__team', 'has_submitted',)
    search_fields = ('team_member__name', 'team_member__email', 'assessment__team__name',)