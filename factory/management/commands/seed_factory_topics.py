"""Seed a starter taxonomy: kinds × CEFR with a small set of named topics.

Idempotent — re-runs update existing rows by slug. Add real depth later
via Django admin or a fixture import; this is the smallest set that
unlocks template-driven generation."""
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from factory.models import Topic

# (kind, cefr, name, parent_slug or None)
SEED = [
    # Grammar
    ("grammar", "A0", "Verb 'to be' — present", None),
    ("grammar", "A1", "Present simple",         None),
    ("grammar", "A1", "Articles a/an/the",      None),
    ("grammar", "A2", "Past simple",            None),
    ("grammar", "A2", "Comparatives",           None),
    ("grammar", "A2", "Superlatives",           None),
    ("grammar", "B1", "Present perfect",        None),
    ("grammar", "B1", "Conditionals — type 1",  None),
    ("grammar", "B2", "Passive voice",          None),
    ("grammar", "B2", "Conditionals — type 2",  None),
    ("grammar", "C1", "Inversion",              None),
    ("grammar", "C2", "Cleft sentences",        None),
    # Vocabulary
    ("vocabulary", "A1", "Common adjectives",   None),
    ("vocabulary", "A2", "Antonyms",            None),
    ("vocabulary", "B1", "Phrasal verbs — basic", None),
    ("vocabulary", "B2", "Collocations",        None),
    ("vocabulary", "C1", "Idioms",              None),
    # Reading / listening
    ("reading",   "A1", "Short signs and notices", None),
    ("reading",   "B1", "News short reports",      None),
    ("listening", "A1", "Numbers and times",       None),
    ("listening", "B1", "Interview snippets",      None),
    # Writing / speaking
    ("writing",   "A2", "Personal email",       None),
    ("writing",   "B2", "Opinion paragraph",    None),
    ("speaking",  "A1", "Self-introduction",    None),
    ("speaking",  "B2", "Discussion prompts",   None),
    ("pronunciation", "A1", "Minimal pairs",    None),
    ("comprehension", "B1", "Inference",        None),
]


class Command(BaseCommand):
    help = "Seed/refresh the canonical Topic taxonomy."

    def handle(self, *args, **opts):
        created = updated = 0
        for kind, cefr, name, parent_slug in SEED:
            slug = slugify(f"{kind}-{cefr}-{name}")
            parent = None
            if parent_slug:
                parent = Topic.objects.filter(slug=parent_slug).first()
            obj, was_created = Topic.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "kind": kind,
                    "cefr_level": cefr,
                    "parent": parent,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"Topics: created={created} updated={updated} "
            f"total_active={Topic.objects.filter(is_active=True).count()}"
        ))
