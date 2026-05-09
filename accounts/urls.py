from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("", views.auth_view, name="auth"),
    path("logout/", views.logout_view, name="logout"),
    path("verify/<str:token>/", views.verify_email, name="verify_email"),
    path("verify-email/", views.verify_email_otp, name="verify_email_otp"),
    path("verify-email/resend/", views.resend_email_otp, name="resend_email_otp"),
    path("onboarding/", views.onboarding_choice, name="onboarding_choice"),
    path("onboarding/beginner/", views.onboarding_beginner, name="onboarding_beginner"),
    path("onboarding/placement/", views.onboarding_placement, name="onboarding_placement"),
    path("profile/", views.profile_view, name="profile"),
    # Password reset (Django's built-in flow + our email template)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="notifications/emails/password_reset.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url="/auth/password-reset/done/",
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
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url="/auth/password-reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
