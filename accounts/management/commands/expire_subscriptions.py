from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Profile


class Command(BaseCommand):
    help = "Expire active subscriptions whose expiry datetime has passed."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print IDs without modifying.")

    def handle(self, *args, **opts):
        now = timezone.now()
        qs = Profile.objects.filter(subscription_status="active", subscription_expires_at__lt=now)

        if opts["dry_run"]:
            ids = list(qs.values_list("id", flat=True))
            self.stdout.write(f"Would expire {len(ids)} profile(s): {ids}")
            return

        n = qs.update(subscription_status="expired")
        self.stdout.write(self.style.SUCCESS(f"Expired {n} subscription(s)."))

