from django.core.management.base import BaseCommand
from django.utils import timezone

from library.models import Book, Chapter


class Command(BaseCommand):
    help = "Seed the digital library with sample books."

    def handle(self, *args, **opts):
        samples = [
            ("First English Words", "Onlenco", "grammar", "A0", 2),
            ("A Day in the Market", "Onlenco", "short", "A1", 1),
            ("Letters from a Friend", "Onlenco", "short", "A2", 3),
            ("News from Khartoum", "Onlenco", "article", "B1", 1),
            ("Beginner's Grammar Pocketbook", "Onlenco", "grammar", "B2", 4),
            ("The Long Road", "Onlenco", "novel", "C1", 5),
        ]

        created_books = 0
        for title, author, category, level, chapters_count in samples:
            book, created = Book.objects.get_or_create(
                title=title,
                defaults={
                    "author": author,
                    "category": category,
                    "level": level,
                    "summary": "A short sample text to read at your level.",
                    "published_at": timezone.now().date(),
                    "is_published": True,
                },
            )
            if created:
                created_books += 1

            if book.pdf:
                continue

            for i in range(1, chapters_count + 1):
                Chapter.objects.get_or_create(
                    book=book,
                    sort_order=i,
                    defaults={
                        "title": f"Chapter {i}",
                        "body": (
                            "This is a sample chapter for demo purposes.\n\n"
                            "Read slowly, notice new words, and practise out loud."
                        )
                        if title != "The Long Road"
                        else (
                            "The road was long, and the sun was low.\n\n"
                            "Lorem ipsum-style placeholder text for a longer novel chapter."
                        ),
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"Library: {created_books} book(s) added, {Book.objects.count()} total."
        ))

