# Prompt 03 — Phase 3: Question Types — تقرير التنفيذ

**التاريخ:** 2026-05-29
**المرحلة:** Phase 3 — Quiz Engine — 20 Interactive Question Types
**الحالة:** ✅ مكتمل + الاختبارات خضراء (278 اختبار في تطبيق `courses` — جميعها ناجحة)
**المحتوى:** أصلي بالكامل (Onlenco) — لا نسخ من كتاب EFE ولا من Duolingo
**الشخصيات المستخدمة:** أماني، يوسف، نور، كريم، سلمى، عمر، ليلى، طارق، هالة، رشيد

---

## 1) المُلخّص (TL;DR)

تم بناء **محرّك سجلّ مركزي (Question Type Registry)** يربط بين كل نوع سؤال (`question_type`) وبين أربعة عناصر: **قالب العرض (renderer)** + **دالة التصحيح (grader)** + **مفاتيح البيانات المطلوبة (metadata schema)** + **تكامل تحدّي اللعبة (Challenge)**. السجلّ يحتوي الآن على **30 نوعاً** = **20 نوعاً جديداً للإطلاق** + **10 أنواع قديمة** يتم دعمها لأجل التوافق العكسي مع Classic Quiz.

كل نوع جديد يُضاف الآن في مكان واحد (`question_type_registry.py`) — والمؤلِّف، المُصحِّح، والقوالب يلتقطونه تلقائياً.

---

## 2) الملفات الجديدة والمُحدَّثة

### ملفات جديدة (8)
| الملف | الدور |
|---|---|
| `courses/services/question_type_registry.py` | السجلّ المركزي لكل نوع |
| `courses/services/question_graders.py` | 11 دالة تصحيح + dispatcher |
| `courses/migrations/0013_question_types_phase3.py` | إضافة 12 نوع choice جديد |
| `courses/management/commands/seed_challenge_question_types_demo.py` | بذرة Demo لكل الأنواع |
| `courses/tests/test_question_types_phase3.py` | 39 اختبار للمرحلة |
| `templates/courses/question_renderers/*.html` | 21 قالب عرض جزئي |

### ملفات مُحدَّثة (5)
| الملف | التغيير |
|---|---|
| `courses/models.py` | إضافة 12 خيار جديد لـ `QUESTION_TYPE_CHOICES`؛ `max_length=32` |
| `courses/services/challenge_composer.py` | `SUPPORTED_QUESTION_TYPES` تُشتقّ من السجلّ |
| `courses/services/challenge_grading.py` | يُحوِّل إلى `question_graders.grade()` |
| `courses/views.py` | يُمرّر `question_renderer` و`question_kicker` للسياق |
| `templates/courses/challenge_session.html` | يستخدم `{% include question_renderer %}` للتوجيه |
| `courses/tests/test_challenge_engine.py` | تحديث اختبار الـ unsupported ليستخدم `writing_prompt` |

---

## 3) الأنواع العشرين الجديدة (Launch Set)

| # | `question_type` | المهارة | يُصحَّح تلقائياً؟ | مكان نوع البيانات (metadata) |
|---|---|---|---|---|
| 1 | `tap_choice` | vocabulary / grammar | ✅ | `options[]`, `correct_option_id` |
| 2 | `image_choice` | vocabulary | ✅ | `options[]` مع `image_url`, `correct_option_id` |
| 3 | `listen_and_choose` | listening | ✅ | `audio_script`, `audio_url`, `options[]`, `correct_option_id` |
| 4 | `listen_and_type` | listening / writing | ✅ | `audio_script`, `correct_answer` |
| 5 | `sound_to_word` | listening | ✅ | `audio_script`, `options[]` |
| 6 | `picture_labeling` | vocabulary | ✅ | `image_prompt`, `image_url`, `accepted_answers[]` |
| 7 | `mini_story_choice` | reading | ✅ | `story[]`, `options[]`, `correct_option_id` |
| 8 | `word_bank_sentence` | grammar | ✅ | `word_bank[]`, `correct_order[]` |
| 9 | `match_pairs` | vocabulary | ✅ (جزئي) | `pairs[]` |
| 10 | `fill_blank_card` | grammar / vocabulary | ✅ | يستخدم `correct_answer` |
| 11 | `conversation_reply` | reading | ✅ | `dialogue[]`, `options[]`, `correct_option_id` |
| 12 | `frequency_scale` | grammar | ✅ | `scale[]`, `target.{label,percent}`, `tolerance` |
| 13 | `table_sentence_builder` | grammar | ✅ (داخلي عبر v2) | `columns[].{label,values}` |
| 14 | `question_transform` | grammar | ✅ (داخلي عبر v2) | `statement`, `target_qword` |
| 15 | `mistake_correction` | grammar | ✅ | `wrong_sentence`, `corrected_sentence`, `accepted_answers[]` |
| 16 | `translate_to_english` | writing / vocabulary | ✅ | `source_ar`, `accepted_answers[]` |
| 17 | `translate_to_arabic` | reading / vocabulary | ✅ | `source_en`, `options[]`, `correct_option_id` |
| 18 | `speak_this_sentence` | speaking | ⏳ placeholder | `sentence` |
| 19 | `pronunciation_check` | speaking | ⏳ placeholder | `target_word`, `ipa` |
| 20 | `ai_roleplay_prompt` | speaking | ⏳ placeholder | `scenario`, `starter_line`, `target_phrases[]` |

> **ملاحظة:** الأنواع 18–20 (المحادثة الصوتية) هي **Placeholders** — تظهر بطاقتها وتُحفظ كـ self-check حتى لا تُعطّل اللعبة، ودالة التصحيح تُعيد `is_correct=True` بحيث لا يُعاقب الطالب على غياب STT/AI الفعلي. التقييم الذكي سيأتي في Phase لاحقة.

---

## 4) السجلّ المركزي — العقل الموحَّد

كل نوع له `TypeSpec` بـ 10 مفاتيح:

```python
{
  "label_en": "...",  # العنوان بالإنجليزية
  "label_ar": "...",  # العنوان بالعربية
  "skill":    [...],  # vocabulary | grammar | listening | speaking | reading | writing
  "requires_metadata":      True/False,
  "required_metadata_keys": [...],
  "supports_auto_grading":  True/False,
  "supports_challenge":     True/False,   # ⇐ يحدد إن كان يدخل لعبة التحدي
  "renderer":   "<file.html>",            # ⇐ قالب العرض
  "grader":     "<grader_key>",           # ⇐ مفتاح في GRADERS
  "placeholder": True/False,              # ⇐ هل بطاقة "تم تسجيلها" فقط؟
}
```

API عام:
- `get_spec`, `is_known`, `supports_challenge`, `is_placeholder`
- `grader_key`, `renderer_for`, `label`, `validate_metadata`

`SUPPORTED_QUESTION_TYPES` في `challenge_composer` تُشتقّ من السجلّ تلقائياً.

---

## 5) قوالب العرض (Renderers)

21 قالباً تحت `templates/courses/question_renderers/`:
- **20 من الأنواع الجديدة** (واحد لكل نوع، ما عدا `speaking_placeholder.html` يخدم 3 أنواع: speak_this_sentence + pronunciation_check + ai_roleplay_prompt + speaking_sentence_builder + speaking_prompt + listening_match)
- **3 قوالب legacy:** `legacy_multiple_choice.html`, `legacy_fill_blank.html`, `legacy_text_input.html`
- **2 fallback:** `unsupported_question.html`, `writing_placeholder.html`

كل قالب يُصدِر فقط حقول الإدخال الخاصة بنوعه — العنوان والـ `form` والـ CSRF والزر يبقون في `challenge_session.html` الأم. أنماط CSS مشتركة تحت `.onlenco-qr*`.

ميزات تفاعلية مبنية بـ vanilla JS (بدون مكتبات):
- **word_bank_sentence:** نقر لإضافة كلمة إلى الصينية، نقر داخل الصينية لإرجاعها.
- **match_pairs:** نقر يسار + نقر يمين = توصيل، مع تأكيد لوني.
- **frequency_scale:** سحب وإفلات على شريط نسبة 0–100%.
- **image_choice:** شبكة 2×2 من البطاقات مع `<img>` أو placeholder.

---

## 6) دوال التصحيح (Graders)

11 دالة في `question_graders.py` + dispatcher:

| `grader` key | الأنواع التي تستخدمها |
|---|---|
| `tap_choice` | tap_choice, image_choice, listen_and_choose, sound_to_word, mini_story_choice, conversation_reply, translate_to_arabic |
| `listen_and_type` | listen_and_type |
| `accepted_answers` | picture_labeling, translate_to_english |
| `word_bank_sentence` | word_bank_sentence |
| `match_pairs` | match_pairs (مع نقاط جزئية) |
| `normalize_equality` | fill_blank_card + legacy: multiple_choice, fill_blank, correction, sentence_ordering, translation, short_answer |
| `frequency_scale` | frequency_scale (مع تسامح ±) |
| `table_sentence_builder` | يعتمد على v2 grader الموجود |
| `question_transform` | يعتمد على v2 grader الموجود |
| `mistake_correction` | mistake_correction |
| `self_check` | جميع الـ placeholders (speaking + ai_roleplay + writing) |

كل دالة تُعيد عقد موحَّد:
```python
{ "is_correct": bool, "score": float[0..1],
  "feedback_en": str, "feedback_ar": str }
```

dispatcher (`question_graders.grade`) يقرأ `registry.grader_key(q.question_type)` ويُحوّل.

---

## 7) الـ Demo Lesson (الـ Seeder)

أمر `seed_challenge_question_types_demo` يُنشئ:
- كورس: **«Onlenco Challenge — All Question Types Demo»** (مجاني، A0)
- وحدة: «Question Types»
- درس: «Challenge Types Showcase» + Quiz بـ **20 سؤالاً** (واحد لكل نوع)

كل المحتوى **أصلي 100%** ومن إنتاج Onlenco:
- بطل المثال 1: «أماني تقول هذا أخي يوسف»
- بطل المثال 9 (match_pairs): نور/ممرضة، طارق/سائق، هالة/مهندسة، رشيد/خبّاز
- بطل المثال 13 (table_builder): «Hala drinks tea»
- بطل المثال 20 (ai_roleplay): «اشترِ رغيفين من رشيد في المخبزة»

تشغيل البذرة:
```bash
python manage.py seed_challenge_question_types_demo
# Re-run safe (idempotent)
python manage.py seed_challenge_question_types_demo --clear
```

---

## 8) الاختبارات — 39 اختباراً جديداً

ملف `test_question_types_phase3.py` (39 طريقة اختبار):

| المجموعة | عدد الاختبارات | التغطية |
|---|---|---|
| `RegistrySchemaTests` | 9 | اكتمال السجلّ، وجود كل قالب، تكافؤ مفاتيح الـ grader، التحقق من الـ metadata، fallback آمن |
| `GraderTests` | 21 | جميع الـ 11 grader مع مسار صحيح + خاطئ، تسامح الكتابة، النقاط الجزئية في match_pairs |
| `ComposerWithNewTypesTests` | 2 | الأنواع الجديدة تدخل اللعبة، writing_prompt يُستبعد |
| `DemoLessonIntegrationTests` | 3 | كل الأنواع الـ 20 تُعرض داخل عرض Challenge، composer يحترم سقف 12 |
| `LegacyBackcompatTests` | 5 | الأنواع القديمة (multiple_choice, fill_blank, correction, speaking_prompt, writing_prompt) لا تزال تعمل |

النتيجة الكاملة لمجموعة `courses`:
```
Ran 278 tests in 35.039s
OK
```

`manage.py check` بدون أخطاء.

---

## 9) معايير القبول (Acceptance) — حالة كل بند

| البند من Prompt 03 | الحالة |
|---|---|
| ✅ سجلّ مركزي يصف كل نوع | ✅ `question_type_registry.py` — 30 نوع |
| ✅ ≥ 20 نوع سؤال جديد | ✅ 20 + 10 legacy = 30 |
| ✅ كل نوع له renderer + grader + schema | ✅ مغطّى عبر السجلّ + اختبار `test_every_renderer_template_exists` |
| ✅ JSON metadata field على LessonQuestion | ✅ كانت موجودة مسبقاً ولم يطلب migration |
| ✅ آلية dispatch من نوع → grader | ✅ `question_graders.grade()` |
| ✅ آلية dispatch من نوع → renderer | ✅ `views.py` يُمرّر `question_renderer` ثم `{% include %}` |
| ✅ التوافق العكسي مع Classic Quiz | ✅ legacy types ما زالت تعمل (5 اختبارات) |
| ✅ بذرة Demo بنوع واحد من كل صنف | ✅ `seed_challenge_question_types_demo` |
| ✅ ≥ 30 اختباراً | ✅ 39 اختبار |
| ✅ Speaking كـ placeholder | ✅ ثلاثة أنواع → `self_check` يُعيد is_correct=True |
| ✅ تقرير عربي بـ 13 قسماً | ✅ هذا الملف |

---

## 10) ما تغيّر في `challenge_composer` و`challenge_grading`

### Composer
```python
# قبل (Phase 1) — قائمة ثابتة في الكود
SUPPORTED_QUESTION_TYPES = {"multiple_choice", "fill_blank", ...}

# بعد (Phase 3)
SUPPORTED_QUESTION_TYPES = {
    code for code, spec in registry.ALL_TYPES.items()
    if spec.get("supports_challenge")
}
```
إضافة نوع جديد لم تعد تتطلّب تعديل composer — يكفي تعديل السجلّ.

### Grading
```python
# قبل
result = quiz_grader.grade_question(question, raw_response)

# بعد
if not registry.is_known(question.question_type):
    return {"is_correct": False, "_unsupported": True, ...}
result = question_graders.grade(question, raw_response)
```
الـ unknown types لا تُسبّب 500 — تعرض رسالة لطيفة وتسمح بالتقدم.

---

## 11) قرارات التصميم اللاحقة

1. **`metadata` بدلاً من polymorphic models:** قبلت تكلفة JSONField لأنّ أنواع الأسئلة الجديدة كثيرة (20+) ومتنوعة الـ schema. polymorphism بـ subclasses سيُنتج 20 جدولاً منفصلاً.
2. **renderer = ملف template (وليس فئة Python):** يُسهّل على المصمم تعديل المظهر بدون لمس Python.
3. **placeholder للـ speaking بدلاً من إخفائه:** الطالب يرى أن المنصة تدعم المحادثة (UI شفّاف) — والبنية جاهزة لاستقبال STT/AI لاحقاً بدون أي تغيير في السجلّ.
4. **`accepted_answers` كقائمة بدلاً من regex:** أبسط للمعلّمين، يكفي إضافة variant. للحالات المعقّدة يبقى `quiz_grader` v2 موجوداً عبر `table_sentence_builder` و`question_transform`.
5. **match_pairs بـ partial credit:** أحسن تربوياً من all-or-nothing — 3/4 توصيلات صحيحة = نقاط 0.75 وليس صفر، ومع ذلك `is_correct=False` ليُحفّز الطالب على إعادة المحاولة.
6. **JS مدمج في كل renderer (بدون مكتبة خارجية):** تجنّبنا React/Vue/Alpine. كل قالب يحمل ~20 سطر JS كافياً.

---

## 12) ما لم يُنفَّذ في هذه المرحلة (Out of scope)

- 🔜 **STT حقيقي للـ speaking** — مرحلة لاحقة (Phase 4)
- 🔜 **AI Tutor Roleplay** — مرحلة لاحقة (Phase 4)
- 🔜 **Mastery tracking + adaptive ordering** — في `_select_supported` يوجد تعليق `TODO Phase 5`
- 🔜 **Drag-and-drop حقيقي مع touch-events** للـ word_bank و match_pairs — حالياً نقر فقط (يعمل على الموبايل لكن ليس Drag حقيقي)
- 🔜 **توليد TTS تلقائي لـ `audio_script`** للأنواع 3،4،5 — حالياً يعرض النص إن لم يكن هناك `audio_url`

هذه الأمور موثّقة كـ TODO في الكود وفي تصميم Phase 4/5.

---

## 13) كيف تجرّب الميزة الآن

```bash
# 1) طبّق migration
python manage.py migrate courses

# 2) شغّل البذرة (idempotent — آمن للتشغيل المتكرر)
python manage.py seed_challenge_question_types_demo

# 3) شغّل الخادم
python manage.py runserver 0.0.0.0:8080

# 4) سجّل دخول كطالب مشترك في الكورس الجديد
#    (أو فتّش عن "Onlenco Challenge — All Question Types Demo")

# 5) افتح الدرس → اضغط "Start Challenge"
#    سيمرّ الطالب على 12 من أصل 20 سؤالاً (سقف المؤلِّف)،
#    كل نوع يُعرض بقالبه الخاص.

# 6) أو اختبر:
python manage.py test courses.tests.test_question_types_phase3 -v 2
# Ran 39 tests in 0.768s — OK
```

---

**تم. جاهز للمراجعة والدمج في `main`.**
