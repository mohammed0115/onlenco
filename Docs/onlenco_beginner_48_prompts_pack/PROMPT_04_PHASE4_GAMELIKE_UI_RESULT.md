# تقرير Prompt 04 — Game-like UI Polish

**التاريخ:** 2026-05-29
**المرحلة:** Phase 4 — تحسين تجربة الـ Challenge UI لتصبح Game-like
**الحالة:** ✅ مكتمل + اختبارات خضراء (312 اختبار في `courses` — كلها ناجحة)
**القيود المُحترَمة:** لا نسخ من Duolingo (لا شعار، لا بومة، لا ألوان مطابقة، لا assets)
**الشخصيات:** أماني، يوسف، نور، كريم، سلمى، عمر، ليلى، طارق، هالة، رشيد

---

## 1) المُلخّص التنفيذي

### قبل Prompt 04
- نظام Game Challenge يعمل وظيفياً (من Prompt 02).
- 20 نوع سؤال تفاعلي مع registry + graders + renderers (من Prompt 03).
- لكن التصميم البصري كان **عاديّاً وتقنيّاً**:
  - الـ HTML طويل ومُكرَّر داخل ملف واحد.
  - الـ feedback ثابت بدون animations.
  - لا توجد رسالة "Audio coming soon" مرتّبة عند غياب الصوت.
  - launcher واحد لا يُفرّق بين Start / Resume / Practice Again.
  - summary بدون شارة Perfect.
  - accessibility محدودة.

### بعد Prompt 04
- ✅ تجربة **Game-like** — animations، شارات، sticky check button، sound-hook placeholders.
- ✅ **Mobile-first** كامل — تصميم متجاوب على كل الأنواع.
- ✅ **8 partials مشتركة** تحت `templates/courses/challenge/components/`.
- ✅ **5 fallbacks جميلة** للصوت/الصورة/الـ metadata الناقصة — لا تُعطي 500.
- ✅ **Smart launcher** — Start / Resume / Practice Again تلقائياً.
- ✅ **Summary مُحسَّن** — Perfect badge متحرّك + Review Mistakes placeholder + Time spent.
- ✅ **Accessibility** — `role="status"`, `aria-live="polite"`, `aria-label`s، focus rings، keyboard 1–9.
- ✅ Classic Quiz لم يُكسَر.
- ✅ كل الـ 20 renderers تعمل + 6 fallback tests.
- ✅ 34 اختبار UI جديد (المجموع 312).

### النتيجة:
الواجهة أصبحت **مناسبة للمبتدئ خلال ثانيتين** — هويّة Onlenco واضحة، بدون نسخ من أي تطبيق آخر.

---

## 2) الملفات المعدلة أو المُنشأة

### ملفات جديدة (10)

| الملف | الدور |
|---|---|
| `templates/courses/challenge/components/challenge_header.html` | Header: Exit + Progress + Hearts + XP |
| `templates/courses/challenge/components/progress_bar.html` | Progress bar مع aria-valuenow |
| `templates/courses/challenge/components/hearts.html` | 5 قلوب + aria-label |
| `templates/courses/challenge/components/xp_badge.html` | XP badge مع البرق ⚡ |
| `templates/courses/challenge/components/feedback_card.html` | بطاقة feedback مع cycle عبارات مديح |
| `templates/courses/challenge/components/check_button.html` | زر Check ثابت أسفل الشاشة |
| `templates/courses/challenge/components/audio_button.html` | مشغّل صوت + "Audio coming soon" |
| `templates/courses/challenge/components/image_placeholder.html` | إطار صورة + "Image coming soon" |
| `templates/courses/challenge/components/empty_state.html` | بطاقة "غير جاهزة بعد" — تمنع 500 |
| `templates/courses/challenge/components/sfx_hooks.html` | hooks SFX (disabled by default) |
| `courses/tests/test_ui_polish_phase4.py` | 34 اختبار UI |
| `Docs/.../PROMPT_04_PHASE4_GAMELIKE_UI_RESULT.md` | هذا التقرير |

### ملفات مُحدَّثة (11)

| الملف | التعديل | السبب |
|---|---|---|
| `templates/courses/challenge_session.html` | إعادة هيكلة كاملة لاستخدام components | نظافة الكود، تكرار أقل |
| `templates/courses/challenge_summary.html` | Perfect badge متحرّك + 6 stats tiles + Review Mistakes placeholder + Time spent + Retry/Practice Again | Summary أصبح مكافأة بصرية |
| `templates/courses/lesson_detail.html` | Launcher يبدّل بين Start / Resume / Practice Again تلقائياً | الطالب يعرف فوراً ماذا يفعل |
| `templates/courses/question_renderers/listen_and_choose.html` | يستخدم `audio_button` المشترك | fallback أنيق عند غياب الصوت |
| `templates/courses/question_renderers/listen_and_type.html` | يستخدم `audio_button` + hint جديد | "Listen and type what you hear." |
| `templates/courses/question_renderers/sound_to_word.html` | يستخدم `audio_button` + empty_state | fallback عند غياب options |
| `templates/courses/question_renderers/picture_labeling.html` | يستخدم `image_placeholder` | "Image coming soon" |
| `templates/courses/question_renderers/image_choice.html` | empty_state عند غياب options | لا 500 |
| `templates/courses/question_renderers/word_bank_sentence.html` | زر Reset + UI نظيف | إعادة المحاولة سهلة |
| `templates/courses/question_renderers/speaking_placeholder.html` | شارة "AI speaking feedback coming soon" | شفافية مع المتعلم |
| `courses/views.py` | تمرير `active_challenge` + `last_challenge` + `time_spent_seconds` + `is_perfect` للسياق | الـ context يخدم القوالب الجديدة |

---

## 3) مكونات الواجهة

### Challenge header (`challenge_header.html`)
3-grid أفقي: `[Exit] [Progress bar مع fill متدرّج] [Hearts + XP badge]`. كل عنصر فرعي يحمل aria-label واضحاً.

### Progress bar (`progress_bar.html`)
- ارتفاع 12px مع `inset shadow` ناعم.
- التعبئة gradient أزرق `#2563EB → #60A5FA` مع `transition: width .35s cubic-bezier(.2,.8,.2,1)`.
- aria-valuenow + aria-valuemax + role="progressbar".

### Hearts (`hearts.html`)
- 5 قلوب `♥` متّحدة لونياً.
- المفقود يتحوّل إلى رمادي ويتقلّص (`transform: scale(.85)`).
- aria-label يقول: "Hearts remaining 4/5".

### XP badge (`xp_badge.html`)
- pill برتقالي مع `⚡` وعدّاد.
- عند الإجابة الصحيحة، الـ feedback card تُنشّط `onlencoXpPop` animation.

### Question card
- Border-radius 22px.
- Shadow `0 10px 24px rgba(15,23,42,0.05)`.
- Kicker بالخط الصغير "PICK THE RIGHT ANSWER".
- Question text بحجم `clamp(1.2rem, 2.5vw, 1.6rem)` وbold 800.

### Feedback card (`feedback_card.html`)
**صحيحة:**
- خلفية خضراء ناعمة (`linear-gradient(180deg, #DCFCE7, #FFF)`).
- شارة `check-circle-2` خضراء.
- مديح يدور: Great job! / Nice work! / Excellent! / Right on.
- `+10 XP` مع animation `onlencoXpPop`.

**خطأ:**
- خلفية حمراء ناعمة + animation `onlencoShake` (هزّة قصيرة).
- شارة `alert-circle` حمراء.
- رسالة لطيفة: "Good try. Let's learn it." (عربياً: محاولة جيدة. هيا نتعلمها.)
- "You lost a heart." إن سقط قلب.
- الإجابة الصحيحة معروضة في pill.

كلتاهما تحملان `role="status" aria-live="polite"` ليقرأهما screen reader.

### Summary screen
- خلفية بيضاء، padding 36px، shadow عميق.
- Emoji كبير 🏆/✨/💪/📊 حسب الحالة.
- شارة Perfect متحرّكة: `onlencoBadgePop` (.5s، scale 0.5 → 1.15 → 1).
- 6 tiles ملوّنة: XP / Accuracy / Correct / Hearts / Time / To review.
- 3 أزرار: Practice Again / Retry / Next + Review mistakes (soon) placeholder.

---

## 4) تحسينات Renderers

| نوع السؤال | التحسين | الحالة |
|---|---|---|
| tap_choice | شبكة `:has(input:checked)` تضيء بـ primary-soft | ✅ |
| image_choice | empty_state عند غياب options + placeholder 🖼 عند غياب image_url | ✅ |
| listen_and_choose | `audio_button` partial يعرض "Audio coming soon" + transcript | ✅ |
| listen_and_type | hint بالإنجليزية + العربية + input كبير | ✅ |
| sound_to_word | pills دائرية مع `:has(input:checked)` | ✅ |
| picture_labeling | hero image مع `image_placeholder` partial + input تحته | ✅ |
| mini_story_choice | story داخل card رمادي ناعم | ✅ |
| word_bank_sentence | **زر Reset + كلمات قابلة للنقر** | ✅ |
| match_pairs | عمودين + animation للنجاح/الخطأ + يصبح عمود واحد على الجوال | ✅ |
| fill_blank_card | الجملة مع الفراغ في sentence card | ✅ |
| conversation_reply | **chat bubbles أصلية بهوية Onlenco** (border-radius مختلف يميناً ويساراً) | ✅ |
| frequency_scale | range slider مع output animated 0–100% | ✅ |
| table_sentence_builder | grid مرن مع overflow-x للجوال | ✅ |
| question_transform | statement بالخط الـ Bold + hint بأداة الاستفهام | ✅ |
| mistake_correction | الجملة الخطأ في pill أحمر مع `<s>` + hint إن وُجد | ✅ |
| translate_to_english | source-card عربي + input إنجليزي | ✅ |
| translate_to_arabic | source-card إنجليزي + choices عربية مع dir="rtl" | ✅ |
| speak_this_sentence | **pill "AI speaking feedback coming soon"** | ✅ |
| pronunciation_check | speaking_placeholder المشترك | ✅ |
| ai_roleplay_prompt | speaking_placeholder مع scenario | ✅ |

كل renderer يستدعي `empty_state` عند `metadata` ناقصة بدلاً من 500.

---

## 5) Mobile-first

- `max-width: 720px` للـ main + padding صغير على الموبايل.
- زر Check sticky أسفل الشاشة (`position: sticky; bottom: 12px`).
- `@media (max-width: 480px)`:
  - Card padding ينقص.
  - `match-grid` يصبح عموداً واحداً.
  - `bubble max-width: 92%`.
- كل touch targets ≥ 40px height (إرشادات Apple/Google).
- لا hover-only — كل تفاعل يعمل بالنقرة.
- Image grid 2×2 على الموبايل، 4× على الديسكتوب.

---

## 6) RTL / LTR

- `dir="ltr"` ثابت على نص السؤال والخيارات الإنجليزية.
- `dir="rtl"` على helper text العربي عند `lang == "ar"`.
- `rtl-flip` على الأسهم — `<i data-lucide="arrow-right" class="rtl-flip">` ينقلب.
- Chat bubbles: `bubble--left` و`bubble--right` يحملان border-radius مختلف يحترم اتجاه الكتابة.
- الـ icon داخل padding مفتوح من الجهتين كي لا ينقلب.
- اختبار `test_arabic_helper_renders_rtl` يتحقّق من `dir="rtl"` لمستخدم عربي.
- اختبار `test_english_question_renders_ltr` يتحقّق من `dir="ltr"` لمستخدم إنجليزي.

---

## 7) Accessibility

| العنصر | aria/role | ملاحظة |
|---|---|---|
| Exit button | `aria-label="Exit Challenge"` | tooltip + focus ring أحمر |
| Progress bar | `role="progressbar"` + `aria-valuenow/min/max` | |
| Hearts | `role="img"` + `aria-label="Hearts remaining 4/5"` | كل قلب `aria-hidden="true"` |
| XP badge | `aria-label="XP earned 40"` | |
| Feedback card | `role="status" aria-live="polite"` | يُقرأ تلقائياً عند ظهوره |
| Inputs | `aria-label` مكتوب صراحة | |
| Sound for correct/wrong | `sr-only` نص يكتب "You earned 10 XP" | |
| `prefers-reduced-motion` | كل الـ animations تُلغى | احترام إعدادات النظام |
| Keyboard 1–9 | اختيار MCQ بسرعة من الكيبورد | |
| Focus rings | `box-shadow: 0 0 0 4px var(--ch-primary-soft)` | واضحة على كل التفاعلات |
| Disabled Check button | `disabled` + opacity .45 + `is-armed` class عند التفعّل | |

---

## 8) Animations

| الـ animation | المدّة | الاستخدام |
|---|---|---|
| `onlencoIn` (fade + translateY 14px) | 0.25s | ظهور أي card |
| `onlencoSlideUp` (24px) | 0.3s | بطاقة feedback |
| `onlencoShake` (±6px) | 0.35s | الخطأ + match_pairs خطأ |
| `onlencoXpPop` (scale 0.6 → 1.12 → 1) | 0.35s | عرض XP earned |
| `onlencoBadgePop` (scale + rotate) | 0.5s | Perfect badge |
| `progress__fill` width transition | 0.35s | تقدم progress bar |
| `hearts is-lost` color + scale | 0.25s | خسارة قلب |
| `match-card is-matched` background | 0.12s | نجاح match |

كلها خفيفة، CSS فقط، بدون JS libs، وتحترم `@media (prefers-reduced-motion: reduce)`.

---

## 9) Summary Screen

### عند `is_perfect`
- 🏆 + "Perfect Challenge!"
- شارة متحرّكة: "Perfect Bonus +10 XP"
- لا زر Review Mistakes (no mistakes!)
- زر "Retry Challenge" + "Next lesson" + "Back to lesson"

### عند `completed` (مع أخطاء)
- ✨ + "Great work!"
- 6 tiles بما فيها "To review: N"
- زر "Retry Challenge" + "Review mistakes (soon)" + "Next lesson"

### عند `failed`
- 💪 + "Good effort."
- "Practice again to strengthen this skill." — لا تحبيط.
- زر "Practice again" (أساسي) + "Review mistakes (soon)" + "Back to lesson"

---

## 10) Lesson Launcher

في `templates/courses/lesson_detail.html`، الواجهة تتفاعل تلقائياً مع حالة الـ session:

| الحالة | الزر | اللون | الرمز |
|---|---|---|---|
| لا session سابق | **Start Game Challenge** | أزرق + ⚡ | `data-action="start-challenge"` |
| session نشط (started/in_progress) | **Resume Challenge — 3/12** | أخضر + ▶️ | `data-action="resume-challenge"` |
| session مكتمل | **Practice Again** | كهرماني + 🔄 | `data-action="practice-challenge"` |

`Classic Quiz` يبقى ظاهراً دائماً جنباً إلى جنب — لم يُخفَ ولم يُكسَر.

---

## 11) الاختبارات

| Test class | عدد | النتيجة |
|---|---|---|
| ChallengeHeaderTests | 6 | ✅ |
| FeedbackCardTests | 2 | ✅ |
| SummaryScreenTests | 5 | ✅ |
| LessonDetailLauncherTests | 4 | ✅ |
| RendererFallbackTests | 5 | ✅ |
| RendererVisualHookTests | 6 (subTest × 20 = 25 internal) | ✅ |
| DirectionalityTests | 2 | ✅ |
| RegressionAfterPolishTests | 3 | ✅ |
| DemoSeedStillWorksTests | 1 | ✅ |
| **مجموع UI** | **34** | **✅** |

عناوين الاختبارات الرئيسية:
- `test_challenge_page_uses_game_layout` ✅
- `test_challenge_header_shows_progress_hearts_xp` ✅
- `test_progress_bar_visible` ✅
- `test_hearts_visible` ✅
- `test_xp_badge_visible` ✅
- `test_exit_button_has_aria_label` ✅
- `test_feedback_card_correct_visible` ✅
- `test_feedback_card_wrong_visible` ✅
- `test_summary_screen_shows_xp_accuracy_hearts` ✅
- `test_summary_perfect_run_shows_perfect_badge` ✅
- `test_summary_failed_state_shows_practice_again` ✅
- `test_summary_shows_mistakes_review_placeholder_when_wrong` ✅
- `test_summary_no_mistakes_review_when_perfect` ✅
- `test_lesson_detail_shows_start_challenge` ✅
- `test_lesson_detail_shows_classic_quiz` ✅
- `test_resume_challenge_button_visible_for_active_session` ✅
- `test_practice_again_visible_after_completion` ✅
- `test_image_choice_without_image_uses_placeholder` ✅
- `test_listen_and_choose_without_audio_uses_placeholder` ✅
- `test_picture_labeling_without_image_uses_placeholder` ✅
- `test_listen_and_choose_without_options_uses_empty_state` ✅
- `test_missing_metadata_does_not_500` ✅
- `test_all_question_renderers_have_game_card_style` ✅
- `test_word_bank_mobile_friendly_markup` ✅
- `test_match_pairs_mobile_friendly_markup` ✅
- `test_frequency_scale_visible` ✅
- `test_conversation_reply_uses_chat_bubbles` ✅
- `test_speaking_placeholder_clear` ✅
- `test_english_question_renders_ltr` ✅
- `test_arabic_helper_renders_rtl` ✅
- `test_challenge_flow_still_works_after_ui_polish` ✅
- `test_legacy_quiz_still_works` ✅
- `test_challenge_page_no_500_error` ✅
- `test_question_types_demo_still_runs` ✅

---

## 12) أوامر الاختبار ونتائجها

```bash
$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check
System check identified no issues (0 silenced).

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses
Ran 312 tests in 39.046s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test \
      courses.tests.test_ui_polish_phase4
Ran 34 tests in 2.313s
OK
```

لا يوجد frontend test runner منفصل في المشروع (Jest/Vitest/Playwright). كل اختبارات الواجهة هي Django request-based markup checks.

---

## 13) Manual QA — Onlenco Challenge — All Question Types Demo

شغّلت يدوياً:
```bash
python manage.py seed_challenge_question_types_demo
python manage.py runserver 0.0.0.0:8080
```

ثم استعرضت الكورس "Onlenco Challenge — All Question Types Demo" وفتحت الـ Challenge:

| السؤال | الانطباع |
|---|---|
| 1. tap_choice (أماني/يوسف) | ✅ خيارات كبيرة، فحص (`:has(input:checked)`) يضيء |
| 2. image_choice بدون image_url | ✅ يعرض 🖼 placeholder، الخيار يضيء |
| 3. listen_and_choose بدون audio_url | ✅ يعرض "Audio coming soon" + transcript بأناقة |
| 4. listen_and_type | ✅ hint واضح + input كبير |
| 5. sound_to_word | ✅ pills قابلة للضغط من الكيبورد بـ 1–3 |
| 6. picture_labeling | ✅ "Image coming soon" مع وصف الصورة |
| 7. mini_story_choice | ✅ القصة في card رمادي ناعم |
| 8. word_bank_sentence | ✅ النقر يحرّك الكلمات + Reset يعمل |
| 9. match_pairs | ✅ توصيل بالنقر + هزّة عند الخطأ |
| 10. fill_blank_card | ✅ الجملة في pill + input كبير |
| 11. conversation_reply | ✅ chat bubbles بهوية Onlenco (ليست Duolingo) |
| 12. frequency_scale | ✅ slider يعمل + output 65% |
| 13. table_sentence_builder | ✅ يعمل، الجدول قابل للسحب أفقياً على الجوال |
| 14. question_transform | ✅ الجملة + hint "Start with: What" |
| 15. mistake_correction | ✅ الجملة الخطأ مشطوبة بـ `<s>` + hint |
| 16. translate_to_english | ✅ بطاقة عربية → input إنجليزي |
| 17. translate_to_arabic | ✅ بطاقة إنجليزية → خيارات عربية بـ dir="rtl" |
| 18. speak_this_sentence | ✅ "AI speaking feedback coming soon" pill واضح |
| 19. pronunciation_check | ✅ placeholder شفّاف |
| 20. ai_roleplay_prompt | ✅ scenario معروض، self-check يعمل |
| Summary | ✅ Perfect badge متحرّك عند 0 أخطاء |
| Mobile (devtools 375px) | ✅ كل شيء يبدو نظيفاً |
| Mobile (devtools 320px) | ✅ يضيق قليلاً لكن مقبول |

**تقييم ذاتي:**
- ✅ هل الشاشة جميلة؟ — نعم، تشبه تطبيق تعلّم حديث بهوية Onlenco.
- ✅ هل كل سؤال واضح؟ — نعم، الـ kicker يوضّح نوع المطلوب فوراً.
- ✅ هل الطالب يعرف ماذا يفعل؟ — نعم، خلال ثانيتين.
- ✅ هل الموبايل مناسب؟ — نعم، اختبرت 320–768px.
- ✅ هل feedback ممتع؟ — نعم، عبارات مديح متنوّعة + animation.
- ✅ هل XP/hearts واضحان؟ — نعم، badge برتقالي + قلوب حمراء بارزة.
- ⚠️ بعض الأسئلة تتطلّب أصول حقيقية (صور + صوت) — هذا متوقّع وله placeholder أنيق.

---

## 14) المشاكل المتبقية

### P0 — حاسمة
لا يوجد.

### P1 — مهمّة لـ Phase 5
- 🔜 **توليد صور حقيقية** لـ image_choice و picture_labeling — حالياً placeholder.
- 🔜 **توليد TTS حقيقي** لـ listen_and_* — حالياً placeholder.
- 🔜 **Mistake review حقيقي** — placeholder button موجود.

### P2 — تحسينات Phase 5+
- 🔜 SFX حقيقية (correct/wrong/click) — hooks جاهزة في `sfx_hooks.html`.
- 🔜 STT للـ speak_* — placeholders جاهزة.
- 🔜 Streak/Daily goal — خارج نطاق Prompt 04 (Prompt 05).
- 🔜 Badges system — Prompt 05.
- 🔜 Drag & drop حقيقي للـ word_bank و match_pairs (الآن نقر).

### P3 — تحسينات صغيرة لاحقاً
- إضافة haptic feedback (`navigator.vibrate(10)`) عند الإجابة الصحيحة.
- Live mistake count عرضه في الـ header (الآن في summary فقط).
- Compact mode عند `prefers-color-scheme: dark` (ليس مطلوباً الآن).

---

## 15) القرار النهائي

✅ **Game-like UI جاهزة للانتقال إلى Prompt 05**.

كل acceptance criteria محقّق:
1. ✅ Challenge UI أصبحت game-like
2. ✅ السؤال يظهر في card جميلة
3. ✅ progress/hearts/XP واضحة
4. ✅ feedback card واضح وجميل
5. ✅ summary screen محسّنة
6. ✅ renderers الـ 20 لا تزال تعمل
7. ✅ placeholders للصوت والصورة جميلة
8. ✅ speaking/AI placeholders واضحة
9. ✅ mobile-first مقبول
10. ✅ RTL/LTR لا ينكسر
11. ✅ Classic Quiz لا يزال يعمل
12. ✅ Challenge Engine لا يزال يعمل
13. ✅ tests تمر (312 / 312)
14. ✅ لا توجد 500 errors

---

## 16) توصية المرحلة التالية

النتيجة الحالية تسمح بالانتقال إلى **Prompt 05 — XP / Hearts / Streak / Rewards System** عند الموافقة.

### ما سيُبنى في Phase 5 (مقترح):
- نظام Streak يومي مع حساب الأيام المتتالية.
- Daily Goal (مثلاً 20 XP/يوم).
- Badges (بدون نسخ Duolingo) — Onlenco-original مثل:
  - "First Five" — أول 5 تحديات مكتملة.
  - "Listening Star" — 10 تحديات استماع صحيحة.
  - "Perfect Day" — يوم كامل بدون خطأ.
- صفحة Rewards شخصية تعرض كل ما اكتسبه الطالب.
- إشعارات Onlenco-style (داخل التطبيق، ليست push) — تشجيعية، ليست عقابية.

**لن أنتقل تلقائياً.** أنتظر مراجعة هذا التقرير من المستخدم أوّلاً.

---

**انتهى التقرير. جاهز للدمج في `main` ومراجعة Phase 4.**
