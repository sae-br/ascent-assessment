from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings
from django.urls import reverse
from anymail.message import AnymailMessage
import datetime

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

class MailgunPasswordResetForm(PasswordResetForm):

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        # Build the absolute reset URL from the provided context
        reset_path = reverse(
            "password_reset_confirm",
            args=[context["uid"], context["token"]],
        )
        reset_url = f"{context['protocol']}://{context['domain']}{reset_path}"

        msg = AnymailMessage(
            subject="Reset your Ascent Assessment password",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.template_id = "password-reset"  # Mailgun template
        msg.merge_global_data = {
            "username": context.get("user").get_username() if context.get("user") else "",
            "reset_url": reset_url,
            "site_name": context.get("site_name", "Ascent Assessment"),
            "valid_days": 1,  # purely for template copy; adjust as desired
            "currentyear": datetime.datetime.now().year,
        }
        msg.send()