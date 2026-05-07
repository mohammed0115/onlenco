from django.db import models


POS_CHOICES = [
    ("noun", "Noun"),
    ("verb", "Verb"),
    ("adj", "Adjective"),
    ("adv", "Adverb"),
    ("prep", "Preposition"),
    ("phrase", "Phrase"),
    ("other", "Other"),
]

SOURCE_CHOICES = [("curated", "Curated"), ("ai", "AI-generated")]


class DictionaryEntry(models.Model):
    english = models.CharField(max_length=80, db_index=True)
    arabic = models.CharField(max_length=80, db_index=True)
    pos = models.CharField(max_length=20, blank=True, choices=POS_CHOICES)
    example_en = models.CharField(max_length=300, blank=True)
    example_ar = models.CharField(max_length=300, blank=True)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, default="curated", choices=SOURCE_CHOICES)
    lookup_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["english"]
        unique_together = [("english", "arabic")]

    def __str__(self):
        return f"{self.english} ↔ {self.arabic}"

