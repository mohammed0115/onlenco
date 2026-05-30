# تقرير Prompt 09 — Quality Review / Super Lesson 01

**التاريخ:** 2026-05-30
**المرحلة:** Phase 9 — Quality Gate (مراجعة لا تعديل)
**الحالة:** ✅ مكتمل — تقرير قرار صريح بدون مجاملة.

---

## 1) الملخّص التنفيذي

### هل الدرس ممتاز؟
**ليس بعد.** الدرس **متين تقنياً** (804 اختبار يمر، 0 أخطاء، idempotent) و**جيد منهجياً** (11 قسم يغطّي كل أركان درس CEFR كلاسيكي)، لكن **فيه ثلاث ثغرات حقيقية** تمنعه من أن يكون "نموذجاً ذهبياً" قابلاً للتعميم على 47 درس آخر دون أن نُنتج 47 درساً بنفس الثغرات.

### هل مناسب للمبتدئ؟
نعم في معظمه. لكن **السؤال 7 (translate_to_english)** بصعوبة 0.5 يطلب من طالب A0 ترجمة جملة من العربية إلى الإنجليزية في **الدرس الأول** قبل أن يكتب جملة كاملة بنفسه — وهذا يعكس الترتيب الطبيعي للاكتساب.

### هل جميل وممتع؟
نعم — الـ Game UI من Phase 4 ممتازة، الـ animations لطيفة، الـ Summary يجمع 5 طبقات (rewards + skills + AI advice). **لا تبدو كنظام Django خام إطلاقاً.**

### هل يصلح كقالب؟
**نعم بشروط** — البنية القاعدية (11 قسم + 10 أسئلة + 4 image prompts + 6 audio scripts + 5 checklist) صالحة. لكن قبل تعميمها على 47 درس يجب إصلاح 3 ثغرات حتى لا تُنسخ الأخطاء.

---

## 2) نتائج الاختبارات التقنية

```bash
$ python manage.py seed_learning_skills
[OK] Learning skills seeded: 0 created, 51 updated, 51 total.

$ python manage.py seed_badge_definitions
[OK] Badge catalog seeded: 0 created, 10 updated, 10 total.

$ python manage.py seed_super_lesson_01
[=] Course updated: Onlenco Beginner English Foundation
[+] Lesson Updated: Introducing Yourself
    · 5 checklist items written
    · 4 image prompts written
    · 6 audio scripts written
[OK] Super Lesson 01 ready — 10 questions (0 new, 10 updated)

$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py test courses tutor motivation learning_core
Ran 804 tests in 122.209s
OK
```

كل شيء يمر. لا 500. لا warnings. ✅

---

## 3) تقييم صفحة الدرس

| المحور | الدرجة /10 | الملاحظة الصريحة |
|---|---|---|
| وضوح الهدف التعليمي | 9 | "Lesson Goal" واضح ومحدّد ب 5 outcomes — ممتاز |
| جمال التصميم | 8 | Phase 4 UI سليمة، sectioned HTML نظيف، لكن لا توجد صور فعلية |
| ترتيب الأقسام | 8 | Goal → New Language → Vocab → Key → How → Visual → Dialogue → Listening → Speaking → AI → Checklist — منطقي |
| سهولة القراءة | 9 | الجمل قصيرة، vocabulary 8 كلمات فقط |
| جودة المحتوى الإنجليزي | 9 | American English طبيعي، contractions موجودة (I'm)، Dialogue حقيقي |
| جودة الشرح العربي | 7 | content_ar = 1753 char vs EN = 2457 char — مختصر ومرتب لكن **يفتقد قسم Listening + Speaking + AI Drill**؛ هذه أقسام مهمّة لمتعلم عربي يبدأ من الصفر |
| Visual Guide readiness | 5 | **القسم نصي بحت** — لا يحوي `<img>` ولا placeholder بصري، فقط جملة "Picture two friendly beginners..." — هذا fail واضح لقسم اسمه "Visual Guide" |
| Listening/Speaking readiness | 5 | قسم Listening Practice يقول "Listen carefully" لكن **لا يحوي زر تشغيل صوت ولا حتى placeholder "Audio coming soon"**. الـ audio_script موجود في LessonAudioScript لكن غير مربوط بالـ rendering في الـ content_html |
| Checklist clarity | 10 | 5 جمل can-do بصيغة بسيطة + ترجمة عربية — مثالي |
| Mobile + RTL/LTR | 8 | `dir="rtl"` على كل قسم عربي، الـ Phase 4 mobile breakpoints سليمة |

**المجموع: 78 / 100**

### تعليقات صريحة
- **هل الصفحة تشبه درسًا حقيقيًا؟** نعم في الـ sectioned HTML، لا في غياب الـ visual + audio inline.
- **هل هي جميلة؟** الـ chrome (Phase 4) جميل. الـ content نفسه طبي/نصي.
- **هل هي خفيفة؟** نعم — 2457 char إنجليزي فقط، لا inline styles.
- **هل الطالب يعرف ماذا يفعل؟** نعم على مستوى الـ macro، لا على مستوى الـ micro (مثلاً: لا يعرف كيف يفتح روليبلاي الـ AI من البطاقة).
- **هل المحتوى العربي كثير أم مناسب؟** **مناسب لكنّه ناقص** — يفتقد 4 أقسام (Visual Guide / Listening / Speaking / AI Drill / Mini Dialogue) عند المقارنة بالـ EN.
- **هل الدرس طويل جدًا؟** لا — 8 دقائق + 10 أسئلة = جلسة 12-15 دقيقة، مثالي.

---

## 4) تقييم المحتوى التعليمي (كمدرّس CEFR)

| المحور | الدرجة |
|---|---|
| Beginner suitability | 21 / 25 |
| Language accuracy | 19 / 20 |
| Pedagogical flow | 18 / 20 |
| Arabic support | 11 / 15 |
| Practice readiness | 7 / 10 |
| Cultural neutrality | 10 / 10 |

**المجموع: 86 / 100**

### تعليقات
- **هل يبدأ من الصفر؟** نعم — Vocabulary 8 كلمات، Grammar pattern واحد (be + name).
- **هل الجمل قصيرة؟** نعم — أطول جملة "What is your name?" (4 كلمات).
- **هل المفردات مناسبة؟** نعم — الـ 8 كلمات أساسية.
- **هل "I am / I'm / My name is" مشروحة بوضوح؟** نعم — مع 3 أمثلة منفصلة + قسم How to Form.
- **هل "What is your name?" مناسب في هذا الموضع؟** نعم — هو السؤال الأساسي للتعريف.
- **هل Mini Dialogue طبيعي؟** نعم — 4 turns، Amani + Yusuf، لا تعقيد.
- **هل الشرح العربي يساعد أم يشتت؟** **يساعد لكنّه غير كامل** — ناقص في 4 أقسام.
- **هل American English واضح؟** نعم — "I'm" + "Nice to meet you" تركيب أمريكي طبيعي.
- **هل فيه أي تعقيد غير مناسب؟** نعم: **Q7 translate_to_english** — يطلب من A0 أن يُنتج "My name is Omar." من العربية، وهو إنتاج (productive) قبل الـ recognition. هذا انعكاس لـ Krashen's input-before-output rule.
- **هل الدرس يصلح كأول درس في منصة كاملة؟** **شبه كامل** — يحتاج إصلاحَيْن صغيرين.

---

## 5) تقييم Challenge Sequence

| # | نوع السؤال | الهدف | مناسب للمبتدئ؟ | ممتع؟ | واضح؟ | الملاحظة الصريحة |
|---|---|---|---|---|---|---|
| 1 | tap_choice | معنى Hello | ✅ | ✅ | ✅ | بداية مثالية: recognition + bilingual options |
| 2 | listen_and_choose | استخراج اسم Sara | ⚠️ | ⚠️ | ⚠️ | **بدون صوت فعلي** → الـ renderer يعرض "Audio coming soon" مع النص — الطالب يقرأ الـ transcript ثم يجيب → الـ skill listening **لا يتحقّق فعلياً** |
| 3 | word_bank_sentence | ترتيب "My name is Amani" | ✅ | ✅ | ✅ | ممتاز — drag-style productive لكن مع كلمات جاهزة |
| 4 | fill_blank_card | ملء "is" في "My name ___ Yusuf" | ✅ | ✅ | ✅ | جيد — productive محدود |
| 5 | match_pairs | EN ↔ AR (4 أزواج) | ✅ | ✅ | ✅ | جيد + bilingual reinforcement |
| 6 | conversation_reply | اختيار "Nice to meet you" | ✅ | ✅ | ✅ | جيد — chat bubble بصرية + 4 خيارات |
| 7 | **translate_to_english** | "اسمي عمر" → "My name is Omar." | ⚠️ | ⚠️ | ✅ | **صعب جداً للدرس الأول.** Productive كامل بدون support. متعلم A0 لم يكتب جملة كاملة بنفسه بعد |
| 8 | **listen_and_type** | "My name is Layla." | ⚠️⚠️ | ⚠️ | ❌ | **مشكلة فعلية**: بدون صوت + يجب كتابة جملة كاملة. الـ renderer يعرض الـ transcript حرفياً → السؤال يصبح "اكتب ما تراه" — هذا ليس تدريب استماع. **متعلم A0 لا يستطيع كتابة "My name is Layla" بدون نسخ** |
| 9 | speak_this_sentence | قراءة "Hello. My name is Amani." | ✅ | ✅ | ✅ | placeholder صادق + checkbox "تدرّبت" — مقبول |
| 10 | ai_roleplay_prompt | تقديم قصير مع AI | ⚠️ | ❌ | ❌ | **الـ endpoint جاهز لكن لا يوجد UI داخل البطاقة لتشغيله** — الطالب يرى speaking_placeholder نفسه + "Short AI roleplay — coming soon"، لا يلمس الـ roleplay فعلياً. الـ Phase 7 endpoint يبقى يتيماً |

### تقييم Challenge من 100

| المحور | الدرجة |
|---|---|
| تنوع السؤال | 14 / 15 — 10 أنواع مختلفة، ممتاز |
| سهولة الفهم | 9 / 15 — Q7/Q8/Q10 صعبة على A0 |
| التدرّج | 11 / 15 — صعوبة 0.1→0.6 لكن Q7 و Q8 يقلبان المنحنى |
| التفاعل | 13 / 15 — match_pairs + word_bank ممتازين |
| التصحيح | 9 / 10 — feedback ثنائي اللغة من Phase 3 |
| Speaking/Listening | 8 / 15 — Q2/Q8 بلا صوت، Q9/Q10 placeholders |
| المتعة | 11 / 15 — جيد لكن Q7-Q8 محبطان |

**المجموع: 75 / 100**

### تعليقات صريحة
- **هل 10 أسئلة عدد مناسب؟** نعم — لا أكثر، لا أقل.
- **هل الترتيب منطقي؟** شبه — Q1-Q6 رائعة، Q7-Q8 يجب أن يُؤجَّلا.
- **هل الأسئلة تبدأ سهلة ثم تزيد؟** نعم لكن القفزة عند Q7-Q8 حادة.
- **هل يوجد تنوع؟** ممتاز — 10 أنواع.
- **هل يوجد Listening كافٍ؟** **لا فعلياً** — السؤالان 2 و 8 يعتمدان على نص بدلاً من صوت.
- **هل يوجد Speaking كافٍ؟** Placeholder فقط — مقبول كمرحلة لكن ليس "ذهبياً".
- **هل translate_to_english صعب جداً لأول درس؟** **نعم.** يجب نقله للدرس 3-4 على الأقل.
- **هل listen_and_type صعب إذا لا يوجد صوت؟** **نعم بشدة** — يجب إخفاؤه أو تحويله إلى placeholder حتى يُولَّد الصوت.
- **هل ai_roleplay مناسب في الدرس الأول؟** الفكرة نعم — لكن **بدون UI ربط في البطاقة، الطالب لا يلمسه**. → P1.
- **هل الطالب سيشعر بالإنجاز أم بالضغط؟** Q1-Q6 إنجاز. Q7-Q8 ضغط. Q9-Q10 إحباط بسيط (placeholder).

---

## 6) تقييم Game-like Experience

| المحور | الدرجة |
|---|---|
| Fun factor | 17 / 20 — animations + sound hooks + XP popup |
| Clarity | 18 / 20 — kicker واضح، check button معطّل حتى الاختيار |
| Motivation | 18 / 20 — encouragement bilingual + XP visible |
| Feedback quality | 14 / 15 — green/red cards + rotating praise |
| Mobile experience | 13 / 15 — sticky check button + match pairs single-column at 480px |
| Not childish | 9 / 10 — ✨/⚡/♥ icons دون "Buddy the Owl" |

**المجموع: 89 / 100**

### تعليقات صريحة
- **هل الطالب سيستمتع؟** نعم — Phase 4 UI من الفئة العليا.
- **هل يشبه تجربة تطبيق حديث؟** نعم.
- **هل ما زال يبدو كـ Django system؟** **لا** — `data-onlenco-challenge` + JSON CSRF endpoints — modern.
- **هل فيه أي ازدحام؟** الـ Summary يحوي 6 أقسام (Stats + Encouragement + XP breakdown + Streak/Goal + Badges + Skills + Recommendation + AI advice + Actions) — **قد يكون مزدحماً على الموبايل**. يستحق مراجعة بصرية.
- **هل يحتاج تحسين بصري قبل التعميم؟** الـ chrome لا. الـ Summary نعم — مراجعة ratios.

---

## 7) تقييم AI Tutor Integration

| المحور | الدرجة |
|---|---|
| Safety | 24 / 25 — guardrails صلبة، لا raw prompt من العميل، sanitised context |
| Usefulness | 17 / 25 — الـ explain يعمل، لكن speaking/roleplay يبقيان placeholders بصرياً |
| Beginner suitability | 17 / 20 — الـ system prompt يفرض "3-4 sentences max" و "one mistake only" |
| Fallback quality | 19 / 20 — rule-based bilingual موجود لكل use case |
| UI clarity | 6 / 10 — **زر Explain موجود لكن Q10 roleplay UI ناقص** |

**المجموع: 83 / 100**

### تعليقات صريحة
- **هل AI اختياري؟** نعم — `CHALLENGE_AI_ENABLED + AI_API_KEY`.
- **هل لا يكسر الدرس عند تعطيله؟** نعم — اختبار `test_super_lesson_ai_disabled_still_completes` يثبت ذلك.
- **هل fallback واضح؟** نعم — bilingual + status="fallback".
- **هل roleplay قصير ومناسب؟** الـ endpoint نعم (5 turns cap). **لكن لا يُفعَّل من البطاقة** = ميزة non-discoverable.
- **هل الشرح قصير؟** نعم — max_tokens=220 + system prompt يفرض.
- **هل لا يقبل raw prompt؟** نعم — اختبار `test_no_raw_prompt_accepted_from_client` يثبت.
- **هل لا يخرج عن الدرس؟** نعم — context_builder يقيّد على lesson + question + skill.

---

## 8) تقييم Rewards / Mastery / Recommendations

| المحور | الدرجة |
|---|---|
| Rewards clarity | 19 / 20 |
| Mastery correctness | 24 / 25 |
| Recommendations | 18 / 20 |
| Summary quality | 18 / 20 — مزدحم بعض الشيء |
| No duplicate issues | 15 / 15 — XPTransaction + MasteryEvent UNIQUE — لا تكرار |

**المجموع: 94 / 100**

### تعليقات صريحة
- **هل XP لا يتكرر؟** ✅ test_super_lesson_awards_xp_once يثبت.
- **هل hearts مفهومة؟** ✅ visual heart + aria-label.
- **هل summary يظهر rewards بدون ازدحام؟** **مزدحم على الموبايل** — حوالي 8-9 أقسام عمودية → 1500-2000px scroll.
- **هل mastery يعمل فعلاً؟** ✅ — 4 skills تُحدَّث (greetings, to_be_names, listening_basic, speaking_intro).
- **هل mistakes تظهر عند الخطأ؟** ✅ — StudentMistake مع mistake_type + severity.
- **هل recommendation منطقي؟** ✅ — 5 فروع، اختبار يثبت كل واحد.
- **هل الطالب يعرف ماذا يفعل بعد الدرس؟** ✅ — "Recommended next" card.

---

## 9) تقييم Media Readiness

| المحور | الملاحظة |
|---|---|
| Image prompts واضحة؟ | ✅ — 4 prompts بـ ~120-180 word لكل واحد، صريحة في الـ style |
| لا تشبه DK أو Duolingo؟ | ✅ — كل prompt يقول صراحةً "no logos, no copyrighted characters, no real brand styling" |
| مناسبة لهوية Onlenco؟ | ✅ — "soft blue and white", "modern friendly cartoon", "clean vector style" |
| يمكن لمولد صور أن ينتج جميل منها؟ | نعم على الأرجح — الـ prompts تحدد scene + style + emotion + ما يجب تجنبه |
| Audio scripts طبيعية؟ | ✅ — 6 scripts بـ American English صريح |
| Scripts قصيرة؟ | ✅ — أطولها 4 جمل (dialogue) |
| لا HTML/underscores/رموز؟ | ✅ — plain text |

**الدرجة: 88 / 100**

### نقطة الخصم الوحيدة
- لا يوجد **مولّد** يربط الـ prompts بـ image/audio فعلية. هذا OK لـ Phase 9 (المرحلة لا تطلب توليد) لكن **Phase 10 لا يمكن أن يعمم 47 درساً بنفس "pending_generation" حال غياب المولّد** — هذا decoupling مهم.

---

## 10) مقارنة منهجية تعليمية

| عنصر المنهجية | موجود في Super Lesson 01؟ | الجودة /5 |
|---|---|---|
| Lesson Goal | ✅ | 5 |
| New Language | ✅ | 5 |
| Vocabulary | ✅ | 5 |
| Key Language | ✅ | 5 |
| How to Form | ✅ | 5 |
| Visual Guide | ⚠️ نص فقط بدون صورة | 2 |
| Practice | ✅ — 10 أسئلة | 4 |
| Listening | ⚠️ قسم موجود + script لكن بدون UI play | 3 |
| Speaking | ⚠️ قسم موجود + script لكن بدون STT | 3 |
| Checklist | ✅ — 5 can-do bilingual | 5 |
| Review readiness | ✅ — Phase 6 mistake scheduler جاهز | 4 |

**الـ Coverage: 11 / 11 عنصر موجود.**
**جودة العناصر: 46 / 55 = 84%.**

### تعليقات صريحة
- **هل الدرس يلتقط منهجية الكتب التعليمية الاحترافية؟** نعم — 11 عنصر = منهجية CEFR كلاسيكية.
- **هل يظل محتوى Onlenco أصلي؟** ✅ — اختبار `test_content_is_original_onlenco_no_efe_strings` يثبت.
- **هل هناك أي خطر حقوق نشر؟** **لا** — لا أسماء brand، لا copyrighted characters، لا direct lifts.
- **هل الدرس يصلح كقالب عام؟** نعم بنيوياً — لكن الـ "Visual Guide نص فقط" و "Listening section بدون play button" نمطان سيتعمّمان على 47 درس إذا لم يُصلَحا الآن.

---

## 11) جاهزية التعميم على 47 Topic

### الأسئلة الجوهرية

1. **هل هذا النمط يصلح لكل 48 Topic؟** نعم بنيوياً، لا في تفاصيله (Q7-Q8 typo، Q10 UI gap، Visual/Listening UI).
2. **هل 11 section كثيرة لكل درس؟** لا — 11 قسم منطقي لـ A0/A1. لمستويات أعلى قد تنمو.
3. **هل 10 أسئلة لكل Topic مناسبة؟** نعم — يطابق الـ MAX_CARDS=12 في challenge_composer.
4. **هل نفس قالب image/audio prompts يصلح؟** نعم — 4 image types + 6 audio types عقد متين.
5. **هل نفس challenge sequence يصلح أم يجب تخصيصه؟** **يجب تخصيصه** — Topic عن "Numbers" لا يحتاج conversation_reply، Topic عن "Family" يحتاج more vocabulary.
6. **هل يحتاج بعض الدروس أسئلة أكثر أو أقل؟** نعم — Phase 6 (Numbers) قد تحتاج 6 أسئلة، Phase 25 (Past Tense) قد تحتاج 12.
7. **هل يجب إنشاء Lesson Template Engine قبل التعميم؟** **نعم بشدة** — بدون template engine، سيكتب الـ AI 47 درساً بنفس الـ patterns المُكَرَّرة + نفس الـ bugs.
8. **هل نحتاج curriculum blueprint قبل التعميم؟** **نعم** — يجب وثيقة blueprint لكل 48 topic تحدّد: skills المستهدفة، new language، vocabulary count، challenge mix.
9. **هل نحتاج مراجعة بشرية بعد التوليد؟** **نعم لا تنازل** — AI يصنع draft، إنسان يصلحه قبل publish.
10. **هل يمكن تعميم seed تلقائي بدون جودة منخفضة؟** **لا الآن** — يجب إصلاح الـ 3 ثغرات أولاً.

### القرار الصريح

**نعمم بشرط إصلاحات قصيرة أولاً (B).**

---

## 12) Scoring Gate

| المحور | الدرجة /100 |
|---|---|
| Lesson Page | 78 |
| Educational Content | 86 |
| Challenge Sequence | 75 |
| Game-like Experience | 89 |
| AI Tutor | 83 |
| Rewards / Mastery | 94 |
| Media Readiness | 88 |
| Methodology Match | 84 |
| Generalization Readiness | 70 |

**المتوسط: (78+86+75+89+83+94+88+84+70) / 9 = 83 / 100**

### تطبيق الـ Scoring Gate من الـ spec

> 80-89: جيد جداً، لكن يجب إصلاح P1 قبل التعميم.

**النتيجة: جيد جداً، يجب إصلاح P1 قبل التعميم.**

### الشروط التي تمنع التعميم (من الـ spec)
| الشرط | الحالة |
|---|---|
| أي P0 | ❌ لا يوجد |
| أكثر من 3 مشاكل P1 | ⚠️ **يوجد 3 بالضبط** — حدّ السماح |
| عدم نجاح الاختبارات | ❌ 804 / 804 يمر |
| 500 errors | ❌ صفر |
| Classic Quiz مكسور | ❌ يعمل |
| AI disabled يكسر الدرس | ❌ لا يكسر |
| المحتوى صعب على A0/A1 | ⚠️ Q7-Q8 صعبان (P1) |
| الدرس طويل جداً أو مزدحم | ⚠️ Summary مزدحم على الموبايل (P2) |
| عدم وضوح الـ Challenge | ⚠️ Q10 roleplay UI غير مرئي (P1) |

**خلاصة:** 3 مشاكل P1 = الحدّ الأقصى المسموح. لا يجب إضافة أي ميزة قبل إصلاحها.

---

## 13) Manual QA Checklist

| الاختبار اليدوي | النتيجة | ملاحظة |
|---|---|---|
| فتح الدرس | ✅ | `/courses/17/lessons/129/` يعرض الـ stepper + content_html |
| قراءة Lesson Goal | ✅ | قسم clear مع 5 outcomes |
| فهم New Language | ✅ | 5 أنماط مع contractions |
| تشغيل Start Challenge | ✅ | composer يأخذ كل 10 أسئلة (MAX_CARDS=12) |
| سؤال tap_choice | ✅ | bilingual options، Hello → مرحباً |
| سؤال listen_and_choose | ⚠️ | يعرض "Audio coming soon" + transcript حرفياً → الـ skill listening لا يُتدرَّب |
| سؤال word_bank | ✅ | reset button + drag chips |
| سؤال fill_blank | ✅ | sentence_with_blank + word_choices hint |
| سؤال match_pairs | ✅ | 4 pairs + click pairing + shake animation |
| سؤال conversation_reply | ✅ | chat bubble + 4 options |
| سؤال translate_to_english | ⚠️ | **يطلب من A0 إنتاج جملة كاملة بنفسه** — صعب جداً |
| سؤال listen_and_type | ❌ | **بدون صوت + يجب كتابة جملة كاملة** — الطالب يرى الـ transcript ويحاول نسخه. ليس استماع |
| سؤال speaking | ✅ | placeholder صادق + checkbox |
| سؤال roleplay | ❌ | يعرض speaking_placeholder + "coming soon" — **لا UI لتشغيل الـ endpoint Phase 7** |
| خطأ متعمد | ✅ | feedback wrong card + correct_answer pill |
| Explain with AI Tutor/fallback | ✅ | بدون AI_API_KEY → fallback bilingual فوراً |
| إكمال الدرس | ✅ | status=completed، XP=120+ |
| Summary | ✅ | كل الـ 6 أقسام تظهر |
| Rewards | ✅ | XP breakdown + Perfect badge |
| Mastery | ✅ | 4 SkillMastery rows تُنشَأ |
| Classic Quiz | ✅ | `/quiz/` route يفتح صفحة كل الأسئلة |
| Mobile | ⚠️ | الـ Summary مزدحم — 8-9 أقسام عمودية |
| RTL/LTR | ✅ | dir="rtl" مع المستخدم العربي، dir="ltr" مع الإنجليزي |

**الـ checklist: 18 ✅ / 4 ⚠️ / 2 ❌**

---

## 14) المشاكل والتوصيات (P0/P1/P2/P3)

### P0 — تمنع التعميم
**لا يوجد.** ✅

### P1 — يجب إصلاحها قبل Prompt 10

| # | المشكلة | التأثير | الحل المقترح |
|---|---|---|---|
| P1-A | **Q10 ai_roleplay_prompt بلا UI لتشغيل الـ endpoint** | الـ Phase 7 endpoint يبقى يتيماً؛ الطالب لا يلمس AI Roleplay فعلياً. لو عُمِّمت 47 درس بنفس النمط = 47 endpoint يتيم | إضافة partial renderer جديد لـ ai_roleplay_prompt يحوي زر "Start AI Roleplay" يُطلق `POST /courses/.../roleplay/start/<q>/` ويعرض chat bubbles |
| P1-B | **Q7 translate_to_english + Q8 listen_and_type صعبان جداً على A0 في Topic 01** | متعلم مبتدئ سيشعر بالإحباط في الـ Drop-off Point. Q8 خصوصاً يصبح "اكتب ما تقرأ" بدون صوت | (أ) نقل Q7 إلى Topic 3-4 حيث الإنتاج بدأ. (ب) في Topic 01: استبدال Q8 بـ sound_to_word أو picture_labeling حتى يُولَّد الصوت |
| P1-C | **Visual Guide + Listening sections في content_html نص بحت** | لا صور، لا زر تشغيل صوت داخل الـ content. الـ stepper يعرض النص فقط رغم وجود LessonImagePrompt و LessonAudioScript | إضافة لتُحقن `<img>` و `<audio controls>` تلقائياً عند `is_generated=True`، و placeholder ("Image coming soon" / "Audio coming soon") عند `is_generated=False` |

**عدد P1: 3 — الحد الأقصى المسموح.**

### P2 — تحسينات مهمة لكن لا تمنع التعميم

| # | المشكلة | التأثير | الحل المقترح |
|---|---|---|---|
| P2-A | الـ content_ar ينقصه 4 أقسام (Visual Guide, Listening, Speaking, AI Drill) | متعلم عربي يقرأ نسخة AR لن يرى نظيراً لأقسام مهمة | إضافة 4 أقسام AR كاملة في `CONTENT_AR` |
| P2-B | Summary screen مزدحم على الموبايل (8-9 أقسام عمودية) | scroll طويل، إجهاد بصري | جمع XP breakdown + Streak + Daily-goal في tabs أو collapsible |
| P2-C | لا توجد content_html `<img>` بـ `lazy-load` على الـ visual-guide | غياب visual reinforcement | أبقَ التحسين مع P1-C |
| P2-D | speaking placeholder لا يُمنَح XP حقيقي من Phase 5 spec (5 XP) | الطالب لا يرى مكافأة على speak placeholder رغم وعد Phase 5 | تحقّق من `xp_for_answer` يطبّق spec |

### P3 — لاحقاً

| # | المشكلة | الحل |
|---|---|---|
| P3-A | لا backfill_question_skills تلقائي بعد seed | إضافة call داخل seed command |
| P3-B | لا audit JSON لما seed تركه | إخراج summary JSON |
| P3-C | LessonImagePrompt + LessonAudioScript لا تربط بـ SkillCode | لاحقاً |
| P3-D | لا preview للـ image_prompt في admin | لاحقاً |

---

## 15) القرار النهائي

### الخيارات
- A. Super Lesson 01 ممتاز وننتقل إلى Prompt 10.
- **B. Super Lesson 01 جيد جداً لكن يحتاج Prompt إصلاح قصير قبل Prompt 10.** ⬅
- C. Super Lesson 01 مناسب للديمو فقط ولا نعمم.
- D. Super Lesson 01 غير جاهز.

### الاختيار: **B**

### مبررات الاختيار B (ليس A)
- المتوسط 83/100 يقع في band الـ "جيد جداً، يجب إصلاح P1".
- يوجد **3 مشاكل P1** (الحد الأقصى المسموح) — تعميم 47 درساً سيُولِّد 141 مشكلة P1 إذا لم تُصلَح أولاً.
- 18/22 manual checks ✅ — جيد لكن ليس "ممتاز".
- الـ scaffolding يعمل، لكن "Listen" بدون صوت و "Roleplay" بدون UI يفشلان في الـ "promise" للطالب.

### مبررات عدم الاختيار C
- 804 اختبار يمر — البنية التحتية ممتازة.
- الـ Phases 2-7 تعمل end-to-end داخل هذا الدرس — هذا إنجاز كبير.
- الـ Phase 4 UI / Phase 5 rewards / Phase 6 mastery / Phase 7 AI integration كلها داخل درس واحد فعلياً.

### المطلوب في Prompt 09.5 — Fix Super Lesson 01 (قصير، 3 إصلاحات فقط)

**إصلاحات محتوى:**
- نقل `translate_to_english` من Topic 01 إلى موضع لاحق (أو استبداله بـ `picture_labeling` للأسماء).
- استبدال `listen_and_type` في Topic 01 بـ `sound_to_word` (4 خيارات اسم).
- توسعة `CONTENT_AR` لتشمل 4 أقسام إضافية.

**إصلاحات UI:**
- إضافة renderer جديد `ai_roleplay_card.html` يحوي زر "Start AI Roleplay" + chat container + JS يستدعي `/roleplay/start/` و `/roleplay/<id>/message/`.
- إضافة auto-injection لـ `<img>` و `<audio>` في step pages عند `is_generated=True`، + placeholder عند False.

**إصلاحات Challenge:**
- اختبار: re-sequence مع الـ skills updated.

**هل هي محتوى؟** نعم.
**هل هي UI؟** نعم.
**هل هي Challenge؟** نعم (re-sequence).
**هل هي AI؟** نعم (روليبلاي UI).
**هل هي media prompts؟** لا — الـ prompts ممتازة.

---

## 16) توصية المرحلة التالية

**Prompt 09.5 — Fix Super Lesson 01 before generalization.**

### Scope مقترح لـ Prompt 09.5
1. **استبدال السؤال 8 (listen_and_type)** في Topic 01 بـ `sound_to_word` حتى يُولَّد الصوت.
2. **نقل/استبدال السؤال 7 (translate_to_english)** إلى Topic 3-4 أو استبداله في Topic 01 بـ `picture_labeling`.
3. **بناء renderer جديد `ai_roleplay_card.html`** يربط Phase 7 endpoint بالـ Q10 card.
4. **بناء step_page renderer يحقن `<img>` و `<audio>` تلقائياً** من LessonImagePrompt و LessonAudioScript عند `is_generated=True`.
5. **توسعة `CONTENT_AR`** لتشمل 4 أقسام (Visual Guide / Listening / Speaking / AI Drill).
6. **اختبارات جديدة** للـ items 1-4 (لا تكسر الـ 804 الموجودة).
7. **بعد نجاح Prompt 09.5** → نعيد Quality Review مختصراً → نقرّر A.

### بعد Prompt 09.5
- لو الـ متوسط يصبح ≥90 → **Prompt 10**: تعميم 48 Topic مع template engine + curriculum blueprint + human-review gate.
- لو لا → جولة إصلاحات إضافية.

### شروط Prompt 10 (عند بلوغها)
- ✅ كل Topic له 8-12 أسئلة.
- ✅ كل سؤال له `metadata.skills`.
- ✅ كل Topic له 4 image prompts + 6 audio scripts (lookup فقط، لا توليد).
- ✅ كل Topic له content_html و content_ar متوازنان.
- ✅ كل Topic له 5+ checklist items.
- ✅ كل Topic يمر `test_super_lesson_xx_runs_start_to_summary`.
- ✅ مراجعة بشرية إلزامية لكل Topic قبل publish.
- ✅ لا توليد media files في Prompt 10.

---

**لن أنتقل إلى Prompt 10 بنفسي.**
**أنتظر قرار المستخدم: إما تنفيذ Prompt 09.5 أو تعديل المسار.**

---

## ملحق — الأرقام الفعلية المسجَّلة من الـ run

| القياس | القيمة |
|---|---|
| Tests passed | **804 / 804** |
| `manage.py check` | clean |
| Skills seeded | 51 / 51 (51 updated، 0 created — idempotent) |
| Badges seeded | 10 / 10 (10 updated، 0 created — idempotent) |
| Super Lesson seeded | 10 questions (0 created، 10 updated — idempotent) |
| content_html chars | 2457 |
| content_ar chars | 1753 (71% من EN — ناقص ~720 char) |
| Image prompts | 4 (cover/vocabulary/grammar/quiz) |
| Audio scripts | 6 (intro/vocab/examples/dialogue/listening/speaking) |
| Checklist items | 5 bilingual |
| Question types used | 10 (كل الـ Phase 3) |
| Avg question difficulty | 0.37 |
| Phase 7 AI endpoints | 4 (explain/roleplay-start/roleplay-message/end-advice) |
| Phase 7 endpoint مع UI داخل البطاقة | 1/4 فقط (explain فقط) |

**انتهى تقرير Phase 9 Quality Review.**
