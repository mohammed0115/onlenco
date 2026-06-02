# تقرير Prompt 16 — Live Media Smoke Test + Media QA for Batch 1

> اختبار دخان حيّ بحجم صغير جدًّا على **dev فقط**: توليد صورة حقيقية واحدة + ملف
> صوت حقيقي واحد لـ Topic 02، بتكلفة فعلية ≈ **$0.022** (أقل من سقف $0.50)، عبر غلاف
> `ai_usage` حصرًا، مع مراجعة قبل ظهورها للطالب. **بموافقة صريحة من المستخدم على
> الإنفاق.** لم تتغيّر أي حالة درس، ولم تُمَس 07–48/المؤرشفة/Topic 01.

## 1. الملخص التنفيذي

* **هل تم توليد وسائط حقيقية؟** نعم — مكالمتان حقيقيتان لـ OpenAI عبر الغلاف.
* **كم صورة وكم صوت؟** صورة واحدة (cover، PNG ‏1.5MB) + ملف صوت واحد (intro، MP3
  ‏140KB، 8 ثوانٍ).
* **هل بقيت التجربة محدودة وآمنة؟** نعم — عنصر واحد لكل نوع، سقف ميزانية محترم،
  إنفاق فعلي ≈ $0.022، dev فقط (development settings، DEBUG=True).
* **هل ظهرت الوسائط للطالب فقط بعد الموافقة؟** نعم — قبل الموافقة مخفية (placeholder)؛
  بعد الموافقة يراها الطالب المعتمد (مُثبَت عبر HTTP حقيقي على dev).

## 2. بيئة التنفيذ

* `DJANGO_SETTINGS_MODULE=config.settings.development` ، `DEBUG=True` (dev، ليست production).
* `AI_API_KEY` موجود (sk-… بطول 164)، `AI_API_BASE=https://api.openai.com/v1`.
* `ONLENCO_MEDIA_GENERATION_ENABLED=False` → استُخدم `--allow-dev-generation`.
* `AI_USAGE_TRACKING_ENABLED=True` ، `ONLENCO_STUDENT_APPROVAL_REQUIRED=True`.
* الميزانية: image cap $0.40، audio cap $0.30 (إجمالي مستهدف < $0.50).
* **تمت موافقة المستخدم الصريحة على الإنفاق قبل أي مكالمة حقيقية.**

## 3. Pre-flight Check

* `manage.py check` → نظيف.
* dry-run لـ Topic 02 image (cover, limit=1) → planned=1، 0 calls، 0 AIUsageLog.
* الحالات: Topic 01 published، 02–06 published، 07–48 pending_review، المؤرشفة archived.
* media pre-state: استُخدم `LessonImagePrompt(cover)` و`LessonAudioScript(intro)`؛ لا
  وسائط معتمدة سابقة لها (لم يُستبدل شيء).
* فحوص الأمان: الـ prompt/script آمنان (لا أسماء علامات whole-word، لا HTML/شرطة سفلية).
* approval gate مفعّل.

## 4. Live Generation Run

| Media type | Topic | Purpose | Result | AIUsageLog | Cost | Status |
|---|---|---|---|---|---|---|
| image | 02 | cover | generated (PNG 1.5MB) | id=1 `media_generation` role=admin success | $0.000000\* | needs_review |
| audio | 02 | intro | generated (MP3 140KB, 8s) | id=2 `tts` role=admin success | $0.002000 | needs_review |

الإجمالي الفعلي ≈ **$0.022** (image est $0.02 + audio $0.002). \*تكلفة الصورة سُجّلت 0
لأن تسعير الصورة لكل صورة غير مُمثَّل بعد في `AIModelPricing` (تحذير، لا تعطّل) — P2.

## 5. Media QA Review

| Item | QA score | Decision | Notes |
|---|---|---|---|
| cover image | تقني 9/10 (PNG صالح 1.5MB، prompt آمن وعلى الموضوع) | approve | تمّت الموافقة للـ pilot؛ **يُوصى بمراجعة بصرية بشرية** (الوكيل لا يرى البكسلات فعليًا). |
| intro audio | تقني 9/10 (MP3 صالح 8s، tts-1، مطابق لنص intro) | approve | تمّت الموافقة؛ **يُوصى بمراجعة سمعية بشرية**. |

ملاحظة صريحة: الـ QA هنا تقنيّ (سلامة الملف/التنسيق/الأمان/المطابقة)؛ التقييم البصري/
السمعي النهائي يتطلّب مُراجِعًا بشريًا عبر لوحة المراجعة.

## 6. Student Visibility Test (حقيقي على dev)

* **قبل الموافقة:** `is_student_visible=False` لكليهما (مخفي، placeholder).
* **بعد الموافقة:** `is_student_visible=True`؛ طالب معتمد فتح Topic 02 (HTTP 200)
  ورأى رابط الصورة الحقيقي في الصفحة. `get_media_for_student` يُرجع الملفين.
* **لا تسريب:** نصّ الـ prompt الخام غير موجود في صفحة الطالب.
* **rejected:** يبقى مخفيًا (مُثبَت باختبار).
* الطالب المعلّق محجوب، والمجهول لا يصل، و07–48 بلا وسائط مرئية.

## 7. AI Usage Verification

* الغلاف: كل التوليد عبر `ai_usage/services/ai_client.py` (generate_image / synthesize_speech).
* Log IDs: image=1 (`media_generation`)، audio=2 (`tts`)، كلاهما role=admin، status=success.
* التكلفة: audio $0.002 (من `AIModelPricing` tts-1)؛ image $0 + تحذير (تسعير غير مُمثَّل).
* لا اتصال مباشر بالمزوّد (الخدمة لا تستورد requests إطلاقًا — تستدعي الغلاف فقط).
* التكلفة مخفية عن الطالب (الـ API/الصفحات لا تعرضها).

## 8. Failure-path Verification

* **budget exceeded (حيّ، بلا إنفاق):** budget=$0.0001 → «budget reached»، generated=0،
  `AIUsageLog_created=0`. ✓
* **unsafe prompt (اختبار):** «Duolingo owl» → لا اتصال بالمزوّد، status=failed،
  detail=`unsafe_word`. ✓
* **provider failure (اختبار، مُحاكى):** استثناء المزوّد → status=failed +
  `AIUsageLog` فاشل، لا تعطّل للدُفعة. ✓
* **duplicate بلا --replace:** يُتخطّى (skipped). ✓

## 9. Cleanup / Rollback Verification

* `cleanup_generated_media_batch --topics=2 --dry-run` → affected=0، لا تغيير.
* `--only-status=approved` dry-run → «approved media untouched»، سجلّ AIUsageLog محفوظ.
* لم يُشغَّل أي cleanup فعلي (العنصران المعتمدان أُبقيا).

## 10. Automated Tests

| Test suite | Result |
|---|---|
| Prompt 16 smoke (limit selector, approved-visible, rejected-placeholder, review-notes, budget, 07–48 untouched) | 6 OK |
| Prompt 15 media suite | 33 OK |
| courses + teacher_portal + ai_usage + accounts | **818 OK** |
| `manage.py check` | نظيف |

## 11. Manual QA

* طالب معتمد: يرى الصورة الحقيقية بعد الموافقة؛ لا prompt خام (HTTP 200 مؤكَّد).
* قبل الموافقة: placeholder فقط.
* طالب معلّق: محجوب من dashboard/الدرس (gate).
* معلّم/أدمن: لوحة `/control/media-review/` تعرض العنصرين مع المعاينة والتكلفة وأزرار approve/reject.

## 12. Remaining Issues

* **P0/P1:** لا يوجد.
* **P2:** تسعير الصورة لكل صورة غير مُمثَّل في `AIModelPricing` (تُسجَّل $0 + تحذير) —
  يُنصح بإضافة صف تسعير قبل التوسّع لقياس التكلفة الحقيقية. المراجعة البصرية/السمعية
  البشرية للوسائط الحقيقية لم تُجرَ (الوكيل لا يرى/يسمع) — مطلوبة قبل التوسّع.
* **P3:** صوت الحوار بصوت واحد (قيد موثّق)؛ تقدير مدة TTS تقريبي. وجود وسائط قديمة على
  dev من مراحل سابقة (غير معتمدة ⇒ غير مرئية) — تنظيف اختياري.

## 13. Final Decision

**Live media smoke test successful.** تمّ توليد وسائط حقيقية (صورة + صوت) عبر الغلاف
بتكلفة ضئيلة ($0.022)، مع سجلّ AIUsageLog حقيقي، بوابة مراجعة، إخفاء عن الطلاب حتى
الموافقة، ظهور صحيح للطالب المعتمد بعد الموافقة (HTTP مؤكَّد)، ميزانية محترمة، ومسارات
فشل/cleanup آمنة — وكل الاختبارات خضراء و`check` نظيف.

## 14. Recommended Next Phase

* **Prompt 17 — Controlled Media Expansion for Batch 1** (توليد بقية وسائط 02–06
  بميزانية، بعد إضافة تسعير الصورة ومراجعة بشرية بصرية/سمعية)، أو
* **Prompt 17 — Teacher Approval Batch 2**.
> لن أبدأ Prompt 17 تلقائيًا — بانتظار مراجعتك. توصية: أضف صفّ تسعير per-image في
> `AIModelPricing` وأجرِ مراجعة بشرية للعنصرين الحقيقيين قبل التوسّع.

---

> **Update (Prompt 16.5):** image pricing support was added to `AIModelPricing`
> (per-image / per-1k), and the smoke image's AIUsageLog cost was reconciled
> $0.00 → **$0.02**. Human QA: the cover image was **visually reviewed and
> approved** (≈9.2/10, on-topic, no brand/distortion); the intro audio was
> approved on technical+script grounds with a human-listen caveat. See
> `docs/PROMPT_16_5_MEDIA_PRICING_AND_QA_REPORT.md`.
