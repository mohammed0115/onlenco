from django.core.management.base import BaseCommand

from analytics.services import compute_metrics


class Command(BaseCommand):
    help = "Print key KPI metrics to stdout."

    def handle(self, *args, **opts):
        m = compute_metrics()
        a = m["acquisition"]
        act = m["activation"]
        r = m["retention"]
        rev = m["revenue"]

        self.stdout.write(self.style.SUCCESS("Onlenco analytics KPIs"))
        self.stdout.write(f"Total users: {a['total_users']}")
        self.stdout.write(f"New users: today={a['new_today']} week={a['new_week']} month={a['new_month']}")
        self.stdout.write(f"Placement done: {act['placement_done']} ({act['activation_rate']:.1f}%)")
        self.stdout.write(f"Active users: DAU={r['dau']} WAU={r['wau']} MAU={r['mau']}")
        self.stdout.write(f"Revenue: month={rev['revenue_month']} SDG all={rev['revenue_all']} SDG")
        self.stdout.write(f"Pending payments: {rev['pending_count']} ({rev['pending_total']} SDG)")
