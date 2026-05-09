"""Procedural question generator — covers ~95 % of bulk volume.

Design:
    * `generate(cefr_level, skill=None, count=N, *, seed=42)` yields up
      to `count` candidate dicts.
    * Each candidate has a deterministic `code` so re-runs with the same
      `seed` and parameters produce the same set (idempotent).
    * The bank of templates is intentionally small but richly
      parameterised — combinatorial expansion gives 50 k+ unique items
      per CEFR level.

The output dicts can be fed directly to `bulk_create(AdaptiveExercise(**d))`.
"""
from __future__ import annotations

import itertools
import random
from typing import Iterable, Optional

from .duplicate_detection import hash_text
from .question_quality import evaluate as evaluate_quality

# Module-level FK cache. Keyed by (skill category | topic slug-or-name) →
# Skill.id / GrammarTopic.id, so a 1k-item batch pays one DB hit per unique
# (skill, topic) pair instead of one per item.
_SKILL_FK_CACHE: dict[str, int | None] = {}
_TOPIC_FK_CACHE: dict[str, int | None] = {}


def _skill_id_for(category: str) -> int | None:
    if category not in _SKILL_FK_CACHE:
        try:
            from learning_core.models import Skill
            row = Skill.objects.filter(category=category, cefr_level="").first()
            _SKILL_FK_CACHE[category] = row.id if row else None
        except Exception:
            _SKILL_FK_CACHE[category] = None
    return _SKILL_FK_CACHE[category]


# Common topic-name → canonical-slug aliases that this module produces.
# Matches the seed in `learning_core.management.commands.backfill_taxonomy`
# so backfill + runtime resolve to the same GrammarTopic row.
_TOPIC_ALIASES = {
    "present-simple":     "present-simple",
    "psimple":            "present-simple",
    "past-simple":        "past-simple",
    "psimple-past":       "past-simple",
    "vocab-inference":    "vocab-in-context",
    "vocab-definitions":  "vocab-definitions",
    "antonyms":           "antonyms",
    "synonyms":           "synonyms",
    "phrasal":            "phrasal-verbs",
    "phrasal-verbs":      "phrasal-verbs",
    "collocations":       "collocations",
    "idioms":             "idioms",
    "free-writing":       "writing-prompt",
    "free-speaking":      "speaking-prompt",
    "past-simple-audio":  "past-simple",
    "gerund-infinitive":  "gerund-infinitive",
    "comparatives":       "comparatives",
    "superlatives":       "superlatives",
    "articles":           "articles",
    "passive-past":       "passive-voice",
    "passive-present":    "passive-voice",
    "passive-modal":      "passive-voice",
    "conditionals-1":     "conditionals",
    "conditionals-2":     "conditionals",
    "conditionals-3":     "conditionals",
    "conditionals-unless":"conditionals",
}


def _topic_id_for(slug_or_name: str) -> int | None:
    raw = (slug_or_name or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    key = _TOPIC_ALIASES.get(raw, raw)
    if key not in _TOPIC_FK_CACHE:
        try:
            from learning_core.models import GrammarTopic
            row = (
                GrammarTopic.objects.filter(slug=key).first()
                or GrammarTopic.objects.filter(name__iexact=slug_or_name).first()
            )
            _TOPIC_FK_CACHE[key] = row.id if row else None
        except Exception:
            _TOPIC_FK_CACHE[key] = None
    return _TOPIC_FK_CACHE[key]

# ---------------------------------------------------------------------------
# Vocabulary substitution banks (small but combinatorial)
# ---------------------------------------------------------------------------

SUBJECTS_SINGULAR = ["she", "he", "the cat", "the dog", "Sara", "Ali",
                     "the teacher", "my friend", "the boy", "the girl",
                     "the doctor", "the driver", "Maria", "Omar"]
SUBJECTS_PLURAL = ["they", "we", "the children", "the students",
                   "my friends", "the boys", "the girls"]
SUBJECTS_I = ["I", "you"]

VERBS_REGULAR = [
    ("walk", "walked", "walking"), ("play", "played", "playing"),
    ("watch", "watched", "watching"), ("listen", "listened", "listening"),
    ("clean", "cleaned", "cleaning"), ("paint", "painted", "painting"),
    ("dance", "danced", "dancing"), ("cook", "cooked", "cooking"),
    ("study", "studied", "studying"), ("travel", "travelled", "travelling"),
    ("call", "called", "calling"), ("open", "opened", "opening"),
    ("close", "closed", "closing"), ("answer", "answered", "answering"),
    ("ask", "asked", "asking"), ("help", "helped", "helping"),
    ("learn", "learned", "learning"), ("work", "worked", "working"),
    ("visit", "visited", "visiting"), ("finish", "finished", "finishing"),
]
VERBS_IRREGULAR = [
    ("go", "went", "gone", "going"),
    ("eat", "ate", "eaten", "eating"),
    ("see", "saw", "seen", "seeing"),
    ("take", "took", "taken", "taking"),
    ("give", "gave", "given", "giving"),
    ("come", "came", "come", "coming"),
    ("write", "wrote", "written", "writing"),
    ("read", "read", "read", "reading"),
    ("speak", "spoke", "spoken", "speaking"),
    ("drive", "drove", "driven", "driving"),
    ("drink", "drank", "drunk", "drinking"),
    ("buy", "bought", "bought", "buying"),
    ("teach", "taught", "taught", "teaching"),
    ("think", "thought", "thought", "thinking"),
    ("bring", "brought", "brought", "bringing"),
    ("find", "found", "found", "finding"),
    ("forget", "forgot", "forgotten", "forgetting"),
    ("get", "got", "got", "getting"),
    ("know", "knew", "known", "knowing"),
    ("make", "made", "made", "making"),
]

OBJECTS = [
    "the book", "a sandwich", "tea", "coffee", "the door", "the window",
    "the homework", "a movie", "the news", "the lesson", "the question",
    "the answer", "the email", "the message", "the phone", "the meeting",
    "the report", "the file", "the room", "the kitchen", "lunch", "dinner",
]
PLACES = [
    "at the office", "at home", "in the park", "at school", "in the kitchen",
    "in the library", "at the gym", "at the cafe", "in class",
    "in Cairo", "in London", "at the airport",
]
TIME_PHRASES = [
    "yesterday", "last night", "last week", "two days ago", "this morning",
    "an hour ago", "in 1995", "before the meeting", "after dinner",
]
FUTURE_TIME = ["tomorrow", "next week", "in an hour", "soon", "this weekend"]
ADVERBS_FREQ = ["always", "often", "usually", "sometimes", "rarely", "never"]
PREPOSITIONS = ["at", "in", "on", "by", "with", "for"]

PREP_QUESTIONS = [
    ("She lives ___ Khartoum.", "in", ["at", "on", "by"], "prepositions_place"),
    ("The meeting is ___ Monday.", "on", ["in", "at", "by"], "prepositions_day"),
    ("I'll see you ___ 9 a.m.", "at", ["on", "in", "by"], "prepositions_time"),
    ("They travel ___ train.", "by", ["in", "on", "at"], "prepositions_means"),
    ("The book is ___ the table.", "on", ["in", "at", "under"], "prepositions_place"),
    ("She works ___ a hospital.", "in", ["at", "on", "by"], "prepositions_place"),
    ("We met ___ the party.", "at", ["in", "on", "by"], "prepositions_event"),
    ("Class starts ___ September.", "in", ["on", "at", "by"], "prepositions_month"),
]

COMPARATIVE_PAIRS = [
    ("tall", "taller", "tallest"), ("big", "bigger", "biggest"),
    ("fast", "faster", "fastest"), ("happy", "happier", "happiest"),
    ("hot", "hotter", "hottest"), ("cold", "colder", "coldest"),
    ("good", "better", "best"), ("bad", "worse", "worst"),
    ("strong", "stronger", "strongest"), ("smart", "smarter", "smartest"),
    ("easy", "easier", "easiest"), ("noisy", "noisier", "noisiest"),
]

ARTICLES_BANK = [
    ("apple", "an"), ("orange", "an"), ("hour", "an"), ("umbrella", "an"),
    ("book", "a"), ("dog", "a"), ("cat", "a"), ("university", "a"),
    ("idea", "an"), ("egg", "an"), ("pen", "a"), ("teacher", "a"),
    ("uncle", "an"), ("apple tree", "an"), ("animal", "an"), ("school", "a"),
]

MODAL_BANK = [
    ("can", "ability"), ("could", "polite_request"), ("should", "advice"),
    ("must", "obligation"), ("may", "permission"), ("might", "possibility"),
    ("would", "polite"), ("ought to", "advice"),
]

CONDITIONAL_BANK = [
    ("If it rains, we ___ stay home.", "will",
     ["would", "had", "shall"], "conditionals_1"),
    ("If I ___ rich, I would travel.", "were",
     ["was", "am", "be"], "conditionals_2"),
    ("If she had studied, she ___ passed.", "would have",
     ["would", "had", "will have"], "conditionals_3"),
    ("Unless you hurry, you ___ miss the bus.", "will",
     ["would", "shall", "do"], "conditionals_unless"),
]

PASSIVE_BANK = [
    ("The Mona Lisa ___ by Da Vinci.", "was painted",
     ["painted", "is painting", "paints"], "passive_past"),
    ("English ___ all over the world.", "is spoken",
     ["speaks", "spoken", "is speaking"], "passive_present"),
    ("The report ___ submitted by Friday.", "must be",
     ["must", "is", "be"], "passive_modal"),
    ("This bridge ___ in 2010.", "was built",
     ["built", "is built", "is being built"], "passive_past"),
]

GERUND_INFINITIVE = [
    ("I enjoy ___ to music.", "listening", ["to listen", "listen", "listened"]),
    ("She decided ___ early.", "to leave", ["leaving", "leave", "left"]),
    ("We can't afford ___ a new car.", "to buy", ["buying", "buy", "bought"]),
    ("He admitted ___ the mistake.", "making", ["to make", "make", "made"]),
    ("They suggested ___ a new plan.", "trying", ["to try", "try", "tried"]),
    ("She refused ___ the offer.", "to accept", ["accepting", "accept", "accepted"]),
]

VOCAB_DEFINITIONS = [
    ("happy",  "feeling joy",            ["sad", "angry", "tired"]),
    ("brave",  "showing courage",        ["scared", "shy", "weak"]),
    ("clever", "intelligent",            ["foolish", "lazy", "rude"]),
    ("kind",   "friendly and helpful",   ["mean", "rude", "selfish"]),
    ("rude",   "not polite",             ["polite", "kind", "shy"]),
    ("tiny",   "very small",             ["huge", "tall", "fat"]),
    ("huge",   "very big",               ["tiny", "small", "short"]),
    ("loud",   "making lots of noise",   ["quiet", "soft", "calm"]),
    ("calm",   "peaceful, not stressed", ["angry", "loud", "afraid"]),
    ("ancient", "extremely old",         ["new", "modern", "fresh"]),
    ("cheap",  "low price",              ["expensive", "free", "rich"]),
    ("famous", "well known",             ["unknown", "private", "secret"]),
    ("polite", "well mannered",          ["rude", "loud", "lazy"]),
    ("lazy",   "not wanting to work",    ["busy", "fast", "active"]),
    ("active", "always moving",          ["lazy", "tired", "calm"]),
    ("safe",   "free from danger",       ["dangerous", "wild", "lost"]),
    ("strange", "unusual",               ["normal", "common", "boring"]),
    ("common", "happens often",          ["rare", "unique", "strange"]),
]

# ---------------------------------------------------------------------------
# Difficulty score banding by CEFR
# ---------------------------------------------------------------------------

DIFF_FOR_LEVEL = {
    "A0": 0.10, "A1": 0.20, "A2": 0.35, "B1": 0.50,
    "B2": 0.65, "C1": 0.80, "C2": 0.92,
}

LEVEL_TIME = {
    "A0": 25, "A1": 28, "A2": 32, "B1": 38,
    "B2": 45, "C1": 55, "C2": 60,
}


def _build(*, cefr, skill, qtype, topic, question, correct,
           distractors, code, explanation="", language="en",
           generated_by="template", metadata_extra: dict | None = None) -> dict:
    """Compose one item dict ready for AdaptiveExercise(**dict)."""
    options = [correct] + list(distractors)
    random.shuffle(options)
    text_hash = hash_text(question + "|" + correct)
    metadata = {
        "topic": topic,
        "bank_code": code,
        "generator": "template",
    }
    if metadata_extra:
        metadata.update(metadata_extra)
    item = {
        "code": code,
        # FK lookups are dict-cached so 1k items pay 1 query per (skill, topic).
        "skill_id": _skill_id_for(skill) if skill else None,
        "topic_id": _topic_id_for(topic) if topic else None,
        "cefr_level": cefr,
        "difficulty_score": DIFF_FOR_LEVEL.get(cefr, 0.5),
        "question_type": qtype,
        "question": question,
        "options": options,
        "correct_answer": correct,
        "explanation": explanation or f"Correct answer: {correct}.",
        "feedback_correct": "Well done!",
        "feedback_wrong": f"The correct answer is '{correct}'.",
        "estimated_time_seconds": LEVEL_TIME.get(cefr, 30),
        "points": 1,
        "language": language,
        "generated_by": generated_by,
        "generated_by_ai": False,
        "is_active": True,
        "is_reviewed": True,         # template-generated content is pre-reviewed
        "quality_score": 100,
        "acceptable_answers": [correct],
        "text_hash": text_hash,
        "metadata": metadata,
    }
    score, _ = evaluate_quality(item)
    item["quality_score"] = score
    return item


# ---------------------------------------------------------------------------
# Per-skill generators
# ---------------------------------------------------------------------------

def _gen_grammar(cefr: str, count: int, rng: random.Random) -> Iterable[dict]:
    yielded = 0

    def yield_(item):
        nonlocal yielded
        if yielded >= count:
            return False
        yield_._items.append(item)
        yielded += 1
        return True
    yield_._items = []

    # 1. Present-simple subject/verb agreement
    for subj, verb in itertools.product(
        SUBJECTS_SINGULAR + SUBJECTS_PLURAL + SUBJECTS_I, VERBS_REGULAR
    ):
        if yielded >= count:
            break
        v_base, v_past, v_ing = verb
        is_3rd = subj.lower() not in ("i", "you", "we", "they") and not (
            subj.lower().startswith("the ") and subj.split()[-1].endswith("s")
        )
        is_3rd = is_3rd and subj not in SUBJECTS_PLURAL and subj not in SUBJECTS_I
        correct = v_base + ("s" if is_3rd else "")
        wrong = v_base if is_3rd else v_base + "s"
        q = f"{subj} ___ to the office every day."
        code = f"tpl:{cefr}:grammar:psimple:{subj.replace(' ', '_')}:{v_base}"
        yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                      topic="present_simple", question=q,
                      correct=correct, distractors=[wrong, v_past, v_ing],
                      code=code,
                      explanation=f"Use '{correct}' with the subject '{subj}' in the present simple."))

    # 2. Past-simple irregulars
    for subj, verb in itertools.product(
        SUBJECTS_SINGULAR + SUBJECTS_PLURAL + SUBJECTS_I, VERBS_IRREGULAR
    ):
        if yielded >= count:
            break
        base, past, pp, ing = verb
        q = f"{subj} ___ {rng.choice(OBJECTS)} {rng.choice(TIME_PHRASES)}."
        code = f"tpl:{cefr}:grammar:psimple_past:{subj.replace(' ', '_')}:{base}"
        yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                      topic="past_simple", question=q,
                      correct=past, distractors=[base, pp, ing],
                      code=code,
                      explanation=f"Past tense of '{base}' is '{past}'."))

    # 3. Articles
    for noun, article in ARTICLES_BANK:
        if yielded >= count:
            break
        q = f"I have ___ {noun}."
        wrong = "a" if article == "an" else "an"
        code = f"tpl:{cefr}:grammar:articles:{noun.replace(' ', '_')}"
        yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                      topic="articles", question=q,
                      correct=article, distractors=[wrong, "the", "—"],
                      code=code,
                      explanation=f"Use '{article}' before '{noun}'."))

    # 4. Comparatives + superlatives
    for adj, comp, sup in COMPARATIVE_PAIRS:
        if yielded >= count:
            break
        q = f"My brother is ___ than me."
        code = f"tpl:{cefr}:grammar:comparative:{adj}"
        yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                      topic="comparatives", question=q,
                      correct=comp, distractors=[adj, sup, f"more {adj}"],
                      code=code,
                      explanation=f"Comparative of '{adj}' is '{comp}'."))
        if yielded >= count:
            break
        q = f"She is the ___ student in class."
        code = f"tpl:{cefr}:grammar:superlative:{adj}"
        yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                      topic="superlatives", question=q,
                      correct=sup, distractors=[adj, comp, f"most {adj}"],
                      code=code,
                      explanation=f"Superlative of '{adj}' is '{sup}'."))

    # 5. Prepositions
    for q, correct, distractors, topic in PREP_QUESTIONS:
        if yielded >= count:
            break
        code = f"tpl:{cefr}:grammar:prep:{topic}:{correct}:{q[:30]}"
        yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                      topic=topic, question=q,
                      correct=correct, distractors=distractors,
                      code=code))

    # 6. Conditionals (B1+)
    if cefr in ("B1", "B2", "C1", "C2"):
        for q, correct, distractors, topic in CONDITIONAL_BANK:
            if yielded >= count:
                break
            code = f"tpl:{cefr}:grammar:cond:{topic}:{correct}"
            yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                          topic=topic, question=q,
                          correct=correct, distractors=distractors,
                          code=code))

    # 7. Passives (B1+)
    if cefr in ("B1", "B2", "C1", "C2"):
        for q, correct, distractors, topic in PASSIVE_BANK:
            if yielded >= count:
                break
            code = f"tpl:{cefr}:grammar:passive:{topic}:{correct[:20]}"
            yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                          topic=topic, question=q,
                          correct=correct, distractors=distractors,
                          code=code))

    # 8. Gerund / infinitive (B1+)
    if cefr in ("B1", "B2", "C1", "C2"):
        for q, correct, distractors in GERUND_INFINITIVE:
            if yielded >= count:
                break
            code = f"tpl:{cefr}:grammar:gerund_inf:{correct[:20]}"
            yield_(_build(cefr=cefr, skill="grammar", qtype="multiple_choice",
                          topic="gerund_infinitive", question=q,
                          correct=correct, distractors=distractors,
                          code=code))

    return yield_._items


def _gen_vocabulary(cefr: str, count: int, rng: random.Random) -> Iterable[dict]:
    items: list[dict] = []
    for word, definition, distractors in VOCAB_DEFINITIONS:
        if len(items) >= count:
            break
        # MCQ: definition → word
        q = f"What does '{word}' mean?"
        code = f"tpl:{cefr}:vocab:def:{word}"
        items.append(_build(cefr=cefr, skill="vocabulary", qtype="multiple_choice",
                            topic="vocab_definitions", question=q,
                            correct=definition,
                            distractors=[d + " (similar word)" for d in distractors],
                            code=code,
                            explanation=f"'{word}' means '{definition}'."))
        if len(items) >= count:
            break
        # Fill-blank: synonyms
        syn = distractors[0]
        q = f"The opposite of '{word}' is ___."
        code = f"tpl:{cefr}:vocab:antonym:{word}"
        items.append(_build(cefr=cefr, skill="vocabulary", qtype="fill_blank",
                            topic="antonyms", question=q,
                            correct=syn,
                            distractors=[word, "thing", "stuff"],
                            code=code,
                            explanation=f"An antonym of '{word}' is '{syn}'."))
    return items


def _gen_reading(cefr: str, count: int, rng: random.Random) -> Iterable[dict]:
    """Short reading-comprehension drills built from vocabulary banks."""
    items: list[dict] = []
    for adj, definition, distractors in VOCAB_DEFINITIONS:
        if len(items) >= count:
            break
        passage = (
            f"{rng.choice(SUBJECTS_SINGULAR).capitalize()} is very {adj}. "
            f"{rng.choice(['Everyone', 'Friends', 'Teachers'])} say so."
        )
        q = f"{passage}\n\nWhich word means '{adj}'?"
        code = f"tpl:{cefr}:reading:vocab_inference:{adj}"
        items.append(_build(cefr=cefr, skill="reading", qtype="reading_comprehension",
                            topic="vocab_inference", question=q,
                            correct=adj,
                            distractors=distractors,
                            code=code,
                            explanation=f"The passage says someone is '{adj}'."))
    return items


def _gen_listening(cefr: str, count: int, rng: random.Random) -> Iterable[dict]:
    items: list[dict] = []
    for v in VERBS_IRREGULAR:
        if len(items) >= count:
            break
        base, past, pp, ing = v
        q = f"Listen and complete: 'Yesterday I ___ to the park.'"
        code = f"tpl:{cefr}:listening:past:{base}"
        items.append(_build(cefr=cefr, skill="listening", qtype="listening_comprehension",
                            topic="past_simple_audio", question=q,
                            correct=past,
                            distractors=[base, pp, ing],
                            code=code,
                            metadata_extra={"audio_target": q}))
    return items


def _gen_writing(cefr: str, count: int, rng: random.Random) -> Iterable[dict]:
    prompts = [
        "Describe your daily routine in 4 sentences.",
        "Write about your favourite hobby.",
        "Describe a memorable trip you took.",
        "Write a short message to a friend inviting them to a party.",
        "Describe your dream job in 5 sentences.",
        "Write 3 sentences about your family.",
        "Describe what you did last weekend.",
        "Write about your plans for next week.",
        "Describe a person you admire.",
        "Write a short complaint email about a faulty product.",
    ]
    items = []
    for i, p in enumerate(prompts):
        if len(items) >= count:
            break
        code = f"tpl:{cefr}:writing:prompt:{i:03d}"
        items.append(_build(cefr=cefr, skill="writing", qtype="writing_prompt",
                            topic="free_writing", question=p,
                            correct="(open response)", distractors=[],
                            code=code,
                            explanation="A model response will be evaluated by the AI tutor."))
    return items


def _gen_speaking(cefr: str, count: int, rng: random.Random) -> Iterable[dict]:
    prompts = [
        "Introduce yourself in 30 seconds.",
        "Describe your hometown.",
        "Talk about your favourite food.",
        "Describe a memorable day from last year.",
        "Talk about a book or film you enjoyed recently.",
        "Discuss the pros and cons of remote learning.",
        "Describe a goal you want to achieve next year.",
        "Talk about a person who influenced you.",
        "Describe your morning routine.",
        "Discuss the importance of learning English.",
    ]
    items = []
    for i, p in enumerate(prompts):
        if len(items) >= count:
            break
        code = f"tpl:{cefr}:speaking:prompt:{i:03d}"
        items.append(_build(cefr=cefr, skill="speaking", qtype="speaking_prompt",
                            topic="free_speaking", question=p,
                            correct="(open response)", distractors=[],
                            code=code,
                            explanation="Recording will be assessed for fluency + pronunciation."))
    return items


SKILL_GENERATORS = {
    "grammar":    _gen_grammar,
    "vocabulary": _gen_vocabulary,
    "reading":    _gen_reading,
    "listening":  _gen_listening,
    "writing":    _gen_writing,
    "speaking":   _gen_speaking,
}


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def generate(
    cefr_level: str,
    *,
    skill: Optional[str] = None,
    count: int = 100,
    seed: int = 42,
    variant: int = 0,
) -> list[dict]:
    """Yield up to `count` items for `cefr_level` (and optionally `skill`).

    `variant` lets callers spawn additional shuffled copies (useful for
    padding the bank without changing the underlying templates).
    """
    rng = random.Random(seed + variant)
    out: list[dict] = []
    skills = [skill] if skill else list(SKILL_GENERATORS.keys())
    # Round-robin draw across skills so we always reach `count` even when
    # `count` doesn't divide evenly. Each skill is over-generated so we can
    # always pull more if a peer skill exhausts its templates first.
    per_skill_pool = max(count, 50)
    pools: list[list[dict]] = []
    for s in skills:
        gen = SKILL_GENERATORS.get(s)
        if not gen:
            pools.append([])
            continue
        rows = list(gen(cefr_level, per_skill_pool, rng))
        if variant:
            for r in rows:
                r["code"] = f"{r['code']}#v{variant}"
        pools.append(rows)
    cursors = [0] * len(pools)
    while len(out) < count:
        progressed = False
        for i, pool in enumerate(pools):
            if len(out) >= count:
                break
            if cursors[i] < len(pool):
                out.append(pool[cursors[i]])
                cursors[i] += 1
                progressed = True
        if not progressed:
            break
    return out[:count]


def generate_unique(
    cefr_level: str,
    *,
    skill: Optional[str] = None,
    target: int,
    seed: int = 42,
) -> list[dict]:
    """Generate >= target items by spinning up variants. Caller is
    responsible for the final dedup pass against the DB (`bulk_filter_new`).
    """
    out: list[dict] = []
    seen_codes: set[str] = set()
    variant = 0
    while len(out) < target and variant < 200:
        for r in generate(cefr_level, skill=skill, count=max(50, target),
                          seed=seed, variant=variant):
            if r["code"] in seen_codes:
                continue
            seen_codes.add(r["code"])
            out.append(r)
            if len(out) >= target:
                break
        variant += 1
    return out
