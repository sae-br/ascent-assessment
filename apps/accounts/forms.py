from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from anymail.message import AnymailMessage
import datetime


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user

class MailgunPasswordResetForm(PasswordResetForm):
    def save(self, domain_override=None,
             subject_template_name=None,
             email_template_name=None,
             use_https=False,
             token_generator=default_token_generator,
             from_email=None,
             request=None,
             html_email_template_name=None,
             extra_email_context=None):
        """
        Send a Mailgun-templated reset email 
        """
        assert request is not None, "request is required to build absolute URL"

        for user in self.get_users(self.cleaned_data["email"]):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)

            path = reverse(
                "accounts:password_reset_confirm",
                kwargs={"uidb64": uid, "token": token},
            )
            reset_url = request.build_absolute_uri(path)

            msg = AnymailMessage(
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            msg.template_id = "password-reset"  # Mailgun template name
            msg.merge_global_data = {
                "username": user.get_username(),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "reset_url": reset_url,
                "currentyear": datetime.datetime.now().year,
            }
            msg.send()