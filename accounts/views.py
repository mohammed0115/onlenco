from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import SignUpForm, EmailLoginForm


@require_http_methods(["GET", "POST"])
def auth_view(request):
    """Combined sign-in / sign-up page. The mode is controlled by either
    the `mode` querystring (?mode=signup) or the form's hidden `mode` field."""

    if request.user.is_authenticated:
        return redirect("dashboard")

    mode = request.POST.get("mode") or request.GET.get("mode") or "signin"
    if mode not in ("signin", "signup"):
        mode = "signin"

    signin_form = EmailLoginForm(request)
    signup_form = SignUpForm()

    if request.method == "POST":
        if mode == "signup":
            signup_form = SignUpForm(request.POST)
            if signup_form.is_valid():
                user = signup_form.save()
                # Authenticate properly so the session is bound
                user = authenticate(
                    request,
                    username=signup_form.cleaned_data["email"],
                    password=signup_form.cleaned_data["password"],
                )
                if user is not None:
                    login(request, user)
                    messages.success(request, "Account created! You're in.")
                    return redirect("dashboard")
        else:
            signin_form = EmailLoginForm(request, data=request.POST)
            if signin_form.is_valid():
                login(request, signin_form.get_user())
                return redirect("dashboard")
            else:
                messages.error(request, "Invalid email or password.")

    return render(request, "accounts/auth.html", {
        "mode": mode,
        "signin_form": signin_form,
        "signup_form": signup_form,
    })


@login_required
@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    return redirect("home")
