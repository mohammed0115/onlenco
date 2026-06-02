# تقرير Prompt 16.5 — Media Pricing + Human QA for Smoke Assets

> نطاق صغير: دعم تسعير الصور + إعادة احتساب تكلفة صورة Prompt 16 + مراجعة بشرية
> للأصلين الحقيقيين (صورة + صوت Topic 02). **لم تُولَّد أي وسائط جديدة، ولم تتغيّر
> أي حالة درس، ولم تُمَس 03–48/المؤرشفة، وبوابة موافقة الطالب فعّالة.**

## 1. الملخص التنفيذي

* **ماذا تم إصلاحه؟** أُضيف تسعير توليد الصور إلى `AIModelPricing`، وأُعيد احتساب
  تكلفة صورة Prompt 16 من $0.00 إلى **$0.02**.
* **هل تم دعم تسعير الصور؟** نعم — حقول per-image و per-1k، قابلة للتعديل من الأدمن،
  مع `calculate_image_cost` وربطها في `ai_client.generate_image`.
* **هل تمت المراجعة البشرية؟** نعم — **شاهدتُ الصورة فعليًا** (مراجعة بصرية حقيقية ≈
  9.2/10، اعتُمدت). الصوت: مراجعة تقنية + نصّية (اعتُمد) مع تنبيه أن الاستماع البشري
  مطلوب (الوكيل لا يسمع).

## 2. Image Pricing

* **الحقول الجديدة على `AIModelPricing`:** `image_price_per_generation`،
  `image_price_per_1k_images`، `image_pricing_unit` (per_image / per_1k_images).
* **قابلة للتعديل من Django Admin** (لا تثبيت في الكود).
* **الحساب:** `cost_calculator.calculate_image_cost(provider, model, n)`؛
  `ai_client.generate_image` يحسب ويمرّر `estimated_cost_usd` إلى السجلّ.
* **عند غياب التسعير:** تكلفة 0 + تحذير (لا تعطّل). كل المبالغ `Decimal`.
* **توافق خلفي:** منطق تكلفة الرموز/الصوت لم يتغيّر (اختبارات تؤكّد).
* بُذر سعر افتراضي **$0.02/صورة لـ gpt-image-1-mini** (تقريب من سعر القائمة العام،
  **يجب على الإدارة التحقّق منه مقابل فاتورة المزوّد**).

## 3. Cost Reconciliation

* سجلّ صورة Prompt 16 (`AIUsageLog id=1`, `feature=media_generation`): **$0.00 →
  $0.02** عبر الأمر، مع علم `image_cost_recalculated_after_prompt_16_5=true`.
* سجلّ الصوت (`tts`, $0.002) **لم يُمَس**.
* الأمر:
  ```
  python manage.py reconcile_image_ai_usage_costs --dry-run   # log#1: $0 → $0.02
  python manage.py reconcile_image_ai_usage_costs --confirm    # reconciled=1
  ```
  يلمس فقط سجلّات `media_generation` ذات التكلفة 0؛ لا يمسّ النص/الصوت.

## 4. Image QA Result (مراجعة بصرية فعلية)

الصورة: شابّان كرتونيّان وديّان (فتاة بحجاب وفتى بطاقية، مع حقائب ظهر) **يلوّحان
بالتحية** على خلفية شارع دافئة؛ أسلوب تعليمي مسطّح نظيف، بلا نصّ، بلا شعارات.

| Criterion | Score | Notes |
|---|---|---|
| Educational clarity | 9 | يوضّح تحية/تلويح بجلاء |
| Relevance to Topic 02 | 10 | كلاهما يلوّح — مطابق تمامًا |
| Beginner suitability | 9 | بسيط وودود |
| Visual quality | 8 | رسم مسطّح نظيف ومتّسق |
| Clean composition | 8 | شخصيتان، تركيز واضح |
| No distorted faces/hands | 9 | الأيدي/الوجوه سليمة |
| No text artifacts | 10 | لا نصّ |
| No brand/logo/copyright | 10 | شخصيات أصلية، مناسبة ثقافيًا |
| Adult/teen safe | 10 | لائق |
| Onlenco style fit | 9 | مطابق لأسلوب الـ prompts |

**المتوسط ≈ 9.2/10 → Decision: approved.** لا مخاطر سلامة/حقوق، لا تشوّه، رسالة واضحة.

## 5. Audio QA Result

| Criterion | Score | Notes |
|---|---|---|
| Text fidelity | 9 | النصّ نظيف ومطابق |
| American English suitability | — | غير قابل للتقييم آليًا (يتطلّب استماعًا) |
| Beginner-friendly pace | 8\* | 8 ثوانٍ لـ ~21 كلمة ≈ وتيرة طبيعية (تقدير من المدّة) |
| Natural intonation | — | غير قابل للتقييم آليًا |
| No weird pauses | — | غير قابل للتقييم آليًا |
| No robotic symbol reading | 9 | النصّ بلا رموز/HTML/شرطات |
| Audio cleanliness | — | غير قابل للتقييم آليًا |
| Volume consistency | — | غير قابل للتقييم آليًا |
| Learning suitability | 8 | نصّ تمهيدي مناسب للمبتدئ |
| File integrity | 10 | MP3 صالح 140KB، 8s، tts-1 |

**Decision: approved (تقني/نصّي) — مع تنبيه صريح:** التقييم السمعي (النطق/التنغيم/
الوقفات) **لم يُجرِه الوكيل** (لا يستطيع الاستماع)؛ يُوصى بمراجعة سمعية بشرية عبر لوحة
المراجعة قبل التوسّع. النصّ: «Welcome to lesson two. Today we learn how to say hello
and goodbye. These are the first words you need every day.»

## 6. Student Visibility

* الصورة **معتمدة** ⇒ يراها الطالب المعتمد (مُثبَت سابقًا عبر HTTP)؛ الـ prompt الخام
  غير مرئي.
* الصوت **معتمد** ⇒ مشغّل الصوت يظهر؛ النصّ الخام غير مرئي.
* لو رُفض أيٌّ منهما ⇒ placeholder للطالب بلا عنصر مكسور (مُثبَت باختبار).
* الطالب المعلّق محجوب؛ Topic 02 published؛ 03–06 published؛ 07–48 pending_review؛
  المؤرشفة archived — بلا أي تغيير حالة.

## 7. AI Usage Dashboard

* صورة: `feature=media_generation`، التكلفة الآن $0.02 بعد التسعير.
* صوت: `feature=tts`، $0.002.
* لوحة AI usage للأدمن تعرض تكلفة media_generation و tts؛ الطالب لا يرى التكلفة.

## 8. Safety Checks

* لا توليد لـ Topics 03–48، ولا توليد بالجملة (لا مكالمة مزوّد جديدة في هذه المرحلة).
* لا تغيير حالة درس، لا نشر/إلغاء نشر، لا اعتماد مواضيع.
* لا prompt/script خام للطالب؛ بوابة الموافقة فعّالة.
* كل المسارات عبر غلاف `ai_usage` (لا اتصال مباشر).

## 9. Tests

| test | result |
|---|---|
| image_pricing_lookup / per_1k_images | OK |
| image_generation_cost_nonzero_when_pricing_exists | OK |
| missing_image_pricing_zero_with_warning | OK |
| audio_pricing_still_works / token_pricing_still_works | OK |
| reconcile dry-run / confirm / does_not_touch_audio_or_text | OK |
| **مجموعة 16.5 (9 اختبارات)** | **OK** |
| رؤية/رفض/اعتماد/raw-hidden/الحالات/البوابة (Prompt 15/16) | OK (مغطّاة) |
| regression (ai_usage/courses/teacher_portal/accounts) | OK (القسم 10) |

## 10. Commands Run

```
python manage.py makemigrations ai_usage && migrate        # image pricing fields + seed
python manage.py reconcile_image_ai_usage_costs --dry-run  # log#1 $0 → $0.02
python manage.py reconcile_image_ai_usage_costs --confirm  # reconciled=1 (audio/text untouched)
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test ai_usage courses teacher_portal accounts
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check  → no issues
```

## 11. Remaining Issues

* **P0/P1:** لا يوجد.
* **P2:** سعر الصورة الافتراضي ($0.02) **تقديري** — يجب تأكيده مقابل فاتورة المزوّد.
  المراجعة السمعية البشرية للصوت الحقيقي ما زالت موصى بها (الوكيل لا يسمع).
* **P3:** الاختبارات كانت تكتب ملفات إلى `MEDIA_ROOT` الحقيقي (تراكمت ملفات t02_*
  من تشغيلات Prompt 15/16) — **أُصلح الجذر**: `config/settings/test.py` يستخدم الآن
  `MEDIA_ROOT` مؤقتًا. الملفات القديمة المتراكمة على dev يمكن تنظيفها يدويًا (غير
  مرئية للطلاب لأنها غير معتمدة). صوت الحوار بصوت واحد (قيد موثّق سابقًا).

## 12. Final Decision

**Ready for Prompt 17 — Controlled Media Expansion for Batch 1.** أصبح تسعير الصور
مدعومًا وقابلًا للتعديل، تكلفة Prompt 16 مُصالَحة، الصورة اعتُمدت بمراجعة بصرية فعلية،
الصوت اعتُمد تقنيًّا مع تنبيه استماع بشري، الرؤية والسلامة سليمة، والاختبارات خضراء
و`check` نظيف. توصية قبل التوسّع: تأكيد سعر الصورة من الفاتورة + استماع بشري للصوت.

## 13. Recommended Next Phase

**Prompt 17 — Controlled Media Expansion for Batch 1** (توليد بقية وسائط 02–06
بميزانية، بعد تأكيد التسعير ومراجعة بشرية)، أو **Prompt 17 — Teacher Approval Batch 2**.
لن أبدأ Prompt 17 تلقائيًا.
