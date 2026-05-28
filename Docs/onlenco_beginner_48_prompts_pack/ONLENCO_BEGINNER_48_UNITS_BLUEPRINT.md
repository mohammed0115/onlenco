# Onlenco Beginner — 48 Units Blueprint

**Course:** `Onlenco Beginner English Foundation — American English`
**Level:** A0 → A1 (CEFR)
**Audience:** Arabic-speaking learners starting from zero, American English target.
**Methodology:** see [ONLENCO_BEGINNER_METHOD_SPEC.md](ONLENCO_BEGINNER_METHOD_SPEC.md)

---

## Implementation choice: Option A (no new model)

**Decision: use existing `Course → CourseUnit → Lesson` with each of the 48
topics = one `Lesson`.** Reasoning:

| Concern | Why Option A wins |
|---|---|
| Schema already supports it | `Lesson` carries `title_en/title_ar`, `cefr_level`, `skill`, `content_html`, plus the new media/checklist/scripts from P02. No model gap to close. |
| Display grouping | `CourseUnit` (cap of 3 lessons per unit) becomes the cluster sub-grouping. 48 topics ÷ 3 = 16 CourseUnits. |
| Progress, mastery, gating | All wired to `Lesson` already — `CourseLessonProgress`, the lesson gate, the AI tutor lesson scoping. Switching to a new `LearningModule` model would mean re-wiring all of that. |
| Reviews | A "review" is just a Lesson whose `lesson_type` we will extend to `"review"` in P10 (additive choice — no schema change). |
| Front-end terminology | Render label on screens is **"Learning Unit"** (en) / **"وحدة"** (ar) — the DB stays "Lesson" so no rename migration is needed. |

**Front-end labels** (template change only, no DB change):

```jinja
{# what students see #}
{% t_either "Learning Unit" "وحدة" %} {{ lesson.order }} — {{ lesson.title }}
```

---

## Cluster map (6 clusters → 6 Reviews)

| Cluster | Units | Topic theme | Review | CourseUnit count |
|---|---|---|---|---|
| **C1** | 01–08 | Identity & relationships | **R1** after 08 | 3 (units 01-03, 04-06, 07-08) |
| **C2** | 09–19 | Daily life & routines | **R2** after 19 | 4 (09-11, 12-14, 15-17, 18-19) |
| **C3** | 20–26 | Places & directions | **R3** after 26 | 3 (20-22, 23-25, 26) |
| **C4** | 27–34 | Possessions & home | **R4** after 34 | 3 (27-29, 30-32, 33-34) |
| **C5** | 35–42 | Preferences & free time | **R5** after 42 | 3 (35-37, 38-40, 41-42) |
| **C6** | 43–48 | Ability & ambition | **R6** after 48 | 2 (43-45, 46-48) |
| | | | | **Total: 18 CourseUnits** |

(Numbers fit neatly under the 3-lesson-per-CourseUnit cap.)

---

## Glossary for the per-unit fields

| Field | Meaning |
|---|---|
| `unit_number` | 1–48, sequential. |
| `title_en` / `title_ar` | Bilingual display title. |
| `cefr_level` | `A0` for first ~24 units, transitions to `A1` for the rest. |
| `estimated_minutes` | Typical completion time at beginner pace. |
| `new_language` | The single new construction taught (pure language item). |
| `vocabulary_focus` | The thematic vocabulary set introduced. |
| `new_skill` | The "can-do" competency unlocked. |
| `grammar_focus` | The grammar slot opened (or "—" for pure vocab units). |
| `pronunciation_focus` | One concrete pronunciation point (or "—"). |
| `speaking_goal` | What the student must record/say. |
| `listening_goal` | What the student must hear/identify. |
| `image_idea` | One sentence describing the cover scene (Onlenco cast only). |
| `audio_idea` | What the supporting audio contains. |
| `quiz_goal` | Brief: how the end-of-unit quiz tests this. |
| `ai_tutor_goal` | What the 2-min drill should practise. |
| `checklist_items` | 2–4 bilingual "I can…" / "أستطيع…" statements. |
| `review_group` | R1…R6 — which Review consumes this unit's construction. |

---

## CLUSTER 1 — Identity & relationships (Units 01–08)

### Unit 01 — Introducing Yourself
- `unit_number`: 1
- `title_en`: Introducing Yourself · `title_ar`: التعريف بنفسك
- `cefr_level`: A0 · `estimated_minutes`: 25
- `new_language`: "to be" with names — *"I am Amani."* / *"My name is Yusuf."*
- `vocabulary_focus`: Greetings (Hello, Hi); the English alphabet (A–Z names)
- `new_skill`: Greet someone and state your own name in English
- `grammar_focus`: 1st-person singular of "to be"
- `pronunciation_focus`: Contraction `/aɪm/` for "I'm"; clear final consonants in names
- `speaking_goal`: Record a 15-second self-introduction using two greetings and the student's own name
- `listening_goal`: Identify 3 names that are spelled aloud, letter by letter
- `image_idea`: Amani and Yusuf wave at each other on a sunny school courtyard, flat Onlenco illustration, soft green background
- `audio_idea`: 4 micro-dialogues at friendly-teacher pace; each contains one introduction model
- `quiz_goal`: 8 items mixing match-greetings, fill-gaps with am/is, and spell-from-audio
- `ai_tutor_goal`: 2-minute drill — tutor asks the student's name three times, varying greetings
- `checklist_items`:
  - I can greet someone in English. / أستطيع التحية بالإنجليزية.
  - I can say my own name. / أستطيع قول اسمي.
  - I can spell my name aloud. / أستطيع تهجئة اسمي بصوت.
- `review_group`: R1

### Unit 02 — Countries (vocabulary-only)
- `unit_number`: 2
- `title_en`: Countries · `title_ar`: البلدان
- `cefr_level`: A0 · `estimated_minutes`: 15
- `new_language`: (none — vocab unit)
- `vocabulary_focus`: 16 countries (USA, UK, Canada, Mexico, Brazil, Egypt, Sudan, Morocco, Tunisia, KSA, UAE, Jordan, Lebanon, Turkey, India, China)
- `new_skill`: Name the country someone is from
- `grammar_focus`: —
- `pronunciation_focus`: Stress in country names (e.g. *MO-rocco*, *BRA-zil*)
- `speaking_goal`: Say 8 country names out loud, matching reference recordings
- `listening_goal`: Pick the country named from a 4-option grid
- `image_idea`: A 4×4 flat tile grid of country silhouettes with their flags' main hue, no flag detail; no character scene
- `audio_idea`: One label per tile in friendly-teacher voice, 600 ms gap between tiles
- `quiz_goal`: 8 items — match flag-colour swatch ↔ country name, audio→name picker
- `ai_tutor_goal`: Quickfire "Where is this place?" — student names the country shown
- `checklist_items`:
  - I can name 10 countries in English. / أستطيع تسمية 10 بلدان بالإنجليزية.
  - I recognise country names when I hear them. / أتعرّف على أسماء البلدان عند سماعها.
- `review_group`: R1

### Unit 03 — Talking About Yourself
- `unit_number`: 3
- `title_en`: Talking About Yourself · `title_ar`: التحدّث عن نفسك
- `cefr_level`: A0 · `estimated_minutes`: 25
- `new_language`: "to be" with age and nationality — *"I am 19. I am Sudanese."*
- `vocabulary_focus`: Numbers 1–30; nationalities (Sudanese, Saudi, Egyptian, American, British, …)
- `new_skill`: Say your age and nationality
- `grammar_focus`: Adjective form of nationalities; *"to be" + age* pattern
- `pronunciation_focus`: Stress on nationality endings (*-ESE*, *-AN*, *-ISH*)
- `speaking_goal`: Record a 20-sec self-introduction adding age + nationality on top of Unit 01
- `listening_goal`: Match each speaker to their age and country in a small table
- `image_idea`: Noor and Salma sitting at a café table, each holding a sign with their age in numbers (no country flag — text-only signs)
- `audio_idea`: 5 voices each saying *"I'm <age>. I'm <nationality>."*
- `quiz_goal`: 8 items — fill-gaps with am/is, ear-it: nationality from audio, number recognition 1–30
- `ai_tutor_goal`: Tutor asks "How old are you?" and "Where are you from?", student answers, tutor confirms
- `checklist_items`:
  - I can say my age. / أستطيع قول عمري.
  - I can say my nationality. / أستطيع قول جنسيتي.
  - I understand numbers 1–30. / أفهم الأرقام من 1 إلى 30.
- `review_group`: R1

### Unit 04 — Family and Pets (vocabulary-only)
- `unit_number`: 4
- `title_en`: Family and Pets · `title_ar`: العائلة والحيوانات الأليفة
- `cefr_level`: A0 · `estimated_minutes`: 18
- `new_language`: (vocab unit)
- `vocabulary_focus`: Family members (mother, father, brother, sister, son, daughter, grandparents, aunt, uncle, cousin); 10 common pets (cat, dog, fish, parrot, rabbit, hamster, turtle, sheep, chicken, horse)
- `new_skill`: Name family members and pets
- `grammar_focus`: —
- `pronunciation_focus`: `-er` and `-her` endings (*mother*, *father*, *brother*)
- `speaking_goal`: Record yourself naming 6 family members from prompted images
- `listening_goal`: Drag heard words into "family" vs "pet" buckets
- `image_idea`: One relationship-tree diagram of Hala's family + one row of stylised pet icons (no DK characters)
- `audio_idea`: Single-word labels with 800 ms gaps; family diagram traversed in fixed order
- `quiz_goal`: 8 items — image→word match, audio→word, group-into-categories
- `ai_tutor_goal`: Tutor names a family member, student replies with a sentence — *"My brother is …"*
- `checklist_items`:
  - I can name family members in English. / أستطيع تسمية أفراد العائلة.
  - I can name common pets. / أستطيع تسمية الحيوانات الأليفة الشائعة.
- `review_group`: R1

### Unit 05 — Things You Have
- `unit_number`: 5
- `title_en`: Things You Have · `title_ar`: الأشياء التي لديك
- `cefr_level`: A0 · `estimated_minutes`: 30
- `new_language`: Possessive adjectives (*my, your, his, her, its, our, their*); demonstratives *this* / *that*
- `vocabulary_focus`: Personal items (phone, key, bag, book, pen, notebook, wallet, ID card)
- `new_skill`: Talk about who things belong to
- `grammar_focus`: Possessive adjective + noun; *this*/*that* before singular nouns
- `pronunciation_focus`: Difference between *his* /hɪz/ and *he's* /hiːz/
- `speaking_goal`: Hold up 4 objects on camera and say *"This is my X."* for each
- `listening_goal`: Match each heard sentence to the correct owner from a small line-up
- `image_idea`: Kareem holding up a notebook and pointing at a phone on his desk; speech bubble shows the construction
- `audio_idea`: 8 short sentences — *"This is my phone. That is her key."* etc.
- `quiz_goal`: 8 items — possessive picker, *this/that* picker, cross-out incorrect form
- `ai_tutor_goal`: Show-and-tell drill — tutor names objects, student replies with *"This is my …"*
- `checklist_items`:
  - I can use *my, your, his, her*. / أستخدم my / your / his / her.
  - I can use *this* and *that*. / أستخدم this و that.
  - I can name 6 personal items. / أستطيع تسمية 6 أشياء شخصية.
- `review_group`: R1

### Unit 06 — Using Apostrophes
- `unit_number`: 6
- `title_en`: Using Apostrophes · `title_ar`: استخدام علامة الملكية
- `cefr_level`: A0 · `estimated_minutes`: 25
- `new_language`: Possessive 's — *"Layla's book"*, *"my parents' house"*
- `vocabulary_focus`: Re-uses family and pets vocab from U04
- `new_skill`: Show ownership with apostrophe-s
- `grammar_focus`: Singular *'s* vs plural-ending *s'* (after plural nouns)
- `pronunciation_focus`: Voiced *-s* /z/ after vowels (*Layla's*) vs voiceless /s/ after voiceless consonants (*Kareem's*)
- `speaking_goal`: Say 5 ownership sentences chosen from a chart
- `listening_goal`: Identify the owner in 6 spoken sentences
- `image_idea`: Side-by-side panels — left: Layla holds her book; right: a small group of friends near a shared car (showing "their car" vs "Layla's book")
- `audio_idea`: 6 sentences with the apostrophe-s clearly enunciated
- `quiz_goal`: 8 items — rewrite ownership sentences, choose 's vs s'
- `ai_tutor_goal`: Quick possession Q&A: *"Whose phone is this?"* → *"It's Omar's."*
- `checklist_items`:
  - I can use *'s* for one owner. / أستخدم 's لمالك واحد.
  - I can use *s'* for plural owners. / أستخدم s' لعدّة مالكين.
- `review_group`: R1

### Unit 07 — Everyday Things (vocabulary-only)
- `unit_number`: 7
- `title_en`: Everyday Things · `title_ar`: أشياء يومية
- `cefr_level`: A0 · `estimated_minutes`: 15
- `new_language`: (vocab unit)
- `vocabulary_focus`: 16 daily objects (laptop, charger, glasses, umbrella, keys, water bottle, lunchbox, headphones, watch, scarf, wallet, sunglasses, tissues, mask, ID, sneakers)
- `new_skill`: Name objects you carry every day
- `grammar_focus`: —
- `pronunciation_focus`: Stress in compound nouns (*WAter bottle*, *HEADphones*)
- `speaking_goal`: Tour your bag on camera, naming 5 items in 30 seconds
- `listening_goal`: Mark which items the speaker says they have
- `image_idea`: Flat-illustration grid of 16 everyday items, soft neutral background, no people
- `audio_idea`: Per-tile labels in friendly-teacher voice
- `quiz_goal`: 8 items — image→word, word→image, hear→name
- `ai_tutor_goal`: Listing drill — *"Tell me 5 things in your bag."*
- `checklist_items`:
  - I can name 10 everyday objects. / أستطيع تسمية 10 أشياء يومية.
- `review_group`: R1

### Unit 08 — Talking About Your Things
- `unit_number`: 8
- `title_en`: Talking About Your Things · `title_ar`: التحدث عن أشيائك
- `cefr_level`: A0 · `estimated_minutes`: 25
- `new_language`: *these* / *those* (plurals of *this*/*that*); determiners → possessive pronouns (my → mine, your → yours, …)
- `vocabulary_focus`: Re-uses everyday-things vocab from U07
- `new_skill`: Talk about who plural things belong to
- `grammar_focus`: Plural demonstratives; *"These books are mine."* pattern
- `pronunciation_focus`: *th* in *these*/*those* — voiced /ð/, soft tongue tap
- `speaking_goal`: Build 12 correct sentences from a slot chart and say them out loud
- `listening_goal`: Sort heard nouns into two characters' bags (Tarek's vs Hala's)
- `image_idea`: Two adjacent desks — Tarek's covered in books, Hala's with chargers and headphones — labelled with "these"/"those" arrows
- `audio_idea`: 10 sample sentences combining possessive pronouns + plural demonstratives
- `quiz_goal`: 8 items — sentence-builder, mine vs my picker, listen-and-group
- `ai_tutor_goal`: Practice swapping *"my X" → "X is mine."* across 8 prompts
- `checklist_items`:
  - I can use *these* and *those*. / أستخدم these و those.
  - I can use *mine, yours, his, hers*. / أستخدم mine / yours / his / hers.
  - I can talk about who things belong to. / أستطيع التحدث عن مَن يملك الأشياء.
- `review_group`: R1 *(triggers REVIEW 1 after this unit)*

---

## CLUSTER 2 — Daily life & routines (Units 09–19)

### Unit 09 — Jobs (vocabulary-only)
- `unit_number`: 9
- `title_en`: Jobs · `title_ar`: المهن
- `cefr_level`: A0 · `estimated_minutes`: 18
- `new_language`: (vocab unit)
- `vocabulary_focus`: 16 jobs (doctor, nurse, dentist, teacher, engineer, chef, driver, farmer, police officer, fire fighter, actor, artist, hairdresser, vet, sales assistant, construction worker)
- `new_skill`: Name common jobs
- `grammar_focus`: —
- `pronunciation_focus`: *-er* ending (*teacher*, *farmer*, *driver*) — schwa
- `speaking_goal`: Record yourself naming 6 jobs from prompted images
- `listening_goal`: Pick the job heard from a 4-image grid
- `image_idea`: 16-tile grid of stylised silhouettes per job, neutral background, no faces
- `audio_idea`: Per-tile job names
- `quiz_goal`: 8 items — image→job, audio→job, job→workplace match
- `ai_tutor_goal`: "What is this person's job?" drill across 10 images
- `checklist_items`:
  - I can name 10 jobs in English. / أستطيع تسمية 10 مهن بالإنجليزية.
- `review_group`: R2

### Unit 10 — Talking About Your Job
- `unit_number`: 10
- `title_en`: Talking About Your Job · `title_ar`: التحدّث عن مهنتك
- `cefr_level`: A0 · `estimated_minutes`: 30
- `new_language`: Using "I am / He is" + a job — *"I am a police officer."*
- `vocabulary_focus`: 8 workplaces (school, hospital, office, restaurant, farm, construction site, store, laboratory); inside vs outside
- `new_skill`: Describe your job and where you work
- `grammar_focus`: Article *a/an* before a job
- `pronunciation_focus`: *a* /ə/ (schwa) before a job
- `speaking_goal`: Record *"I am a/an X. I work in/at Y."* using your real or future job
- `listening_goal`: Match each speaker to their workplace
- `image_idea`: Yusuf in a small tech office at his desk, name tag visible, soft greens
- `audio_idea`: 6 voices — each gives job + workplace
- `quiz_goal`: 8 items — a vs an picker, job-from-audio, fill-gaps with "to be"
- `ai_tutor_goal`: *"What do you do?"* / *"Where do you work?"* mini-dialogue
- `checklist_items`:
  - I can say what my job is. / أستطيع قول مهنتي.
  - I can say where I work. / أستطيع قول مكان عملي.
- `review_group`: R2

### Unit 11 — Telling the Time
- `unit_number`: 11
- `title_en`: Telling the Time · `title_ar`: قول الوقت
- `cefr_level`: A0 · `estimated_minutes`: 25
- `new_language`: Time expressions — *"It's 3 o'clock"*, *"half past 7"*, *"quarter to 9"*; am/pm
- `vocabulary_focus`: Hours 1–12, words for time (o'clock, half, quarter, past, to)
- `new_skill`: Ask and tell the time in English
- `grammar_focus`: *It's* + time
- `pronunciation_focus`: Reduction of *o'clock* /əˈklɑk/
- `speaking_goal`: Read out 6 clock faces shown in the lesson
- `listening_goal`: Drag time labels onto matching clock faces
- `image_idea`: A row of stylised analogue clocks set to varied times against a soft background
- `audio_idea`: 8 time announcements + matching tick effect
- `quiz_goal`: 8 items — clock→words, words→clock, am/pm picker
- `ai_tutor_goal`: *"What time is it?"* asked 5 times, varied clocks
- `checklist_items`:
  - I can read times on a clock. / أستطيع قراءة الوقت على الساعة.
  - I can ask "What time is it?". / أستطيع السؤال عن الوقت.
- `review_group`: R2

### Unit 12 — Daily Routines (vocabulary-only)
- `unit_number`: 12
- `title_en`: Daily Routines · `title_ar`: الروتين اليومي
- `cefr_level`: A0 · `estimated_minutes`: 18
- `new_language`: (vocab unit)
- `vocabulary_focus`: 12 routine verbs (wake up, get up, take a shower, have breakfast, go to work, start work, finish work, come home, have dinner, watch TV, study, go to bed)
- `new_skill`: Name daily activities
- `grammar_focus`: —
- `pronunciation_focus`: Phrasal verb stress (*WAKE up*, *GO to bed*)
- `speaking_goal`: Say 8 routine actions out loud
- `listening_goal`: Order heard activities along a timeline
- `image_idea`: Strip of 12 icons of a person doing each action, ordered by time of day
- `audio_idea`: Each routine spoken with a one-second pause
- `quiz_goal`: 8 items — image→verb, audio→verb, order routines by time
- `ai_tutor_goal`: *"What do you do in the morning?"* listing drill
- `checklist_items`:
  - I can name 8 daily routines. / أستطيع تسمية 8 من أنشطة الروتين اليومي.
- `review_group`: R2

### Unit 13 — Describing Your Day
- `unit_number`: 13
- `title_en`: Describing Your Day · `title_ar`: وصف يومك
- `cefr_level`: A1 · `estimated_minutes`: 35
- `new_language`: Present simple — *"I wake up at 7. He starts work at 9."*
- `vocabulary_focus`: Re-uses routine verbs from U12
- `new_skill`: Talk about your daily routine
- `grammar_focus`: 3rd-person *-s* (*she works*, *he watches*)
- `pronunciation_focus`: *-s* endings — /s/, /z/, /ɪz/ rules
- `speaking_goal`: Record a 30-sec description of your typical day
- `listening_goal`: Fill 4 time-blanks in a transcript while listening
- `image_idea`: Vertical timeline showing Rashid's day from morning to night, one icon per stage
- `audio_idea`: Two narrators describe their days back-to-back
- `quiz_goal`: 8 items — fill-gaps with verb+s, time placement, hear→verb
- `ai_tutor_goal`: Tutor asks 3 *"What time do you …?"* and gives feedback
- `checklist_items`:
  - I can use the present simple. / أستخدم المضارع البسيط.
  - I can talk about my daily routine. / أستطيع التحدث عن روتيني اليومي.
  - I add *-s* with *he* and *she*. / أضيف -s مع he و she.
- `review_group`: R2

### Unit 14 — Describing Your Week
- `unit_number`: 14
- `title_en`: Describing Your Week · `title_ar`: وصف أسبوعك
- `cefr_level`: A1 · `estimated_minutes`: 28
- `new_language`: Days + prepositions — *"on Monday"*, *"on weekdays"*, *"at the weekend"*
- `vocabulary_focus`: Days of the week; *weekday* vs *weekend*
- `new_skill`: Talk about your weekly routine
- `grammar_focus`: Preposition *on* with days
- `pronunciation_focus`: *Wednesday* /ˈwɛnz.deɪ/ (silent *d*)
- `speaking_goal`: Record 5 sentences about your week using *"on …"*
- `listening_goal`: Mark which days a speaker is busy
- `image_idea`: A 7-cell calendar strip, each day's cell containing a tiny activity icon (no characters)
- `audio_idea`: 7 voices each saying *"On Monday I … On Tuesday I …"*
- `quiz_goal`: 8 items — preposition picker, day spelling, weekly schedule build
- `ai_tutor_goal`: *"What do you do on Saturday?"* — Q&A loop across 4 days
- `checklist_items`:
  - I can name the 7 days. / أستطيع تسمية الأيام السبعة.
  - I can use *on* with days. / أستخدم on مع الأيام.
- `review_group`: R2

### Unit 15 — Negatives with To Be
- `unit_number`: 15
- `title_en`: Negatives with To Be · `title_ar`: النفي مع to be
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: *"I am not"*, *"he is not"*, contractions (*isn't, aren't*)
- `vocabulary_focus`: Re-uses jobs, nationalities
- `new_skill`: Say what things are not
- `grammar_focus`: Adding *not* after "to be"
- `pronunciation_focus`: Contraction *isn't* /ˈɪz.ənt/
- `speaking_goal`: Correct 5 false statements about classmates aloud
- `listening_goal`: Mark each statement true/false from short audio
- `image_idea`: Side-by-side panels — wrong assumption ("She is a chef") vs reality ("She is a doctor")
- `audio_idea`: 6 negative-affirmative pairs
- `quiz_goal`: 8 items — make-it-negative, full vs contraction picker, T/F from audio
- `ai_tutor_goal`: *"Are you …?"* questions where the student must reply *"No, I am not."*
- `checklist_items`:
  - I can use *not* with "to be". / أستخدم not مع to be.
  - I can use contractions *isn't, aren't*. / أستخدم isn't و aren't.
- `review_group`: R2

### Unit 16 — More Negatives
- `unit_number`: 16
- `title_en`: More Negatives · `title_ar`: المزيد من النفي
- `cefr_level`: A1 · `estimated_minutes`: 28
- `new_language`: Present simple negative — *"I do not work outside."*, *"He does not live in Khartoum."*
- `vocabulary_focus`: Re-uses routine and place vocab
- `new_skill`: Say what you don't do
- `grammar_focus`: *don't / doesn't* + base form; 3rd-person rule reversed in negation
- `pronunciation_focus`: *doesn't* /ˈdʌz.ənt/
- `speaking_goal`: Record 4 sentences about things you don't do daily
- `listening_goal`: Mark for each item whether the speaker does or doesn't do it
- `image_idea`: Single character on the left doing an activity; right panel crossed out — the activity they don't do
- `audio_idea`: 6 voices describing one habit and one non-habit each
- `quiz_goal`: 8 items — fill-gaps with don't/doesn't, fix the verb form, listen-and-group
- `ai_tutor_goal`: *"Do you …?"* leading to *"No, I don't."* responses
- `checklist_items`:
  - I can say what I don't do. / أستطيع قول ما لا أفعله.
  - I can use *don't* and *doesn't*. / أستخدم don't و doesn't.
- `review_group`: R2

### Unit 17 — Simple Questions
- `unit_number`: 17
- `title_en`: Simple Questions · `title_ar`: الأسئلة البسيطة
- `cefr_level`: A1 · `estimated_minutes`: 28
- `new_language`: Yes/no questions — *"Are you a student?"*, *"Does he work outside?"*
- `vocabulary_focus`: Re-uses jobs & routines
- `new_skill`: Ask simple yes/no questions
- `grammar_focus`: Inversion with *to be*; *do/does* + subject for present simple
- `pronunciation_focus`: Rising intonation at end of yes/no questions
- `speaking_goal`: Ask 5 yes/no questions about a partner's day
- `listening_goal`: Distinguish question vs statement from intonation
- `image_idea`: Two characters facing each other; one's speech bubble has a question mark glyph emphasized
- `audio_idea`: 6 question-statement minimal pairs
- `quiz_goal`: 8 items — turn statement → question, pick correct auxiliary, intonation match
- `ai_tutor_goal`: Student must produce 6 yes/no questions about the tutor
- `checklist_items`:
  - I can ask yes/no questions. / أستطيع طرح أسئلة نعم/لا.
  - I use rising intonation. / أرفع نبرة صوتي في نهاية السؤال.
- `review_group`: R2

### Unit 18 — Answering Questions
- `unit_number`: 18
- `title_en`: Answering Questions · `title_ar`: الإجابة عن الأسئلة
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: Short answers — *"Yes, I am."*, *"No, I'm not."*, *"Yes, he does."*, *"No, he doesn't."*
- `vocabulary_focus`: Re-uses jobs & routines
- `new_skill`: Give natural short answers, not just "yes/no"
- `grammar_focus`: Echo auxiliary in the short answer
- `pronunciation_focus`: Stress fall on the auxiliary in the short answer (*"Yes, I DO."*)
- `speaking_goal`: Respond to 8 prompted yes/no questions with full short answers
- `listening_goal`: Map heard short answers to the questions they answer
- `image_idea`: Chat-bubble exchange between Omar and Layla — question + matched short answer
- `audio_idea`: 8 mini Q&A exchanges
- `quiz_goal`: 8 items — choose short answer, fix the auxiliary, match Q to A
- `ai_tutor_goal`: Drill 6 personal yes/no Qs requiring the student to use the right auxiliary
- `checklist_items`:
  - I give natural short answers. / أعطي إجابات قصيرة طبيعية.
  - I echo the right auxiliary. / أكرر الفعل المساعد الصحيح.
- `review_group`: R2

### Unit 19 — Asking Questions
- `unit_number`: 19
- `title_en`: Asking Questions · `title_ar`: طرح الأسئلة
- `cefr_level`: A1 · `estimated_minutes`: 30
- `new_language`: WH-questions — *"What do you do?"*, *"Where does she work?"*, *"When do they study?"*, *"Who is he?"*, *"Why are you tired?"*
- `vocabulary_focus`: Five question words (what, where, when, who, why)
- `new_skill`: Ask for details, not just yes/no
- `grammar_focus`: WH + auxiliary + subject + base verb
- `pronunciation_focus`: Falling intonation at end of WH questions
- `speaking_goal`: Ask 6 WH-questions to learn 3 facts about a partner
- `listening_goal`: Match each heard WH question to its category (what/where/when/who/why)
- `image_idea`: Five colored chat bubbles, one per WH-word, around a central listener
- `audio_idea`: 5 WH questions modelled, then 5 more for student to identify
- `quiz_goal`: 8 items — pick WH word, build the question, listen-and-sort
- `ai_tutor_goal`: Tutor invites student to ask 4 WH-questions to fill an info gap
- `checklist_items`:
  - I can ask WH-questions. / أستطيع طرح أسئلة WH.
  - I know what, where, when, who, why. / أعرف what / where / when / who / why.
  - I use falling intonation. / أهبط بنبرة صوتي.
- `review_group`: R2 *(triggers REVIEW 2 after this unit)*

---

## CLUSTER 3 — Places & directions (Units 20–26)

### Unit 20 — Around Town (vocabulary-only)
- `unit_number`: 20
- `title_en`: Around Town · `title_ar`: في أرجاء المدينة
- `cefr_level`: A1 · `estimated_minutes`: 18
- `new_language`: (vocab unit)
- `vocabulary_focus`: 18 places (bank, supermarket, school, hospital, pharmacy, mosque, church, post office, library, park, café, restaurant, gas station, bus stop, train station, museum, hotel, bakery)
- `new_skill`: Name common places in a town
- `grammar_focus`: —
- `pronunciation_focus`: Schwa in unstressed syllables (*supermARket*, *resTAUrant*)
- `speaking_goal`: Tour your neighbourhood on a mental map, name 8 places aloud
- `listening_goal`: Pick the place heard from a 4-image grid
- `image_idea`: 18-tile flat illustration grid of place icons, soft pastel background
- `audio_idea`: One word per tile, friendly-teacher voice
- `quiz_goal`: 8 items — image→word, word→image, hear→name
- `ai_tutor_goal`: *"What's near your home?"* listing drill
- `checklist_items`:
  - I can name 10 places in a town. / أستطيع تسمية 10 أماكن في المدينة.
- `review_group`: R3

### Unit 21 — Talking About Your Town
- `unit_number`: 21
- `title_en`: Talking About Your Town · `title_ar`: التحدث عن مدينتك
- `cefr_level`: A1 · `estimated_minutes`: 28
- `new_language`: *There is / there are* — *"There is a park near my house."*, *"There are two schools."*
- `vocabulary_focus`: Town buildings; numbers 1–20 used for counting buildings
- `new_skill`: Describe what is in your town
- `grammar_focus`: Singular vs plural noun → choice of *is/are*
- `pronunciation_focus`: Linking *"there's a"* → /ðerz.ə/
- `speaking_goal`: Record 6 sentences about your neighbourhood using *there is* / *there are*
- `listening_goal`: Tick what the speaker says exists in their town
- `image_idea`: Top-down stylised map of a small fictional town with labelled landmarks
- `audio_idea`: A guided tour through the same map by a narrator
- `quiz_goal`: 8 items — *is/are* picker, sentence builder, T/F from audio
- `ai_tutor_goal`: Tutor asks *"What's in your town?"* — student replies with 4 *there's a/there are* sentences
- `checklist_items`:
  - I can use *there is* and *there are*. / أستخدم there is و there are.
  - I can describe my town. / أستطيع وصف مدينتي.
- `review_group`: R3

### Unit 22 — Using A, An, and The
- `unit_number`: 22
- `title_en`: Using A, An, and The · `title_ar`: استخدام a / an / the
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: Definite vs indefinite articles — *a / an / the*
- `vocabulary_focus`: Re-uses town places
- `new_skill`: Use the correct article
- `grammar_focus`: *a* before consonant sound, *an* before vowel sound, *the* for known reference
- `pronunciation_focus`: *the* /ðiː/ before vowels vs /ðə/ before consonants
- `speaking_goal`: Read 8 sentences aloud, picking the right article
- `listening_goal`: Identify which article was used in 6 spoken sentences
- `image_idea`: Three side-by-side café scenes labelled *a café* / *an old café* / *the café* showing the meaning shift
- `audio_idea`: 8 spoken sentences spotlighting each article
- `quiz_goal`: 8 items — pick article, fill gaps, cross-out wrong choice
- `ai_tutor_goal`: Article picker drill across 8 nouns + contexts
- `checklist_items`:
  - I use *a* before consonants. / أستخدم a قبل الحروف الساكنة.
  - I use *an* before vowels. / أستخدم an قبل الحروف المتحركة.
  - I use *the* for known things. / أستخدم the للأشياء المعروفة.
- `review_group`: R3

### Unit 23 — Orders and Directions
- `unit_number`: 23
- `title_en`: Orders and Directions · `title_ar`: الأوامر والاتجاهات
- `cefr_level`: A1 · `estimated_minutes`: 30
- `new_language`: Imperatives — *"Turn left."*, *"Go straight."*, *"Don't stop."*
- `vocabulary_focus`: Direction verbs (turn, go, take, cross, stop, walk, follow); left/right/straight/here/there
- `new_skill`: Give and follow directions
- `grammar_focus`: Bare imperative; negative imperative with *don't*
- `pronunciation_focus`: Imperative stress on the action verb
- `speaking_goal`: Give a 30-sec set of directions from a starting point on a map to a target
- `listening_goal`: Trace a route on a map while listening to instructions
- `image_idea`: A simple street grid with one route highlighted by green dashes
- `audio_idea`: A turn-by-turn voice guide using each direction verb
- `quiz_goal`: 8 items — match verb→arrow icon, fill-in imperative, T/F from spoken route
- `ai_tutor_goal`: Tutor names a destination, student gives directions in 4 steps
- `checklist_items`:
  - I can give simple directions. / أستطيع إعطاء اتجاهات بسيطة.
  - I can follow spoken directions. / أستطيع متابعة اتجاهات منطوقة.
- `review_group`: R3

### Unit 24 — Joining Sentences
- `unit_number`: 24
- `title_en`: Joining Sentences · `title_ar`: ربط الجمل
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: *and* / *but* coordinators
- `vocabulary_focus`: Re-uses town, job, family vocab
- `new_skill`: Combine 2 short sentences into one
- `grammar_focus`: Coordinator placement; comma before *but* in longer sentences
- `pronunciation_focus`: Unstressed *and* → /ən/ in fast speech
- `speaking_goal`: Combine 6 sentence pairs out loud using *and* or *but*
- `listening_goal`: Mark which coordinator the speaker used
- `image_idea`: A two-panel composition — left "She's a teacher" + right "She's a runner" joined by *and*
- `audio_idea`: 6 modelled combined sentences
- `quiz_goal`: 8 items — pick and/but, combine pair, fix the comma
- `ai_tutor_goal`: Tutor gives a sentence; student adds a contrasting or additive clause
- `checklist_items`:
  - I can join sentences with *and*. / أستطيع ربط الجمل بـ and.
  - I can contrast with *but*. / أستطيع المعارضة بـ but.
- `review_group`: R3

### Unit 25 — Describing Places
- `unit_number`: 25
- `title_en`: Describing Places · `title_ar`: وصف الأماكن
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: Adjectives — *"a small park"*, *"an old library"*, *"a busy street"*
- `vocabulary_focus`: 10 place adjectives (small, big, old, new, busy, quiet, clean, dirty, beautiful, modern)
- `new_skill`: Describe places using adjectives
- `grammar_focus`: Adjective before noun; multiple adjectives order (size, age, opinion)
- `pronunciation_focus`: Stress on opinion adjectives in noun phrases
- `speaking_goal`: Describe 5 places in your town using 2 adjectives each
- `listening_goal`: Match adjective sets to the described place
- `image_idea`: Side-by-side scenes — "a small park" vs "a big park" / "an old café" vs "a modern café"
- `audio_idea`: 8 adjective-noun phrases modelled
- `quiz_goal`: 8 items — match adjective→picture, fill-gap, cross-out the opposite
- `ai_tutor_goal`: *"Describe X"* prompts, tutor offers feedback on adjective use
- `checklist_items`:
  - I can use adjectives before nouns. / أستخدم الصفات قبل الأسماء.
  - I can describe places. / أستطيع وصف الأماكن.
- `review_group`: R3

### Unit 26 — Giving Reasons
- `unit_number`: 26
- `title_en`: Giving Reasons · `title_ar`: إعطاء الأسباب
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: *because* — *"I'm tired because I work at night."*
- `vocabulary_focus`: Re-uses jobs, places, routine verbs
- `new_skill`: Give a reason for a fact
- `grammar_focus`: Main clause + *because* + subordinate clause
- `pronunciation_focus`: Pause before *because* in slow speech
- `speaking_goal`: Give 4 *because* answers to *"Why …?"* prompts
- `listening_goal`: Match each reason to its cause statement
- `image_idea`: Cause-effect dual panel — top: "She is happy." bottom (linked by arrow): "She has a new job."
- `audio_idea`: 6 cause-and-reason sentences
- `quiz_goal`: 8 items — match cause/effect, fill *because* gap, fix word order
- `ai_tutor_goal`: Tutor asks *"Why …?"* 4 times across topics
- `checklist_items`:
  - I can give reasons with *because*. / أستطيع إعطاء أسباب بـ because.
- `review_group`: R3 *(triggers REVIEW 3 after this unit)*

---

## CLUSTER 4 — Possessions & home (Units 27–34)

### Unit 27 — Around the House (vocabulary-only)
- `unit_number`: 27
- `title_en`: Around the House · `title_ar`: في أرجاء المنزل
- `cefr_level`: A1 · `estimated_minutes`: 18
- `new_language`: (vocab unit)
- `vocabulary_focus`: 12 rooms/areas (kitchen, living room, bedroom, bathroom, garage, garden, balcony, hallway, dining room, office, attic, basement)
- `new_skill`: Name rooms
- `grammar_focus`: —
- `pronunciation_focus`: Compound stress (*LIVing room*, *BEDroom*)
- `speaking_goal`: Walk through your home in 30 sec, naming rooms
- `listening_goal`: Drag heard rooms onto a floor-plan
- `image_idea`: A flat floor plan of a small fictional apartment with labelled rooms
- `audio_idea`: A guided tour of the same floor plan
- `quiz_goal`: 8 items — image→room, audio→room, floor-plan placement
- `ai_tutor_goal`: *"What rooms are in your home?"* listing drill
- `checklist_items`:
  - I can name 8 rooms in a house. / أستطيع تسمية 8 غرف في المنزل.
- `review_group`: R4

### Unit 28 — The Things I Have
- `unit_number`: 28
- `title_en`: The Things I Have · `title_ar`: الأشياء التي لديّ
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: *have / has* — *"I have a TV."*, *"She has two kids."*
- `vocabulary_focus`: 16 household objects (TV, fridge, oven, microwave, sofa, bed, table, chair, washing machine, lamp, mirror, carpet, curtains, clock, plant, shelf)
- `new_skill`: Talk about possessions
- `grammar_focus`: *have* vs *has*; *I/you/we/they* vs *he/she/it*
- `pronunciation_focus`: *has* /hæz/ vs reduced *'s* /z/
- `speaking_goal`: List 5 things you have in your living room
- `listening_goal`: Mark which items the speaker has
- `image_idea`: A stylised living room cross-section; objects labelled
- `audio_idea`: 6 voices describing 2-3 possessions each
- `quiz_goal`: 8 items — have/has picker, fill-gap, listen-and-tick
- `ai_tutor_goal`: *"Do you have a …?"* questions across 6 items
- `checklist_items`:
  - I can use *have* and *has*. / أستخدم have و has.
  - I can name 10 household items. / أستطيع تسمية 10 أدوات منزلية.
- `review_group`: R4

### Unit 29 — What Do You Have?
- `unit_number`: 29
- `title_en`: What Do You Have? · `title_ar`: ماذا لديك؟
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: Questions with *have* — *"Do you have a microwave?"*, *"Does he have a car?"*
- `vocabulary_focus`: Re-uses house and furniture
- `new_skill`: Ask about possessions
- `grammar_focus`: *do/does* + subject + *have*
- `pronunciation_focus`: Linking *do you* → /ˈdʒə/
- `speaking_goal`: Ask 5 *Do you have …?* questions of a partner
- `listening_goal`: Note yes/no answers in a simple grid
- `image_idea`: Two characters in a kitchen — one checks items off a shopping list, the other answers
- `audio_idea`: 6 mini Q&A pairs
- `quiz_goal`: 8 items — make question, pick auxiliary, T/F from audio
- `ai_tutor_goal`: Tutor asks 5 *Do you have …?* about Sudan-typical items
- `checklist_items`:
  - I can ask *Do you have …?*. / أستطيع السؤال بـ Do you have …?.
  - I can ask *Does he/she have …?*. / أستطيع السؤال بـ Does he/she have …?.
- `review_group`: R4

### Unit 30 — Food and Drink (vocabulary-only)
- `unit_number`: 30
- `title_en`: Food and Drink · `title_ar`: الطعام والشراب
- `cefr_level`: A1 · `estimated_minutes`: 20
- `new_language`: (vocab unit)
- `vocabulary_focus`: 20 food/drink items (bread, rice, chicken, fish, beef, eggs, milk, water, tea, coffee, juice, fruit, apples, bananas, tomatoes, onions, salt, sugar, cheese, yogurt)
- `new_skill`: Name common foods and drinks
- `grammar_focus`: —
- `pronunciation_focus`: Voiced/voiceless plurals (*eggs* vs *cats*)
- `speaking_goal`: List 6 foods you eat weekly
- `listening_goal`: Pick the food heard from a 4-tile grid
- `image_idea`: Flat-illustration tile grid of foods, no plates or characters
- `audio_idea`: Per-tile spoken labels
- `quiz_goal`: 8 items — image→word, hear→word, group into food vs drink
- `ai_tutor_goal`: *"What do you eat for breakfast?"* listing drill
- `checklist_items`:
  - I can name 10 foods. / أستطيع تسمية 10 أطعمة.
  - I can name 5 drinks. / أستطيع تسمية 5 مشروبات.
- `review_group`: R4

### Unit 31 — Counting
- `unit_number`: 31
- `title_en`: Counting · `title_ar`: العَدّ
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: Uncountable nouns — *"some bread"*, *"a piece of cheese"*, *"two glasses of water"*
- `vocabulary_focus`: Food containers (bottle, glass, cup, slice, piece, bowl, can, pack)
- `new_skill`: Talk about food quantities
- `grammar_focus`: *a/an* with countable; *some* with uncountable; container + *of*
- `pronunciation_focus`: Reduction of *of* → /əv/
- `speaking_goal`: Order 5 items from a stylised café menu
- `listening_goal`: Mark the quantity heard in 6 audio orders
- `image_idea`: A café counter with labelled containers (bottle, glass, cup) and food items
- `audio_idea`: 6 short café orders
- `quiz_goal`: 8 items — countable/uncountable sort, container picker, audio→quantity
- `ai_tutor_goal`: Café role-play — tutor takes the student's order
- `checklist_items`:
  - I know countable and uncountable nouns. / أعرف الأسماء المعدودة وغير المعدودة.
  - I can order food and drink. / أستطيع طلب طعام وشراب.
- `review_group`: R4

### Unit 32 — Measuring
- `unit_number`: 32
- `title_en`: Measuring · `title_ar`: القياس
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: Measurements — *"500 grams of flour"*, *"2 liters of milk"*, *"1 cup of sugar"*
- `vocabulary_focus`: Units (gram, kilogram, liter, milliliter, cup, teaspoon, tablespoon); cooking ingredients
- `new_skill`: State quantities like a recipe
- `grammar_focus`: Numeral + unit + *of* + noun
- `pronunciation_focus`: Plurals of units after numbers (*two grams*, *one liter*)
- `speaking_goal`: Read a 4-line recipe out loud
- `listening_goal`: Fill quantities in a 6-line shopping list while listening
- `image_idea`: A measuring jug, a scale, and a spoon labelled with their units, no character scene
- `audio_idea`: 6 sentences from a recipe instruction
- `quiz_goal`: 8 items — match quantity→unit, fill-gap, recipe order
- `ai_tutor_goal`: Tutor dictates a 4-step recipe, student repeats each step
- `checklist_items`:
  - I can talk about amounts. / أستطيع الحديث عن الكميات.
  - I know 4 units of measure. / أعرف 4 وحدات قياس.
- `review_group`: R4

### Unit 33 — Clothes (vocabulary-only)
- `unit_number`: 33
- `title_en`: Clothes · `title_ar`: الملابس
- `cefr_level`: A1 · `estimated_minutes`: 18
- `new_language`: (vocab unit)
- `vocabulary_focus`: 18 clothes (shirt, t-shirt, sweater, jacket, coat, pants, jeans, shorts, skirt, dress, suit, sneakers, shoes, boots, hat, scarf, gloves, socks)
- `new_skill`: Name clothes
- `grammar_focus`: —
- `pronunciation_focus`: Silent-letter *clothes* /kloʊz/
- `speaking_goal`: Name 6 items in your wardrobe
- `listening_goal`: Pick the item heard from a 4-tile grid
- `image_idea`: A wardrobe view with labelled garments on hangers
- `audio_idea`: Per-tile spoken labels
- `quiz_goal`: 8 items — image→word, hear→word, group by season
- `ai_tutor_goal`: *"What are you wearing today?"* listing drill
- `checklist_items`:
  - I can name 10 clothes items. / أستطيع تسمية 10 قطع ملابس.
- `review_group`: R4

### Unit 34 — At the Store
- `unit_number`: 34
- `title_en`: At the Store · `title_ar`: في المتجر
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: *too* / *fit* — *"This is too big."*, *"It doesn't fit."*
- `vocabulary_focus`: Sizes (small, medium, large, XL); shopping verbs (try on, buy, pay, return)
- `new_skill`: Describe clothes that fit or don't fit
- `grammar_focus`: *too* + adjective; negative *doesn't fit*
- `pronunciation_focus`: *too* /tuː/ — long vowel
- `speaking_goal`: Role-play a 30-sec store conversation
- `listening_goal`: Mark which sizes the speaker tried
- `image_idea`: A character in a stylised fitting room; speech bubble *"This is too big."*
- `audio_idea`: A 4-turn dialogue in a clothing store
- `quiz_goal`: 8 items — fit/doesn't fit picker, size order, dialogue gap-fill
- `ai_tutor_goal`: Role-play tutor as shop assistant for 90 sec
- `checklist_items`:
  - I can describe clothes that fit. / أستطيع وصف ملابس مناسبة المقاس.
  - I can use *too* with adjectives. / أستخدم too مع الصفات.
- `review_group`: R4 *(triggers REVIEW 4 after this unit)*

---

## CLUSTER 5 — Preferences & free time (Units 35–42)

### Unit 35 — Describing Things
- `unit_number`: 35
- `title_en`: Describing Things · `title_ar`: وصف الأشياء
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: Opinion adjectives — *"It's nice."*, *"That's interesting."*
- `vocabulary_focus`: Opinion adjectives (nice, ugly, expensive, cheap, interesting, boring, easy, hard, comfortable, uncomfortable)
- `new_skill`: Give an opinion
- `grammar_focus`: *to be* + opinion adjective
- `pronunciation_focus`: Stress on the opinion adjective
- `speaking_goal`: Give 5 opinions on shown objects
- `listening_goal`: Match opinion adjectives to the noun they describe
- `image_idea`: A 6-item product board, each item with a thought-bubble showing one adjective
- `audio_idea`: 6 voices each giving an opinion on a different item
- `quiz_goal`: 8 items — adjective→item, fill-gap, find opposite
- `ai_tutor_goal`: *"What do you think of …?"* across 6 prompts
- `checklist_items`:
  - I can give an opinion. / أستطيع إعطاء رأي.
  - I can use opinion adjectives. / أستخدم صفات الرأي.
- `review_group`: R5

### Unit 36 — Sports (vocabulary-only)
- `unit_number`: 36
- `title_en`: Sports · `title_ar`: الرياضات
- `cefr_level`: A1 · `estimated_minutes`: 15
- `new_language`: (vocab unit)
- `vocabulary_focus`: 14 sports (soccer, basketball, tennis, running, swimming, cycling, volleyball, table tennis, boxing, golf, baseball, skiing, surfing, hiking)
- `new_skill`: Name sports
- `grammar_focus`: —
- `pronunciation_focus`: *-ing* in sport names — /ɪŋ/
- `speaking_goal`: List 6 sports you've tried or seen
- `listening_goal`: Pick sport heard from a 4-image grid
- `image_idea`: 14-tile flat illustration grid of sport pictograms
- `audio_idea`: Per-tile spoken labels
- `quiz_goal`: 8 items — image→sport, audio→sport
- `ai_tutor_goal`: *"Which sports do you know?"* listing drill
- `checklist_items`:
  - I can name 10 sports. / أستطيع تسمية 10 رياضات.
- `review_group`: R5

### Unit 37 — Talking About Sports
- `unit_number`: 37
- `title_en`: Talking About Sports · `title_ar`: التحدث عن الرياضة
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: *go* / *play* — *"I go swimming."*, *"I play soccer."*
- `vocabulary_focus`: Re-uses sports
- `new_skill`: Talk about which sports you do
- `grammar_focus`: *go* + *-ing* sports vs *play* + ball sports
- `pronunciation_focus`: Reduced *to go* /təˈɡoʊ/ in fast speech
- `speaking_goal`: Describe what sports you do per week
- `listening_goal`: Sort sports into *go* vs *play* buckets while listening
- `image_idea`: Split-screen — left: someone running ("go running"), right: people playing soccer ("play soccer")
- `audio_idea`: 6 sample sentences combining *go/play* + sport
- `quiz_goal`: 8 items — go/play picker, fill-gap, hear-and-sort
- `ai_tutor_goal`: Tutor asks *"What do you play?"* and *"What do you go …ing?"*
- `checklist_items`:
  - I can use *go* + sport. / أستخدم go مع الرياضة.
  - I can use *play* + sport. / أستخدم play مع الرياضة.
- `review_group`: R5

### Unit 38 — Hobbies and Pastimes (vocabulary-only)
- `unit_number`: 38
- `title_en`: Hobbies and Pastimes · `title_ar`: الهوايات
- `cefr_level`: A1 · `estimated_minutes`: 18
- `new_language`: (vocab unit)
- `vocabulary_focus`: 14 hobbies (reading, painting, gardening, cooking, photography, gaming, dancing, knitting, fishing, chess, writing, singing, drawing, traveling)
- `new_skill`: Name hobbies
- `grammar_focus`: —
- `pronunciation_focus`: *-ing* hobby forms (consonant + ing)
- `speaking_goal`: List 4 hobbies you have and 2 you'd like to try
- `listening_goal`: Pick hobby heard from a 4-tile grid
- `image_idea`: 14-tile grid of stylised hobby icons
- `audio_idea`: Per-tile spoken labels
- `quiz_goal`: 8 items — image→hobby, audio→hobby
- `ai_tutor_goal`: *"What are your hobbies?"* listing drill
- `checklist_items`:
  - I can name 10 hobbies. / أستطيع تسمية 10 هوايات.
- `review_group`: R5

### Unit 39 — Free Time
- `unit_number`: 39
- `title_en`: Free Time · `title_ar`: وقت الفراغ
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: Adverbs of frequency — *always, usually, often, sometimes, rarely, never*
- `vocabulary_focus`: Re-uses hobbies
- `new_skill`: Talk about how often you do hobbies
- `grammar_focus`: Adverb position before main verb, after *to be*
- `pronunciation_focus`: Stress on the adverb in fast speech
- `speaking_goal`: Build 6 sentences from a chart: *"I [adverb] [hobby]."*
- `listening_goal`: Map heard adverbs to a frequency scale 0–100%
- `image_idea`: A horizontal bar gauge labelled with the 6 adverbs at intervals
- `audio_idea`: 6 voices describing their frequency for a hobby
- `quiz_goal`: 8 items — order adverbs by frequency, fix word order, fill-gap
- `ai_tutor_goal`: Tutor asks *"How often do you …?"* about 4 hobbies
- `checklist_items`:
  - I can use 6 frequency adverbs. / أستخدم 6 ظروف تكرار.
  - I can talk about my free-time habits. / أستطيع التحدث عن عاداتي في وقت الفراغ.
- `review_group`: R5

### Unit 40 — Likes and Dislikes
- `unit_number`: 40
- `title_en`: Likes and Dislikes · `title_ar`: الإعجاب وعدم الإعجاب
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: *love / like / don't like / hate* + noun or *-ing* form
- `vocabulary_focus`: Re-uses sports, hobbies, food
- `new_skill`: Express what you like and don't like
- `grammar_focus`: Verb + noun OR verb + *-ing*
- `pronunciation_focus`: *like* /laɪk/ — diphthong
- `speaking_goal`: Give 5 likes/dislikes with a reason each
- `listening_goal`: Mark each heard statement on a like/dislike scale
- `image_idea`: A 4-bubble scale with thumbs gestures from love → hate
- `audio_idea`: 6 sentences with each of the 4 verbs
- `quiz_goal`: 8 items — pick verb, fix verb-ing vs noun, opposites
- `ai_tutor_goal`: Tutor asks *"Do you like …?"* about 6 prompts
- `checklist_items`:
  - I can say what I like. / أستطيع قول ما أحبه.
  - I can say what I don't like. / أستطيع قول ما لا أحبه.
- `review_group`: R5

### Unit 41 — Music (vocabulary-only)
- `unit_number`: 41
- `title_en`: Music · `title_ar`: الموسيقى
- `cefr_level`: A1 · `estimated_minutes`: 15
- `new_language`: (vocab unit)
- `vocabulary_focus`: 12 music genres + 6 instruments (pop, rock, jazz, classical, hip-hop, country, electronic, folk, blues, soul, R&B, reggae; guitar, piano, drums, violin, flute, saxophone)
- `new_skill`: Name music genres and instruments
- `grammar_focus`: —
- `pronunciation_focus`: Stress in genre names (*JAZZ*, *CLAS-si-cal*)
- `speaking_goal`: List 4 genres you like + 3 instruments you know
- `listening_goal`: Match genre/instrument heard to image
- `image_idea`: Stylised iconography — speaker, headphones, instruments arranged in two strips
- `audio_idea`: Per-tile spoken labels with a 1-second instrument sound after each
- `quiz_goal`: 8 items — image→genre/instrument, hear→name
- `ai_tutor_goal`: *"What music do you listen to?"* drill
- `checklist_items`:
  - I can name music genres. / أستطيع تسمية أنواع الموسيقى.
  - I can name instruments. / أستطيع تسمية الآلات الموسيقية.
- `review_group`: R5

### Unit 42 — Expressing Preference
- `unit_number`: 42
- `title_en`: Expressing Preference · `title_ar`: التعبير عن التفضيل
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: *favorite* — *"My favorite music is jazz."*
- `vocabulary_focus`: Re-uses food, music, sports, hobbies
- `new_skill`: Talk about favorites
- `grammar_focus`: Possessive + *favorite* + noun
- `pronunciation_focus`: *favorite* /ˈfeɪ.vɚ.ɪt/ — 3 syllables
- `speaking_goal`: Give 4 *"My favorite X is Y"* statements
- `listening_goal`: Match speakers to their favorites
- `image_idea`: A board of "favorites" — small cards each with a topic + selected item
- `audio_idea`: 6 voices each declaring a favorite
- `quiz_goal`: 8 items — fill-gap with favorite, build the sentence, listen-and-match
- `ai_tutor_goal`: Tutor asks *"What's your favorite …?"* across 5 categories
- `checklist_items`:
  - I can talk about favorites. / أستطيع التحدث عن المفضلات.
  - I can use *favorite* in a sentence. / أستخدم favorite في جملة.
- `review_group`: R5 *(triggers REVIEW 5 after this unit)*

---

## CLUSTER 6 — Ability & ambition (Units 43–48)

### Unit 43 — Abilities (vocabulary-only)
- `unit_number`: 43
- `title_en`: Abilities · `title_ar`: المهارات والقدرات
- `cefr_level`: A1 · `estimated_minutes`: 15
- `new_language`: (vocab unit)
- `vocabulary_focus`: 14 abilities (drive, swim, cook, dance, sing, draw, paint, code, type, ride a bike, speak French, play piano, juggle, ski)
- `new_skill`: Name abilities
- `grammar_focus`: —
- `pronunciation_focus`: *-ɪv* endings (*drive*, *type*)
- `speaking_goal`: List 4 things you can do
- `listening_goal`: Mark each ability heard as can/can't
- `image_idea`: 14-tile flat-illustration grid of stick figures doing each ability
- `audio_idea`: Per-tile spoken labels
- `quiz_goal`: 8 items — image→verb, audio→verb
- `ai_tutor_goal`: *"What can you do?"* listing drill
- `checklist_items`:
  - I can name 10 abilities. / أستطيع تسمية 10 قدرات.
- `review_group`: R6

### Unit 44 — What You Can and Can't Do
- `unit_number`: 44
- `title_en`: What You Can and Can't Do · `title_ar`: ما تستطيع وما لا تستطيع فعله
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: *can / can't / cannot* — *"I can drive."*, *"He can't swim."*
- `vocabulary_focus`: Re-uses abilities
- `new_skill`: State abilities and inabilities
- `grammar_focus`: Modal *can* — no *-s* in 3rd person; base form follows
- `pronunciation_focus`: *can* /kən/ (weak) vs *can't* /kænt/ (strong)
- `speaking_goal`: Make 6 *can/can't* statements about yourself
- `listening_goal`: Distinguish *can* vs *can't* in 8 spoken sentences (the hardest skill in this cluster)
- `image_idea`: Two characters side-by-side — one checking a "can" box, the other a "can't" box
- `audio_idea`: 8 minimal pairs to train the *can/can't* listening discrimination
- `quiz_goal`: 8 items — can/can't picker, listen-and-pick, fill-gap
- `ai_tutor_goal`: Tutor asks *"Can you …?"* 5 times; student answers with full short answer
- `checklist_items`:
  - I can use *can* and *can't*. / أستخدم can و can't.
  - I can hear the difference. / أستطيع سماع الفرق بينهما.
- `review_group`: R6

### Unit 45 — Describing Actions
- `unit_number`: 45
- `title_en`: Describing Actions · `title_ar`: وصف الأفعال
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: Regular adverbs (*quickly, slowly, quietly*) + irregular (*well, fast, hard*)
- `vocabulary_focus`: 10 manner adverbs; re-uses ability verbs
- `new_skill`: Describe how an action is done
- `grammar_focus`: Adverb position after verb-object; *-ly* derivation from adjectives
- `pronunciation_focus`: *-ly* /li/ ending
- `speaking_goal`: Describe 5 ability + adverb pairs
- `listening_goal`: Match adverb to ability in 6 audio clips
- `image_idea`: Side-by-side panels — same action done two ways (*quickly* vs *slowly*)
- `audio_idea`: 6 verb + adverb sentences
- `quiz_goal`: 8 items — adverb fill-in, *-ly* derivation, opposites
- `ai_tutor_goal`: Tutor asks *"How well do you …?"* across 4 actions
- `checklist_items`:
  - I can use adverbs of manner. / أستخدم ظروف الكيفية.
  - I can form *-ly* adverbs. / أستطيع تكوين ظروف بـ -ly.
- `review_group`: R6

### Unit 46 — Describing Ability
- `unit_number`: 46
- `title_en`: Describing Ability · `title_ar`: وصف مستوى المهارة
- `cefr_level`: A1 · `estimated_minutes`: 22
- `new_language`: Modifying adverbs — *very well, quite well, a little, not at all*
- `vocabulary_focus`: Skill-level adverbs; re-uses abilities
- `new_skill`: Say how well you can do something
- `grammar_focus`: Adverb-of-degree + manner adverb
- `pronunciation_focus`: *quite* /kwaɪt/ and *very* /ˈvɛr.i/
- `speaking_goal`: Describe 5 of your abilities by level
- `listening_goal`: Map heard descriptions to a 4-level skill scale
- `image_idea`: A horizontal bar gauge from *not at all* → *very well* with marked positions
- `audio_idea`: 6 voices placing themselves on the scale for one skill
- `quiz_goal`: 8 items — level order, fix the adverb chain, listen-and-place
- `ai_tutor_goal`: Tutor asks *"How well do you …?"* and helps refine the answer
- `checklist_items`:
  - I can describe my skill level. / أستطيع وصف مستوى مهارتي.
  - I can use *very well, a little, not at all*. / أستخدم very well و a little و not at all.
- `review_group`: R6

### Unit 47 — Wishes and Desires
- `unit_number`: 47
- `title_en`: Wishes and Desires · `title_ar`: الرغبات والأمنيات
- `cefr_level`: A1 · `estimated_minutes`: 25
- `new_language`: *want* / *would like* — *"I want a coffee."*, *"I'd like to learn Spanish."*
- `vocabulary_focus`: Leisure goals (learn a language, travel, study abroad, get a job, move, save money)
- `new_skill`: Talk about your ambitions
- `grammar_focus`: *want / would like* + noun OR *to* + base verb
- `pronunciation_focus`: Contraction *I'd* /aɪd/
- `speaking_goal`: Record 4 wishes for next year
- `listening_goal`: Match each speaker to their goal
- `image_idea`: A wish-board collage — sticky notes with goals and small icons
- `audio_idea`: 6 voices stating personal wishes
- `quiz_goal`: 8 items — want vs would like picker, infinitive vs noun, full vs contraction
- `ai_tutor_goal`: Tutor asks *"What do you want to learn / do?"* — student gives 3 goals
- `checklist_items`:
  - I can use *want* and *would like*. / أستخدم want و would like.
  - I can talk about my goals. / أستطيع التحدث عن أهدافي.
- `review_group`: R6

### Unit 48 — Studying
- `unit_number`: 48
- `title_en`: Studying · `title_ar`: الدراسة
- `cefr_level`: A1 · `estimated_minutes`: 30
- `new_language`: Adverbs of frequency + articles together — *"I usually study in the library."*
- `vocabulary_focus`: Academic subjects (math, science, history, geography, English, Arabic, art, music, biology, chemistry, physics, computer science)
- `new_skill`: Talk about studying habits and subjects
- `grammar_focus`: Adverb position with *to be* + articles for places
- `pronunciation_focus`: *usually* /ˈjuː.ʒu.ə.li/ — 4 syllables
- `speaking_goal`: Record a 40-sec routine about how you study
- `listening_goal`: Fill 6 gaps in a study-routine transcript while listening
- `image_idea`: A character at a library desk; sticky note with weekly subject list
- `audio_idea`: 2 students compare their study routines
- `quiz_goal`: 12 items — capstone mixing adverbs, articles, present simple, subjects
- `ai_tutor_goal`: 3-minute closing drill: tutor checks every major construction from the cluster
- `checklist_items`:
  - I can talk about my subjects. / أستطيع التحدث عن مواد دراستي.
  - I can use frequency adverbs naturally. / أستخدم ظروف التكرار بشكل طبيعي.
  - I'm ready for A1. / أنا جاهز للمستوى A1.
- `review_group`: R6 *(triggers REVIEW 6 — final course review)*

---

## Cluster sizing summary

| # | Cluster | Skill units | Vocab units | Total | Review |
|---|---|---|---|---|---|
| 1 | Identity | 4 | 4 | 8 | R1 |
| 2 | Daily life | 8 | 3 | 11 | R2 |
| 3 | Places | 6 | 1 | 7 | R3 |
| 4 | Possessions | 5 | 3 | 8 | R4 |
| 5 | Preferences | 4 | 4 | 8 | R5 |
| 6 | Ability | 4 | 2 | 6 | R6 |
| | **Total** | **31** | **17** | **48** | **6 reviews** |

---

## How this maps to the existing schema (no new models)

```
courses.Course        →  Onlenco Beginner English Foundation
courses.CourseUnit    →  18 sub-groups (≤ 3 Lessons each)
courses.Lesson        →  48 rows (one per topic above)
   .title_en/.title_ar  →  from this blueprint
   .lesson_type         →  "grammar" | "vocabulary" | "speaking" | "listening" (closest match)
   .cefr_level          →  A0 / A1
   .duration_minutes    →  from estimated_minutes
   .content_html        →  populated in P04 (seed)
courses.LessonQuiz       →  one per Lesson (1:1)
courses.LessonQuestion   →  populated in P05 (quiz bank)
courses.LessonChecklist  →  from checklist_items (this blueprint)
courses.LessonAudioScript→  one row per script_type per Lesson; payload from audio_idea
courses.LessonImagePrompt→  one row per prompt_type per Lesson; payload from image_idea
courses.LessonMedia      →  populated by P07 (image generator) and P08 (audio generator)
courses.LessonResource   →  unused for the auto-generated content (kept for teacher uploads)
```

**Reviews** are simply Lessons (`order` between the cluster's last topic and the
next cluster's first), with `lesson_type` = `"review"` — we'll add `"review"` to
`LESSON_TYPE_CHOICES` in P10 (one-line additive choice change).

This proves we **don't need a `LearningModule` model**. The existing schema +
P02 additions cover every field this blueprint needs.
