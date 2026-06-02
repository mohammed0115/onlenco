# تقرير Prompt 12B — Human Review QA Pass for 47 Topics

> مرحلة مراجعة وتصنيف وتقارير فقط. **لم يُنشر أي Topic، ولم يتغيّر أي status، ولم
> تُولَّد أي وسائط.** Topic 01 (Gold Reference) لم يُمَس. التقييمات مبنية على
> بيانات حقيقية من `content_quality_checker` + قراءة فعلية للمحتوى.

## 1. الملخص التنفيذي

* **هل المحتوى جيد؟** نعم، عمومًا قويّ. الدروس مكتوبة كدروس حقيقية (Lesson Goal /
  New Language / Vocabulary / Key Language / Checklist، ثنائية اللغة، بشخصيات
  متكرّرة مثل Amani/Yusuf) وليست نصًا عامًّا من الذكاء الاصطناعي. متوسط الجودة **91.1/100**.
* **كم Topic جاهز؟** **39** بتصنيف `approved_ready` (96–100).
* **كم يحتاج تعديل بسيط؟** **8** (`needs_minor_changes`) — وهي T26–T33 فقط.
* **كم يحتاج تعديل كبير؟** **0**.
* **هل يوجد Topic مرفوض؟** **0** (`reject_regenerate`).
* **هل نبدأ الاعتماد أم نحتاج إصلاحات؟** السبب الوحيد لحجب الـ 8 هو **ذكر أسماء
  علامات تجارية ("DK/Duolingo") داخل عبارات النفي في image prompts** — وهو إصلاح
  لفظي بسيط في الـ prompts فقط (المحتوى التعليمي سليم). التوصية: **Prompt 12B.1 —
  Minor Content Fix Pass** لإصلاح الـ image prompts، ثم اعتماد الدفعة الأولى.

## 2. نتائج الاختبارات التقنية

أوامر التهيئة (على قاعدة بيانات التطوير):

```
python manage.py seed_learning_skills            → 51 skills
python manage.py seed_badge_definitions          → 10 badges
python manage.py seed_super_lesson_01            → Gold Reference (10 أسئلة) سليم
python manage.py seed_beginner_48_topics --confirm  → 47 topics pending_review
python manage.py check_generated_content_quality --course=onlenco-beginner --save
```

الاختبارات (إطار `manage.py test`، وليس pytest):

```
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test \
  courses teacher_portal tutor motivation learning_core ai_usage
→ Ran 1016 tests … OK  (exit 0)
python manage.py check → System check identified no issues (0 silenced)
```

| البند | النتيجة |
|---|---|
| إجمالي الاختبارات | **1016**، OK |
| manage.py check | نظيف (0 issues) |
| Topics pending_review | **47** |
| Topics فيها errors | **8** (T26–T33، جميعها `brand_risk`) |
| Topics فيها warnings | **7** (T2، T26، T37–T41 — `fallback_skill`) |
| أدنى score | **40** (T26) |
| أعلى score | **100** |
| متوسط score | **91.1** |
| Student visibility protection | محفوظة: الدروس pending تُرجع 404 للطالب (`published_lesson_queryset`) |
| AI usage tracking not bypassed | المراجعة لا تستدعي أي AI (الـ checker حتمي؛ AIUsageLog لم يزد) |

## 3. ملخص Quality Scores

| Metric | Value |
|---|---|
| Total reviewed topics | 47 |
| Highest score | 100 |
| Lowest score | 40 (T26) |
| Average score | 91.1 |
| Error flags (topics) | 8 (T26–T33) |
| Warning flags (topics) | 7 (T2, T26, T37–T41) |
| Passed (≥85, no errors) | 39 |

## 4. تصنيف Topics

| Classification | Count | Topic numbers |
|---|---|---|
| approved_ready | 39 | 02–25, 34–48 |
| needs_minor_changes | 8 | 26, 27, 28, 29, 30, 31, 32, 33 |
| needs_major_changes | 0 | — |
| reject_regenerate | 0 | — |

> ملاحظة منهجية مهمة (لا تعتمد على الـ score الآلي وحده): T26–T33 تحصل على
> 40–52 بسبب 4 أعلام `brand_risk` (×12 خصم) — لكن السبب الجذري **واحد ومتكرّر**:
> عبارة «No logos, no copyrighted characters, no DK or Duolingo styling» داخل
> الـ image prompts. الـ checker يرصد كلمة "Duolingo" حتى داخل النفي. المحتوى
> التعليمي والأسئلة والعربية سليمة. لذلك التصنيف البشري = **needs_minor_changes**
> (تعديل لفظي للـ prompts) وليس major/reject.

## 5. Review by Group

| Group | Topics | Avg | Strongest | Weakest | Findings | Decision |
|---|---|---|---|---|---|---|
| 1 | 02–06 | 99.2 | 03–06 (100) | T02 (96) | T02 فيه fallback_skill بسيط (greetings+general_beginner) | ready_for_teacher_approval |
| 2 | 07–12 | 100 | كلها | — | تسلسل ممتاز (this/that → these/those) | ready_for_teacher_approval |
| 3 | 13–18 | 100 | كلها | — | T18 يحوي translate_to_english عند A1 (ملاحظة صعوبة، غير حاجب) | ready_for_teacher_approval |
| 4 | 19–24 | 100 | كلها | — | translate_to_english في 24 (ملاحظة صعوبة) | ready_for_teacher_approval |
| 5 | 25–30 | 58.0 | T25 (100) | T26 (40) | T26–T30 محجوبة بـ brand_risk (image prompts) فقط | needs_minor_edit_pass (26–30)؛ 25 جاهز |
| 6 | 31–36 | 76.0 | 34–36 (100) | 31–33 (52) | T31–T33 brand_risk فقط | needs_minor_edit_pass (31–33)؛ 34–36 جاهز |
| 7 | 37–42 | 96.7 | T42 (100) | 37–41 (96) | fallback_skill في سؤال mistake_correction (لها skill حقيقي أيضًا) | ready_for_teacher_approval (تنظيف skill بسيط) |
| 8 | 43–48 | 100 | كلها | — | تسلسل قوي (can/can't، تكرار، مستقبل) | ready_for_teacher_approval |

## 6. Common Issues

* **brand_risk (الأبرز):** ذكر "DK/Duolingo" داخل عبارات النفي في image prompts لـ
  T26–T33 (8 دروس × 4 prompts). إصلاح لفظي بسيط (احذف اسم العلامة من النفي).
* **fallback skills:** بعض الأسئلة تحمل `general_beginner` بجانب skill حقيقي
  (T37–T41 أسئلة mistake_correction، وT2 Q3)، وثلاثة أسئلة في T26 تحمل
  `general_beginner` فقط. منخفضة الخطورة.
* **difficulty notes (غير حاجبة):** `translate_to_english` (T13–T25) و
  `listen_and_type` (T25–T41) عند A1 — مقبولة منهجيًا خارج نطاق 02–12، لكن تستحق
  متابعة صعوبة لمتعلّم عربي مبتدئ.
* **لا تكرار ضار، لا إفراط في الكلام (speaking ≤ 1)، الإنجليزية أمريكية طبيعية،
  العربية قصيرة وواضحة وRTL-safe.**

## 7. Fallback Skill Review

| Topic | Question | Current skill | Recommended skill | Severity |
|---|---|---|---|---|
| 02 | Q3 (match_pairs) | greetings, general_beginner | greetings | low |
| 26 | Q1 (tap_choice) | general_beginner | places_in_town / prepositions_of_place | medium |
| 26 | Q3 (match_pairs) | general_beginner | places_in_town | medium |
| 26 | Q6 (mini_story_choice) | general_beginner | places_in_town | medium |
| 37 | Q5 (mistake_correction) | countable_uncountable, general_beginner | countable_uncountable | low |
| 38 | Q6 (mistake_correction) | how_much_many, general_beginner | how_much_many | low |
| 39 | Q6 (mistake_correction) | clothes, general_beginner | clothes | low |
| 40 | Q6 (mistake_correction) | shopping, general_beginner | shopping | low |
| 41 | Q6 (mistake_correction) | adjectives_basic, general_beginner | adjectives_basic | low |

> السبب الجذري لـ T37–T41: نوع السؤال `mistake_correction` كان skill-code غير معروف
> فأُعيد تعيينه إلى `general_beginner` أثناء الـ seed (تحذير ظاهر في الـ seed).
> التوصية: إضافة skill `mistake_correction` إلى كتالوج المهارات أو إبقاء الـ skill
> الحقيقي فقط.

## 8. Early Topic Difficulty Review (Topics 02–12)

* ✅ لا يوجد `listen_and_type` في 02–12.
* ✅ لا يوجد `translate_to_english` في 02–12.
* ✅ لا توجد مهام كتابة حرّة طويلة؛ الأسئلة المنتجة محصورة في
  speak_this_sentence (واحد) و word_bank_sentence (مدعوم).
* أول ظهور لـ `translate_to_english` = T13، ولـ `listen_and_type` = T25 — أي بعد
  نافذة المبتدئ المبكّر، وعند مستوى A1. مقبول، مع متابعة الصعوبة.

## 9. Manual QA Sample

| Topic | Result | Notes |
|---|---|---|
| 02 Saying Hello/Goodbye | approved_ready | بنية كاملة، شخصيات متّسقة، تنوّع جيد؛ fallback بسيط في Q3 |
| 06 Basic Personal Info | approved_ready | name/age/country/city، أسئلة هادفة، عربية واضحة |
| 12 These and Those | approved_ready | تدرّج منطقي من this/that، 10 أسئلة متنوّعة |
| 18 Daily Routines | approved_ready | listening + speaking؛ Q7 translate_to_english (ملاحظة صعوبة) |
| 24 Short Answers | approved_ready | إجابات قصيرة طبيعية؛ Q8 translate_to_english |
| 30 Joining And/But | needs_minor_changes | المحتوى سليم؛ الحاجب الوحيد brand_risk في image prompts |
| 36 Food and Drink | approved_ready | مفردات طبيعية، listening + speaking |
| 42 Sports | approved_ready | تمييز play/do/go ممتاز |
| 45 Adverbs of Frequency | approved_ready | نوع frequency_scale مناسب، تسلسل جيد |
| 48 Studying/Future Goals | approved_ready | أهداف مستقبلية بسيطة، خاتمة منطقية للمنهج |

كل العيّنات تقرأ كدروس حقيقية هادفة (ليست نصًا عامًّا)، والأسئلة تخدم هدف الدرس.

## 10. Review Dashboard / Gate Verification

* لوحة المراجعة: `teacher_portal:content_review_list` و`content_review_detail`
  (gated بـ `teacher_required`، يشمل الأدمن) تعرض الحالة، quality_score،
  quality_flags، عدد الأسئلة/الصور/الصوت/الـ checklist، الملاحظات، والـ audit trail.
* ✅ المعلّم/الأدمن يصل للوحة؛ ✅ الطالب لا يصل (403/redirect)؛ ✅ المجهول يُعاد
  توجيهه لتسجيل الدخول.
* ✅ دروس pending مخفيّة عن الطلاب؛ الرابط المباشر لدرس pending يُرجع **404**.
* ✅ تمّ إنشاء **47** سجلّ `LessonReviewEvent(action="quality_check")` (واحد لكل
  Topic) يحمل score والتصنيف في metadata — والحالة بقيت `pending_review` للجميع.
* ✅ Topic 01 (Gold Reference، lesson 129) سليم: published، order=1، 10 أسئلة، لم يُمَس.

## 11. P0/P1/P2/P3

**P0 (حاجبة):** لا يوجد ما يمنع المراجعة. لا Topic يحتاج إعادة توليد.

**P1 (يجب الإصلاح قبل الاعتماد):**
* T26–T33: إزالة أسماء العلامات ("DK/Duolingo") من نصوص الـ image prompts (8 دروس ×
  4 prompts) — يرفع الـ score من 40–52 إلى 100 ويزيل أعلام الـ error.
* **(خارج نطاق 12B — تنبيه):** الكورس `onlenco-beginner` منشور ويضم **47 درسًا قديمًا
  منشورًا بدرجة 0** (محتوى مكسور مرئي للطلاب حاليًا) إلى جانب الـ 47 الجديدة pending.
  لم نلمسها (المرحلة مراجعة فقط)، لكنها تستحق مرحلة تنظيف منفصلة عاجلة.

**P2 (يُفضّل قبل توليد الوسائط):**
* تصحيح fallback skills (الجدول في القسم 7) وإضافة skill `mistake_correction`.
* مراجعة صعوبة `translate_to_english`/`listen_and_type` عند A1 لمتعلّم عربي.

**P3 (لاحقًا):**
* توحيد عبارة النفي القياسية في كل الـ image prompts (نمط واحد بدون أسماء علامات).
* إضافة سؤال listening مخصّص في الدروس المبكّرة جدًّا (02–17) إن رغبنا في توازن أعلى.

## 12. Final Decision

**B. Needs Prompt 12B.1 — Minor Content Fix Pass.**

الأغلبية الساحقة (39/47) جاهزة للاعتماد، والـ 8 المتبقية محجوبة فقط بإصلاح لفظي
بسيط في image prompts (لا مشكلة محتوى). بعد تمريرة إصلاح بسيطة تصبح كل الـ 47 جاهزة.

## 13. Recommended Next Phase

**Prompt 12B.1 — Minor Content Fix Pass** يشمل:
1. إعادة صياغة image prompts لـ T26–T33 لإزالة أسماء العلامات (DK/Duolingo) مع
   إبقاء عبارة نفي عامة («no logos, no copyrighted characters, no brand mascots»).
2. تصحيح fallback skills (القسم 7) وإضافة skill `mistake_correction`.
3. (موصى به بشدّة، منفصل) معالجة الـ 47 درسًا القديمة المنشورة المكسورة في
   `onlenco-beginner` (إلغاء نشر/أرشفة) قبل أي اعتماد للطلاب.

بعد 12B.1 → **Prompt 13 — Teacher Approval Batch 1**.

> تذكير: لا نشر لأي Topic، لا توليد وسائط، ولا بدء دفعة اعتماد قبل مراجعة هذا التقرير.
