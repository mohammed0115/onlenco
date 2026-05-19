import time

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()


# Bots usually submit signup forms either instantly (under a second) or
# from a script that fills every field they can find. We catch both:
#   1. A hidden `website` honeypot — only filled by bots that fill
#      everything blindly.
#   2. A signed timestamp the template renders into a hidden field
#      when the page loads. Submissions under MIN_FILL_SECONDS reject.
HONEYPOT_FIELD = "website"
SIGNUP_FORM_TIMESTAMP_FIELD = "form_started_at"
MIN_FILL_SECONDS = 3


class SignUpForm(forms.Form):
    """Custom signup form. We use email as the canonical login identifier
    but copy it into the `username` field too (Django's default User
    model requires `username`)."""

    full_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(max_length=255, required=True)
    password = forms.CharField(min_length=6, max_length=100, widget=forms.PasswordInput)
    # Honeypot — must be left empty. Hidden via CSS in the template.
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    # Set by the template on page load. We reject submissions where the
    # gap between page-load and submit is unrealistically short.
    form_started_at = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        if (self.cleaned_data.get("website") or "").strip():
            # Don't tell the bot what tripped it — pretend the email is taken.
            raise forms.ValidationError("An account with this email already exists.")
        return ""

    def clean_form_started_at(self):
        started = self.cleaned_data.get("form_started_at") or 0
        if not started:
            # Older client (no JS) or stale page — let it through.
            return started
        elapsed = int(time.time()) - int(started)
        if elapsed < MIN_FILL_SECONDS:
            raise forms.ValidationError("Please take a moment to review the form.")
        if elapsed > 24 * 60 * 60:
            raise forms.ValidationError("Page expired — please refresh and try again.")
        return started

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or \
           User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self):
        email = self.cleaned_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            password=self.cleaned_data["password"],
        )
        # Profile is auto-created by the post_save signal — fill in the name
        user.profile.full_name = self.cleaned_data["full_name"]
        user.profile.save(update_fields=["full_name"])
        return user


class EmailLoginForm(AuthenticationForm):
    """Login form that accepts an email address in the username field."""

    username = forms.EmailField(label="Email", max_length=255)

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class EmailOTPForm(forms.Form):
    """6-digit code typed by the user from the verification email."""

    code = forms.CharField(
        label="Verification code",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
            "pattern": r"[0-9]{6}",
            "placeholder": "123456",
        }),
    )

    def clean_code(self):
        code = (self.cleaned_data["code"] or "").strip()
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError("Enter the 6-digit code from your email.")
        return code
