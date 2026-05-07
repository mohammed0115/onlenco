from django.db import models

from accounts.models import CEFR_CHOICES


CATEGORY_CHOICES = [
    ("novel", "Novel"),
    ("short", "Short story"),
    ("grammar", "Grammar reference"),
    ("article", "Article"),
]


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    level = models.CharField(max_length=2, choices=CEFR_CHOICES)
    summary = models.TextField(blank=True)
    cover = models.ImageField(upload_to="library/covers/", blank=True, null=True)
    pdf = models.FileField(upload_to="library/pdfs/", blank=True, null=True)
    published_at = models.DateField(blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at", "title"]

    def __str__(self):
        return f"{self.title} ({self.level})"


class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=200)
    body = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.book.title} — Chapter {self.sort_order}: {self.title}"

