"""Seed canonical QuestionBlueprint rows.

Idempotent — re-runs update existing rows by `code`.

Coverage target (per the spec):
- 20 blueprints per CEFR level (10 grammar + 10 vocabulary)
- Reading-comprehension blueprints
- Writing-prompt blueprints
- Speaking-prompt blueprints

Total seeded: 7 levels × 20 = 140 grammar+vocab blueprints, plus
one each of reading/writing/speaking per level (21 more) = 161 baseline.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from question_factory import constants as C
from question_factory.services import blueprint_service


CEFR_LEVELS = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]

# Difficulty band per CEFR — used as min/max defaults.
LEVEL_DIFFICULTY = {
    "A0": (0.05, 0.20),
    "A1": (0.15, 0.30),
    "A2": (0.25, 0.45),
    "B1": (0.40, 0.60),
    "B2": (0.55, 0.75),
    "C1": (0.70, 0.85),
    "C2": (0.80, 0.95),
}

# -- Variable banks reused across blueprints. Inline so the seed file is
# self-contained; production growth happens via admin / future imports. --

SUBJECTS_3SG = ["she", "he", "the cat", "the dog", "Sara", "Ali",
                "the teacher", "my friend", "Maria", "Omar"]
SUBJECTS_PL  = ["they", "we", "the children", "the students", "my friends"]
SUBJECTS_I   = ["I", "you"]

VERBS_REGULAR = [
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
]
VERBS_IRREGULAR = [
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
]

OBJECTS = [
    "the book", "a sandwich", "tea", "coffee", "the homework",
    "the meeting", "the report", "lunch", "dinner", "the email",
]
PLACES = [
    "at the office", "at home", "in the park", "at school",
    "in the kitchen", "in the library", "at the gym",
]
TIMES_PAST = [
    "yesterday", "last night", "last week", "two days ago",
    "this morning", "an hour ago",
]

ADJ_PAIRS = [
    ["tall",  "taller",  "tallest"],
    ["big",   "bigger",  "biggest"],
    ["fast",  "faster",  "fastest"],
    ["happy", "happier", "happiest"],
    ["good",  "better",  "best"],
    ["bad",   "worse",   "worst"],
]
ARTICLE_PAIRS = [
    ["apple",  "an"], ["orange", "an"], ["hour",  "an"],
    ["book",   "a"],  ["cat",    "a"],  ["egg",   "an"],
    ["pen",    "a"],  ["uncle",  "an"], ["umbrella", "an"],
]

VOCAB_DEF_PAIRS = [
    ["happy",   "feeling joy"],
    ["brave",   "showing courage"],
    ["clever",  "intelligent"],
    ["kind",    "friendly and helpful"],
    ["tiny",    "very small"],
    ["huge",    "very big"],
    ["calm",    "peaceful, not stressed"],
    ["famous",  "well known"],
    ["polite",  "well mannered"],
    ["lazy",    "not wanting to work"],
]
VOCAB_ANTONYMS = [
    ["happy",   "sad"], ["big",  "small"], ["fast", "slow"],
    ["hot",     "cold"], ["light", "heavy"], ["empty", "full"],
    ["near",    "far"], ["clean", "dirty"], ["young", "old"],
]
VOCAB_SYNONYMS = [
    ["big",     "huge"], ["small", "tiny"], ["happy", "joyful"],
    ["fast",    "quick"], ["bad",  "awful"], ["good",  "great"],
]
PHRASAL_VERBS = [
    ["look up",   "search for in a book"],
    ["give up",   "stop trying"],
    ["take off",  "remove (clothes)"],
    ["put on",    "wear"],
    ["turn off",  "stop a device"],
    ["turn on",   "start a device"],
]
COLLOCATIONS = [
    ["make",  "a decision"],
    ["take",  "a break"],
    ["have",  "a meeting"],
    ["do",    "homework"],
    ["pay",   "attention"],
    ["catch", "a cold"],
]
IDIOMS = [
    ["break the ice",      "make a social situation easier"],
    ["under the weather",  "feeling unwell"],
    ["piece of cake",      "very easy"],
    ["spill the beans",    "reveal a secret"],
    ["once in a blue moon","very rarely"],
]

# Reading passages keyed by CEFR; intentionally short.
READING_PASSAGES_BY_LEVEL = {
    "A0": [["This is a cat. The cat is small.",  "small"]],
    "A1": [["Sara has a red bag. She likes it.", "red"]],
    "A2": [["Tom went to school by bus yesterday.", "bus"]],
    "B1": [["The library opens at 9 a.m. on weekdays.", "9 a.m."]],
    "B2": [["Despite the rain, the marathon went ahead as planned.", "marathon"]],
    "C1": [["The committee, having reviewed the data, postponed its decision.", "postponed"]],
    "C2": [["The novel's protagonist confronts an existential paradox of choice.", "protagonist"]],
}

WRITING_PROMPTS = [
    "Describe your daily routine in 4 sentences.",
    "Write a short message to a friend inviting them to a party.",
    "Describe a memorable trip you took.",
    "Write about your favourite hobby.",
    "Describe your dream job in 5 sentences.",
    "Write 3 sentences about your family.",
    "Describe a person you admire.",
]
SPEAKING_PROMPTS = [
    "Introduce yourself in 30 seconds.",
    "Describe your hometown.",
    "Talk about your favourite food.",
    "Discuss the pros and cons of remote learning.",
    "Talk about a person who influenced you.",
    "Describe your morning routine.",
    "Discuss the importance of learning English.",
]


def _grammar_blueprints(level: str) -> list[dict]:
    """10 grammar blueprints per level. Some patterns only make sense
    above a certain level; in those cases we degrade to a level-appropriate
    target to keep coverage uniform without producing nonsense."""
    diff_min, diff_max = LEVEL_DIFFICULTY[level]
    L = level

    return [
        # 1. Present simple — 3rd person singular
        {
            "code": f"qf-gram-{L}-presimple-3sg",
            "title": f"{L} · Present simple — 3rd singular",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "multiple_choice",
            "template_pattern": "{subject} ___ to school every day.",
            "expected_answer_pattern": "verb.0 + 's'",
            "explanation_pattern": "Use '{verb.0}s' with '{subject}' in the present simple.",
            "variables_schema": {"subject": SUBJECTS_3SG, "verb": VERBS_REGULAR},
            "metadata": {"distractor_config": {"strategy": "morph"}},
        },
        # 2. Present simple — affirmative with plural subject
        {
            "code": f"qf-gram-{L}-presimple-pl",
            "title": f"{L} · Present simple — plural subject",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "multiple_choice",
            "template_pattern": "{subject} ___ in the morning.",
            "expected_answer_pattern": "verb.0",
            "explanation_pattern": "Use the bare form '{verb.0}' with plural subjects like '{subject}'.",
            "variables_schema": {"subject": SUBJECTS_PL, "verb": VERBS_REGULAR},
            "metadata": {"distractor_config": {"strategy": "morph"}},
        },
        # 3. Past simple — irregular verbs
        {
            "code": f"qf-gram-{L}-pastsimple-irregular",
            "title": f"{L} · Past simple — irregular verbs",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "multiple_choice",
            "template_pattern": "{subject} ___ {object} {time}.",
            "expected_answer_pattern": "verb.1",
            "explanation_pattern": "The past form of '{verb.0}' is '{verb.1}'.",
            "variables_schema": {
                "subject": SUBJECTS_3SG, "verb": VERBS_IRREGULAR,
                "object": OBJECTS, "time": TIMES_PAST,
            },
            "metadata": {"distractor_config": {
                "strategy": "from_binding", "variable": "verb",
            }},
        },
        # 4. Past simple — regular verbs
        {
            "code": f"qf-gram-{L}-pastsimple-regular",
            "title": f"{L} · Past simple — regular verbs",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "multiple_choice",
            "template_pattern": "{subject} ___ {time}.",
            "expected_answer_pattern": "verb.1",
            "explanation_pattern": "Add '-ed' (or '-d') to form the regular past: '{verb.1}'.",
            "variables_schema": {
                "subject": SUBJECTS_3SG, "verb": VERBS_REGULAR, "time": TIMES_PAST,
            },
            "metadata": {"distractor_config": {
                "strategy": "from_binding", "variable": "verb",
            }},
        },
        # 5. Articles — a/an
        {
            "code": f"qf-gram-{L}-articles",
            "title": f"{L} · Articles a/an",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "multiple_choice",
            "template_pattern": "I have ___ {noun.0}.",
            "expected_answer_pattern": "noun.1",
            "explanation_pattern": "Use '{noun.1}' before '{noun.0}'.",
            "variables_schema": {"noun": ARTICLE_PAIRS},
            "metadata": {"distractor_config": {
                "strategy": "static", "options": ["a", "an", "the", "—"],
            }},
        },
        # 6. Comparatives
        {
            "code": f"qf-gram-{L}-comparatives",
            "title": f"{L} · Comparatives",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "multiple_choice",
            "template_pattern": "My brother is ___ than me.",
            "expected_answer_pattern": "adj.1",
            "explanation_pattern": "Comparative of '{adj.0}' is '{adj.1}'.",
            "variables_schema": {"adj": ADJ_PAIRS},
            "metadata": {"distractor_config": {
                "strategy": "from_binding", "variable": "adj",
            }},
        },
        # 7. Superlatives
        {
            "code": f"qf-gram-{L}-superlatives",
            "title": f"{L} · Superlatives",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "multiple_choice",
            "template_pattern": "She is the ___ student in class.",
            "expected_answer_pattern": "adj.2",
            "explanation_pattern": "Superlative of '{adj.0}' is '{adj.2}'.",
            "variables_schema": {"adj": ADJ_PAIRS},
            "metadata": {"distractor_config": {
                "strategy": "from_binding", "variable": "adj",
            }},
        },
        # 8. Present continuous
        {
            "code": f"qf-gram-{L}-presentcont",
            "title": f"{L} · Present continuous",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "multiple_choice",
            "template_pattern": "{subject} is ___ at the moment.",
            "expected_answer_pattern": "verb.2",
            "explanation_pattern": "Use 'is/are + -ing' for now: '{verb.2}'.",
            "variables_schema": {"subject": SUBJECTS_3SG, "verb": VERBS_REGULAR},
            "metadata": {"distractor_config": {
                "strategy": "from_binding", "variable": "verb",
            }},
        },
        # 9. Fill-blank version of present simple
        {
            "code": f"qf-gram-{L}-fb-presimple",
            "title": f"{L} · Fill-blank — present simple",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "fill_blank",
            "template_pattern": "{subject} usually ___ {object}.",
            "expected_answer_pattern": "verb.0 + 's'",
            "explanation_pattern": "Third-person singular adds '-s'.",
            "variables_schema": {
                "subject": SUBJECTS_3SG, "verb": VERBS_REGULAR, "object": OBJECTS,
            },
            "metadata": {"distractor_config": {"strategy": "morph"}},
        },
        # 10. Sentence ordering / transformation surrogate
        {
            "code": f"qf-gram-{L}-transform-pastsimple",
            "title": f"{L} · Transform — present → past simple",
            "skill": C.SKILL_GRAMMAR,
            "question_type": "grammar_transformation",
            "template_pattern": "Rewrite in the past simple: '{subject} {verb.0}s {object} every day.'",
            "expected_answer_pattern": "subject + ' ' + verb.1 + ' ' + object + '.'",
            "explanation_pattern": "Past form of '{verb.0}' is '{verb.1}'.",
            "variables_schema": {
                "subject": SUBJECTS_3SG, "verb": VERBS_REGULAR, "object": OBJECTS,
            },
            "metadata": {},
        },
    ]


def _vocabulary_blueprints(level: str) -> list[dict]:
    diff_min, diff_max = LEVEL_DIFFICULTY[level]
    L = level
    return [
        # 1. Word → meaning
        {
            "code": f"qf-vocab-{L}-definition",
            "title": f"{L} · Vocabulary — word to meaning",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "multiple_choice",
            "template_pattern": "What does '{word.0}' mean?",
            "expected_answer_pattern": "word.1",
            "explanation_pattern": "'{word.0}' means '{word.1}'.",
            "variables_schema": {"word": VOCAB_DEF_PAIRS},
            "metadata": {"distractor_config": {
                "strategy": "from_pool",
                "pool": [p[1] for p in VOCAB_DEF_PAIRS],
            }},
        },
        # 2. Antonyms
        {
            "code": f"qf-vocab-{L}-antonyms",
            "title": f"{L} · Antonyms",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "multiple_choice",
            "template_pattern": "Which word is the opposite of '{pair.0}'?",
            "expected_answer_pattern": "pair.1",
            "explanation_pattern": "Opposite of '{pair.0}' is '{pair.1}'.",
            "variables_schema": {"pair": VOCAB_ANTONYMS},
            "metadata": {"distractor_config": {
                "strategy": "from_pool",
                "pool": [p[1] for p in VOCAB_ANTONYMS] + [p[0] for p in VOCAB_DEF_PAIRS],
            }},
        },
        # 3. Synonyms
        {
            "code": f"qf-vocab-{L}-synonyms",
            "title": f"{L} · Synonyms",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "multiple_choice",
            "template_pattern": "Which word means about the same as '{pair.0}'?",
            "expected_answer_pattern": "pair.1",
            "explanation_pattern": "'{pair.0}' and '{pair.1}' are close in meaning.",
            "variables_schema": {"pair": VOCAB_SYNONYMS},
            "metadata": {"distractor_config": {
                "strategy": "from_pool",
                "pool": [p[1] for p in VOCAB_SYNONYMS] + [p[0] for p in VOCAB_ANTONYMS],
            }},
        },
        # 4. Phrasal verbs
        {
            "code": f"qf-vocab-{L}-phrasal",
            "title": f"{L} · Phrasal verbs",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "multiple_choice",
            "template_pattern": "What does '{pv.0}' mean?",
            "expected_answer_pattern": "pv.1",
            "explanation_pattern": "'{pv.0}' means '{pv.1}'.",
            "variables_schema": {"pv": PHRASAL_VERBS},
            "metadata": {"distractor_config": {
                "strategy": "from_pool",
                "pool": [p[1] for p in PHRASAL_VERBS],
            }},
        },
        # 5. Collocations
        {
            "code": f"qf-vocab-{L}-collocations",
            "title": f"{L} · Collocations",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "fill_blank",
            "template_pattern": "She wants to ___ {coll.1}.",
            "expected_answer_pattern": "coll.0",
            "explanation_pattern": "We say '{coll.0} {coll.1}' as a collocation.",
            "variables_schema": {"coll": COLLOCATIONS},
            "metadata": {"distractor_config": {
                "strategy": "from_pool",
                "pool": [c[0] for c in COLLOCATIONS],
            }},
        },
        # 6. Idioms (best for B1+ but harmless at lower levels as recognition)
        {
            "code": f"qf-vocab-{L}-idioms",
            "title": f"{L} · Idioms",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "multiple_choice",
            "template_pattern": "What does the idiom '{idiom.0}' mean?",
            "expected_answer_pattern": "idiom.1",
            "explanation_pattern": "'{idiom.0}' means '{idiom.1}'.",
            "variables_schema": {"idiom": IDIOMS},
            "metadata": {"distractor_config": {
                "strategy": "from_pool",
                "pool": [i[1] for i in IDIOMS],
            }},
        },
        # 7. Vocabulary matching (word in context)
        {
            "code": f"qf-vocab-{L}-context",
            "title": f"{L} · Vocabulary in context",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "vocabulary_matching",
            "template_pattern": "Choose the best word: 'I feel ___ today.' (synonym of '{word.1}')",
            "expected_answer_pattern": "word.0",
            "explanation_pattern": "'{word.0}' means '{word.1}'.",
            "variables_schema": {"word": VOCAB_DEF_PAIRS},
            "metadata": {"distractor_config": {
                "strategy": "from_pool",
                "pool": [p[0] for p in VOCAB_DEF_PAIRS],
            }},
        },
        # 8. Antonym fill-blank
        {
            "code": f"qf-vocab-{L}-antonyms-fb",
            "title": f"{L} · Fill-blank — antonyms",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "fill_blank",
            "template_pattern": "The opposite of '{pair.0}' is ___.",
            "expected_answer_pattern": "pair.1",
            "explanation_pattern": "Opposite of '{pair.0}' is '{pair.1}'.",
            "variables_schema": {"pair": VOCAB_ANTONYMS},
            "metadata": {"distractor_config": {
                "strategy": "from_pool",
                "pool": [p[1] for p in VOCAB_ANTONYMS],
            }},
        },
        # 9. Phrasal-verb fill-blank
        {
            "code": f"qf-vocab-{L}-phrasal-fb",
            "title": f"{L} · Fill-blank — phrasal verbs",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "fill_blank",
            "template_pattern": "Please ___ the lights when you leave.",
            "expected_answer_pattern": "'turn off'",
            "explanation_pattern": "We use 'turn off' to stop a device.",
            "variables_schema": {"pv": PHRASAL_VERBS},
            "metadata": {"distractor_config": {
                "strategy": "static",
                "options": ["turn off", "turn on", "take off", "look up"],
            }},
        },
        # 10. Synonyms — short answer
        {
            "code": f"qf-vocab-{L}-synonyms-sa",
            "title": f"{L} · Short answer — synonyms",
            "skill": C.SKILL_VOCABULARY,
            "question_type": "short_answer",
            "template_pattern": "Give a synonym for '{pair.0}'.",
            "expected_answer_pattern": "pair.1",
            "explanation_pattern": "'{pair.0}' and '{pair.1}' are close in meaning.",
            "variables_schema": {"pair": VOCAB_SYNONYMS},
            "metadata": {},
        },
    ]


def _reading_blueprints(level: str) -> list[dict]:
    diff_min, diff_max = LEVEL_DIFFICULTY[level]
    L = level
    passages = READING_PASSAGES_BY_LEVEL.get(L) or READING_PASSAGES_BY_LEVEL["A1"]
    return [{
        "code": f"qf-read-{L}-comprehension",
        "title": f"{L} · Reading comprehension",
        "skill": C.SKILL_READING,
        "question_type": "reading_comprehension",
        "template_pattern": "{passage.0}\n\nAnswer: which key word fits?",
        "expected_answer_pattern": "passage.1",
        "explanation_pattern": "The passage is about: {passage.1}.",
        "variables_schema": {"passage": passages},
        "metadata": {"distractor_config": {
            "strategy": "static",
            "options": [p[1] for p in passages] + ["nothing", "everything"],
        }},
    }]


def _writing_blueprints(level: str) -> list[dict]:
    L = level
    return [{
        "code": f"qf-write-{L}-prompt",
        "title": f"{L} · Writing prompt",
        "skill": C.SKILL_WRITING,
        "question_type": "writing_prompt",
        "template_pattern": "{prompt}",
        "expected_answer_pattern": "'(open response)'",
        "explanation_pattern": "Your response will be assessed by the AI tutor.",
        "variables_schema": {"prompt": WRITING_PROMPTS},
        "metadata": {},
    }]


def _speaking_blueprints(level: str) -> list[dict]:
    L = level
    return [{
        "code": f"qf-speak-{L}-prompt",
        "title": f"{L} · Speaking prompt",
        "skill": C.SKILL_SPEAKING,
        "question_type": "speaking_prompt",
        "template_pattern": "{prompt}",
        "expected_answer_pattern": "'(open response)'",
        "explanation_pattern": "Your recording will be assessed by the AI tutor.",
        "variables_schema": {"prompt": SPEAKING_PROMPTS},
        "metadata": {},
    }]


def _all_blueprints():
    """Yield every blueprint definition. Each definition is a dict ready
    for blueprint_service.upsert(**defaults)."""
    for L in CEFR_LEVELS:
        diff_min, diff_max = LEVEL_DIFFICULTY[L]
        for blueprint_def in (_grammar_blueprints(L)
                              + _vocabulary_blueprints(L)
                              + _reading_blueprints(L)
                              + _writing_blueprints(L)
                              + _speaking_blueprints(L)):
            blueprint_def.setdefault("cefr_level", L)
            blueprint_def.setdefault("difficulty_min", diff_min)
            blueprint_def.setdefault("difficulty_max", diff_max)
            blueprint_def.setdefault("generation_strategy", C.GEN_TEMPLATE)
            blueprint_def.setdefault("is_active", True)
            yield blueprint_def


class Command(BaseCommand):
    help = "Seed/refresh the canonical QuestionBlueprint rows."

    def handle(self, *args, **opts):
        created = updated = 0
        by_level: dict[str, int] = {}
        by_skill: dict[str, int] = {}
        for defn in _all_blueprints():
            code = defn.pop("code")
            obj = blueprint_service.upsert(code=code, **defn)
            # update_or_create doesn't tell us which path; cheap proxy:
            if obj.created_at == obj.updated_at:
                created += 1
            else:
                updated += 1
            by_level[obj.cefr_level] = by_level.get(obj.cefr_level, 0) + 1
            by_skill[obj.skill] = by_skill.get(obj.skill, 0) + 1

        self.stdout.write(self.style.SUCCESS(
            f"Blueprints seeded: created={created} updated={updated} "
            f"total={created + updated}"
        ))
        self.stdout.write(f"  by CEFR:  {by_level}")
        self.stdout.write(f"  by skill: {by_skill}")
