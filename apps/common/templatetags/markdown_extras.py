import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def markdown(text):
    if not text:
        return ""
    return mark_safe(md.markdown(text))