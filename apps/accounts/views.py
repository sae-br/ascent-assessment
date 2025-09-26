from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.utils import timezone
from django.http import HttpResponse, HttpResponseBadRequest


from django.contrib import messages
from django.conf import settings
from .forms import CustomUserCreationForm
from django import forms
from anymail.message import AnymailMessage
import datetime

import logging
logger = logging.getLogger(__name__)

from django.views.decorators.http import require_POST
from django.db import transaction
from django.views.generic import TemplateView
from django.urls import reverse


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
                "currentyear": timezone.now().year,
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
                "currentyear": timezone.now().year,
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
            "confirm_delete": request.GET.get("confirm_delete") == "1",
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
        "currentyear": timezone.now().year,
    }
    # Let Anymail raise if there's an API error; caller will catch/log
    msg.send()

@login_required
@require_POST
def delete_account(request):
    """
    Permanently delete the signed-in user's account.

    Notes on cascades:
    - Team.admin -> User uses on_delete=CASCADE
    - Assessment.team -> Team uses on_delete=CASCADE
    - FinalReport.assessment -> Assessment uses on_delete=CASCADE
    - TeamMember.team -> Team uses on_delete=CASCADE
    - AssessmentParticipant.assessment -> Assessment uses on_delete=CASCADE

    Therefore deleting the User will cascade to Teams, Assessments, FinalReports,
    TeamMembers, and AssessmentParticipants automatically.
    """
    user = request.user

    # Require explicit confirmation via checkbox
    if request.method != "POST" or "acknowledge" not in request.POST:
        messages.error(request, "You must confirm the deletion before continuing.")
        return redirect(f"{reverse('accounts:account_settings')}?confirm_delete=1")

    # Stash some info to log/audit
    user_pk = user.pk
    user_repr = f"{user.username} <{user.email}>"

    # Delete the user and rely on database cascades defined in models
    with transaction.atomic():
        user.delete()

    # Log out after deletion to clear any cached auth in the session
    logout(request)
    logger.info("Deleted user %s (pk=%s) via self-service; cascades applied.", user_repr, user_pk)

    return redirect("accounts:account_deleted")

@login_required
def delete_confirm_partial(request):
    if request.method != "GET":
        return HttpResponseBadRequest("GET only")
    return render(request, "accounts/_delete_confirm.html")

@login_required
def delete_confirm_cancel(request):
    if request.method != "GET":
        return HttpResponseBadRequest("GET only")
    return render(request, "accounts/account_settings_delete_button.html")


class AccountDeletedView(TemplateView):
    template_name = "accounts/account_deleted.html"
