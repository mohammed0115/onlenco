"""Seed a starter set of SubstitutionBank rows.

Tiny on purpose. Real growth happens in admin / future imports — but
even with these small banks, a single template can produce thousands of
unique items via combinatorial expansion."""
from django.core.management.base import BaseCommand

from factory.models import SubstitutionBank

# (name, kind, items, description)
SEED = [
    ("subjects_singular", "subject", [
        "she", "he", "the cat", "the dog", "Sara", "Ali",
        "the teacher", "my friend", "Maria", "Omar",
    ], "3rd-person singular subjects."),

    ("subjects_plural", "subject", [
        "they", "we", "the children", "the students", "my friends",
    ], "Plural subjects."),

    ("verbs_regular", "verb", [
        ["walk", "walked", "walking"],
        ["play", "played", "playing"],
        ["watch", "watched", "watching"],
        ["clean", "cleaned", "cleaning"],
        ["paint", "painted", "painting"],
        ["dance", "danced", "dancing"],
        ["cook", "cooked", "cooking"],
        ["learn", "learned", "learning"],
        ["help", "helped", "helping"],
        ["finish", "finished", "finishing"],
    ], "Regular verb tuples: [base, past, gerund]."),

    ("verbs_irregular", "verb", [
        ["go",    "went",    "gone",    "going"],
        ["eat",   "ate",     "eaten",   "eating"],
        ["see",   "saw",     "seen",    "seeing"],
        ["take",  "took",    "taken",   "taking"],
        ["give",  "gave",    "given",   "giving"],
        ["come",  "came",    "come",    "coming"],
        ["write", "wrote",   "written", "writing"],
        ["speak", "spoke",   "spoken",  "speaking"],
        ["buy",   "bought",  "bought",  "buying"],
        ["teach", "taught",  "taught",  "teaching"],
    ], "Irregular verb tuples: [base, past, past_participle, gerund]."),

    ("objects_common", "object", [
        "the book", "a sandwich", "tea", "coffee", "the door",
        "the homework", "the meeting", "the report", "lunch", "dinner",
    ], "Common direct objects."),

    ("places", "place", [
        "at the office", "at home", "in the park", "at school",
        "in the kitchen", "in the library", "at the gym", "in the cafe",
    ], "Place adjuncts."),

    ("times_past", "time", [
        "yesterday", "last night", "last week", "two days ago",
        "this morning", "an hour ago",
    ], "Past time adjuncts."),

    ("adj_pairs", "adjective_pair", [
        ["tall",  "taller",  "tallest"],
        ["big",   "bigger",  "biggest"],
        ["fast",  "faster",  "fastest"],
        ["happy", "happier", "happiest"],
        ["good",  "better",  "best"],
        ["bad",   "worse",   "worst"],
    ], "Comparative/superlative adjective tuples."),

    ("articles_nouns", "article", [
        ["apple",  "an"],
        ["orange", "an"],
        ["hour",   "an"],
        ["book",   "a"],
        ["cat",    "a"],
        ["egg",    "an"],
        ["pen",    "a"],
        ["uncle",  "an"],
    ], "Noun + correct article tuples."),

    ("vocab_def_pairs", "vocab_def", [
        ["happy",  "feeling joy"],
        ["brave",  "showing courage"],
        ["clever", "intelligent"],
        ["kind",   "friendly and helpful"],
        ["tiny",   "very small"],
        ["huge",   "very big"],
        ["calm",   "peaceful, not stressed"],
        ["famous", "well known"],
    ], "Word ↔ short definition tuples."),
]


class Command(BaseCommand):
    help = "Seed/refresh the starter substitution banks."

    def handle(self, *args, **opts):
        created = updated = 0
        for name, kind, items, desc in SEED:
            _, was_created = SubstitutionBank.objects.update_or_create(
                name=name,
                defaults={
                    "kind": kind, "items": items,
                    "description": desc, "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"SubstitutionBank: created={created} updated={updated}"
        ))
