from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()


# Bot mitigation on signup is handled in accounts/views.py — per-IP
# rate limiting plus optional hCaptcha. Two earlier in-form heuristics
# were removed because they produced false positives that silently
# blocked real signups:
#   - a hidden `website` honeypot — browser autofill and password
#     managers fill off-screen hidden fields;
#   - a `form_started_at` page-load timestamp — it compared a value
#     from the *client* clock against the *server* clock, so clock
#     skew (or a fast autofill submit) wrongly rejected real users.


class SignUpForm(forms.Form):
    """Custom signup form. We use email as the canonical login identifier
    but copy it into the `username` field too (Django's default User
    model requires `username`)."""

    full_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(max_length=255, required=True)
    password = forms.CharField(min_length=8, max_length=100, widget=forms.PasswordInput)

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
