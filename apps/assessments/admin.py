from django.contrib import admin
from .models import Peak, Question, Answer, Assessment, AssessmentParticipant

@admin.register(Peak)
class PeakAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'peak', 'order')
    list_filter = ('peak',)
    ordering = ('peak', 'order')

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('participant', 'question', 'value', 'submitted_at')
    list_filter = ('participant__assessment', 'question__peak')
    search_fields = ('participant__team_member__name',)

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('team', 'deadline', 'created_at')
    list_filter = ('team',)
    search_fields = ('team__name',)

@admin.register(AssessmentParticipant)
class AssessmentParticipantAdmin(admin.ModelAdmin):
    list_display = ('team_member', 'assessment', 'has_submitted', 'token')
    readonly_fields = ('token',)
    list_filter = ('assessment__team', 'has_submitted')
    search_fields = ('team_member__name', 'team_member__email', 'assessment__team__name')