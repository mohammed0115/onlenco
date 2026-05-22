from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from courses.models import Course, Lesson, LessonResource
from payments.models import PaymentMethodAccount, PaymentSubmission
from placement.models import PlacementQuestion
from platform_admin.models import RISK_STATUS_CHOICES
from subscriptions.models import SubscriptionPlan


class RegisterTeacherForm(forms.Form):
    """Admin-side teacher registration. Password is generated server-side
    and emailed to the teacher; this form does not collect a password."""

    first_name = forms.CharField(max_length=80, label=_("First name"))
    last_name = forms.CharField(max_length=80, label=_("Last name"))
    email = forms.EmailField(max_length=254, label=_("Email"))
    email_confirm = forms.EmailField(max_length=254, label=_("Confirm email"))

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        User = get_user_model()
        if User.objects.filter(username=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account with this email already exists."))
        return email

    def clean_email_confirm(self):
        return (self.cleaned_data.get("email_confirm") or "").strip().lower()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("email") and cleaned.get("email_confirm"):
            if cleaned["email"] != cleaned["email_confirm"]:
                self.add_error("email_confirm", _("Email addresses do not match."))
        return cleaned


class StudentNoteForm(forms.Form):
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=2000)
    is_private = forms.BooleanField(required=False)


class StudentNotificationForm(forms.Form):
    title = forms.CharField(max_length=160)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), max_length=2000)


class StudentRiskForm(forms.Form):
    risk_status = forms.ChoiceField(choices=RISK_STATUS_CHOICES)


class AssignCourseForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.none())

    def __init__(self, *args, course_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = course_queryset or Course.objects.none()


class ExtendSubscriptionForm(forms.Form):
    days = forms.IntegerField(min_value=1, max_value=730, initial=30)


class PaymentRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=1000)


class PaymentRefundForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=1000)


class PaymentMethodAccountForm(forms.ModelForm):
    """Create / edit the bank or wallet account a student transfers to."""

    class Meta:
        model = PaymentMethodAccount
        fields = [
            "method", "label", "account_number", "account_holder",
            "instructions", "is_active", "sort_order",
        ]
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 3}),
        }


class CourseRejectForm(forms.Form):
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), max_length=2000)


class TeacherAssignCourseForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.order_by("title")


class CourseAssignTeacherForm(forms.Form):
    teacher = forms.ModelChoiceField(queryset=get_user_model().objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields["teacher"].queryset = User.objects.filter(groups__name="Teacher").distinct().order_by("email", "username")


class CourseEditorForm(forms.ModelForm):
    """Admin create / edit form for a Course. Slug is derived from title
    automatically on save; status + reviewer fields are managed by the
    workflow actions (approve / reject / publish / archive), not by this
    form. is_active and is_free stay editable because admins legitimately
    flip them outside the review flow.
    """

    class Meta:
        model = Course
        fields = [
            "title",
            "title_ar", "title_en",
            "description",
            "description_ar", "description_en",
            "level",
            "teacher",
            "language",
            "estimated_duration_hours",
            "learning_objectives",
            "objectives_ar", "objectives_en",
            "prerequisites",
            "is_free",
            "is_active",
            "cover_image",
            "intro_video",
        ]
        widgets = {
            "description":      forms.Textarea(attrs={"rows": 3}),
            "description_ar":   forms.Textarea(attrs={"rows": 3}),
            "description_en":   forms.Textarea(attrs={"rows": 3}),
            "learning_objectives": forms.Textarea(attrs={"rows": 3}),
            "objectives_ar":    forms.Textarea(attrs={"rows": 3}),
            "objectives_en":    forms.Textarea(attrs={"rows": 3}),
            "prerequisites":    forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        # Teachers dropdown — same set the assign-teacher action uses.
        self.fields["teacher"].queryset = (
            User.objects.filter(groups__name="Teacher")
            .distinct().order_by("email", "username")
        )
        self.fields["teacher"].required = False


class LessonEditorForm(forms.ModelForm):
    worksheet_file = forms.FileField(required=False, help_text="Optional worksheet file for this lesson.")
    worksheet_title = forms.CharField(required=False, max_length=200, initial="Worksheet")

    class Meta:
        model = Lesson
        fields = [
            "unit",
            "title",
            "order",
            "lesson_type",
            "cefr_level",
            "skill",
            "grammar_topic",
            "vocabulary_topic",
            "video_file",
            "video_url",
            "audio_file",
            "pdf_file",
            "content_html",
            "transcript",
            "duration_minutes",
            "status",
            "is_active",
        ]
        widgets = {
            "content_html": forms.Textarea(attrs={"rows": 6}),
            "transcript": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, course=None, can_review=False, **kwargs):
        super().__init__(*args, **kwargs)
        if course is not None:
            self.fields["unit"].queryset = course.units.all()
        if not can_review:
            self.fields["status"].choices = [
                choice for choice in self.fields["status"].choices
                if choice[0] in {"draft", "pending_review"}
            ]


class PaymentFilterForm(forms.Form):
    status = forms.ChoiceField(required=False, choices=[("", "All")] + list(PaymentSubmission._meta.get_field("status").choices))
    plan = forms.ChoiceField(required=False, choices=[("", "All")] + list(PaymentSubmission._meta.get_field("plan").choices))
    method = forms.ChoiceField(required=False, choices=[("", "All")] + list(PaymentSubmission._meta.get_field("method").choices))
    q = forms.CharField(required=False)


class AIExampleActionForm(forms.Form):
    example_id = forms.IntegerField(min_value=1)


class SubscriptionPlanForm(forms.ModelForm):
    """Create / edit a SubscriptionPlan from the Control Center."""

    class Meta:
        model = SubscriptionPlan
        fields = [
            "code", "name_en", "name_ar",
            "description_en", "description_ar",
            "price_sdg", "currency", "billing_cycle",
            "ai_tutor_daily_minutes", "library_audio_daily_minutes",
            "is_active", "is_free_trial", "is_featured", "sort_order",
        ]
        widgets = {
            "description_en": forms.Textarea(attrs={"rows": 2}),
            "description_ar": forms.Textarea(attrs={"rows": 2}),
        }


class PlacementQuestionForm(forms.ModelForm):
    """Create / edit a placement-test question from the Control Center.

    The question bank feeds both Part 1 (written MCQ) and Part 2 (the
    voice-call interview). `options` / `scoring_rubric` are JSON fields —
    Django renders them as a textarea; admins paste valid JSON.
    """

    class Meta:
        model = PlacementQuestion
        fields = [
            "code",
            "question_type", "skill", "topic",
            "question_text", "question_text_ar",
            "cefr_min_level", "cefr_max_level", "difficulty_score",
            "expected_answer_type", "options", "scoring_rubric",
            "is_active",
        ]
        widgets = {
            "question_text":    forms.Textarea(attrs={"rows": 3}),
            "question_text_ar": forms.Textarea(attrs={"rows": 3}),
            "options":          forms.Textarea(attrs={"rows": 2}),
            "scoring_rubric":   forms.Textarea(attrs={"rows": 2}),
        }

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        qs = PlacementQuestion.objects.filter(code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A question with this code already exists.")
        return code
