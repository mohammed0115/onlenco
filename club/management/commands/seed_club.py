from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from club.models import ClubEvent


class Command(BaseCommand):
    help = "Seed the English Club with sample events."

    def handle(self, *args, **opts):
        now = timezone.now()
        samples = [
            ("Weekly English Club — Small Talk", "Small talk practice", "Coach", now + timedelta(days=2), 60),
            ("Weekly English Club — Travel", "Travel roleplay", "Coach", now + timedelta(days=5), 60),
            ("Weekly English Club — Job Interview", "Interview questions", "Coach", now + timedelta(days=8), 60),
            ("Weekly English Club — Past Session", "A past demo event", "Coach", now - timedelta(days=3), 60),
        ]

        created = 0
        for title, topic, host, starts_at, dur in samples:
            obj, was_created = ClubEvent.objects.get_or_create(
                title=title,
                defaults={
                    "topic": topic,
                    "description": "A live discussion session on a practical topic.",
                    "host_name": host,
                    "starts_at": starts_at,
                    "duration_minutes": dur,
                    "meet_url": "https://meet.google.com/example-abc-def",
                    "capacity": 20,
                    "is_published": True,
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Club: {created} event(s) added, {ClubEvent.objects.count()} total."
        ))

