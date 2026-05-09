"""Seed 1000+ adaptive exercises across A0..C2 using small structured banks.

Idempotent: each exercise is keyed on a deterministic `bank_code` that we
store in `metadata["bank_code"]`. Re-running the command updates existing
rows in place rather than duplicating.

Banks:
    A0 — emoji-based picture words (animals, food, body, family, colors)
    A1 — picture verbs (run, eat, sleep…), present-simple MCQ, articles
    A2 — past simple, prepositions, comparatives, basic questions
    B1 — present perfect, conditionals, modals, phrasal verbs
    B2 — passive voice, reported speech, gerund-vs-infinitive, advanced MCQ
    C1 — subjunctive, advanced phrasals, idioms, formal register
    C2 — literary register, nuance, register-shift correction

Picture exercises store the emoji in `metadata["picture"]` so the
front-end can render it as the question's hero. The text question stays
useful for clients that don't render emoji.
"""
from __future__ import annotations

import random
from typing import List

from django.core.management.base import BaseCommand
from django.db import transaction

from learning_core.models import AdaptiveExercise, Skill


# ---------------------------------------------------------------------------
# A0 — picture words (emoji-as-image)
# ---------------------------------------------------------------------------

PICTURE_WORDS = [
    # (emoji, correct, distractors)
    ("🍎", "apple",  ["banana", "orange", "mango"]),
    ("🍌", "banana", ["apple", "pear", "lemon"]),
    ("🍊", "orange", ["apple", "lemon", "peach"]),
    ("🍇", "grape",  ["cherry", "plum", "berry"]),
    ("🍉", "watermelon", ["pineapple", "melon", "mango"]),
    ("🍓", "strawberry", ["raspberry", "cherry", "tomato"]),
    ("🥕", "carrot", ["potato", "onion", "radish"]),
    ("🥔", "potato", ["onion", "tomato", "garlic"]),
    ("🍞", "bread",  ["cake", "toast", "rice"]),
    ("🧀", "cheese", ["butter", "milk", "yogurt"]),
    ("🥛", "milk",   ["water", "tea", "juice"]),
    ("☕", "coffee", ["tea", "water", "soup"]),
    ("🍵", "tea",    ["coffee", "soup", "milk"]),
    ("🍕", "pizza",  ["burger", "pasta", "sandwich"]),
    ("🍔", "burger", ["pizza", "hot dog", "sandwich"]),
    ("🍟", "fries",  ["chips", "pasta", "rice"]),
    ("🍣", "sushi",  ["rice", "fish", "noodles"]),
    ("🍜", "noodles", ["rice", "pasta", "soup"]),
    ("🍪", "cookie", ["cake", "biscuit", "candy"]),
    ("🎂", "cake",   ["bread", "pie", "donut"]),

    ("🐶", "dog",    ["cat", "wolf", "fox"]),
    ("🐱", "cat",    ["dog", "tiger", "rabbit"]),
    ("🐭", "mouse",  ["rat", "hamster", "rabbit"]),
    ("🐰", "rabbit", ["hamster", "mouse", "fox"]),
    ("🦊", "fox",    ["wolf", "dog", "cat"]),
    ("🐻", "bear",   ["panda", "dog", "monkey"]),
    ("🐼", "panda",  ["bear", "koala", "raccoon"]),
    ("🦁", "lion",   ["tiger", "cat", "leopard"]),
    ("🐯", "tiger",  ["lion", "cat", "leopard"]),
    ("🐮", "cow",    ["bull", "horse", "goat"]),
    ("🐷", "pig",    ["cow", "boar", "sheep"]),
    ("🐸", "frog",   ["lizard", "fish", "snake"]),
    ("🐟", "fish",   ["shark", "dolphin", "whale"]),
    ("🐦", "bird",   ["chicken", "duck", "owl"]),
    ("🐔", "chicken", ["duck", "bird", "owl"]),
    ("🦆", "duck",   ["chicken", "swan", "goose"]),
    ("🐝", "bee",    ["wasp", "fly", "ant"]),
    ("🐌", "snail",  ["worm", "slug", "ant"]),
    ("🐢", "turtle", ["frog", "lizard", "tortoise"]),
    ("🦋", "butterfly", ["bee", "moth", "fly"]),

    ("👁️", "eye",    ["ear", "nose", "mouth"]),
    ("👃", "nose",   ["ear", "eye", "mouth"]),
    ("👂", "ear",    ["eye", "nose", "mouth"]),
    ("👄", "mouth",  ["lip", "tongue", "teeth"]),
    ("✋", "hand",   ["foot", "arm", "finger"]),
    ("🦶", "foot",   ["hand", "leg", "toe"]),
    ("🦷", "tooth",  ["tongue", "lip", "mouth"]),
    ("💪", "arm",    ["leg", "hand", "muscle"]),
    ("🧠", "brain",  ["heart", "head", "mind"]),
    ("❤️", "heart", ["lung", "brain", "love"]),

    ("👨", "man",    ["boy", "father", "uncle"]),
    ("👩", "woman",  ["girl", "mother", "aunt"]),
    ("👦", "boy",    ["man", "kid", "son"]),
    ("👧", "girl",   ["woman", "kid", "daughter"]),
    ("👶", "baby",   ["kid", "child", "boy"]),
    ("👴", "grandfather", ["father", "uncle", "old man"]),
    ("👵", "grandmother", ["mother", "aunt", "old woman"]),
    ("👨‍👩‍👧", "family", ["group", "team", "friends"]),
    ("👫", "couple", ["friends", "siblings", "team"]),

    ("🟥", "red",    ["blue", "yellow", "green"]),
    ("🟦", "blue",   ["red", "green", "purple"]),
    ("🟩", "green",  ["red", "blue", "yellow"]),
    ("🟨", "yellow", ["red", "blue", "orange"]),
    ("🟧", "orange", ["red", "yellow", "brown"]),
    ("🟪", "purple", ["pink", "blue", "violet"]),
    ("⬛", "black",  ["white", "grey", "brown"]),
    ("⬜", "white",  ["black", "grey", "silver"]),
    ("🟫", "brown",  ["black", "grey", "tan"]),
    ("🩷", "pink",   ["red", "purple", "rose"]),

    ("🚗", "car",    ["bus", "truck", "taxi"]),
    ("🚌", "bus",    ["car", "truck", "train"]),
    ("🚲", "bike",   ["scooter", "motorbike", "skateboard"]),
    ("✈️", "plane", ["helicopter", "rocket", "bird"]),
    ("🚂", "train",  ["bus", "tram", "subway"]),
    ("🛏️", "bed",   ["sofa", "chair", "table"]),
    ("🪑", "chair",  ["sofa", "stool", "bench"]),
    ("📚", "book",   ["magazine", "notebook", "paper"]),
    ("📱", "phone",  ["tablet", "computer", "laptop"]),
    ("💻", "laptop", ["phone", "tablet", "desktop"]),
    ("🏠", "house",  ["building", "tent", "hut"]),
    ("🏫", "school", ["library", "office", "house"]),
    ("🏥", "hospital", ["clinic", "school", "office"]),
    ("🌳", "tree",   ["bush", "flower", "plant"]),
    ("🌹", "rose",   ["tulip", "flower", "lily"]),
    ("🌞", "sun",    ["moon", "star", "earth"]),
    ("🌙", "moon",   ["sun", "star", "earth"]),
    ("⭐", "star",   ["sun", "moon", "planet"]),
    ("☁️", "cloud",  ["rain", "fog", "sky"]),
    ("☔", "umbrella", ["coat", "hat", "raincoat"]),
]


# ---------------------------------------------------------------------------
# A1 — picture verbs
# ---------------------------------------------------------------------------

PICTURE_VERBS = [
    ("🏃", "run",   ["walk", "jump", "stand"]),
    ("🚶", "walk",  ["run", "stand", "sit"]),
    ("🏊", "swim",  ["dive", "float", "sail"]),
    ("🚴", "cycle", ["drive", "walk", "run"]),
    ("😴", "sleep", ["rest", "dream", "nap"]),
    ("🍴", "eat",   ["cook", "drink", "taste"]),
    ("🥤", "drink", ["eat", "sip", "swallow"]),
    ("📖", "read",  ["write", "study", "learn"]),
    ("✏️", "write", ["read", "draw", "type"]),
    ("🎤", "sing",  ["talk", "shout", "whisper"]),
    ("💃", "dance", ["jump", "walk", "stand"]),
    ("🎨", "paint", ["draw", "color", "sketch"]),
    ("🍳", "cook",  ["bake", "fry", "boil"]),
    ("🧹", "clean", ["wash", "wipe", "tidy"]),
    ("🛁", "bathe", ["wash", "shower", "swim"]),
    ("🤣", "laugh", ["smile", "cry", "shout"]),
    ("😢", "cry",   ["laugh", "smile", "frown"]),
    ("👏", "clap",  ["wave", "shake", "high-five"]),
    ("🤝", "shake hands", ["wave", "hug", "clap"]),
    ("👋", "wave",  ["clap", "shake", "point"]),
    ("🙋", "raise hand", ["wave", "point", "stand"]),
    ("🤔", "think", ["wonder", "imagine", "guess"]),
    ("📞", "call",  ["text", "speak", "shout"]),
    ("✉️", "send",  ["write", "post", "mail"]),
    ("🛒", "buy",   ["pay", "sell", "shop"]),
    ("💰", "pay",   ["buy", "sell", "earn"]),
    ("🎁", "give",  ["take", "send", "share"]),
    ("👀", "look",  ["see", "watch", "stare"]),
    ("👂", "listen", ["hear", "speak", "whisper"]),
    ("🗣️", "speak", ["talk", "shout", "whisper"]),
]


# ---------------------------------------------------------------------------
# A1/A2 — picture adjectives
# ---------------------------------------------------------------------------

PICTURE_ADJECTIVES = [
    ("😊", "happy",  ["sad", "angry", "tired"]),
    ("😢", "sad",    ["happy", "angry", "scared"]),
    ("😡", "angry",  ["happy", "sad", "calm"]),
    ("😨", "scared", ["brave", "happy", "calm"]),
    ("😴", "tired",  ["awake", "energetic", "happy"]),
    ("🤒", "sick",   ["healthy", "tired", "well"]),
    ("🥳", "excited", ["bored", "tired", "calm"]),
    ("😍", "in love", ["angry", "scared", "tired"]),
    ("🐘", "big",    ["small", "tiny", "short"]),
    ("🐭", "small",  ["big", "huge", "tall"]),
    ("📏", "long",   ["short", "tall", "wide"]),
    ("📐", "short",  ["long", "tall", "wide"]),
    ("🗻", "high",   ["low", "deep", "short"]),
    ("⬇️", "low",    ["high", "tall", "deep"]),
    ("🍦", "cold",   ["hot", "warm", "cool"]),
    ("🔥", "hot",    ["cold", "warm", "cool"]),
    ("☀️", "bright", ["dark", "dim", "shadowy"]),
    ("🌑", "dark",   ["bright", "light", "shiny"]),
    ("⚡", "fast",   ["slow", "quick", "rapid"]),
    ("🐢", "slow",   ["fast", "quick", "rapid"]),
    ("💪", "strong", ["weak", "soft", "thin"]),
    ("🪶", "light",  ["heavy", "strong", "hard"]),
    ("🪨", "heavy",  ["light", "soft", "fluffy"]),
    ("🧊", "hard",   ["soft", "smooth", "flexible"]),
    ("☁️", "soft",   ["hard", "rough", "stiff"]),
    ("🆕", "new",    ["old", "used", "ancient"]),
    ("🏚️", "old",    ["new", "modern", "fresh"]),
    ("🧼", "clean",  ["dirty", "messy", "stained"]),
    ("💩", "dirty",  ["clean", "tidy", "neat"]),
    ("💎", "expensive", ["cheap", "free", "affordable"]),
]


# ---------------------------------------------------------------------------
# Grammar banks (text-only) — A1..C2
# Each tuple: (cefr, type, question, correct, distractors, topic)
# ---------------------------------------------------------------------------

GRAMMAR_BANK = [
    # ----- A1 (basic present simple, articles, plurals, to be) -----
    ("A1", "multiple_choice", "She _____ to school every day.", "goes", ["go", "going", "gone"], "present_simple"),
    ("A1", "multiple_choice", "I _____ a student.", "am", ["is", "are", "be"], "to_be"),
    ("A1", "multiple_choice", "They _____ my friends.", "are", ["am", "is", "be"], "to_be"),
    ("A1", "multiple_choice", "He _____ tea every morning.", "drinks", ["drink", "drinking", "drank"], "present_simple"),
    ("A1", "multiple_choice", "We _____ in London.", "live", ["lives", "living", "lived"], "present_simple"),
    ("A1", "multiple_choice", "She has _____ apple.", "an", ["a", "the", "—"], "articles"),
    ("A1", "multiple_choice", "I have _____ cat.", "a", ["an", "the", "—"], "articles"),
    ("A1", "multiple_choice", "There are three _____.", "books", ["book", "bookes", "bookies"], "plurals"),
    ("A1", "multiple_choice", "I have two _____.", "children", ["childs", "childrens", "child"], "plurals"),
    ("A1", "multiple_choice", "_____ name is Ali.", "My", ["I", "Me", "Mine"], "possessive"),
    ("A1", "multiple_choice", "What is _____ name?", "your", ["you", "yours", "ya"], "possessive"),
    ("A1", "multiple_choice", "She _____ from Sudan.", "is", ["are", "am", "be"], "to_be"),
    ("A1", "multiple_choice", "I _____ like coffee.", "don't", ["doesn't", "isn't", "not"], "negation"),
    ("A1", "multiple_choice", "He _____ speak French.", "doesn't", ["don't", "isn't", "not"], "negation"),
    ("A1", "multiple_choice", "_____ you English?", "Are", ["Is", "Am", "Be"], "questions"),
    ("A1", "multiple_choice", "_____ does she live?", "Where", ["What", "Who", "When"], "wh_questions"),
    ("A1", "multiple_choice", "_____ is your birthday?", "When", ["Where", "Who", "Why"], "wh_questions"),
    ("A1", "multiple_choice", "_____ is the capital of Egypt?", "What", ["When", "Why", "How"], "wh_questions"),
    ("A1", "multiple_choice", "I have ___ brother.", "one", ["a one", "the one", "an"], "numbers"),
    ("A1", "multiple_choice", "There ___ many books on the shelf.", "are", ["is", "am", "be"], "there_be"),

    # ----- A2 (past simple, prepositions, comparatives) -----
    ("A2", "multiple_choice", "Yesterday, I _____ to the market.", "went", ["go", "goes", "gone"], "past_simple"),
    ("A2", "multiple_choice", "She _____ her homework last night.", "did", ["does", "do", "doing"], "past_simple"),
    ("A2", "multiple_choice", "We _____ a movie last weekend.", "watched", ["watch", "watching", "watches"], "past_simple"),
    ("A2", "multiple_choice", "He _____ in 1990.", "was born", ["born", "is born", "borned"], "past_simple"),
    ("A2", "multiple_choice", "They _____ their friends yesterday.", "met", ["meet", "meets", "meeting"], "past_simple"),
    ("A2", "multiple_choice", "The cat is _____ the table.", "under", ["over", "in", "on"], "prepositions"),
    ("A2", "multiple_choice", "We meet _____ Mondays.", "on", ["in", "at", "of"], "prepositions"),
    ("A2", "multiple_choice", "She lives _____ Khartoum.", "in", ["at", "on", "to"], "prepositions"),
    ("A2", "multiple_choice", "The store opens _____ 9 a.m.", "at", ["in", "on", "by"], "prepositions"),
    ("A2", "multiple_choice", "This book is _____ than that one.", "better", ["good", "best", "more good"], "comparatives"),
    ("A2", "multiple_choice", "She is the _____ student in the class.", "best", ["good", "better", "more good"], "superlatives"),
    ("A2", "multiple_choice", "My brother is _____ than me.", "taller", ["tall", "tallest", "more tall"], "comparatives"),
    ("A2", "multiple_choice", "It is _____ today than yesterday.", "hotter", ["hot", "hottest", "more hot"], "comparatives"),
    ("A2", "multiple_choice", "I _____ go to the gym three times a week.", "usually", ["usual", "use", "usuall"], "adverbs"),
    ("A2", "multiple_choice", "She speaks English _____.", "fluently", ["fluent", "fluence", "fluentily"], "adverbs"),
    ("A2", "multiple_choice", "_____ you come to the party last night?", "Did", ["Do", "Does", "Are"], "past_questions"),
    ("A2", "fill_blank", "She _____ a sandwich for lunch yesterday.", "ate", ["eat", "eats", "eating"], "past_simple"),
    ("A2", "fill_blank", "We _____ to Cairo last summer.", "went", ["go", "goes", "going"], "past_simple"),
    ("A2", "fill_blank", "He _____ the door slowly.", "opened", ["open", "opens", "opening"], "past_simple"),
    ("A2", "fill_blank", "Look! It _____ raining.", "is", ["are", "am", "be"], "present_continuous"),

    # ----- B1 (present perfect, conditionals, modals) -----
    ("B1", "multiple_choice", "I _____ to Paris three times.", "have been", ["was", "had been", "am"], "present_perfect"),
    ("B1", "multiple_choice", "She _____ her keys.", "has lost", ["lost", "losed", "is losing"], "present_perfect"),
    ("B1", "multiple_choice", "We _____ each other since 2010.", "have known", ["know", "knew", "are knowing"], "present_perfect"),
    ("B1", "multiple_choice", "He _____ already finished.", "has", ["have", "is", "did"], "present_perfect"),
    ("B1", "multiple_choice", "If I _____ rich, I would travel.", "were", ["was", "am", "be"], "conditionals_2"),
    ("B1", "multiple_choice", "If you study, you _____ pass.", "will", ["would", "should", "must"], "conditionals_1"),
    ("B1", "multiple_choice", "If I had known, I _____ helped.", "would have", ["will", "would", "had"], "conditionals_3"),
    ("B1", "multiple_choice", "You _____ smoke here. It's forbidden.", "must not", ["shouldn't", "don't", "won't"], "modals"),
    ("B1", "multiple_choice", "She _____ speak French fluently.", "can", ["could", "is", "may"], "modals"),
    ("B1", "multiple_choice", "We _____ leave early today.", "have to", ["has to", "must to", "should to"], "modals"),
    ("B1", "multiple_choice", "_____ I open the window?", "May", ["Mays", "Mayed", "Maying"], "modals"),
    ("B1", "multiple_choice", "He _____ be at home; his car is here.", "must", ["should", "could", "may"], "modals_deduction"),
    ("B1", "multiple_choice", "I'm _____ ('m looking forward) seeing you.", "to", ["for", "in", "of"], "phrasal_verbs"),
    ("B1", "fill_blank", "She _____ never visited Italy before.", "has", ["have", "is", "had"], "present_perfect"),
    ("B1", "fill_blank", "If it _____, we'll cancel the picnic.", "rains", ["rain", "raining", "rained"], "conditionals_1"),
    ("B1", "fill_blank", "I _____ to call you yesterday but I forgot.", "meant", ["mean", "means", "meaning"], "past_simple"),
    ("B1", "fill_blank", "By the time we arrived, the show _____.", "had ended", ["has ended", "ended", "was ending"], "past_perfect"),
    ("B1", "fill_blank", "The book _____ by millions of readers.", "has been read", ["read", "is read", "was read"], "passive_voice"),
    ("B1", "correction", "Choose the corrected sentence: 'She don't likes coffee.'", "She doesn't like coffee.", ["She no like coffee.", "She don't like coffee.", "She doesn't likes coffee."], "negation"),
    ("B1", "correction", "Choose the corrected sentence: 'He been to London.'", "He has been to London.", ["He is been to London.", "He been to London.", "He been London."], "present_perfect"),

    # ----- B2 (passive, reported, gerund/infinitive) -----
    ("B2", "multiple_choice", "The Mona Lisa _____ by Da Vinci.", "was painted", ["painted", "is painting", "paints"], "passive_voice"),
    ("B2", "multiple_choice", "English _____ all over the world.", "is spoken", ["speaks", "is speaking", "spoken"], "passive_voice"),
    ("B2", "multiple_choice", "She said she _____ tired.", "was", ["is", "has been", "be"], "reported_speech"),
    ("B2", "multiple_choice", "He told me he _____ call later.", "would", ["will", "shall", "is"], "reported_speech"),
    ("B2", "multiple_choice", "I enjoy _____ to music.", "listening", ["to listen", "listen", "listened"], "gerund_infinitive"),
    ("B2", "multiple_choice", "She decided _____ early.", "to leave", ["leaving", "leave", "left"], "gerund_infinitive"),
    ("B2", "multiple_choice", "We can't afford _____ a new car.", "to buy", ["buying", "buy", "bought"], "gerund_infinitive"),
    ("B2", "multiple_choice", "He admitted _____ the mistake.", "making", ["to make", "make", "made"], "gerund_infinitive"),
    ("B2", "multiple_choice", "Despite _____ tired, she finished the race.", "being", ["be", "to be", "was"], "linking_words"),
    ("B2", "multiple_choice", "_____ the rain, we went hiking.", "Despite", ["Although", "Because", "Even though"], "linking_words"),
    ("B2", "fill_blank", "By next year, she _____ here for ten years.", "will have lived", ["will live", "has lived", "lived"], "future_perfect"),
    ("B2", "fill_blank", "If I had studied harder, I _____ the exam.", "would have passed", ["would pass", "had passed", "will pass"], "conditionals_3"),
    ("B2", "fill_blank", "The report _____ submitted by Friday.", "must be", ["must", "is", "be"], "passive_modal"),
    ("B2", "correction", "Choose the corrected sentence: 'He suggested to go for a walk.'", "He suggested going for a walk.", ["He suggested go.", "He suggested to going.", "He suggested for going."], "gerund_infinitive"),
    ("B2", "correction", "Choose the corrected sentence: 'I look forward to hear from you.'", "I look forward to hearing from you.", ["I look forward hearing.", "I look forward hear.", "I am looking forward hear."], "gerund_infinitive"),

    # ----- C1 (advanced, idioms, register) -----
    ("C1", "multiple_choice", "Had I known earlier, I _____ differently.", "would have acted", ["would act", "had acted", "will act"], "inversion"),
    ("C1", "multiple_choice", "Not only _____ late, but he was rude.", "was he", ["he was", "did he", "he did"], "inversion"),
    ("C1", "multiple_choice", "She is reluctant _____ admit her mistake.", "to", ["for", "of", "in"], "advanced_grammar"),
    ("C1", "multiple_choice", "I'd rather you _____ smoke here.", "didn't", ["don't", "won't", "wouldn't"], "subjunctive"),
    ("C1", "multiple_choice", "It's high time we _____.", "left", ["leave", "leaving", "have left"], "subjunctive"),
    ("C1", "multiple_choice", "He insisted that she _____ on time.", "be", ["is", "was", "will be"], "subjunctive"),
    ("C1", "multiple_choice", "She has a knack _____ languages.", "for", ["of", "to", "in"], "collocations"),
    ("C1", "multiple_choice", "He's known for _____ his cool under pressure.", "keeping", ["to keep", "keep", "kept"], "idioms"),
    ("C1", "multiple_choice", "It's not my cup of _____.", "tea", ["coffee", "drink", "thing"], "idioms"),
    ("C1", "multiple_choice", "The project went _____ schedule.", "ahead of", ["before of", "in front of", "above of"], "idioms"),
    ("C1", "fill_blank", "Should you require assistance, please _____.", "let me know", ["letting me know", "let knowing", "letting know"], "formal_register"),
    ("C1", "correction", "Choose the corrected sentence: 'The sooner we leave, sooner we arrive.'", "The sooner we leave, the sooner we arrive.", ["The sooner we leave, sooner arriving.", "Sooner we leave, sooner we arrive.", "The sooner leave, the sooner arrive."], "comparative_correlatives"),

    # ----- C2 (literary, nuance) -----
    ("C2", "multiple_choice", "Were it not for her efforts, the project _____ failed.", "would have", ["had", "will have", "would"], "inversion"),
    ("C2", "multiple_choice", "The very notion that he _____ guilty is absurd.", "is", ["was", "be", "had been"], "subjunctive"),
    ("C2", "multiple_choice", "Hardly _____ when the bell rang.", "had I sat down", ["I had sat", "did I sit", "I sat"], "inversion"),
    ("C2", "multiple_choice", "The argument is, in essence, _____.", "circular", ["round", "loopy", "spinning"], "register"),
    ("C2", "multiple_choice", "She is, _____, the most qualified candidate.", "without doubt", ["without doubts", "with no doubt", "with doubts"], "register"),
    ("C2", "multiple_choice", "His tone was _____, betraying his irritation.", "clipped", ["short", "small", "cut"], "register"),
    ("C2", "fill_blank", "The author _____ a haunting picture of post-war life.", "paints", ["draws", "writes", "shows"], "literary_register"),
    ("C2", "fill_blank", "His arguments are _____ persuasive.", "compellingly", ["very", "more", "really"], "register"),
    ("C2", "correction", "Choose the corrected sentence: 'Less people came than expected.'", "Fewer people came than expected.", ["Less people came than expected.", "Lesser people came than expected.", "More less people came."], "register"),
    ("C2", "correction", "Choose the corrected sentence: 'Between you and I, this is private.'", "Between you and me, this is private.", ["Between you and I, this is private.", "Between you and myself, this is private.", "Between we two, this is private."], "register"),
]


THETA_FOR_LEVEL = {
    "A0": -2.8, "A1": -2.0, "A2": -1.0,
    "B1":  0.0, "B2":  1.0,
    "C1":  2.0, "C2":  2.6,
}


def _difficulty_for_level(level: str) -> float:
    """Map CEFR → 0..1 difficulty score (matches recommend_next_difficulty)."""
    table = {"A0": 0.05, "A1": 0.15, "A2": 0.30, "B1": 0.50,
             "B2": 0.70, "C1": 0.85, "C2": 0.95}
    return table.get(level, 0.5)


def _resolve_skill(category: str) -> Skill | None:
    """Pick any active skill in this category as the FK target."""
    return Skill.objects.filter(category=category).first()


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _picture_rows(level: str, kind: str, bank: list, *, seed: int) -> list[dict]:
    """Yield exercise dicts from a picture bank.
    `kind` is one of `picture_word`, `picture_verb`, `picture_adjective`."""
    rng = random.Random(seed)
    skill = _resolve_skill("vocabulary")
    rows = []
    prompts = {
        "picture_word":      "What is this?",
        "picture_verb":      "What is this person doing?",
        "picture_adjective": "Which word describes this?",
    }
    arabic_prompts = {
        "picture_word":      "ما هذا؟",
        "picture_verb":      "ماذا يفعل هذا الشخص؟",
        "picture_adjective": "أي كلمة تصف هذا؟",
    }
    for emoji, correct, distractors in bank:
        opts = [correct] + list(distractors)
        rng.shuffle(opts)
        rows.append({
            "skill": skill,
            "cefr_level": level,
            "difficulty_score": _difficulty_for_level(level),
            "question_type": kind,
            "question": f"{emoji}  —  {prompts[kind]}",
            "options": opts,
            "correct_answer": correct,
            "explanation": f"This is {correct}.",
            "generated_by_ai": False,
            "metadata": {
                "bank_code": f"{kind}:{emoji}:{correct}",
                "picture":   emoji,
                "prompt_en": prompts[kind],
                "prompt_ar": arabic_prompts[kind],
            },
        })
    return rows


def _grammar_rows(*, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    skill_grammar = _resolve_skill("grammar")
    skill_vocab = _resolve_skill("vocabulary")
    for cefr, qtype, q, correct, distractors, topic in GRAMMAR_BANK:
        opts = [correct] + list(distractors)
        rng.shuffle(opts)
        rows.append({
            "skill": skill_grammar if topic != "vocabulary" else skill_vocab,
            "cefr_level": cefr,
            "difficulty_score": _difficulty_for_level(cefr),
            "question_type": qtype,
            "question": q,
            "options": opts,
            "correct_answer": correct,
            "explanation": "",
            "generated_by_ai": False,
            "metadata": {
                "bank_code": f"grammar:{cefr}:{topic}:{q[:60]}",
                "topic": topic,
            },
        })
    return rows


def _expand_with_variations(rows: list[dict], *, seed: int, target_count: int) -> list[dict]:
    """Pad the bank with light variations (different distractor orders) so
    the live database has enough material to randomise from."""
    rng = random.Random(seed)
    out = list(rows)
    # Each row spawns 2 sibling variants with reshuffled distractors and
    # a stable bank_code suffix. 3× yields ~3 rows per template ⇒ many
    # exercises while still being curated.
    for variant in range(2):
        for r in rows:
            opts = list(r["options"])
            rng.shuffle(opts)
            sibling = {**r, "options": opts}
            sibling["metadata"] = {**r["metadata"],
                                   "bank_code": f"{r['metadata']['bank_code']}#v{variant + 1}"}
            out.append(sibling)
    return out[:target_count] if target_count else out


def _persist(rows: list[dict]) -> tuple[int, int]:
    """Bulk upsert into AdaptiveExercise keyed on metadata['bank_code']."""
    created = updated = 0
    with transaction.atomic():
        for r in rows:
            code = r["metadata"]["bank_code"]
            existing = AdaptiveExercise.objects.filter(
                metadata__bank_code=code
            ).first()
            if existing:
                for k, v in r.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
            else:
                AdaptiveExercise.objects.create(**r)
                created += 1
    return created, updated


class Command(BaseCommand):
    help = "Seed 1000+ adaptive exercises across A0..C2 (picture banks for A0/A1)."

    def add_arguments(self, parser):
        parser.add_argument("--target", type=int, default=1000,
                            help="Approximate target exercise count (default 1000)")
        parser.add_argument("--seed", type=int, default=42,
                            help="RNG seed for distractor shuffling.")

    def handle(self, *args, target: int = 1000, seed: int = 42, **opts):
        all_rows: list[dict] = []

        # A0 picture-words (~100 base × 3 variants = ~300)
        all_rows += _expand_with_variations(
            _picture_rows("A0", "picture_word", PICTURE_WORDS, seed=seed),
            seed=seed, target_count=0,
        )
        # A1 picture-verbs (~30 × 3 = ~90)
        all_rows += _expand_with_variations(
            _picture_rows("A1", "picture_verb", PICTURE_VERBS, seed=seed + 1),
            seed=seed + 1, target_count=0,
        )
        # A1/A2 picture-adjectives (~30 × 3 = ~90), tagged at A1
        all_rows += _expand_with_variations(
            _picture_rows("A1", "picture_adjective", PICTURE_ADJECTIVES, seed=seed + 2),
            seed=seed + 2, target_count=0,
        )
        # Grammar bank A1..C2 (~75 × 3 = ~225)
        all_rows += _expand_with_variations(
            _grammar_rows(seed=seed + 3), seed=seed + 3, target_count=0,
        )

        # If we still need more to hit the target, spawn extra variants of
        # the grammar bank only (we don't want to over-pad picture types).
        if len(all_rows) < target:
            shortfall = target - len(all_rows)
            extra = []
            base = _grammar_rows(seed=seed + 4)
            v = 3
            while len(extra) < shortfall:
                rng = random.Random(seed + 100 + v)
                for r in base:
                    if len(extra) >= shortfall:
                        break
                    opts = list(r["options"]); rng.shuffle(opts)
                    sib = {**r, "options": opts,
                           "metadata": {**r["metadata"],
                                        "bank_code": f"{r['metadata']['bank_code']}#v{v}"}}
                    extra.append(sib)
                v += 1
            all_rows += extra

        created, updated = _persist(all_rows)
        self.stdout.write(self.style.SUCCESS(
            f"seed_exercise_banks: prepared={len(all_rows)} created={created} updated={updated}"
        ))
