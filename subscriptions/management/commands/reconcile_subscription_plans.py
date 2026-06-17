"""Reconcile 'subscribed-but-no-plan' users (data fix).

Some accounts have ``profile.subscription_status = "active"`` (so they pass
the access gate / ``is_subscribed``) but have **no** active ``UserSubscription``
— so they resolve to no plan and get 0 AI/library minutes. This command finds
those users and attaches an active subscription on a plan, with the end_date
aligned to the profile's existing expiry.

Safety:
  * DRY-RUN by default (writes nothing). Pass ``--apply`` to write.
  * NEVER downgrades or changes a user who already has an active plan.
  * NEVER changes the access flag or copyright/content — only fills the gap.

Examples:
  python manage.py reconcile_subscription_plans --dry-run
  python manage.py reconcile_subscription_plans --apply --plan starter_5m
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone

from subscriptions.models import SubscriptionPlan
from subscriptions.services import subscription_service


class Command(BaseCommand):
    help = "Attach a plan to users marked subscribed but with no active subscription."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run).")
        parser.add_argument("--dry-run", action="store_true", help="Preview only (default).")
        parser.add_argument("--plan", default=None, help="Plan code to grant (default: the default plan).")

    def handle(self, *args, **opts):
        apply = opts.get("apply")

        if opts.get("plan"):
            plan = SubscriptionPlan.objects.filter(code=opts["plan"], is_active=True).first()
            if plan is None:
                raise CommandError(f"No active plan with code {opts['plan']!r}.")
        else:
            plan = subscription_service.default_subscription_plan()
            if plan is None:
                raise CommandError("No active subscription plan exists to grant.")

        User = get_user_model()
        now = timezone.now()
        affected = []
        for u in User.objects.select_related("profile").all():
            profile = getattr(u, "profile", None)
            if not profile or not profile.is_subscribed:
                continue
            if subscription_service.active_subscription_for(u) is not None:
                continue  # already has a working plan — never touch
            affected.append(u)

        self.stdout.write(self.style.MIGRATE_HEADING("Reconcile subscription plans"))
        self.stdout.write(f"  grant plan          : {plan.code} ({plan.name_en}, "
                          f"{plan.library_audio_daily_minutes} lib min/day)")
        self.stdout.write(f"  affected users      : {len(affected)}")
        for u in affected:
            self.stdout.write(f"      {u.email or u.username} "
                              f"(expires {u.profile.subscription_expires_at})")

        if not affected:
            self.stdout.write(self.style.SUCCESS("Nothing to reconcile."))
            return

        if not apply:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN — nothing written. Re-run with --apply to grant the plan."))
            return

        granted = 0
        for u in affected:
            expires = u.profile.subscription_expires_at
            days = max(1, (expires - now).days) if expires else 30
            subscription_service.activate_subscription(user=u, plan=plan, duration_days=days)
            granted += 1
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Granted '{plan.code}' to {granted} user(s). Existing plans untouched."))
