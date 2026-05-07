from django import forms

from .models import PaymentMethodAccount, PaymentSubmission, PLAN_DETAILS


class PaymentSubmissionForm(forms.ModelForm):
    class Meta:
        model = PaymentSubmission
        fields = ["plan", "method", "transaction_reference", "screenshot"]
        widgets = {
            "transaction_reference": forms.TextInput(
                attrs={"placeholder": "e.g. TRX-908123 or last 4 digits"}
            ),
        }

    def clean_screenshot(self):
        f = self.cleaned_data["screenshot"]
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Image must be 5 MB or smaller.")
        allowed = {"image/png", "image/jpeg", "image/webp", "image/gif"}
        content_type = getattr(f, "content_type", "") or ""
        if content_type and content_type not in allowed:
            raise forms.ValidationError(
                "Only PNG, JPEG, WEBP, or GIF images are accepted."
            )
        return f

    def clean_method(self):
        method = self.cleaned_data["method"]
        if not PaymentMethodAccount.objects.filter(method=method, is_active=True).exists():
            raise forms.ValidationError("This payment method is not currently available.")
        return method

    def save(self, user, commit=True):
        obj = super().save(commit=False)
        obj.user = user
        obj.amount_sdg = PLAN_DETAILS[obj.plan]["price_sdg"]
        if commit:
            obj.save()
        return obj
