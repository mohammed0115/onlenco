# Onlenco Beginner — Method Spec

*Derived methodology from the EFE Level 1 Beginner Course Book (DK, 2016).*
*This document encodes the **pattern** only. All Onlenco content (sentences,
characters, images, audio, exercises) is original. American English. Bilingual
EN/AR student-facing UI; teaching audio is en-US monolingual.*

---

## 0. Course Topology

| Property | Value |
|---|---|
| Total units | **48** |
| Unit types | **Skill** (new language + vocab + new skill) and **Vocabulary-only** (themed label grids) |
| Pure vocabulary units (no grammar) | ~30% of total (e.g. positions 02, 04, 07, 09, 12, 20, 27, 30, 33, 36, 38, 41, 43) |
| Cluster size | 6–8 consecutive units share a thematic colour token |
| Reviews | **6 review modules** — one after each cluster |
| Modules per skill unit | typically **8–12** numbered modules (e.g. 10.1 → 10.10) |
| Modules per vocab unit | typically **5–7** themed cards/grids |
| Pause boundary | After any module — progress saves at module granularity |
| End-of-unit | Checklist (3 chips: language / vocab / skill) |

Thematic clusters (palette tokens are **Onlenco**'s; the EFE colour set is *not*
reused):

| Cluster | Units | Theme | Onlenco colour token |
|---|---|---|---|
| C1 | 01–08 | Identity & relationships | `cluster-identity` |
| C2 | 09–19 | Daily life & routines | `cluster-routine` |
| C3 | 20–26 | Places & directions | `cluster-place` |
| C4 | 27–34 | Possessions & home | `cluster-possess` |
| C5 | 35–42 | Preferences & free time | `cluster-leisure` |
| C6 | 43–48 | Ability & ambition | `cluster-ability` |

---

## 1. Lesson Structure

### 1.1 Skill Unit (the dominant pattern)

A skill unit is a **vertical stack of modules**. Each module is a self-contained
chunk the student can finish in 2–5 minutes. Order is fixed; the student
progresses module-by-module.

```
┌──────────────────────────────────────────────────────────────┐
│  Unit cover                                                  │
│   • Unit number + short title                                │
│   • One-line intro (≤ 2 sentences)                           │
│   • 3 learning-point chips:                                  │
│       ⚙  New language: <construction>                        │
│       Aa Vocabulary: <topic>                                 │
│       🧩 New skill: <can-do>                                  │
└──────────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────┐
│  Teach: KEY LANGUAGE                                         │
│    Two characters speaking. Annotated sample(s).             │
│    Construction highlighted in `--accent-new` colour.        │
│    Side notes explain when / why.                            │
│    🔊 audio                                                   │
└──────────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────┐
│  Teach: OTHER WAYS / FURTHER EXAMPLES (optional)             │
│    Variations, contractions, edge cases. 3–5 examples.       │
│    🔊 audio                                                   │
└──────────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────┐
│  Teach: HOW TO FORM (grammar)                                │
│    Tabular "puzzle-piece" breakdown:                         │
│      SUBJECT | VERB | OBJECT                                 │
│    No prose paragraphs — visual structure only.              │
└──────────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────┐
│  Vocabulary panel(s)                                         │
│    Themed label grid (5–20 items)                            │
│    Image + EN label + dotted "your-language" line            │
│    🔊 per panel                                               │
└──────────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────┐
│  Practice modules (3–6 exercises, mixed types)               │
│    Each begins with the skill icon (G/R/L/S/V — see §2)      │
│    First item always pre-filled as a **sample answer**       │
│    Most have supporting audio after completion               │
└──────────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────┐
│  Speaking module                                             │
│    Chart-driven sentence generator OR repeat-after-model     │
│    Compare your recording vs reference audio                 │
└──────────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────┐
│  CHECKLIST                                                   │
│    3 boxes: ⚙ New language ☐  Aa Vocab ☐  🧩 New skill ☐    │
│    Auto-checked when the student finishes the matching       │
│    teach + practice pair.                                    │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Vocabulary-only Unit

Only image grids. No grammar puzzle pieces, no exercises *within* the unit
(exercises live in the next skill unit that uses this vocab).

```
Unit cover (title only — no learning-point chips)
        ↓
3–6 themed "cards" (relationship diagrams for family/professions, or
flat label grids for things/places).
Each card = a module: ID like `04.1`, `04.2`, ...
Each item = { image, en_label, ar_label, en_audio_clip }.
The card itself has 🔊 to play all its labels in order.
        ↓
(no checklist for vocab units — they feed the next skill unit)
```

### 1.3 Module Taxonomy

Every module is one of **11 types**. Each maps cleanly to a Django model
(`LessonModule.kind`) and a renderer template. Listed with required fields:

| `kind` | Render hint | Required fields |
|---|---|---|
| `KEY_LANGUAGE` | 2 cartoon speakers + speech bubbles + side annotations | `lead_sentence_en`, `lead_sentence_ar`, `highlight_spans`, `notes[]`, `audio_clip` |
| `OTHER_WAYS` | Before/after arrow with construction variants | `pairs[] {from, to, note}`, `audio_clip` |
| `HOW_TO_FORM` | Tabular puzzle pieces (one row per pattern) | `slots[] {label, options[]}`, `example` |
| `FURTHER_EXAMPLES` | Icon + sentence grid (3–6 rows) | `items[] {icon, sentence_en, sentence_ar, highlight_spans}`, `audio_clip` |
| `VOCAB_GRID` | Flat image grid | `items[] {image_ref, label_en, label_ar}`, `audio_clip` |
| `VOCAB_DIAGRAM` | Relationship tree (family / org chart style) | `nodes[] {id, image_ref, label_en, label_ar}`, `edges[] {from, to, label}`, `audio_clip` |
| `EX_FILL_GAPS` | Sentence with blank inputs | `items[] {prompt, blanks[]}`, `sample_answer_index`, `audio_after?` |
| `EX_MATCH` | Two columns to connect | `left[]`, `right[]`, `solution{left_id: right_id}`, `sample_pair` |
| `EX_CROSS_OUT` | Two choices per item, strike the wrong one | `items[] {sentence_with_two_choices, correct}` |
| `EX_TRUE_FALSE` | Statement + audio + T/F | `items[] {audio_clip, statement, answer}` |
| `EX_LISTEN_GROUP` | Listen, then drag tokens into buckets | `buckets[]`, `tokens[]`, `solution{token: bucket}`, `audio_clip` |
| `EX_SPEAK_CHART` | Chart with slots — student composes & records | `slots[][]`, `min_sentences`, `reference_audio` |
| `EX_SPEAK_REPEAT` | Listen + repeat + score | `items[] {audio_clip, text, target_score}` |

The render template for each is a one-file Django partial
(`templates/courses/modules/<kind>.html`).

---

## 2. Quiz / Exercise Structure

### 2.1 The 5 skill icons

Each exercise module is tagged with one icon (matches the EFE convention but
uses Onlenco's own glyph set, not DK's):

| Symbol | Skill | Module kinds that carry it |
|---|---|---|
| ⚙ Grammar | construction practice | `EX_FILL_GAPS`, `EX_CROSS_OUT` |
| 📖 Reading | comprehension on a passage | `EX_FILL_GAPS` over a short passage, `EX_TRUE_FALSE` text-only |
| 🎧 Listening | audio-driven | `EX_LISTEN_GROUP`, `EX_TRUE_FALSE` audio-based |
| 💬 Speaking | recording / repeat-after | `EX_SPEAK_CHART`, `EX_SPEAK_REPEAT` |
| Aa Vocabulary | word recall | `EX_MATCH` (word ↔ image), `EX_FILL_GAPS` (word slot) |

### 2.2 Scaffolding rules (universal)

1. **First item pre-filled** as a model answer (visible, not editable). The
   student sees "here's how it's done" before producing their own.
2. **Visual cue** alongside the prompt where it disambiguates (e.g. a tiny job
   icon next to a "Talk about your job" cloze).
3. **Audio after submission** plays the correct sentence so the student hears
   the pronunciation while reading.
4. **No penalty on first wrong answer** — the system shows the right answer and
   moves on. Mastery is decided in the Review (§4), not module-by-module.
5. **Auto-grading** is deterministic for `FILL_GAPS / MATCH / CROSS_OUT /
   TRUE_FALSE / LISTEN_GROUP`. Speaking modules grade via STT + similarity to
   the reference text (existing `placement.services.stt` infrastructure).

### 2.3 Quiz Bank vs in-lesson exercises

| | In-lesson exercise (this spec, §2.1–§2.2) | Quiz Bank (separate — see P05) |
|---|---|---|
| Belongs to | A single `LessonModule` | A whole `LearningUnit` |
| Purpose | Reinforce *this* construction | Test the unit as a whole, mark mastery |
| Scoring | Formative (no mastery lock) | Summative (mastery flag persists) |
| When taken | Inline, in module order | End of unit, optional retry |
| Distribution | 3–6 per skill unit | 8–10 mixed-skill items per unit |

---

## 3. Media Structure (Images)

### 3.1 Three image roles

| Role | Used where | Onlenco style rules |
|---|---|---|
| **Character scenes** | `KEY_LANGUAGE`, `EX_SPEAK_CHART` | Two stylised flat-illustration humans in conversation. Speech-bubble overlay. |
| **Vocab tiles** | `VOCAB_GRID`, `EX_MATCH` | Single object/person on a clean pale background, centred, 1:1 aspect, no caption baked into image. |
| **Diagram nodes** | `VOCAB_DIAGRAM`, `HOW_TO_FORM` | Minimal silhouettes / icons; connector lines drawn in CSS, not in the image. |

### 3.2 Onlenco style guide (must differ from DK)

- **Palette**: Onlenco brand greens + warm neutrals (defined in
  `static/css/onlenco-tokens.css`). EFE's red/blue/green primary trio is *not*
  reused as a system.
- **Illustration**: flat, no shadows, no gradient backgrounds. Lines = 2 px.
- **People**: diverse cast (see §10) — 8 fictional recurring "Onlenco students"
  whose names and looks are our own. **Never reuse EFE character names**
  (Lyla, Joe, Pablo, Mary, Sarah, Dan, Harry, Bruno, Aman, Leesa, Una, Ben, Jo,
  John, Milo, Tom, Charlotte, Lina, Carlos, Bruno).
- **Iconography**: Lucide icon set (already a project dependency).
- **No DK trade dress**: no red header bars, no `Aa` glyph that mimics DK's
  typography, no puzzle-piece visual signature for grammar tables — use a
  3-column tabular layout instead.

### 3.3 Storage & references

Every image row in the DB stores `(asset_ref, alt_en, alt_ar)`. `asset_ref` is
either:
- a relative path under `/media/lessons/img/cluster-XX/`, or
- an `S3://…` key (future), or
- a Lucide icon name (for diagram nodes) prefixed `icon:`.

Render order of preference: `icon:` → local file → S3.

---

## 4. Audio Structure

### 4.1 Two audio roles

| Role | When played | Tagged in DB as |
|---|---|---|
| **Supporting** | After student finishes reading the module, on tap | `audio_kind = "supporting"` |
| **Listening exercise** | Inline — student listens *to answer* | `audio_kind = "listening"` |

A module may have *one* clip of each kind (e.g. `EX_LISTEN_GROUP` has a
listening clip; `KEY_LANGUAGE` has a supporting clip).

### 4.2 Voice spec

- **Accent**: **General American**, neutral pace (~140 wpm for teach modules,
  ~110 wpm for listening exercises).
- **Voices**: minimum 4 distinct speakers (2 female / 2 male) so dialogue
  modules feel natural. Use the same 4 voices throughout the course for
  consistency.
- **TTS provider**: OpenAI TTS (`gpt-4o-mini-tts` or `tts-1-hd`) configured via
  the project's existing `AI_API_KEY`. Fallback: pre-recorded files committed
  under `media/lessons/audio/`.
- **Audio format**: 48 kHz mono MP3 at 96 kbps. Naming: `UU_M.mp3` where `UU` is
  zero-padded unit number and `M` is module sub-id (e.g. `01_1.mp3`).
- **Length cap**: 30 s per supporting clip, 60 s per listening clip. Longer
  prompts split into multiple sub-clips.

### 4.3 SSML conventions

- Wrap target constructions in `<emphasis level="moderate">` for teach modules.
- Pause 300 ms between dialogue turns; 600 ms between vocab grid items.
- Spell-out letters (names like "S-A-R-A") with `<say-as interpret-as="characters">`.

---

## 5. Review Structure

### 5.1 Review module shape

One Review module is inserted **after every cluster** (see §0). Format:

```
┌──────────────────────────────────────────────────────────────────────┐
│  REVIEW — units NN–MM                                                │
├──────────────────────────────────────────────────────────────────────┤
│  | NEW LANGUAGE   | SAMPLE SENTENCE (highlighted) | ✓ | UNIT       │
│  | Introducing... | "I'm <name>." / "My name's…"  | ☐ | 1.1        │
│  | How old…?      | "I'm <N> years old."          | ☐ | 3.1        │
│  | Possessive adj | "<name>'s <object>."          | ☐ | 5.1        │
│  | ...                                                              │
└──────────────────────────────────────────────────────────────────────┘
```

- One row per **construction taught** in the cluster, not per module.
- The sample sentence reuses the **highlighting colours** from the original
  teaching module so the student visually recognises the construction.
- ✓ box self-graded: "I'm comfortable with this." Persists per student so the
  next visit can prioritise the un-checked rows.
- `UNIT` cell is a deep link back to the source module — clicking it scrolls
  the lesson view to that anchor.

### 5.2 Review composition rules

| Cluster size | Review row count |
|---|---|
| 6 units | 4–6 rows |
| 7 units | 5–7 rows |
| 8 units | 6–8 rows |

A pure-vocabulary unit (no new construction) contributes **0** review rows; its
vocab is folded into the rows of skill units that consume it.

---

## 6. AI Tutor Drill Structure

The existing `tutor` app already runs voice-call drills. For the Beginner
course we wire **per-module drill prompts** so a student can say *"Practise
this module with me"* and get a 2-minute targeted conversation.

### 6.1 When the tutor opens

| Trigger | Behaviour |
|---|---|
| Student taps "Practise with tutor" on a module | Opens a voice call **scoped** to that module's target construction |
| Student fails the **end-of-unit Quiz Bank** | Auto-suggests a tutor drill on the weakest construction |
| Student requests it from the dashboard | Picks the most-recent module with no ✓ in its Review row |

### 6.2 Per-module drill template

Stored on `LessonModule.tutor_prompt` (TextField). Standard shape:

```
You are a friendly American-English tutor. The student just learned:
  {{ construction_label }}      e.g. "Present simple negative"
  Pattern: {{ pattern }}         e.g. "I do not work outside."
  Vocab in scope: {{ vocab_items|join:", " }}

Run a 2-minute drill:
  1. Greet the student and remind them of the construction in one sentence.
  2. Ask 3 short Q&A pairs that force the construction (e.g. "Do you work
     outside?" → "No, I do not work outside.").
  3. After each answer, give one-line feedback in en-US, then either repeat
     with a fresh prompt or move on.
  4. End by encouraging the student and naming the next module.

Rules:
  - en-US only. No code-switching to Arabic.
  - Stay inside the cluster's vocab list. Do not introduce new tenses.
  - Keep each of your turns under 12 words.
```

Each unit author overrides only `construction_label`, `pattern`, and
`vocab_items` — the rest is shared.

### 6.3 Personalisation hooks

- The tutor reads the student's last 3 exercise attempts from the same module
  (via `LessonAttempt`) and front-loads drill items on whatever they got
  wrong.
- Profile signals: `profile.cefr_level`, `profile.full_name` (used as the
  student's name in the call).

---

## 7. Copyright Safety Rules

This spec is the **methodology** only. The methodology — graded modules,
visual grammar tables, dual-audio policy, end-of-unit checklists, cluster
reviews — is **patent-style "method" knowledge** that cannot be copyrighted.
What *is* copyrighted in EFE is the specific copy: sentences, illustrations,
character names, audio, exact exercise items. Our hard rules:

1. **No verbatim sentences** from EFE. Every example sentence in Onlenco is
   original — write fresh, even if the construction taught is the same.
2. **No EFE character names** (Lyla, Joe, Pablo, Mary, Sarah, Dan, Harry,
   Bruno, Aman, Leesa, Una, Ben, Jo, John, Milo, Tom, Charlotte, Lina, Carlos,
   Robbie, Felix, Ginger, Coco, Lizzie). Onlenco uses its own cast (§10).
3. **No EFE illustrations**. All art is either AI-generated to our prompt or
   commissioned/stock-licensed under our own pipeline.
4. **No EFE audio**. All audio is TTS or studio-recorded under our own
   contracts.
5. **No DK trade dress**: do *not* copy DK's red title bar, DK logo placement,
   the specific puzzle-piece visual signature for grammar, the precise
   colour-coded cluster palette, or the exact icon set for the 5 skills.
   Onlenco brand tokens replace all of those.
6. **No EFE exercise items**. We re-derive exercises from the construction in
   abstract, not by paraphrasing EFE exercises.
7. **TOC topic order**: the choice to teach "to be" before "have", and to put
   articles after places, is **language-pedagogy convention**, not unique to
   EFE — it appears in every CEFR A1 syllabus (Cambridge, Oxford, Cutting
   Edge, etc.). Reusing the order is safe.

Every seed file ships with a header:

```python
# All content original to Onlenco Academy.
# Methodology inspired by published A1 syllabi (Cambridge / EFE / Cutting Edge).
# No copy reuses verbatim text, characters, illustrations, or audio from any
# specific source publication.
```

---

## 8. American English Rules

### 8.1 Vocabulary choices

When a UK/US variant exists, the **US form is the headword** and the UK form
is the *secondary* label shown in parentheses (mirroring how EFE prints
"construction worker (US) / builder (UK)" — but here US wins).

| US headword | UK secondary |
|---|---|
| mom | mum |
| sneakers | trainers |
| sweater | jumper |
| apartment | flat |
| elevator | lift |
| truck | lorry |
| trash | rubbish |
| store | shop |
| vacation | holiday |
| fall (season) | autumn |
| candy | sweets |
| diaper | nappy |
| line (queue) | queue |
| cell phone | mobile phone |
| soccer | football |
| highway | motorway |
| stove | cooker |
| trunk (car) | boot |
| hood (car) | bonnet |

### 8.2 Spelling

- `-ize` (organize, realize, recognize)
- `-or` (color, flavor, honor)
- `-er` (center, theater, meter)
- `-led / -ling` (traveled, modeling)
- `-og` (catalog, dialog)
- `defense / offense` (not defence / offence)
- `program` (not programme), `gray` (not grey)

### 8.3 Punctuation

- **Double quotes** as primary, single inside (`"He said 'hi.'"`).
- Periods/commas **inside** quotation marks.
- Oxford comma used in lists of 3+ items.
- Numerals: 12-hour clock with am/pm ("8:30 am"); dates `MM/DD/YYYY` in copy,
  ISO `YYYY-MM-DD` in DB.
- `dollar` symbol `$` (no `£` outside cultural notes).

### 8.4 Pronunciation policy

TTS configured for `en-US` voice profile. Stress patterns and intonation are
GenAm, not RP. Pronunciation tips in the lesson copy use IPA or a
simplified phonetic respelling (`/ˈsneɪ.kɚz/` or `SNAY-kərz`), not the
EFE-style phonetic guide.

---

## 9. Arabic Support Rules

The teaching audio is **en-US only** — students improve faster when they don't
hear an L1 crutch. But the *student-facing UI* and *write-along lines* are
bilingual:

### 9.1 What's bilingual

| Surface | Behaviour |
|---|---|
| Unit titles & module headings | EN + AR side-by-side, dir-aware (RTL when `lang=ar`) |
| Vocab labels under each image | EN bold above, AR dotted-line below (matches the "write your translation" affordance in EFE — for Onlenco it's pre-filled) |
| Exercise *instructions* | EN line + AR line below |
| Sample sentences in `KEY_LANGUAGE` / Review | EN only — these are the audio-target sentences and must read the way they sound |
| Error / status messages | Whichever the user's `profile.preferred_language` is set to |
| Tutor voice call | **EN only** — the system prompt explicitly forbids code-switching |

### 9.2 Storage

Every bilingual model has `<field>_en` and `<field>_ar` columns. The renderer
helper `text_for(language)` returns the requested locale with EN fallback when
AR is blank (already implemented on `PlacementQuestion`; we copy the same
pattern to `LearningUnit`, `LessonModule`, `VocabItem`, etc.).

### 9.3 RTL & typography

- Existing project CSS already supports `dir="rtl"` (see
  `static/css/onlenco-components.css`). Layouts must mirror cleanly when AR
  is active.
- Arabic copy uses **Modern Standard Arabic** — no dialect, so a Sudanese
  student and a Saudi student both read the same explanation.

### 9.4 Translation policy

- AR labels for vocab are **translation pairs**, not transliterations. e.g.
  `cat → قطة`, not `cat → كات`.
- AR explanations for new constructions are **short paraphrases**, not
  word-by-word glosses. Keep ≤ 25 words per gloss.

---

## 10. Student Experience Flow

End-to-end student journey through the Beginner course:

```
1. Sign up
   └─ verify email → onboarding language pick (en / ar)
2. Placement (existing flow — placement app)
   └─ result: cefr_level = A0 / A1 / A2
3. Enrol in Beginner course (A0 / A1)
   └─ dashboard shows the 48-unit roadmap, cluster-coloured
4. Open a unit
   └─ unit cover with the 3 learning-point chips
   └─ ⟶ first module auto-expanded
5. Inside a module
   ├─ Teach modules: read + 🔊 listen
   ├─ Exercise modules: answer → instant feedback → 🔊 listen
   ├─ Speaking modules: chart-driven sentence build → record → score
   └─ "Practise with AI tutor" button: opens scoped voice drill (§6)
6. End of unit
   └─ Checklist auto-fills based on completion
   └─ Optional Quiz Bank (summative) — sets mastery flag
7. End of cluster (units 08 / 19 / 26 / 34 / 42 / 48)
   └─ Review module: 6 constructions table, student self-checks
8. Course completion
   └─ Certificate + auto-advance to Pre-Intermediate (A2)
```

Pause/resume contract:

- Progress saves on **module completion** (not within a module).
- "Continue" CTA on the dashboard deep-links to the next un-completed module.
- A student who pauses mid-exercise loses the in-flight answer but not the
  module's prior state.

---

## 11. Onlenco character cast (replaces EFE characters)

10 fictional recurring students whose names, looks, and back-stories are
**original to Onlenco**. Reused across units so the student feels they're
learning *with a class*.

| ID | Name | Age | Origin (fictional) | Hook |
|---|---|---|---|---|
| `c-amani` | Amani | 19 | Khartoum, Sudan | Wants to study medicine abroad. |
| `c-yusuf` | Yusuf | 22 | Omdurman, Sudan | Engineering graduate, new tech-support job. |
| `c-noor` | Noor | 17 | Cairo, Egypt | High-school senior, loves photography. |
| `c-kareem` | Kareem | 25 | Amman, Jordan | Architect, plans a postgrad in Toronto. |
| `c-salma` | Salma | 30 | Marrakech, Morocco | Pharmacist, language for travel. |
| `c-omar` | Omar | 28 | Riyadh, Saudi Arabia | Software developer, remote-work English. |
| `c-layla` | Layla | 21 | Tunis, Tunisia | Computer-science student, learns fast. |
| `c-tarek` | Tarek | 35 | Beirut, Lebanon | Restaurant owner, learns for tourists. |
| `c-hala` | Hala | 24 | Khartoum, Sudan | Civil-society NGO worker, English-for-grants. |
| `c-rashid` | Rashid | 16 | Wad Madani, Sudan | Youngest of the group, gaming + YouTube fan. |

Each character ships with a flat illustration (commissioned or AI-generated to
our brief) and a 1-line "today's intro" used when they first appear in a unit.

---

## 12. Mapping back to Django

This spec implies the following **new model layout** (full schema in P02):

```
LearningCourse
  └─ cluster_set (cluster_id, label, colour_token)
       └─ LearningUnit (number, title_en, title_ar, kind=skill|vocab, …)
            ├─ LessonModule (order, kind ∈ {11 types}, payload_json, …)
            │    └─ MediaAsset[] (image_ref / audio_clip per audio_kind)
            └─ UnitChecklistItem (auto-derived) – no separate table
       └─ ReviewModule (after the last unit of the cluster)
            └─ ReviewRow (label_en, sample_html, source_module_ref)
```

`LearningCourse.code` is auto-generated using the existing
`courses.services.code_generator` (e.g. `ONL-A0-COURSE-001`). `LearningUnit`,
`LessonModule`, and `ReviewRow` get their own auto-codes following the same
project convention (e.g. `ONL-A0-C001-U01`, `…-U01-M3`, `…-U08-RVW-R2`).

Quiz Bank items, batch-image jobs, batch-audio jobs, and tutor drill prompts
are all addressed in subsequent prompts (P05, P07, P08, P09).
