# Onlenco Super Learning Experience — Product + Architecture

*Planning document. No code, migrations or seeds change as a result of
this document — it is the blueprint for Phases 1 → 10 that follow.*

---

## 0. North Star

**The student should never feel they are taking a test. They should feel
they are playing a game that happens to teach English.**

Today: Onlenco renders a Django form quiz with 9 questions per lesson.
The student fills inputs, clicks Submit, sees a score.

Target: each interaction is **one card on the screen**, answered in
seconds, with **immediate feedback**, audio, an XP counter that ticks
up, a heart that occasionally pulses, and a finish screen that
encourages another round.

Onlenco's identity stays clean and modern. Mascot, palette, motion
language are **all original to Onlenco** — never reuse competitor
trade dress (mascots, signature greens, idle-bounce animations).

---

## 1. Vision — 15 Promises to the Student

A student opening Onlenco must feel each of these *every session*:

| # | Promise | How we deliver |
|---|---|---|
| 1 | "This isn't a school test." | One card per screen. No long forms. No score-after-30-questions UX. |
| 2 | "I always know what's next." | Linear path, single CTA per screen, never two competing buttons. |
| 3 | "I can do this in 3 minutes." | Default Challenge = 6 cards · ~3 min, configurable up to 12 cards. |
| 4 | "Every tap feels real." | 80 ms tap response, button press scales 0.96, soft click sound. |
| 5 | "It tells me right away." | Feedback card slides in within 250 ms of Check. |
| 6 | "Wrong is fine — I learn from it." | Wrong = gentle red, short fix, *no penalty until 5th mistake*. |
| 7 | "I'm climbing." | XP bar fills visibly. Confetti at milestones (100/500/1000 XP). |
| 8 | "I have something to lose." | 5 hearts per session. Lost on consecutive errors only. |
| 9 | "Today counts." | Streak counter on dashboard. Even 1 minute counts. |
| 10 | "I can hear native English." | All audio en-US, voice profiles consistent across a level. |
| 11 | "I see the language." | Every vocab card has an original illustration (no stock photos of people). |
| 12 | "Someone is helping me." | AI Tutor appears at 3 moments: after a wrong-streak, in Speaking cards, end-of-lesson. |
| 13 | "It speaks my language when needed." | Arabic hint only on the "Why is this wrong?" tap. UI is English-first. |
| 14 | "I won't lose my progress." | Resume mid-Challenge. Persisted server-side after every card. |
| 15 | "It remembers me." | Dashboard greets by name, shows yesterday's last topic. |

These are not nice-to-haves — they are *acceptance criteria* for every
Phase that follows.

---

## 2. Student Learning Flow — End-to-End

```
SIGN UP ─────► VERIFY EMAIL ────────► CHOOSE PATH ────► DASHBOARD
                                            │
                                ┌───────────┴───────────┐
                                │                       │
                          "Start at 0"           "I have some English"
                                │                       │
                          A0 Course                Placement Test
                                │                       │
                                └───────────┬───────────┘
                                            ▼
                                    LEARNING PATH (48 topics)
                                            │
                                            ▼
                                       TOPIC HUB
                                  ┌─────────┴─────────┐
                                  │                   │
                            Lesson Cards         AI Tutor Drill
                            (6 stepper steps)    (optional)
                                  │
                                  ▼
                        CHALLENGE SESSION
                       (6–12 game cards)
                                  │
                                  ▼
                          SUMMARY SCREEN
                       ┌─────────┴─────────┐
                       │                   │
                Mistakes Review      Next Topic CTA
```

### 2.1 Step-by-step

| Step | The student sees | The student does | The system saves |
|---|---|---|---|
| **Sign up** | Single-page email + password form, hCaptcha | Submits form | `User`, `Profile`, `NotificationPreference` |
| **Verify email** | OTP screen with 6-digit input | Pastes the code | `profile.email_verified=True` |
| **Choose path** | 2 big cards: "Start at zero" / "I know some English" | Taps one | `profile.onboarding_path` |
| **Placement (optional)** | Existing placement (5 written + voice call) | Answers | `PlacementAttempt`, `profile.cefr_level` |
| **Dashboard** | Greeting by name, streak, XP, current topic, "Continue" CTA | Taps Continue | last-active timestamp |
| **Learning path** | Vertical scrolling map of 48 topic nodes for current level | Picks the highlighted current topic | — |
| **Topic hub** | Topic title, 7 stage cards (Intro → Speaking → Finish + "Take the Challenge" CTA) | Taps a stage or Challenge | — |
| **Lesson intro** | Hero image + audio "play" button | Listens | — (audio is consumed) |
| **Vocabulary step** | Audio + 3–8 vocab tiles (image + word) | Listens, replays | — |
| **Examples step** | Numbered example sentences with per-sentence audio | Listens, taps to replay | — |
| **Dialogue step** | Chat-bubble script of 4 turns + audio | Listens | — |
| **Listening step** | Single listen-then-pick card | Picks the right option | `CardAttempt` row |
| **Speaking step** | Mic card. "Say it back." | Records 5–10 s | `SpeakingAttempt` + STT transcript |
| **Challenge Session** | Sequence of 6–12 game cards | Plays through | Per-card `CardAttempt` |
| **Per-card feedback** | Green check or red X with one-line fix | Taps Continue | XP delta, heart delta, mastery delta |
| **AI Tutor moment** | Appears if 3 consecutive wrongs OR Speaking card OR end-of-lesson | Talks for 60–120 s | `TutorConversation` + scores |
| **Summary** | XP earned, time spent, accuracy, badges popped | Taps "Mistakes Review" or "Next" | `LessonCompletion` row |
| **Mistakes Review** | Only the cards they got wrong, sequenced for relearning | Re-attempts | `MistakeReview` row (kept for SRS) |
| **Next topic** | Returns to Learning Path; next node now glowing | — | unlock event |

### 2.2 Exit & resume contract

- A Challenge is **interruptible at any card boundary**. The next visit
  resumes at the exact card. The XP / hearts are restored from server.
- If the student abandons mid-Challenge for > 24 h, the Challenge is
  archived and "Start again" is offered (no partial XP credited).

### 2.3 What happens when…

| Situation | System response |
|---|---|
| 3 wrongs in a row in one Challenge | AI Tutor mini-card slides in: "Quick coaching?". Skip is allowed. |
| Heart count hits 0 | "Take 5" screen — short breathing animation + a free vocab review. No paywall. |
| Same skill missed 3+ times in 7 days | Next session inserts a Refresher card for that skill before the new Topic. |
| Student returns after > 3 days | Dashboard says "Welcome back. Today is a Comeback day — half the cards, double the XP." |
| Student tries to skip ahead in the path | Locked topics show a single-line CEFR explanation, not a generic lock icon. |

---

## 3. Game Challenge Experience — 8 Screen Specs

The Challenge Session is the heartbeat of the experience. Every screen
below is a single Django template + Alpine.js (or vanilla) state.

### 3.1 Start Challenge screen

```
   ┌──────────────────────────────────────────┐
   │  ◀  Topic 13 · Describing your day        │
   ├──────────────────────────────────────────┤
   │                                          │
   │         🌅 Today's Challenge               │
   │                                          │
   │            6 cards · ~3 min               │
   │                                          │
   │     ❤❤❤❤❤        +12 XP avg               │
   │                                          │
   │      ┌────────────────────────┐           │
   │      │     START CHALLENGE    │           │
   │      └────────────────────────┘           │
   │                                          │
   │      "Practice with AI Tutor first" link  │
   └──────────────────────────────────────────┘
```

Purpose: set expectations (length, hearts, reward) so the student
commits.

### 3.2 Question screen (generic shell)

Top bar: **progress dots** (filled = done), **hearts**, **XP counter**.
Card body: depends on question type (see §4).
Bottom: a single **CHECK** button. Card is disabled until input is
valid.

```
┌──────────────────────────────────────────┐
│ ● ● ● ○ ○ ○      ❤❤❤❤❤      0 ▲ +12 XP   │
├──────────────────────────────────────────┤
│                                          │
│   How do you say "I usually wake up at 7"│
│   in a question? Use How often.          │
│                                          │
│   ┌────────────────────────────────────┐ │
│   │ How often                          │ │
│   └────────────────────────────────────┘ │
│                                          │
│   💡 Hint: do you use 'does'?            │
│                                          │
├──────────────────────────────────────────┤
│              ┌──────────┐                │
│              │  CHECK   │                │
│              └──────────┘                │
└──────────────────────────────────────────┘
```

### 3.3 Correct feedback

Tone: short, warm, *specific*. Never "Good job!" alone.

```
   ┌──────────────────────────────────────────┐
   │   ✓  Nice — that's the right verb.        │
   │                                          │
   │   "She works." → "Does she work?"         │
   │                                          │
   │              +12 XP                      │
   ├──────────────────────────────────────────┤
   │            ┌──────────┐                  │
   │            │ CONTINUE │                  │
   │            └──────────┘                  │
   └──────────────────────────────────────────┘
```

Animation: card border flashes green (300 ms), XP counter ticks
+1 each frame (40 ms × 12 frames), soft click on Continue.

### 3.4 Wrong feedback

Tone: empathetic, points at the *one* fix.

```
   ┌──────────────────────────────────────────┐
   │   ✕  Almost — your verb form              │
   │                                          │
   │   You wrote:   "How often do she work?"   │
   │   The fix:     "How often does she work?" │
   │   Why:         She / he / it → does       │
   │                                          │
   │   ❤ -1                                    │
   ├──────────────────────────────────────────┤
   │  [ Ask AI Tutor ]      [   CONTINUE   ]   │
   └──────────────────────────────────────────┘
```

Wrong feedback always shows **one** rule, never two. If multiple were
broken, pick the highest-priority (verb form > word order > spelling).

### 3.5 Speaking feedback

```
   ┌──────────────────────────────────────────┐
   │   🗣  Your recording                       │
   │   "I usually wake up at seven"            │
   │                                          │
   │   Pronunciation     ████████░░  82%      │
   │   Grammar           ██████████  100%     │
   │   Confidence        ███████░░░  74%      │
   │                                          │
   │   Tip from tutor:                        │
   │   "Stress the word USUALLY a bit harder." │
   ├──────────────────────────────────────────┤
   │  [ Try again ]        [   CONTINUE   ]    │
   └──────────────────────────────────────────┘
```

Speaking always shows 3 scores. Tutor tip is one sentence, max 12
words.

### 3.6 Listening feedback

Identical layout to 3.3/3.4 but the wrong-feedback card includes a
**Replay** affordance:

```
   ┌──────────────────────────────────────────┐
   │   ✕  Listen again                         │
   │                                          │
   │   You picked:  "She studies in Cairo."    │
   │   The audio:   "She studies in Paris."    │
   │                                          │
   │   🔊 [Play audio again]                   │
   ├──────────────────────────────────────────┤
   │            ┌──────────┐                  │
   │            │ CONTINUE │                  │
   │            └──────────┘                  │
   └──────────────────────────────────────────┘
```

### 3.7 Summary screen

```
   ┌──────────────────────────────────────────┐
   │     ⚡ 92 XP                              │
   │     🎯 5 / 6 correct                      │
   │     ⏱ 2 min 47 s                          │
   │     🔥 Streak: day 4                      │
   │                                          │
   │     New badge: Speaking Brave 🏅          │
   │                                          │
   │     1 mistake to review.                 │
   │                                          │
   │  ┌────────────────────────────────────┐  │
   │  │   Review the 1 mistake             │  │
   │  └────────────────────────────────────┘  │
   │  ┌────────────────────────────────────┐  │
   │  │   Continue to next topic           │  │
   │  └────────────────────────────────────┘  │
   └──────────────────────────────────────────┘
```

### 3.8 Mistake review screen

A focused replay loop: only the wrong cards, with a 1-line hint above
each. No XP penalty here (XP is awarded only on first encounter).
Completing review boosts the related skill's mastery faster than a
normal correct answer (×1.5).

---

## 4. Question Types — 20 Cards in the Deck

For each type below: **purpose · skill · sketch · grading · media
needs**. Original example wording uses Onlenco's 10-character cast
(Amani, Yusuf, Noor, Kareem, Salma, Omar, Layla, Tarek, Hala, Rashid).

| Code | One-line | Skill | Audio | Image | Tutor |
|---|---|---|---|---|---|
| `tap_choice` | Big card MCQ | varies | — | optional | — |
| `image_choice` | Pick the right picture | vocab | — | **req** | — |
| `listen_and_choose` | Hear → tap matching written form | listening | **req** | optional | — |
| `listen_and_type` | Hear → type what you heard | listening + writing | **req** | — | — |
| `speak_this_sentence` | Read aloud + STT score | speaking | reference | — | **yes** |
| `word_bank_sentence` | Tap word chips to build a sentence | grammar | — | optional | — |
| `match_pairs` | Two columns → connect | vocab | — | optional | — |
| `fill_blank_card` | Single blank in a sentence | grammar | — | — | — |
| `translate_to_english` | AR phrase → EN | productive | — | — | — |
| `translate_to_arabic` | EN phrase → AR (multiple choice) | comprehension | — | — | — |
| `conversation_reply` | Pick the natural reply | pragmatics | optional | optional | — |
| `picture_labeling` | Tap parts of a picture | vocab | — | **req** | — |
| `sound_to_word` | Hear a single word → pick it | listening | **req** | — | — |
| `pronunciation_check` | Repeat-after-model + score | pronunciation | reference | — | **yes** |
| `frequency_scale` | Place adverbs on 0–100 % | grammar | — | — | — |
| `table_sentence_builder` | Build sentences from 4 columns | grammar | — | — | optional |
| `question_transform` | Statement → How often / When | grammar | — | — | — |
| `mistake_correction` | Fix the wrong sentence | grammar | — | — | — |
| `mini_story_choice` | Read a paragraph → answer | reading | — | optional | — |
| `ai_roleplay_prompt` | 60-sec scoped chat with AI tutor | speaking | — | — | **core** |

### 4.1 Per-type detail (selected)

**`tap_choice`** — 2–4 large rectangular cards, one is correct.
Example: "Which one means *bedroom* in your house? → غرفة النوم".
Grading: exact match of selected card ID. Wrong-feedback shows the
right answer + the meaning of the distractor.

**`listen_and_type`** — Audio plays once; student types what they
heard. Grading: edit-distance ≤ 1 → correct; ≤ 3 → partial credit
(½ XP); else wrong with the correct text shown.

**`speak_this_sentence`** — Big sentence on the card with target word
highlighted. Mic button records. STT returns transcript + 3 scores
(pronunciation / grammar / confidence). XP scales with score
(80%+ = full XP, 60–80% = half, <60% = retry).

**`word_bank_sentence`** — 6–8 word chips in a "bank"; student taps to
move them into a "target" tray. Bank shuffled per attempt to prevent
muscle memory.

**`match_pairs`** — Two columns of 4–6 items. Tap one on the left, tap
its match on the right. Connected pairs lock. Wrong = brief shake.

**`mini_story_choice`** — A 3–5 sentence original mini-story
(Onlenco-cast based) followed by 1–2 comprehension questions. Always
provides an audio version for accessibility.

**`ai_roleplay_prompt`** — Scoped voice call (existing `tutor` app)
with a system prompt that:
- Locks the topic to today's lesson
- Limits the tutor's vocabulary to the current cluster
- Demands single-correction feedback
- Ends at 90 seconds maximum

### 4.2 What's NOT a card type

We intentionally avoid:
- Free-text essays in beginner Challenges (too slow + needs grading)
- Drag-and-drop puzzles requiring fine motor control (mobile-hostile)
- Anything that requires reading > 60 words at A0/A1 level

---

## 5. Gamification System

### 5.1 XP economy

Conservative, predictable, never feels random:

| Event | XP |
|---|---|
| Correct on first try | 10 |
| Correct after a hint | 5 |
| Correct after mistake-review pass | 7 |
| Speaking card 80%+ | 15 |
| Speaking card 60–80% | 8 |
| Perfect Challenge (no wrongs) | +25 bonus |
| Daily streak day +1 | +10 |
| Completing the AI Roleplay | +15 |
| First time using a new skill correctly | +5 ("Skill Unlocked") |

Daily XP cap: **300** (prevents grinding burn-out). XP shown to user is
clamped + a small "+0 (daily cap)" message.

### 5.2 Hearts / Lives

- Start each session with **5 hearts**
- Lose 1 heart only on a **wrong card that ended a streak of correct
  cards** (so two wrongs in a row = 1 heart lost, not 2)
- Hearts refill: **1 per 4 real-time hours** OR completing a Refresher
  (free, drawn from past mistakes)
- 0 hearts ≠ paywall: instead the student goes into a "Refresher Run"
  — a vocab-only session that refills hearts on completion
- Hearts are session-local (do not carry between sessions)

### 5.3 Streak

A streak day requires **either**:
- Completing at least 1 Challenge, OR
- 5 minutes of any activity (Lesson, Speaking, Tutor)

Local timezone is the user's `profile.timezone` (default Africa/
Khartoum). Streak freezes on weekends are **off** to keep the model
honest — but a "Comeback Bonus" exists after a break (see §2.3).

### 5.4 Badges (mature, not childish)

12 launch badges:

| Badge | Earned by |
|---|---|
| **First Steps** | Complete Topic 01 |
| **7-Day Streak** | 7 consecutive day streak |
| **30-Day Streak** | 30 consecutive day streak |
| **Speaking Brave** | Record 10 speaking cards in a week |
| **Listening Star** | 90%+ accuracy on listening cards over a week |
| **Vocabulary Hero** | Master 100 distinct vocab items |
| **Grammar Builder** | Master 10 distinct grammar skills |
| **Perfect Challenge** | Complete a Challenge with 0 wrongs |
| **Comeback** | Return after 7+ days absent and finish a session |
| **Night Owl / Early Bird** | 7 sessions before 8 am or after 10 pm |
| **Cluster Closer** | Complete all 8 topics in a cluster |
| **Mastery** | Complete the A0 course |

Visual language: each badge is a **single flat geometric icon**, no
character mascots, no cartoonish faces. Colour palette pulls from the
Onlenco brand tokens only.

### 5.5 Daily goal

User picks once at onboarding:
- Casual: 5 minutes
- Regular: 10 minutes
- Serious: 15 minutes
- Intense: 30 minutes

Goal is met by total active time, not Challenge count. Daily goal hit
= confetti once, no further celebrations.

### 5.6 Encouragement messages — tone register

Voice = mid-twenties American teacher, warm but not childish. No
exclamation marks except in big-win moments.

**Success (correct):**
- "Right on." / "Got it."
- "Clean — that's the form we wanted."
- "Yes — the verb agrees."
- (AR hint variant when ar locale: "أصبت — هذا التركيب الصحيح.")

**Wrong:**
- "Close. Try the verb form."
- "Almost — the auxiliary."
- "Heads up: the word order."
- (AR variant: "قريب — راجع الفعل المساعد.")

**Comeback:**
- "Welcome back. Let's pick up where you left off."
- "Good to see you. Today's session is light — half the cards."
- (AR: "أهلاً بعودتك. سنبدأ بنصف الكروت اليوم.")

**Streak:**
- "5 days. Discipline shows."
- "10 days. You're building a habit."

**Speaking improvement:**
- "Your pronunciation of *usually* went up 18 points since Tuesday."

**No** confetti-based messaging like "AMAZING JOB!!". No mascot speech.

---

## 6. Adaptive Learning — Mastery System

### 6.1 Skill model

A **skill** is a discrete, observable competence. Examples:

```
A0 / A1 skills (~30):
  greetings, alphabet, to_be_singular, to_be_plural, ages, nationalities,
  possessive_adj, this_that, these_those, apostrophe_s,
  present_simple_pos, present_simple_neg, present_simple_q, short_answers,
  wh_questions, prepositions_time, prepositions_place, articles,
  there_is_there_are, adjectives_position, modals_can, modals_must,
  going_to_future, comparatives, superlatives, adverbs_frequency,
  listening_basic, speaking_intro, pronunciation_alphabet,
  pronunciation_ed_endings
```

Each skill row: `code`, `name_en`, `name_ar`, `cefr_level`, `parent`
(optional), `prerequisites` (array of skill codes).

### 6.2 Mastery score

Per (student, skill): a value in [0, 100] computed as exponential
moving average of card outcomes.

```
weight = 0.30                          # smoothing
new_mastery = (1 - weight) * old_mastery + weight * card_score

card_score:
  correct first-try        = 100
  correct after a hint     =  70
  correct in review        =  85
  wrong                    =   0      (capped: never goes below half of avg)
  speaking score x/100     =   x      (already 0–100)
```

Mastery thresholds:
- < 30 → **At risk** (red on the path)
- 30–69 → **Practicing**
- 70–89 → **Mastered**
- 90+ → **Fluent** (shown with star on the path)

### 6.3 Error journal

Every wrong card writes a row to `LearnerError`:
```
{ user, skill, card_id, card_type, snapshot_prompt,
  student_answer, expected_answer, error_category, lesson, occurred_at }
```

`error_category` is one of: `verb_form`, `word_order`, `aux_choice`,
`article`, `preposition`, `vocab_recall`, `spelling`,
`pronunciation`, `comprehension`, `other` — assigned by a small rule
engine on the server (deterministic, no AI dependency).

### 6.4 Refresher selection

Daily, the system picks the next card from this priority order:

1. **At-risk skills with recent errors** (last 7 days)
2. **Skills overdue** (no practice for ≥ 5 days)
3. **The next planned topic's prerequisite skills**
4. **A diversity sample** across mastered skills (prevents forgetting)

The Challenge composer reads this priority list and **always includes
1–2 review cards** in any Challenge that isn't the very first one in
a topic.

### 6.5 Topic unlocking

A topic unlocks when *all* prerequisite skills hit Practicing (≥ 30).
Mastered isn't required — the student learns by doing. The "unlock
banner" tells them which skills they're standing on.

### 6.6 Fallback when AI is unavailable

The whole mastery system is **deterministic and AI-free**. AI helps:
- Score Speaking cards (with rule-based fallback below 1.0 RTT)
- Generate per-error explanations (with template-based fallback)

If `AI_API_KEY` is unset or the API errors, the Challenge keeps
running with rule-based feedback. Adaptive learning never depends on
the API being live.

---

## 7. AI Tutor Inside the Learning Loop

The tutor stops being a "chat tab". It becomes 6 short cameos inside
the experience.

### 7.1 The 6 Tutor moments

| Moment | Trigger | Duration | Mode |
|---|---|---|---|
| **Pre-lesson** | Student taps "Practice with tutor first" before Challenge | 60 s voice | Warm-up Q&A on the day's vocab |
| **Speaking card** | Inside a `speak_this_sentence` card with score < 70 | 30 s voice | Single repeat-after-me drill |
| **Mistake explainer** | After 2 wrongs on same skill in same Challenge | 20 s text | One-sentence rule + one model sentence |
| **Roleplay card** | `ai_roleplay_prompt` card | 90 s voice | Scoped 4-turn roleplay |
| **End-of-lesson tutor** | Summary screen → "Talk to tutor" CTA | 120 s voice | Recap + one challenge sentence |
| **Mistake review** | Inside Mistake Review screen, "Why is this wrong?" tap | 15 s text | One-line explanation |

### 7.2 Hard rules baked into every system prompt

```
1. American English. Slow, clear.
2. Beginner-friendly: short sentences, common words.
3. No lecturing. Max 12 words per turn.
4. One correction at a time. Acknowledge before correcting.
5. Stay on the lesson's topic.
6. Use only the vocab from the cluster.
7. Never read symbols, underscores, or placeholders.
8. Encourage. Never embarrass.
9. Arabic hint allowed once per session, ≤ 1 sentence, ONLY when student is stuck.
10. End on a positive line.
```

### 7.3 Tutor prompt sketch (Pre-lesson moment)

```
SYSTEM:
You are a friendly American-English tutor speaking with {{ student_name }},
an Arabic-speaking beginner. Tonight's topic: "{{ topic_title_en }}".
Allowed vocab: {{ vocab_list }}. Grammar focus: {{ skill_focus }}.

Goal of this 60-second cameo:
1. Greet them by name.
2. Ask 2 questions that use the new construction.
3. After each answer, one short correction OR one short praise.
4. End with: "You're ready — let's start."

Hard rules: short turns (≤ 12 words). American English. No lecturing.
One correction per turn. Arabic hint only if they're stuck.
```

### 7.4 What the tutor does NOT do

- Does not give grades / scores aloud
- Does not promise rewards ("you'll earn 10 XP")
- Does not advise outside the lesson topic
- Does not respond to off-topic chat ("How was your day?") — instead:
  "Good — let's stay with today's topic. Try this:..."

---

## 8. Learning Path / Skill Tree

### 8.1 Visual model

```
                  ┌─────────┐
                  │ Topic 01│ ◀── current  (glowing ring)
                  └────┬────┘
                       │
                  ┌────┴────┐
                  │ Topic 02│
                  └────┬────┘
                       │
                  ┌────┴────┐
                  │ Topic 03│
                  └────┬────┘
                  ┌────┴────┐
                  │ Topic 04│   ◀── locked (faded, single-line CEFR hint)
                  └─────────┘
                       │
                  ╭───── REVIEW R1 ─────╮
                  │  units 01 – 08      │
                  ╰─────────────────────╯
                       │
                  …
```

- **Vertical scroll** on mobile, snake-shaped on desktop
- Each topic node is a circle with the topic's emoji and a thin
  progress ring (% of cards mastered)
- A topic shows its **estimated time** (e.g. "3 min") on tap
- The 6 cluster reviews appear as **wider rounded-rectangle nodes**
- Past clusters collapse to a single "Cluster 1 — completed" pill
  after the 3rd cluster is done

### 8.2 Topic states

| State | Visual cue |
|---|---|
| **Completed** | Solid filled circle, soft check, dim |
| **Current** | Outlined circle, pulsing glow, tap → topic hub |
| **Available** | Filled colour, no glow |
| **Locked** | Greyscale + single-line CEFR explanation on tap |
| **Needs review** | Yellow ring around an otherwise completed node |
| **Mastered** | Star icon inside the filled circle |

### 8.3 Weakness display

The dashboard shows up to **3 weak skills** as small chips:

```
Today's weak spots:
[ Verb agreement 38% ]  [ /θ/ sound 41% ]  [ Articles 28% ]
```

Tapping a chip starts a 4-card "Skill Booster" focused on that skill.

---

## 9. Lesson 01 — Gold Standard Mockup

**Topic 01 · Introducing Yourself** — full design with original
Onlenco content (no copying from any reference source). Characters:
Amani, Yusuf, Noor.

### 9.1 Lesson side (Stepper — 6 steps + Finish)

| Step | Content (original Onlenco) |
|---|---|
| **Intro** | 12-second audio: "In this topic, you'll meet two new people. By the end you can greet someone and say your own name." |
| **Vocabulary** | 6 tiles: Hello · Hi · My name is · I'm · spell · meet. Audio per tile (one voice). |
| **Examples** | "Hello, I'm Amani." / "Hi! My name is Yusuf." / "Nice to meet you." / "Can you spell that?" |
| **Dialogue** | Amani ↔ Yusuf chat-bubble, 4 turns. Audio in two voices. |
| **Listening** | Three short audio clips, each names a different speaker. Student picks the spoken name. |
| **Speaking** | Repeat-after-model: "Hello. My name is _____." Student records, sees 3 scores. |
| **Finish** | Checklist + "Take the Challenge" CTA (6 cards). |

### 9.2 Challenge side — the 6-card session

| # | Card type | Original content |
|---|---|---|
| 1 | `tap_choice` | "Which one is a greeting?" → [Hello / Window / Apple] |
| 2 | `listen_and_choose` | Audio: "My name is Noor." → Pick the speaker's name |
| 3 | `word_bank_sentence` | Chips: [name / my / is / Amani / Hello] → "Hello, my name is Amani" |
| 4 | `match_pairs` | Hello↔مرحباً · spell↔تهجّى · meet↔التقى · name↔اسم |
| 5 | `speak_this_sentence` | "Hi, I'm <YOUR NAME>." — student substitutes real name |
| 6 | `conversation_reply` | "Hello, I'm Yusuf." → [Hi, my name is ___ ✓ / Window / Tomato] |

### 9.3 AI Tutor moment for Topic 01

Trigger: a Speaking card with score below 70.

```
TUTOR: Hi Hala. Try one more time: "Hello, my name is Hala."
HALA:  "Hello, my name Hala."
TUTOR: Almost — say "my name IS Hala". Try again.
HALA:  "Hello, my name is Hala."
TUTOR: Yes — clean. You're ready.
```

Total time: ~20 seconds. Tutor never breaks the rules in §7.2.

### 9.4 Media manifest (planning only — no generation in this prompt)

| Asset | Source |
|---|---|
| Topic cover image | AI-generated to the prompt "Two friendly characters waving in a sunny school courtyard, flat Onlenco illustration, soft pastel background." |
| 6 vocab tile images | AI-generated, single object per tile, neutral background. |
| 4 audio scripts | TTS (en-US), 2 distinct voices (one female for Amani/Noor, one male for Yusuf). |
| 6 Challenge card audio | TTS reuse of dialogue + speaking model lines. |

---

## 10. Current State Assessment

Honest read of the codebase as of this session.

| Pillar | Current | Target | Gap |
|---|---|---|---|
| **Quiz Engine** | LessonQuestion + metadata JSONField, 13 question types, per-type grader | 20 card types, micro-feedback per card, Challenge composer | 7 new card types, Challenge composer, micro-feedback loop |
| **Question Types** | 13 (8 legacy + 5 new interactive from previous prompt) | 20 game card types | 7 new types: tap_choice (rebrand), image_choice, listen_and_choose, listen_and_type, sound_to_word, picture_labeling, mini_story_choice |
| **Student UI** | Stepper lesson page (7 steps), launcher overview, traditional quiz page | Card-at-a-time Challenge engine with feedback animations | Whole `templates/courses/challenge_*.html` family + state machine |
| **Gamification** | `motivation` app with toasts, XP rewards, basic streak | Hearts, daily goal, badges (12), encouragement messages, daily cap | Hearts model + heart refill, daily-goal model, badge engine, message bank |
| **AI Tutor** | `tutor` app with voice call + lesson-scoped prompt builder | 6 short cameos inside Challenge | Cameo triggers in Challenge runner; tutor prompt presets per cameo |
| **Speaking** | `placement.services.stt` (Whisper), tutor voice call | Per-card scoring (3-axis) + retry loop | Card-grade STT wrapper returning {pronunciation, grammar, confidence} |
| **Listening** | TTS-generated audio per lesson (intro/vocab/examples/…), audio chips on lesson page | Per-card audio with replay button + speed control 0.75× / 1.0× | Card-level audio attachment via `QuestionMedia` (exists) + UI |
| **Adaptive Learning** | `learning_core` app has Skill, SkillMastery, UserError, UserWeakness, AdaptiveExercise | Mastery EMA, refresher selector, error-journal driven path | Wire the existing learning_core into the Challenge runner |
| **Progress** | `CourseLessonProgress` per (user, lesson) | Per-card attempts, per-skill mastery, per-mistake review state | New `CardAttempt`, `MistakeReview` tables |
| **Lesson Design** | 7-step stepper per lesson (Intro → Speaking → Finish) | Lesson stepper + Challenge runner side-by-side | Add Challenge runner without rewiring stepper |

### 10.1 Notes I'm sure of from this session

- 336 lessons exist across 7 levels, with bilingual content
- 1,739 generated TTS audio clips attached (gpt-4o-mini-tts pipeline)
- 196 of 290 cover images generated (B2/C1/C2 blocked on OpenAI billing)
- Quiz Engine v2 added `metadata` JSONField + 5 interactive types
- The `learning_core` app has the relevant models for mastery but they
  aren't wired to lesson outcomes yet

### 10.2 Where I'm not certain (and shouldn't guess)

- The exact wiring of `motivation` events to lesson completion
- Whether `tutor.services.evaluation_service` already produces a
  3-axis score, or only a single overall number
- The current behavior of `MistakeReview`-style SRS — I don't see
  such a table; we will add one in Phase 5

I'm flagging these as **open questions for Phase 1 kickoff**, not
hidden assumptions.

---

## 11. Implementation Roadmap — 10 Phases

Each phase is independently shippable and reversible.

### Phase 1 — Challenge Engine

| | |
|---|---|
| **Goal** | A single Challenge runs end-to-end with the existing 13 types. |
| **Files** | `courses/services/challenge_composer.py`, `courses/services/challenge_runner.py`, `courses/views.py::challenge_*`, URL routes, `templates/courses/challenge_session.html`, JS state machine. |
| **Risks** | URL collisions with existing quiz routes; state persistence on refresh. |
| **Tests** | `test_challenge_starts_resumes_finishes`, `test_challenge_persists_per_card`, `test_legacy_quiz_still_works`. |
| **Success** | Student walks through 6 cards, sees +XP, sees Summary. |

### Phase 2 — 7 New Card Types

| | |
|---|---|
| **Goal** | Add `tap_choice`, `image_choice`, `listen_and_choose`, `listen_and_type`, `sound_to_word`, `picture_labeling`, `mini_story_choice`. |
| **Files** | New entries in `QUESTION_TYPE_CHOICES`, partial templates per type, grader modules. |
| **Risks** | Backward-compat with existing seed data; image_choice needs real images. |
| **Tests** | 1 grader test + 1 renderer test per type (14 total). |
| **Success** | All 20 types render and grade in a Challenge with mixed types. |

### Phase 3 — Game-like UI Polish

| | |
|---|---|
| **Goal** | Animations, sound, micro-interactions, mobile gestures. |
| **Files** | `static/css/onlenco-challenge.css`, `static/js/challenge.js`, sound assets (`/static/sounds/`). |
| **Risks** | Accessibility (focus management, screen reader); motion-reduce honoured. |
| **Tests** | `test_focus_advances_on_correct`, `test_motion_reduce_disables_animations`. |
| **Success** | Lighthouse mobile score ≥ 90; reduced-motion users get a static path. |

### Phase 4 — XP / Hearts / Streak

| | |
|---|---|
| **Goal** | The full §5 economy live. |
| **Files** | New `gamification` app OR extend `motivation` app: `models.HeartBalance`, `DailyGoal`, `Badge`, `BadgeAward`. Migrations. Service layer. UI chrome. |
| **Risks** | Daily-cap edge cases (timezone, midnight rollover). |
| **Tests** | `test_xp_cap_per_day`, `test_heart_refill_4h`, `test_streak_timezone`. |
| **Success** | XP/heart values match §5.1/§5.2 exactly in 12 e2e scenarios. |

### Phase 5 — Adaptive Learning

| | |
|---|---|
| **Goal** | Mastery EMA + refresher selector wired into the Challenge composer. |
| **Files** | `learning_core/services/mastery_ema.py`, `learning_core/services/refresher_picker.py`, `LearnerError` + `MistakeReview` models, migration. |
| **Risks** | Mastery thrashing if EMA weight too high; cold start for new students. |
| **Tests** | `test_mastery_ema_step`, `test_refresher_prioritises_at_risk`, `test_topic_unlocks_at_30%`. |
| **Success** | 14-day simulation produces a sensible mastery curve. |

### Phase 6 — AI Tutor Inside Challenges

| | |
|---|---|
| **Goal** | The 6 §7.1 cameos wired and triggered by real events. |
| **Files** | `tutor/services/cameo_prompts.py`, `tutor/views.py::cameo_start`, modal UI in challenge template. |
| **Risks** | Cost spike if cameos over-trigger; latency on cold call start. |
| **Tests** | `test_speaking_score_60_triggers_cameo`, `test_offtopic_response_redirects`. |
| **Success** | Cameo opens within 2 s, closes within 90 s, scoped to lesson. |

### Phase 7 — Super Lesson 01

| | |
|---|---|
| **Goal** | Build Topic 01 from §9 as the gold standard. |
| **Files** | Seed for Topic 01 lesson + 6-card Challenge with original content + media manifest. |
| **Risks** | Media generation slips; tone of feedback messages. |
| **Tests** | `test_super_lesson_01_renders_intro_to_finish`, `test_topic_01_challenge_grades_6_cards`. |
| **Success** | A new student can finish Topic 01 in ≤ 8 minutes total. |

### Phase 8 — QA Super Lesson 01

| | |
|---|---|
| **Goal** | 100% pass rate on the Topic 01 gold standard across 4 user profiles (new beginner, returning student, low-bandwidth, mobile). |
| **Files** | `courses/tests/test_super_lesson_01_e2e.py`. |
| **Risks** | Mobile-only bugs (audio autoplay, mic permission). |
| **Tests** | Above + manual real-device matrix. |
| **Success** | 0 P0/P1 bugs; ≤ 2 P2. |

### Phase 9 — Beginner 48 Topics

| | |
|---|---|
| **Goal** | Apply Phase 7's pattern to all 48 topics in A0. |
| **Files** | Bulk seed command that consumes the existing UNITS data and emits one Challenge per topic. |
| **Risks** | Content quality at scale (auto-generated cards need review). |
| **Tests** | `test_every_a0_topic_has_a_challenge`, `test_no_challenge_has_more_than_12_cards`. |
| **Success** | All 48 topics playable + reviewed by one human. |

### Phase 10 — Media Generation

| | |
|---|---|
| **Goal** | Generate remaining 129 covers + per-card listening audio when needed. |
| **Files** | Extend existing batch commands; new `picture_labeling_image_batch`. |
| **Risks** | OpenAI billing limit (currently triggered); content policy rejections. |
| **Tests** | Existing batch tests + dry-run validation. |
| **Success** | Topic 01 visually complete; remaining topics ship at ≥ 90% media coverage. |

### 11.1 Total picture

| Phase | Weeks (est) | Engineer-days |
|---|---|---|
| 1 | 1 | 4 |
| 2 | 1 | 5 |
| 3 | 1 | 4 |
| 4 | 1 | 4 |
| 5 | 1.5 | 7 |
| 6 | 1 | 4 |
| 7 | 0.5 | 3 |
| 8 | 0.5 | 2 |
| 9 | 1 | 4 |
| 10 | 0.5 | 2 |
| **Total** | **~9 weeks** | **~39 engineer-days** |

This is one engineer working full-time; with the existing infrastructure
we built in this session, several Phases overlap nicely.

---

## 12. Architectural Decisions to Lock Before Phase 1

These five decisions are blocking — they need a yes/no from product
before any code is written.

| # | Decision | Recommendation |
|---|---|---|
| 1 | New `gamification` app vs extend `motivation` | **Extend `motivation`** — already has reward events, XP, toasts. |
| 2 | Card state: client-only vs server-checked per card | **Server-checked per card** (POST after CHECK). Slightly slower, but resilient + analytics-ready. |
| 3 | Speaking grading: local rule-engine vs OpenAI per-card | **Hybrid**: rules first (free, fast), OpenAI fallback only when rules return low confidence. |
| 4 | Mastery storage: re-use `SkillMastery` from `learning_core` vs new | **Re-use** `SkillMastery`. The model already supports per-(user, skill) values. |
| 5 | Challenge composer: pure Python algorithm vs YAML/JSON templates | **Pure Python** — keeps the algorithm versionable and testable; YAML templates can come later for teacher authoring. |

---

## 13. What This Document Is Not

To prevent scope drift in the next prompts:

- It is **not** a feature wish-list. Anything not here is out of scope.
- It does **not** require new model fields beyond those named in §11.
- It does **not** assume new external services (no Firebase, no
  Algolia, no third-party gamification SDK).
- It does **not** depend on a UI framework rewrite — Django templates
  + sprinkle of vanilla JS / Alpine.js is enough.
- It does **not** propose offline / native mobile work. Web first.

---

*End of design document.*
