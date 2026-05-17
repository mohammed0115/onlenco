from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError

from courses.models import (
    Course,
    Lesson,
    LessonQuestion,
    LessonQuiz,
    QUESTION_TYPE_CHOICES,
)

from .models import (
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


class TeacherQuestionForm(forms.ModelForm):
    options_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "[\"A\", \"B\"] or one option per line"}),
    )

    class Meta:
        model = LessonQuestion
        fields = [
            "question_type",
            "question_text_ar",
            "question_text_en",
            "options_text",
            "correct_answer",
            "explanation_ar",
            "explanation_en",
            "difficulty_score",
            "points",
            "order",
        ]
        widgets = {
            "question_text_ar": forms.Textarea(attrs={"rows": 3}),
            "question_text_en": forms.Textarea(attrs={"rows": 3}),
            "explanation_ar": forms.Textarea(attrs={"rows": 2}),
            "explanation_en": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["options_text"].initial = json.dumps(self.instance.options or [], ensure_ascii=False)
        self.fields["question_type"].choices = QUESTION_TYPE_CHOICES

    def clean_options_text(self):
        raw = (self.cleaned_data.get("options_text") or "").strip()
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = [line.strip() for line in raw.splitlines() if line.strip()]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValidationError("Options must be a list of text choices.")
        return value

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("question_text_ar") or cleaned.get("question_text_en")):
            raise ValidationError("Question text is required.")
        if not cleaned.get("correct_answer"):
            raise ValidationError("Correct answer is required.")
        if cleaned.get("question_type") == "multiple_choice":
            options = cleaned.get("options_text") or []
            if len(options) < 2:
                raise ValidationError("Multiple-choice questions need at least 2 options.")
            if cleaned.get("correct_answer") not in options:
                raise ValidationError("Correct answer must be one of the options.")
        self.instance.options = cleaned.get("options_text") or []
        return cleaned

    def save(self, commit=True):
        question = super().save(commit=False)
        question.options = self.cleaned_data.get("options_text") or []
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
