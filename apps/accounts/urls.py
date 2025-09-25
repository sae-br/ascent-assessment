from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from .forms import MailgunPasswordResetForm
from . import views

app_name = "accounts"

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.account_settings, name='account_settings'),
    path('delete/', views.delete_account, name='delete_account'),
    path("delete/confirm/", views.delete_confirm_partial, name="delete_confirm_partial"),
    path("delete/cancel/", views.delete_confirm_cancel, name="delete_confirm_cancel"),
    path("deleted/", views.AccountDeletedView.as_view(), name="account_deleted"),

    # Password reset views
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            form_class=MailgunPasswordResetForm,
            template_name="accounts/password_reset_form.html",  # your page with the email field
            email_template_name=None,            # not used (Mailgun template instead)
            subject_template_name=None,          # not used
            html_email_template_name=None,       # not used
            success_url="/accounts/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url="/accounts/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]