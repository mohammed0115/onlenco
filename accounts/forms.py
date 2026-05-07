from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()


class SignUpForm(forms.Form):
    """Custom signup form. We use email as the canonical login identifier
    but copy it into the `username` field too (Django's default User
    model requires `username`)."""

    full_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(max_length=255, required=True)
    password = forms.CharField(min_length=6, max_length=100, widget=forms.PasswordInput)

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
