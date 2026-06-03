from __future__ import annotations

import json

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
    option_1 = forms.CharField(required=False, label=_("Option 1"))
    option_2 = forms.CharField(required=False, label=_("Option 2"))
    option_3 = forms.CharField(required=False, label=_("Option 3"))
    option_4 = forms.CharField(required=False, label=_("Option 4"))
    correct_option = forms.ChoiceField(
        required=False,
        choices=[
            ("", _("Choose the correct option")),
            ("1", _("Option 1")),
            ("2", _("Option 2")),
            ("3", _("Option 3")),
            ("4", _("Option 4")),
        ],
        label=_("Correct option"),
    )
    expected_answer = forms.CharField(required=False, label=_("Expected answer"))
    accepted_answers = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label=_("Accepted alternatives"),
        help_text=_("One accepted answer per line."),
    )
    voice_keywords = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label=_("Keywords"),
        help_text=_("One keyword per line."),
    )
    minimum_words = forms.IntegerField(required=False, min_value=0, label=_("Minimum words"))
    fluency_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label=_("Fluency notes"),
    )
    grammar_weight = forms.IntegerField(required=False, min_value=0, max_value=100, label=_("Grammar weight"))
    vocabulary_weight = forms.IntegerField(required=False, min_value=0, max_value=100, label=_("Vocabulary weight"))
    pronunciation_weight = forms.IntegerField(required=False, min_value=0, max_value=100, label=_("Pronunciation weight"))
    fluency_weight = forms.IntegerField(required=False, min_value=0, max_value=100, label=_("Fluency weight"))
    minimum_passing_score = forms.IntegerField(required=False, min_value=0, max_value=100, label=_("Minimum passing score"))
    rubric_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label=_("Rubric notes"),
    )
    options = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    scoring_rubric = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    class Meta:
        model = PlacementQuestion
        fields = [
            "question_type", "skill", "topic",
            "question_text", "question_text_ar",
            "cefr_min_level", "cefr_max_level", "difficulty_score",
            "expected_answer_type", "options", "scoring_rubric",
            "is_active",
        ]
        widgets = {
            "question_text":    forms.Textarea(attrs={"rows": 3}),
            "question_text_ar": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.show_advanced_json = bool(getattr(user, "is_superuser", False))
        for field_name in ("options", "scoring_rubric"):
            self.fields[field_name].required = False
        self._hydrate_visual_builder_fields()

    def _hydrate_visual_builder_fields(self):
        options = self.instance.options if self.instance and self.instance.pk else []
        rubric = self.instance.scoring_rubric if self.instance and self.instance.pk else {}
        if not isinstance(options, list):
            options = []
        if not isinstance(rubric, dict):
            rubric = {}
        self.fields["options"].initial = json.dumps(options, ensure_ascii=False, indent=2) if options else ""
        self.fields["scoring_rubric"].initial = json.dumps(rubric, ensure_ascii=False, indent=2) if rubric else ""

        answer_type = self.initial.get("expected_answer_type") or getattr(self.instance, "expected_answer_type", "")
        if answer_type == "mcq":
            raw_options = []
            correct_option = ""
            for item in options:
                if isinstance(item, dict):
                    raw_options.append(item.get("text", ""))
                else:
                    raw_options.append(str(item))
            for idx, value in enumerate(raw_options[:4], start=1):
                self.fields[f"option_{idx}"].initial = value
            for idx, item in enumerate(options[:4], start=1):
                if isinstance(item, dict) and item.get("is_correct"):
                    correct_option = str(idx)
                    break
            self.fields["correct_option"].initial = correct_option
        elif answer_type in {"short_text", "sentence", "paragraph"}:
            answers = rubric.get("accepted_answers") or []
            self.fields["expected_answer"].initial = rubric.get("expected_answer", "")
            self.fields["accepted_answers"].initial = "\n".join(
                str(item) for item in answers if str(item).strip()
            )
        elif answer_type == "voice":
            keywords = rubric.get("keywords") or []
            self.fields["expected_answer"].initial = rubric.get("expected_answer", "")
            self.fields["voice_keywords"].initial = "\n".join(
                str(item) for item in keywords if str(item).strip()
            )
            self.fields["minimum_words"].initial = rubric.get("minimum_words")
            self.fields["fluency_notes"].initial = rubric.get("fluency_notes", "")

        self.fields["grammar_weight"].initial = rubric.get("grammar_weight")
        self.fields["vocabulary_weight"].initial = rubric.get("vocabulary_weight")
        self.fields["pronunciation_weight"].initial = rubric.get("pronunciation_weight")
        self.fields["fluency_weight"].initial = rubric.get("fluency_weight")
        self.fields["minimum_passing_score"].initial = rubric.get("minimum_passing_score")
        self.fields["rubric_notes"].initial = rubric.get("notes", "")

    def clean_difficulty_score(self):
        value = self.cleaned_data.get("difficulty_score")
        if value is None or not 0 <= value <= 1:
            raise forms.ValidationError(_("Difficulty must be between 0 and 1."))
        return value

    def _clean_visual_options(self):
        answer_type = self.cleaned_data.get("expected_answer_type")
        if answer_type != "mcq":
            return []
        values = []
        correct_index = self.cleaned_data.get("correct_option")
        for idx in range(1, 5):
            text = (self.cleaned_data.get(f"option_{idx}") or "").strip()
            if text:
                values.append({
                    "text": text,
                    "is_correct": correct_index == str(idx),
                })
        if len(values) < 2:
            raise forms.ValidationError(_("Add at least two options and choose the correct answer."))
        if not any(item["is_correct"] for item in values):
            raise forms.ValidationError(_("Add at least two options and choose the correct answer."))
        return values

    def _clean_visual_rubric(self):
        answer_type = self.cleaned_data.get("expected_answer_type")
        rubric = {
            "grammar_weight": self.cleaned_data.get("grammar_weight") or 0,
            "vocabulary_weight": self.cleaned_data.get("vocabulary_weight") or 0,
            "pronunciation_weight": self.cleaned_data.get("pronunciation_weight") or 0,
            "fluency_weight": self.cleaned_data.get("fluency_weight") or 0,
            "minimum_passing_score": self.cleaned_data.get("minimum_passing_score") or 0,
            "notes": (self.cleaned_data.get("rubric_notes") or "").strip(),
        }
        if answer_type in {"short_text", "sentence", "paragraph"}:
            expected = (self.cleaned_data.get("expected_answer") or "").strip()
            alternatives = [
                line.strip()
                for line in (self.cleaned_data.get("accepted_answers") or "").splitlines()
                if line.strip()
            ]
            rubric.update({
                "expected_answer": expected,
                "accepted_answers": alternatives,
            })
        elif answer_type == "voice":
            keywords = [
                line.strip()
                for line in (self.cleaned_data.get("voice_keywords") or "").splitlines()
                if line.strip()
            ]
            rubric.update({
                "expected_answer": (self.cleaned_data.get("expected_answer") or "").strip(),
                "keywords": keywords,
                "minimum_words": self.cleaned_data.get("minimum_words") or 0,
                "fluency_notes": (self.cleaned_data.get("fluency_notes") or "").strip(),
            })
        return rubric

    def clean(self):
        cleaned = super().clean()
        if not ((cleaned.get("question_text") or "").strip() or (cleaned.get("question_text_ar") or "").strip()):
            raise forms.ValidationError(_("Add the question in Arabic or English."))
        try:
            cleaned["options"] = self._clean_visual_options()
        except forms.ValidationError as exc:
            self.add_error(None, exc)
        cleaned["scoring_rubric"] = self._clean_visual_rubric()
        self.instance.options = cleaned.get("options") or []
        self.instance.scoring_rubric = cleaned.get("scoring_rubric") or {}
        return cleaned
