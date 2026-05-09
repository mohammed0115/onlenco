"""On-demand variations — print sample items WITHOUT persisting.

Use this to:
  * sanity-check a template's surface forms
  * sample a topic for a manual review
  * benchmark virtual capacity ("how many items can this topic produce?")

Examples:
    python manage.py factory_variations --topic-kind grammar --cefr A1 --count 10
    python manage.py factory_variations --topic grammar-a1-articles-aanthe --count 5
    python manage.py factory_variations --capacity --topic-kind grammar
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from factory.services.variation_generator import (
    variations_for_topic,
    variations_for_topic_kind,
    virtual_capacity,
)


class Command(BaseCommand):
    help = "Generate question variations on demand (no DB writes)."

    def add_arguments(self, parser):
        parser.add_argument("--topic", type=str, default="",
                            help="Topic slug. Mutually exclusive with --topic-kind.")
        parser.add_argument("--topic-kind", type=str, default="")
        parser.add_argument("--cefr", type=str, default="")
        parser.add_argument("--count", type=int, default=10)
        parser.add_argument("--capacity", action="store_true", default=False)
        parser.add_argument("--json", action="store_true", default=False)

    def handle(self, *args, **opts):
        if opts["capacity"]:
            cap = virtual_capacity(
                topic_slug=opts["topic"] or None,
                topic_kind=opts["topic_kind"] or None,
                cefr_level=opts["cefr"] or None,
            )
            self.stdout.write(self.style.SUCCESS(
                f"virtual capacity: {cap:,} unique items "
                f"(without persisting any of them)."
            ))
            return

        if opts["topic"]:
            items = variations_for_topic(opts["topic"], count=opts["count"])
        elif opts["topic_kind"]:
            items = variations_for_topic_kind(
                opts["topic_kind"],
                cefr_level=opts["cefr"] or None,
                count=opts["count"],
            )
        else:
            self.stdout.write(self.style.ERROR(
                "Provide --topic or --topic-kind."
            ))
            return

        if opts["json"]:
            self.stdout.write(json.dumps(items, ensure_ascii=False, indent=2))
            return
        for i, it in enumerate(items, 1):
            self.stdout.write(f"{i}. [{it['cefr_level']}] {it['question']}")
            if it.get("options"):
                for o in it["options"]:
                    mark = "✓" if o == it["correct_answer"] else " "
                    self.stdout.write(f"     {mark} {o}")
            else:
                self.stdout.write(f"     ✓ {it['correct_answer']}")
        self.stdout.write(self.style.SUCCESS(f"({len(items)} items)"))
