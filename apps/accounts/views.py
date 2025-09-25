from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .forms import CustomUserCreationForm
from django import forms
from anymail.message import AnymailMessage
import datetime

import logging
logger = logging.getLogger(__name__)

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    elif request.method == "POST":
        form = CustomUserCreationForm(request.POST)  
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "New user created account.")
            # --- Mailgun via Anymail: notify superadmin ---
            admin_msg = AnymailMessage(
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.SUPERADMIN_EMAIL], # Change this if new user sign ups should be monitored by someone else
            )
            admin_msg.template_id = "new-user-alert"  # Mailgun template name
            admin_msg.merge_global_data = {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "created_at": user.date_joined.strftime("%B %d, %Y %H:%M %Z"),
                "currentyear": datetime.datetime.now().year,
            }
            admin_msg.send()

            # --- Mailgun via Anymail: welcome email to the user ---
            welcome = AnymailMessage(
                subject="Welcome to Ascent Assessment",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            welcome.template_id = "new-user-welcome"  # Mailgun template name
            welcome.merge_global_data = {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "currentyear": datetime.datetime.now().year,
            }
            welcome.send()
            return redirect("dashboard:home")
    else:
        form = CustomUserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    elif request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "Login successful.")
            return redirect("dashboard:home")
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return render(request, "accounts/logout.html")

class UpdateAccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email"]

@login_required
def account_settings(request):
    user = request.user

    if request.method == "POST":
        update_form = UpdateAccountForm(request.POST, instance=user)
        password_form = PasswordChangeForm(user, request.POST)

        if "update_account" in request.POST and update_form.is_valid():
            update_form.save()
            messages.success(request, "Account updated.")
            return redirect("accounts:account_settings")

        elif "change_password" in request.POST and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)  # keep the user logged in
            # Try to send the confirmation email; log (but don't break UX) on failure
            try:
                send_password_change_confirmation(user)
                messages.success(
                    request,
                    "Password changed. We've emailed you a confirmation."
                )
            except Exception as e:
                logger.warning("Password change email failed for %s: %s", user.pk, e)
                messages.success(
                    request,
                    "Password changed."
                )
            return redirect("accounts:account_settings")

    else:
        update_form = UpdateAccountForm(instance=user)
        password_form = PasswordChangeForm(user)

    return render(
        request,
        "accounts/account_settings.html",
        {
            "update_form": update_form,
            "password_form": password_form,
        },
    )

def send_password_change_confirmation(user):
    msg = AnymailMessage(
        # Subject set in MailGun
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.template_id = "password-change-confirm"  # Mailgun template name
    msg.merge_global_data = {
        "username": user.username,
        "first_name": getattr(user, "first_name", "") or "",
        "last_name": getattr(user, "last_name", "") or "",
        "currentyear": datetime.datetime.now().year,
    }
    # Let Anymail raise if there's an API error; caller will catch/log
    msg.send()