from django.contrib import admin
from .models import Team, TeamMember

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'team')
    search_fields = ('name', 'email', 'team__name')
    list_filter = ('team',)

admin.site.register(Team)