from django.conf import settings
from django.db import models

from accounts.models import CEFR_CHOICES


SKILL_CHOICES = [
    ("reading", "Reading"),
    ("writing", "Writing"),
    ("listening", "Listening"),
    ("speaking", "Speaking"),
    ("grammar", "Grammar"),
    ("vocabulary", "Vocabulary"),
]


class Lesson(models.Model):
    """A single video-led lesson tagged with skill and CEFR level."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    skill = models.CharField(max_length=12, choices=SKILL_CHOICES)
    level = models.CharField(max_length=2, choices=CEFR_CHOICES)
    video_url = models.URLField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=10)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "level", "title"]

    def __str__(self):
        return f"[{self.level}] {self.title}"


class Quiz(models.Model):
    """Multiple-choice quiz attached to a lesson."""

    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name="quiz")
    pass_score = models.PositiveSmallIntegerField(default=70)

    def __str__(self):
        return f"Quiz: {self.lesson}"


class Question(models.Model):
    """A multiple-choice question belonging to a quiz."""

    ANSWER_CHOICES = [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    prompt = models.TextField()
    choice_a = models.CharField(max_length=200)
    choice_b = models.CharField(max_length=200)
    choice_c = models.CharField(max_length=200, blank=True)
    choice_d = models.CharField(max_length=200, blank=True)
    correct = models.CharField(max_length=1, choices=ANSWER_CHOICES)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Q{self.id} ({self.quiz.lesson})"


class LessonProgress(models.Model):
    """Tracks a user's completion of a lesson (video + optional quiz)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="progress_entries",
    )
    video_completed = models.BooleanField(default=False)
    quiz_score = models.PositiveSmallIntegerField(null=True, blank=True)
    quiz_passed = models.BooleanField(default=False)
    last_attempt_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "lesson")]

    @property
    def is_complete(self):
        if not self.video_completed:
            return False
        try:
            self.lesson.quiz
        except Quiz.DoesNotExist:
            return True
        return self.quiz_passed
