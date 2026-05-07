"""Seed the database with an admin user and a small set of demo lessons.

Usage:
    python manage.py seed_demo
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from lessons.models import Lesson, Question, Quiz


SAMPLE_LESSONS = [
    # (title, description, skill, level, duration, sort_order)
    ("Greetings & Introductions",
     "Learn how to say hello, introduce yourself, and ask basic questions.",
     "speaking", "A0",  8, 10),
    ("The Alphabet & Sounds",
     "Master English letter sounds and tricky pronunciation pairs.",
     "listening", "A0", 10, 20),
    ("Everyday Vocabulary",
     "Family, home, food — the 200 words you'll use daily.",
     "reading", "A1", 12, 30),
    ("Present Simple",
     "Build sentences in the present tense with confidence.",
     "writing", "A1", 14, 40),
    ("Asking for Directions",
     "Practical phrases for travel and getting around the city.",
     "speaking", "A2",  9, 50),
    ("Past Simple Stories",
     "Talk about what happened yesterday, last week, or last year.",
     "writing", "A2", 15, 60),
    ("Conversational Listening",
     "Train your ear with natural-speed dialogues and interviews.",
     "listening", "B1", 18, 70),
    ("Reading the News",
     "Decode article headlines and pull out the key information.",
     "reading", "B1", 16, 80),
    ("Workplace Email",
     "Write professional emails for requests, follow-ups, and updates.",
     "writing", "B2", 20, 90),
    ("Debate & Discussion",
     "Defend your opinion and respond to counterarguments live.",
     "speaking", "B2", 22, 100),
    ("Academic Reading",
     "Strategies for tackling dense, formal academic texts.",
     "reading", "C1", 24, 110),
    ("Native-level Idioms",
     "Idioms, collocations, and the small phrases that show fluency.",
     "speaking", "C2", 18, 120),
]


class Command(BaseCommand):
    help = "Create an admin user and seed demo lessons."

    def add_arguments(self, parser):
        parser.add_argument("--admin-email",    default="admin@onlenco.local")
        parser.add_argument("--admin-password", default="onlenco123")

    def handle(self, *args, **opts):
        User = get_user_model()
        email = opts["admin_email"].strip().lower()
        password = opts["admin_password"]

        admin, created = User.objects.get_or_create(
            username=email,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password(password)
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()
            admin.profile.full_name = "Onlenco Admin"
            admin.profile.role = "admin"
            admin.profile.save()
            self.stdout.write(self.style.SUCCESS(
                f"Created admin {email!r} with password {password!r}."
            ))
        else:
            self.stdout.write(f"Admin user {email!r} already exists, skipping creation.")

        new_lessons = 0
        for title, desc, skill, level, dur, sort in SAMPLE_LESSONS:
            obj, created = Lesson.objects.get_or_create(
                title=title,
                defaults=dict(description=desc, skill=skill, level=level,
                              duration_minutes=dur, sort_order=sort),
            )
            if created:
                new_lessons += 1

        # Add a short demo quiz to the first four lessons.
        quiz_defs = [
            dict(
                prompt="Choose the correct sentence: 'I ___ coffee every morning.'",
                choice_a="drink",
                choice_b="drinks",
                choice_c="drinking",
                choice_d="drank",
                correct="a",
                sort_order=10,
            ),
            dict(
                prompt="What does 'cheap' mean?",
                choice_a="Not expensive",
                choice_b="Very large",
                choice_c="Very fast",
                choice_d="Very old",
                correct="a",
                sort_order=20,
            ),
            dict(
                prompt=(
                    "Read: 'Sara wakes up at 6:00 and takes the bus to work.' "
                    "How does Sara go to work?"
                ),
                choice_a="By bus",
                choice_b="By car",
                choice_c="On foot",
                choice_d="By train",
                correct="a",
                sort_order=30,
            ),
        ]

        seeded_quizzes = 0
        for lesson in Lesson.objects.order_by("sort_order", "id")[:4]:
            quiz, created = Quiz.objects.get_or_create(lesson=lesson)
            if created:
                seeded_quizzes += 1

            for qd in quiz_defs:
                Question.objects.get_or_create(
                    quiz=quiz,
                    sort_order=qd["sort_order"],
                    prompt=qd["prompt"],
                    defaults={
                        "choice_a": qd["choice_a"],
                        "choice_b": qd["choice_b"],
                        "choice_c": qd["choice_c"],
                        "choice_d": qd["choice_d"],
                        "correct": qd["correct"],
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"Lessons: {new_lessons} added, {Lesson.objects.count()} total."
        ))
        if seeded_quizzes:
            self.stdout.write(self.style.SUCCESS(
                f"Quizzes: {seeded_quizzes} added."
            ))

        # Seed the digital library (idempotent).
        try:
            call_command("seed_books")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"seed_books failed: {e}"))

        # Seed the dictionary (idempotent).
        try:
            call_command("seed_dictionary")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"seed_dictionary failed: {e}"))

        # Seed the English Club events (idempotent).
        try:
            call_command("seed_club")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"seed_club failed: {e}"))
