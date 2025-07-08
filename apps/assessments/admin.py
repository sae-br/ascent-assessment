from django.contrib import admin
from .models import Peak, Question, Answer, Assessment

admin.site.register(Peak)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(Assessment)