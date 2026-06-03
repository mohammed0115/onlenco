from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from courses.models import (
    Course,
    Lesson,
    LessonQuestion,
    LessonQuiz,
    QUESTION_TYPE_CHOICES,
)

from .models import (
    LiveSession,
    MAX_LIVE_SESSIONS_PER_WEEK,
    StudentAssignmentSubmission,
    TeacherAssignment,
    TeacherProfile,
    TeacherStudentNote,
)
from .permissions import teacher_course_queryset


class TeacherProfileForm(forms.ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ["bio_ar", "bio_en", "specialization", "avatar"]
        widgets = {
            "bio_ar": forms.Textarea(attrs={"rows": 4}),
            "bio_en": forms.Textarea(attrs={"rows": 4}),
        }


class TeacherCourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "title_ar",
            "title_en",
            "description_ar",
            "description_en",
            "level",
            "language",
            "objectives_ar",
            "objectives_en",
            "cover_image",
            "intro_video",
            "estimated_duration_hours",
            "is_free",
            "drip_enabled",
        ]
        widgets = {
            "description_ar": forms.Textarea(attrs={"rows": 4}),
            "description_en": forms.Textarea(attrs={"rows": 4}),
            "objectives_ar": forms.Textarea(attrs={"rows": 3}),
            "objectives_en": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("title_ar") or cleaned.get("title_en")):
            raise ValidationError("Arabic or English title is required.")
        return cleaned

    def save(self, commit=True):
        course = super().save(commit=False)
        course.title = course.title_en or course.title_ar or course.title
        course.description = course.description_en or course.description_ar or course.description
        course.learning_objectives = course.objectives_en or course.objectives_ar or course.learning_objectives
        if commit:
            course.save()
            self.save_m2m()
        return course


class TeacherLessonForm(forms.ModelForm):
    worksheet_file = forms.FileField(required=False)
    worksheet_title = forms.CharField(required=False, max_length=200, initial="Worksheet")

    class Meta:
        model = Lesson
        fields = [
            "title_ar",
            "title_en",
            "order",
            "lesson_type",
            "cefr_level",
            "skill",
            "grammar_topic",
            "vocabulary_topic",
            "content_ar",
            "content_en",
            "video_file",
            "video_url",
            "audio_file",
            "pdf_file",
            "transcript",
            "duration_minutes",
        ]
        widgets = {
            "content_ar": forms.Textarea(attrs={"rows": 5}),
            "content_en": forms.Textarea(attrs={"rows": 5}),
            "transcript": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("title_ar") or cleaned.get("title_en")):
            raise ValidationError("Arabic or English lesson title is required.")
        return cleaned

    def save(self, commit=True):
        lesson = super().save(commit=False)
        lesson.title = lesson.title_en or lesson.title_ar or lesson.title
        lesson.content_html = lesson.content_en or lesson.content_ar or lesson.content_html
        if commit:
            lesson.save()
            self.save_m2m()
        return lesson


class TeacherQuizForm(forms.ModelForm):
    class Meta:
        model = LessonQuiz
        fields = ["title_ar", "title_en", "passing_score", "time_limit_minutes", "is_active"]

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("title_ar") or cleaned.get("title_en")):
            raise ValidationError("Arabic or English quiz title is required.")
        return cleaned

    def save(self, commit=True):
        quiz = super().save(commit=False)
        quiz.title = quiz.title_en or quiz.title_ar or quiz.title
        if commit:
            quiz.save()
            self.save_m2m()
        return quiz


# Question types that present discrete choices to the student (visual MCQ builder).
MCQ_QUESTION_TYPES = {
    "multiple_choice",
    "image_choice",
    "listen_and_choose",
    "tap_choice",
    "listening_match",
    "sound_to_word",
    "mini_story_choice",
    "conversation_reply",
}
# Open-ended prompts that have no single correct string (speaking/writing practice).
OPEN_PROMPT_QUESTION_TYPES = {
    "speaking_prompt",
    "writing_prompt",
    "ai_roleplay_prompt",
    "pronunciation_check",
    "speak_this_sentence",
}


class TeacherQuestionForm(forms.ModelForm):
    """Visual question builder — same pattern as the placement question builder.

    Normal teachers never write JSON: multiple-choice options are entered through
    discrete ``option_1..option_4`` fields with a ``correct_option`` picker, and
    text answers use ``correct_answer`` directly. The raw ``options`` JSON is only
    exposed to superusers through a collapsible advanced panel.
    """

    option_1 = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": ""}))
    option_2 = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": ""}))
    option_3 = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": ""}))
    option_4 = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": ""}))
    correct_option = forms.ChoiceField(
        required=False,
        choices=[("", "—"), ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")],
    )
    options_json = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "dir": "ltr", "spellcheck": "false"}),
    )

    class Meta:
        model = LessonQuestion
        fields = [
            "question_type",
            "question_text_ar",
            "question_text_en",
            "correct_answer",
            "explanation_ar",
            "explanation_en",
            "difficulty_score",
            "points",
            "order",
        ]
        widgets = {
            "question_text_ar": forms.Textarea(attrs={"rows": 3, "dir": "rtl"}),
            "question_text_en": forms.Textarea(attrs={"rows": 3, "dir": "ltr"}),
            "explanation_ar": forms.Textarea(attrs={"rows": 2, "dir": "rtl"}),
            "explanation_en": forms.Textarea(attrs={"rows": 2, "dir": "ltr"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["question_type"].choices = QUESTION_TYPE_CHOICES
        # Only superusers/developers ever see the raw JSON escape hatch.
        self.show_advanced_json = bool(user and getattr(user, "is_superuser", False))
        # Pre-fill the visual builder from any existing options on edit.
        if self.instance and self.instance.pk:
            options = self.instance.options or []
            for idx in range(4):
                value = options[idx] if idx < len(options) else ""
                self.fields[f"option_{idx + 1}"].initial = value
            answer = self.instance.correct_answer
            if answer and answer in options:
                self.fields["correct_option"].initial = str(options.index(answer) + 1)
            self.fields["options_json"].initial = json.dumps(options, ensure_ascii=False)

    def _visual_options(self):
        out = []
        for idx in range(1, 5):
            value = (self.cleaned_data.get(f"option_{idx}") or "").strip()
            if value:
                out.append(value)
        return out

    def clean_options_json(self):
        raw = (self.cleaned_data.get("options_json") or "").strip()
        if not raw:
            return None
        if not self.show_advanced_json:
            # A non-superadmin can never submit raw JSON, even if they craft the field.
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            raise ValidationError("JSON غير صالح في المحرر المتقدم. / Invalid JSON in advanced editor.")
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValidationError("الخيارات يجب أن تكون قائمة نصوص. / Options must be a list of text choices.")
        return value

    def clean(self):
        cleaned = super().clean()
        qtype = cleaned.get("question_type")

        if not (cleaned.get("question_text_ar") or cleaned.get("question_text_en")):
            raise ValidationError("أضف نص السؤال بالعربية أو الإنجليزية. / Add the question in Arabic or English.")

        # Advanced JSON (superadmin only) overrides the visual options when present.
        advanced = cleaned.get("options_json")
        options = advanced if advanced is not None else self._visual_options()

        if qtype in MCQ_QUESTION_TYPES:
            if len(options) < 2:
                raise ValidationError("أسئلة الاختيار من متعدد تحتاج خيارين على الأقل. / Multiple-choice needs at least 2 options.")
            picked = (cleaned.get("correct_option") or "").strip()
            correct = ""
            if picked.isdigit() and 1 <= int(picked) <= len(options):
                correct = options[int(picked) - 1]
            elif cleaned.get("correct_answer") in options:
                correct = cleaned["correct_answer"]
            if not correct:
                raise ValidationError("اختر الإجابة الصحيحة من الخيارات. / Select the correct answer from the options.")
            cleaned["correct_answer"] = correct
        elif qtype in OPEN_PROMPT_QUESTION_TYPES:
            # Open practice prompts have no single correct string.
            options = []
            cleaned["correct_answer"] = cleaned.get("correct_answer") or ""
        else:
            options = []
            if not cleaned.get("correct_answer"):
                raise ValidationError("أضف الإجابة الصحيحة. / Add the correct answer.")

        self._resolved_options = options
        self.instance.options = options
        return cleaned

    def save(self, commit=True):
        question = super().save(commit=False)
        question.options = getattr(self, "_resolved_options", []) or []
        question.question_text = question.question_text_en or question.question_text_ar or question.question_text
        question.explanation = question.explanation_en or question.explanation_ar or question.explanation
        if commit:
            question.save()
            self.save_m2m()
        return question


class TeacherStudentNoteForm(forms.ModelForm):
    class Meta:
        model = TeacherStudentNote
        fields = ["course", "note", "visibility", "needs_support"]
        widgets = {"note": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher is not None:
            self.fields["course"].queryset = teacher_course_queryset(teacher)


class TeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeacherAssignment
        fields = [
            "course",
            "lesson",
            "title_ar",
            "title_en",
            "instructions_ar",
            "instructions_en",
            "assignment_type",
            "due_date",
            "xp_reward",
            "is_active",
        ]
        widgets = {
            "instructions_ar": forms.Textarea(attrs={"rows": 4}),
            "instructions_en": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher is not None:
            courses = teacher_course_queryset(teacher)
            self.fields["course"].queryset = courses
            self.fields["lesson"].queryset = Lesson.objects.filter(course__in=courses)

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("title_ar") or cleaned.get("title_en")):
            raise ValidationError("Arabic or English assignment title is required.")
        lesson = cleaned.get("lesson")
        course = cleaned.get("course")
        if lesson is not None and course is not None and lesson.course_id != course.id:
            raise ValidationError("Lesson must belong to the selected course.")
        return cleaned


class StudentAssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = StudentAssignmentSubmission
        fields = ["text_answer", "audio_file", "file"]
        widgets = {"text_answer": forms.Textarea(attrs={"rows": 5})}

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("text_answer") or cleaned.get("audio_file") or cleaned.get("file")):
            raise ValidationError("Submit an answer, audio, or file.")
        return cleaned


class ReviewSubmissionForm(forms.ModelForm):
    class Meta:
        model = StudentAssignmentSubmission
        fields = ["score", "feedback", "status"]
        widgets = {"feedback": forms.Textarea(attrs={"rows": 4})}


class LiveSessionForm(forms.ModelForm):
    """Schedule a live class. Course choices are scoped to the teacher; at
    most two active sessions per course per ISO week are allowed."""

    class Meta:
        model = LiveSession
        fields = ["course", "title", "description", "scheduled_at", "duration_minutes"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher
        if teacher is not None:
            self.fields["course"].queryset = teacher_course_queryset(teacher)

    def clean_scheduled_at(self):
        when = self.cleaned_data.get("scheduled_at")
        if when and when <= timezone.now():
            raise ValidationError(_("Pick a time in the future. / اختر وقتاً في المستقبل."))
        return when

    def clean(self):
        cleaned = super().clean()
        course = cleaned.get("course")
        when = cleaned.get("scheduled_at")
        if self.teacher is not None and course is not None and when is not None:
            count = LiveSession.weekly_count(
                self.teacher, course, when, exclude_pk=self.instance.pk,
            )
            if count >= MAX_LIVE_SESSIONS_PER_WEEK:
                raise ValidationError(
                    _("You can schedule at most %(n)d live sessions per course each week. / "
                      "يمكنك جدولة %(n)d حصص مباشرة كحد أقصى لكل كورس أسبوعياً.")
                    % {"n": MAX_LIVE_SESSIONS_PER_WEEK}
                )
        return cleaned
