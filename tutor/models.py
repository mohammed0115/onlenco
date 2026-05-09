from django.conf import settings
from django.db import models


from django.utils.translation import gettext_lazy as _
class TutorConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tutor_conversations",
    )
    title = models.CharField(max_length=200, blank=True)
    topic = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Tutor conversation")
        verbose_name_plural = _("Tutor conversations")
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation #{self.pk}"


class TutorMessage(models.Model):
    ROLE_CHOICES = [("user", "user"), ("assistant", "assistant")]

    conversation = models.ForeignKey(
        TutorConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Tutor message")
        verbose_name_plural = _("Tutor messages")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}".strip()

