from django.contrib import admin
from .models import Team, TeamMember

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'team', 'has_submitted', 'unique_token')
    readonly_fields = ('unique_token',)

admin.site.register(Team)