# Onlenco — Library & Sudanese School Novels Architecture Audit (19.0A)

> Audit-only. No code, models, or migrations added. No images/audio generated.
> No copyrighted novel text copied. No product behavior changed.
> Branch: `feat/beginner-media-and-tutor-usage` · HEAD `933af04`.

---

## 1. Executive Summary

**The Library is already built, and most of the interactive-reader plumbing already exists.** 19.0 is largely an *assembly + thin additive-schema* job, not a from-scratch build:

- A `library` app ships `Book` / `Chapter` / `VocabularyExtract` / `GrammarExtract` / `ComprehensionQuestion` / `LibraryProgress`.
- A **Natural Reader** already does TTS-on-the-fly with **text normalization** (no commas/underscores read aloud), **voice selection**, chunked synthesis, and **library-minute deduction** through `LibraryAudioSession` + `consume_library_seconds`.
- The **media review lifecycle** (`needs_review → approved`, `is_student_visible`) is reusable for per-segment illustrations and pre-rendered audio.
- Every **Duolingo-style question type** the product asks for already exists (`image_choice`, `listen_and_choose`, `word_bank_sentence`/ordering, `fill_blank_card`, `match_pairs`) with a grading dispatcher, plus **XP / streak / hearts / badges / mistake-SRS / vocabulary mastery**.

What's genuinely missing for the *interactive novel* experience is **segment-level structure** (paragraph/sentence units with a per-segment illustration + Arabic translation + short Arabic explanation), **interactive click-a-word vocabulary UI**, **copyright/provenance fields**, and a **Library nav entry**. These are additive.

---

## 2. Existing Library Architecture

App: [`library/`](library/). Models in [library/models.py](library/models.py):

| Model | Role | Maps to novel concept |
|-------|------|-----------------------|
| `Book` | title/author/category(`novel`/`short`/…)/level(CEFR)/cover/pdf/video_url/is_published/code | **Novel** |
| `Chapter` | body (one TextField), `audio_file`/`audio_url`, `duration_seconds`, `sort_order`, `code` | **Novel part** |
| `VocabularyExtract` | term/translation/pos/example/cefr | **Vocabulary highlight** |
| `GrammarExtract` | topic/explanation/example | grammar focus |
| `ComprehensionQuestion` | question/options(JSON)/correct_answer/explanation | part comprehension |
| `LibraryProgress` | (user, chapter) completed/comprehension_score/last_position | **StudentNovelProgress** |

Routes ([library/urls.py](library/urls.py)): `book_list`, `book_detail`, `update_position`, `mark_chapter_complete`, `chapter_summary`, `submit_comprehension`, `chapter_listen`, and the audio trio `chapter_audio_start` / `chapter_audio_chunk` / `chapter_audio_finish`.

Access: most views require `profile.is_subscribed`; the book list shows a lock when unsubscribed ([library/views.py](library/views.py)).

**Gaps vs. the interactive-reader vision:** `Chapter.body` is a single blob (no paragraph/sentence segmentation); only `Book.cover` (no per-segment illustration); no Arabic translation of the body; `VocabularyExtract` is **not rendered interactively** in templates; no Duolingo-style part quiz wired; no copyright fields.

---

## 3. Existing Media / Audio Reuse Points

**Media lifecycle** — [courses/models.py](courses/models.py) `GeneratedMediaReviewMixin` (used by `LessonAudioScript`, `LessonImagePrompt`):

- `generation_status` choices: `pending_generation` → `generated` → `needs_review` (default) → `approved` / `rejected` / `failed`.
- `is_student_visible == (status == "approved" and file_exists)` — students never see pending/failed/rejected; they get a clean placeholder ([templates/courses/_lesson_image_placeholder.html](templates/courses/_lesson_image_placeholder.html)).
- Admin review queue: [platform_admin/views_media_review.py](platform_admin/views_media_review.py) (`mark_media_approved`/`mark_media_rejected`).
- Manifest concept exists for beginner illustrations (audit-trail JSON), not a student-delivery cache.

**Answers to B (reuse):**
1. **Illustrations** → reuse the `GeneratedMediaReviewMixin` pattern with a FK to the novel segment (new thin model, e.g. `NovelIllustration`). Same status field; no lifecycle change.
2. **Audio** → two paths already exist: (a) **Natural Reader TTS-on-the-fly** (already wired, no asset needed) and (b) optional **pre-rendered** audio via the same mixin if you want reviewable, cached narration.
3. **Approval before student sees it** → yes, via `is_student_visible`; applies the moment illustrations use the mixin.
4. **Pending/failed hidden** → yes, by the same property + template gate.
5. **Manifest** → yes; a novel manifest can be generated later exactly like the beginner-media manifest.

**TTS safety** — [core/services/text_humanizer.py](core/services/text_humanizer.py) `humanize_for_speech()` strips underscores, HTML, URLs, symbols, and punctuation-labels **before** synthesis, and beginner speed is 0.9×. This already satisfies "don't read commas/underscores aloud."

---

## 4. Subscription Library Minutes Integration

Confirmed wired end-to-end (from 18.5B + existing Natural Reader):

- Plan fields: `library_audio_daily_minutes`, `library_session_cap_minutes` (admin-editable).
- Helpers: `quota_service.daily_library_limit_seconds`, `library_session_cap_seconds`.
- Counter: `UserDailyQuota.library_seconds_used`; deduction: `consume_library_seconds`.
- Session: `LibraryAudioSession` (one in-progress per user) opened in `chapter_audio_start`, **deducted on `chapter_audio_finish`** via [subscriptions/services/library_audio_service.py](subscriptions/services/library_audio_service.py) `end_session()`.

**Answers to C:**
1. **Best place to open `LibraryAudioSession`** → exactly where it is today: on **audio start** (`chapter_audio_start` → `library_audio_service.start_session`), deduct on **finish**. The novel reader should call the same service per part.
2. **Enforce the cap** → `start_session` raises `LibraryQuotaExhausted` (402) when no seconds remain; the per-session cap (`library_session_cap_seconds`) bounds a single listen. Keep this.
3. **Text reading vs audio** → today **only audio (TTS) is metered**; silent text reading is free.
4. **Images / silent reading** → not counted.
5. **UAT recommendation → meter AUDIO only.** Reasons: it maps to real provider cost, it's already implemented and tested, it doesn't punish slow readers, and it keeps the free-but-valuable silent-reading path open. Revisit a "reading-session" meter only if abuse appears. **Recommendation: keep audio-only metering for UAT.**

---

## 5. Copyright / Content Safety

**Policy (recommended `copyright_status` values):**
- `public_domain` — original work in the public domain; source text from Project Gutenberg etc.
- `licensed` — used under an explicit publisher/author license.
- `adapted_original` — Onlenco-written simplified text *inspired by* a theme, no copying.
- `school_excerpt_with_permission` — short excerpt used with documented written permission.

**Per the requested titles** (original-work status; *not* the school graded-reader editions):

| Title | Original work | Likely status |
|-------|---------------|---------------|
| Treasure Island (Stevenson, 1883) | PD | `public_domain` |
| Jane Eyre (C. Brontë, 1847) | PD | `public_domain` |
| Oliver Twist (Dickens, 1838) | PD | `public_domain` |
| A Tale of Two Cities (Dickens, 1859) | PD | `public_domain` |
| Our Mutual Friend (Dickens, 1865) | PD | `public_domain` |
| The Black Tulip (Dumas, 1850) | PD | `public_domain` |
| The Prisoner of Zenda (A. Hope, 1894) | PD | `public_domain` |
| Things Fall Apart (Achebe, 1958) | © | `licensed` (permission needed) |
| The Lost Ship / The Lucky Number / Anna and the Fighter | graded readers | `licensed` (publisher; permission needed) |

> **Critical nuance:** the Sudanese-curriculum versions are usually **abridged/simplified graded-reader editions** under *publisher* copyright **even when the source novel is public domain**. So: use the **public-domain source text** (Gutenberg) for PD titles, and write **`adapted_original`** short demos for the rest — **never copy the school/publisher abridged edition**.

**For the first UAT:** ship **one `adapted_original` short demo** (Onlenco-written, copyright-clean) plus optionally one `public_domain` excerpt. Represent provenance in DB with: `copyright_status`, `source` (e.g. "Project Gutenberg #120"), `source_url`, `license_notes`, `is_copyright_cleared` (bool gate before publish).

---

## 6. Proposed Novel Reader Architecture (design only — NOT implemented)

Reuse `Book`/`Chapter` as **Novel/Part**; add thin segment-level models. Indicative shape:

```
Book (= Novel)         + copyright_status, source, source_url, license_notes, is_copyright_cleared
Chapter (= NovelPart)  + arabic_summary (short Arabic explanation per part)
NovelSegment           (NEW) part FK, order, text_en, text_ar (translation toggle),
                       est_seconds; the unit that carries one illustration
NovelIllustration      (NEW) segment FK + GeneratedMediaReviewMixin (reuse lifecycle)
VocabularyExtract      (EXISTS) — render interactively; optionally add segment FK + char offsets
NovelPartQuiz          → REUSE LessonQuestion + ChallengeSession (no new grading)
StudentNovelProgress   → REUSE/extend LibraryProgress
StudentVocabularyProgress → REUSE learning_core SkillMastery (category="vocabulary")
LibraryAudioSession    (EXISTS) — already meters audio per part
```

**Do NOT build** `NovelParagraph`/`NovelSentence`/`NovelQuiz`/`NovelQuizQuestion`/`StudentNovelQuizAttempt` as new tables — they duplicate `NovelSegment` + the existing `LessonQuestion`/`ChallengeSession`/`ChallengeAnswer` stack.

---

## 7. Proposed MVP Scope

**MVP (necessary):**
- Additive copyright/provenance fields on `Book` + `is_copyright_cleared` publish gate.
- `NovelSegment` (text_en, text_ar, order, est_seconds) + per-segment `NovelIllustration` (mixin).
- Reader UI: segmented scroll, **translation toggle**, **interactive vocabulary** (tap word → Arabic meaning from `VocabularyExtract`), **voice picker + Natural Reader** (already exists), per-part **Arabic summary**.
- One copyright-safe demo novel (`adapted_original`).
- Library nav entry.

**Later:**
- Duolingo-style part quizzes wired to `ChallengeSession` (XP/streak/hearts).
- Daily-Quiz vocabulary-review integration.
- Pre-rendered reviewable audio (mixin) + novel manifest.
- Full Sudan catalog with cleared content.

---

## 8. UX / Mobile Navigation Findings

1. **No "Library / المكتبة" link in the main app header** ([templates/_app_header.html](templates/_app_header.html)). Library is reachable only from a dashboard card and the direct URL. **First fix.**
2. Navigation between Profile / Courses / AI Tutor / Library is **dashboard-card-based**, not a persistent nav — acceptable but not ideal for a "primary feature."
3. **Mobile-friendly:** Tailwind responsive grids + viewport meta throughout; library list/detail use breakpoints. `chapter_listen.html` uses an inline `max-width` (minor cleanup).
4. **WebView/APK-ready:** server-rendered, cookie-based language (no URL locale prefix), standard `<audio>`/fetch — fine for a WebView shell. Watch: TTS chunk fetch + base64 audio playback must be tested under WebView autoplay policies.
5. **RTL/Arabic:** full support — `base.html` sets `dir="{{ dir }}"`, computed in [core/context_processors.py](core/context_processors.py).
6. **First UX fixes before the reader:** add a persistent Library nav item; surface vocabulary interactivity; standardize the reader container (remove inline max-width); confirm WebView audio autoplay.

---

## 9. Duolingo-style Learning Design (reuse map)

Apply the pattern without copying Duolingo's design, by **reusing what exists**:

| Duolingo element | Reuse | Location |
|------------------|-------|----------|
| Short parts | `Chapter` + `NovelSegment` (new) | library |
| Image choice / listen-and-choose / order sentence / fill blank / match | `QUESTION_TYPE_CHOICES` (`image_choice`, `listen_and_choose`, `word_bank_sentence`, `fill_blank_card`, `match_pairs`) | [courses/models.py](courses/models.py) + `question_type_registry` |
| Instant feedback / grading | `challenge_grading.grade()` dispatcher | [courses/services/challenge_grading.py](courses/services/challenge_grading.py) |
| XP | `UserXP` / `XPTransaction` / `award_xp()` | [motivation/services/xp_service.py](motivation/services/xp_service.py) |
| Streak | `StudentStreak` / `StreakActivity` / `streak_v2` | motivation |
| Hearts | `ChallengeSession` (`hearts_total`/`hearts_remaining`) | courses |
| Mistake review (SRS) | `StudentMistake.next_review_at` | learning_core |
| Vocabulary mastery | `SkillMastery` (category=`vocabulary`) | learning_core |
| Unlock next part | `LibraryProgress.completed` gate | library |
| Daily review of novel words | `DailyLearningItem` (`item_type=vocabulary/review`) | daily_learning |

**Net:** the part-quiz feature is a *wiring* task (attach `LessonQuestion`s to a part, run a `ChallengeSession`, award XP/streak) — no new grading or gamification engine.

---

## 10. Sudanese School Novels Roadmap

- **19.0A — Audit** (this document). ✅
- **19.0B — Schema MVP + Admin:** additive copyright fields on `Book`, `NovelSegment`, `NovelIllustration` (mixin), per-part `arabic_summary`; admin screens; migrations. No reader UI yet.
- **19.0C — Reader UI + one safe demo novel:** segmented reader, voice picker (existing Natural Reader), one `adapted_original` demo; Library nav entry.
- **19.0D — Vocabulary highlights + Arabic explanation:** interactive tap-word (from `VocabularyExtract`), translation toggle, per-part Arabic summary.
- **19.0E — AI voice reading + voice selection + library-minute tracking:** wire the existing `library_audio_service` per part (already meters minutes); confirm caps.
- **19.0F — Duolingo-style part quizzes:** attach `LessonQuestion`s, run `ChallengeSession`, award XP/streak/hearts.
- **19.0G — Daily-Quiz vocabulary-review integration:** feed novel vocabulary into `DailyLearningItem` review.
- **19.0H — Sudan school catalog with a copyright-safe content process:** provenance gate (`is_copyright_cleared`), PD-source ingestion + `adapted_original` authoring workflow; obtain licenses for `licensed` titles.

---

## 11. Risks and Blockers

- **Copyright (highest):** the school graded-reader editions are publisher-copyrighted even for PD source novels. Mitigation: PD-source for PD titles, `adapted_original` for the rest, `is_copyright_cleared` publish gate, never import the abridged school edition.
- **Segmentation quality:** auto-splitting `Chapter.body` into pedagogically sound segments + matching illustrations needs review (reuse the media approval queue).
- **WebView audio:** autoplay/codec behavior for chunked base64 TTS must be validated on Android WebView.
- **Scope creep:** resist building the redundant `NovelParagraph/Sentence/Quiz*` tables — reuse `NovelSegment` + `LessonQuestion`/`ChallengeSession`.
- **Translation accuracy:** Arabic translations/summaries need human review before publish (no auto-publish of MT).

No production blockers introduced here (audit only). Payment/subscription remains HOLD for production per 18.5B.

---

## 12. Recommended Next Prompt

**Prompt 19.0B — Interactive Novel Reader MVP Schema and Admin** — because the Library foundation, Natural Reader, minute metering, media lifecycle, and the full question/gamification stack already exist. 19.0B only needs additive schema (copyright fields + `NovelSegment` + `NovelIllustration` + per-part Arabic summary) and admin, with no rebuild of foundations.

---

> **19.0A audited the Library and Sudanese school novels architecture without adding copyrighted content or changing product behavior.**
