# وثيقة متطلبات النظام SRS
# Onlenco — AI-Powered Adaptive English Learning Platform

**الإصدار:** 1.0  
**التاريخ:** 2026-05-08  
**نوع الوثيقة:** Software Requirements Specification — SRS  
**النظام:** Onlenco  
**اللغة الأساسية:** العربية مع دعم الإنجليزية  

---

## 1. الملخص التنفيذي

منصة **Onlenco** هي نظام تعليم لغة إنجليزية ذكي وتكيفي، لا يعتمد فقط على وجود AI Tutor أو ChatGPT داخل النظام، بل يبني تجربة تعليم كاملة حول سبعة محركات مترابطة:

1. **LLM Engine**
2. **Adaptive Learning Engine**
3. **CEFR Mapping Engine**
4. **Speech Recognition & Speaking Assessment Engine**
5. **Gamification Engine**
6. **Behavioral Analytics Engine**
7. **Smart Motivation & Encouragement Engine**

الهدف من النظام هو تعليم الطالب اللغة الإنجليزية بطريقة شخصية، حيث يبدأ الطالب باختبار تحديد مستوى كتابي وشفهي، ثم يتم وضعه في مستوى من **A0 إلى C2**، وبعد ذلك يقدّم له النظام دروسًا وتمارين واختبارات ومحادثات AI مناسبة لمستواه، مع متابعة أخطائه ونقاط ضعفه وتحسين صعوبة التمارين تلقائيًا.

النظام يجب ألا يكون مجرد منصة فيديوهات أو كورسات ثابتة، بل منصة تتعلم من سلوك الطالب وأخطائه وتقدمه اليومي، وتستخدم التحفيز، الإشعارات، النقاط، الشارات، السلاسل اليومية، والتحليلات السلوكية لزيادة الاستمرارية والنتائج التعليمية.

---

## 2. الهدف من الوثيقة

تهدف هذه الوثيقة إلى تحديد المتطلبات الوظيفية وغير الوظيفية لمنصة Onlenco بشكل واضح، بحيث تكون مرجعًا لفريق التطوير، الاختبار، التصميم، الإدارة، والمستثمرين.

هذه الوثيقة تغطي:

- رؤية النظام
- المستخدمين والأدوار
- الوظائف الأساسية
- محركات الذكاء والتكيف
- إدارة الطلاب
- المدفوعات والاشتراكات
- الإشعارات والتحفيز
- لوحة الإدارة
- واجهات API
- الأمن والصلاحيات
- الاختبارات ومعايير القبول
- خطة التنفيذ المرحلية

---

## 3. نطاق النظام

### 3.1 داخل النطاق

يشمل النظام:

- تسجيل الطلاب وإدارة الحسابات
- اختبار تحديد مستوى كتابي وشفهي
- تصنيف الطلاب حسب CEFR من A0 إلى C2
- بناء ملف تعلم ذكي لكل طالب
- دروس إنجليزية مقسمة حسب المستوى والمهارات
- كويز بعد كل درس
- اختبار أسبوعي بعد كل 3 دروس
- تحليل أخطاء الطالب
- التنبؤ بنقاط الضعف
- توليد تمارين مخصصة
- تعديل الصعوبة حسب أداء الطالب
- AI Tutor نصي وصوتي
- مكتبة رقمية للكتب والقصص والفيديوهات
- استخراج المفردات والقواعد من محتوى المكتبة
- Gamification: XP, Badges, Streaks, Challenges
- Smart Motivation Engine
- Notifications by email and in-app
- إدارة الاشتراكات والمدفوعات اليدوية
- لوحة تحكم إدارية لإدارة الطلاب
- تحليلات تعليمية وسلوكية
- REST APIs للتوسع المستقبلي
- دعم عربي/إنجليزي و RTL/LTR
- تجهيز للنشر Production

### 3.2 خارج النطاق في النسخة الأولى

يمكن تأجيل هذه العناصر إلى إصدارات لاحقة:

- Leaderboards عامة بين الطلاب
- Pronunciation scoring متقدم على مستوى phoneme
- تطبيق موبايل Native
- تكامل دفع إلكتروني مباشر
- Marketplace للمعلمين
- Live classes كاملة
- شهادات رسمية معتمدة خارجيًا

---

## 4. التعاريف والمصطلحات

| المصطلح | التعريف |
|---|---|
| CEFR | الإطار الأوروبي المرجعي لمستويات اللغة: A0, A1, A2, B1, B2, C1, C2 |
| LLM | نموذج لغوي كبير يستخدم في الشرح، المحادثة، التوليد، وتحليل النصوص |
| Adaptive Learning | تعلم تكيفي يغير المحتوى والصعوبة حسب أداء الطالب |
| Theta Score | مؤشر قدرة الطالب في نموذج صعوبة تكيفي |
| UserError | خطأ لغوي تم اكتشافه في إجابة الطالب |
| UserWeakness | نقطة ضعف تعليمية مستخرجة من أخطاء الطالب |
| SkillMastery | درجة إتقان الطالب لمهارة معينة |
| AI Tutor | معلم ذكي يساعد الطالب بالمحادثة والشرح والتصحيح |
| Motivation Engine | محرك تحفيز ذكي يرسل رسائل وأهداف حسب سلوك الطالب |
| Notification Event | حدث داخل النظام ينتج عنه إشعار أو بريد |
| Streak | عدد الأيام المتتالية التي تعلم فيها الطالب |
| XP | نقاط خبرة يحصل عليها الطالب مقابل النشاط والتقدم |

---

## 5. المستخدمون والأدوار

### 5.1 الطالب Student

الطالب هو المستخدم الأساسي للنظام. يستطيع:

- إنشاء حساب
- إجراء اختبار تحديد المستوى
- متابعة الدروس
- حل الكويزات والتمارين
- التحدث مع AI Tutor
- استخدام المكتبة
- رؤية تقدمه ونقاط ضعفه
- استلام إشعارات وتحفيز
- دفع الاشتراك

### 5.2 Super Admin

لديه صلاحية كاملة على النظام:

- إدارة الطلاب
- إدارة المدفوعات
- إدارة المحتوى
- رؤية التحليلات
- إدارة الصلاحيات
- مراجعة AI usage
- إدارة الإشعارات

### 5.3 Academic Admin

مسؤول أكاديمي يستطيع:

- متابعة تقدم الطلاب
- مراجعة نتائج تحديد المستوى
- مراجعة نقاط الضعف
- تعيين دروس وتمارين
- رؤية تحليلات التعلم

### 5.4 Finance Admin

مسؤول مالي يستطيع:

- مراجعة المدفوعات
- قبول أو رفض المدفوعات
- تمديد الاشتراكات
- رؤية تقارير الإيرادات

### 5.5 Support Admin

مسؤول دعم يستطيع:

- رؤية بيانات الطالب الأساسية
- إرسال إشعارات
- إضافة ملاحظات إدارية
- مساعدة الطالب دون تعديل المدفوعات

### 5.6 Read-only Admin

مستخدم إداري للعرض فقط، يستطيع رؤية التقارير دون إجراء تغييرات.

---

## 6. الرؤية المعمارية العامة

ينبغي بناء النظام كمنصة متعددة المحركات لا كمنصة شات فقط.

### 6.1 التطبيقات المقترحة داخل Django

```text
onlenco/
├── accounts
├── cefr
├── learning_core
├── ai_engine
├── speech
├── lessons
├── placement
├── tutor
├── library
├── gamification
├── behavioral_analytics
├── motivation
├── notifications
├── payments
├── admin_panel
├── analytics
├── api
└── core
```

### 6.2 مبدأ التصميم

- لا توضع Business Logic داخل Views مباشرة.
- كل منطق مهم يجب أن يكون داخل Services.
- كل AI call يجب أن يمر عبر `ai_engine`.
- كل إشعار يجب أن يمر عبر `notifications`.
- كل تحديث تعليمي يجب أن يمر عبر `learning_core`.
- كل فعل إداري حساس يجب أن يسجل في Audit Log.

---

## 7. المحركات السبعة الأساسية

## 7.1 CEFR Mapping Engine

### الهدف

ربط كل طالب، درس، تمرين، اختبار، ومهارة بمستوى CEFR واضح من A0 إلى C2.

### المتطلبات الوظيفية

| ID | المتطلب |
|---|---|
| CEFR-001 | يجب أن يدعم النظام المستويات: A0, A1, A2, B1, B2, C1, C2 |
| CEFR-002 | يجب أن يكون لكل درس مستوى CEFR |
| CEFR-003 | يجب أن يكون لكل تمرين مستوى CEFR |
| CEFR-004 | يجب أن يحول اختبار تحديد المستوى النتيجة إلى CEFR |
| CEFR-005 | يجب أن يحدد النظام متطلبات الترقية من مستوى إلى آخر |
| CEFR-006 | يجب أن يحسب نسبة تقدم الطالب داخل مستواه الحالي |

### النماذج المقترحة

```text
CEFRLevel
CEFRSkillDescriptor
CEFRProgressRule
```

### معايير القبول

- عند انتهاء Placement يظهر مستوى الطالب.
- تظهر الدروس المناسبة فقط لمستوى الطالب أو القريبة منه.
- يمكن للنظام حساب: كم تبقى للطالب للوصول إلى المستوى التالي.

---

## 7.2 Adaptive Learning Engine

### الهدف

هذا هو عقل النظام التعليمي. يجب أن يتابع أخطاء الطالب، نقاط ضعفه، إتقان المهارات، وصعوبة التمارين.

### المتطلبات الوظيفية

| ID | المتطلب |
|---|---|
| ALE-001 | يجب إنشاء StudentLearningProfile لكل طالب |
| ALE-002 | يجب حفظ أخطاء الطالب في UserError |
| ALE-003 | يجب تصنيف الأخطاء إلى Grammar, Spelling, Vocabulary, Punctuation, Word Order, Pronunciation, Comprehension |
| ALE-004 | يجب حساب UserWeakness حسب التكرار والشدة والحداثة |
| ALE-005 | يجب تحديث SkillMastery بعد كل تمرين أو كويز |
| ALE-006 | يجب تحديث theta_score حسب أداء الطالب |
| ALE-007 | يجب توليد توصيات تعلم بعد كل نشاط مهم |
| ALE-008 | يجب توليد تمارين مخصصة بناءً على أعلى 3 نقاط ضعف |
| ALE-009 | يجب أن يعمل النظام حتى لو فشل AI باستخدام fallback |

### النماذج المطلوبة

```text
StudentLearningProfile
Skill
GrammarTopic
SkillMastery
UserError
UserWeakness
AdaptiveExercise
ExerciseAttempt
LearningRecommendation
```

### الخدمات المطلوبة

```text
error_analyzer.py
weakness_engine.py
adaptive_difficulty.py
exercise_generator.py
recommendation_engine.py
learning_loop.py
```

### حلقة التعلم الأساسية

```text
Student answers question
→ Save attempt
→ Analyze error
→ Create UserError
→ Update UserWeakness
→ Update SkillMastery
→ Update theta_score
→ Generate recommendations
→ Generate personalized exercises
→ Update dashboard
```

### معايير القبول

لا يعتبر المحرك مكتملًا إلا إذا:

- خطأ الطالب ينتج عنه UserError.
- UserWeakness يتغير بعد تكرار الأخطاء.
- SkillMastery يتغير بعد الإجابات.
- theta_score يتغير حسب النجاح والفشل.
- تظهر تمارين أو توصيات جديدة بعد النشاط.

---

## 7.3 LLM Engine

### الهدف

استخدام LLM كمساعد داخل النظام وليس كنظام كامل. يجب أن يكون LLM مسؤولًا عن الشرح والتوليد والتحليل، لكن مع وجود منطق داخلي وقواعد fallback.

### المتطلبات الوظيفية

| ID | المتطلب |
|---|---|
| LLM-001 | يجب أن تمر كل نداءات AI عبر خدمة مركزية |
| LLM-002 | يجب تسجيل كل استخدام AI في AIUsageLog |
| LLM-003 | يجب وجود fallback عند فشل AI |
| LLM-004 | يجب التحقق من JSON القادم من AI |
| LLM-005 | يجب ألا يتم عرض أخطاء AI الخام للمستخدم |
| LLM-006 | يجب دعم rate limiting أو AI usage limits |
| LLM-007 | يجب تنظيف النص قبل عرضه أو نطقه للطالب |

### الخدمات المطلوبة

```text
llm_client.py
prompt_builder.py
response_validator.py
fallback_service.py
usage_tracker.py
```

### استخدامات LLM

- تحليل الأخطاء
- توليد التمارين
- شرح الإجابة
- AI Tutor
- تلخيص نصوص المكتبة
- استخراج المفردات والقواعد
- توليد رسائل تحفيزية متقدمة

### معايير القبول

- لا توجد نداءات AI مباشرة داخل Views.
- جميع الردود التي تتطلب JSON يتم التحقق منها.
- عند فشل AI لا ينهار النظام.

---

## 7.4 Speech Recognition & Speaking Assessment Engine

### الهدف

توفير تجربة Speaking حقيقية، تبدأ بـ Speech-to-Text وتحليل النص، ثم تتطور إلى تقييم النطق والطلاقة.

### مستويات التنفيذ

| المستوى | الوصف |
|---|---|
| MVP | تسجيل صوت، تحويل إلى نص، تحليل transcript |
| Improved | تقييم fluency، طول الإجابة، التوقفات، المفردات |
| Advanced | تقييم pronunciation و phoneme-level feedback |

### المتطلبات الوظيفية

| ID | المتطلب |
|---|---|
| SPEECH-001 | يجب أن يستطيع الطالب إرسال إجابة صوتية |
| SPEECH-002 | يجب تحويل الصوت إلى نص |
| SPEECH-003 | يجب تحليل transcript لغويًا |
| SPEECH-004 | يجب إعطاء speaking feedback |
| SPEECH-005 | يجب تحديث UserError عند وجود أخطاء في speaking |
| SPEECH-006 | يجب تحديث UserWeakness و SkillMastery |
| SPEECH-007 | يجب دعم AI Tutor voice readiness |

### النموذج المقترح

```text
SpeakingAttempt
- user
- prompt
- audio_file
- transcript
- pronunciation_score
- fluency_score
- grammar_score
- vocabulary_score
- overall_score
- feedback
```

### معايير القبول

- يستطيع الطالب تنفيذ speaking task.
- يحصل على تقييم واضح.
- يتم ربط الأخطاء بالتعلم التكيفي.

---

## 7.5 Gamification Engine

### الهدف

زيادة الالتزام اليومي وجعل التعلم ممتعًا من خلال نقاط وشارات وسلاسل وتحديات.

### المتطلبات الوظيفية

| ID | المتطلب |
|---|---|
| GAME-001 | يجب منح XP عند إكمال نشاط تعليمي |
| GAME-002 | يجب منح Badges عند إنجاز أهداف محددة |
| GAME-003 | يجب حساب Daily Streak |
| GAME-004 | يجب دعم Weekly Challenges |
| GAME-005 | يجب منع تكرار نفس Badge لنفس الطالب |
| GAME-006 | يجب عرض XP و Badges و Streak في Dashboard |

### قواعد XP المقترحة

| النشاط | XP |
|---|---:|
| إكمال درس | 20 |
| إكمال Quiz | 10 |
| دقة أعلى من 80% | 15 |
| 10 دقائق Speaking | 15 |
| قراءة 500 كلمة | 10 |
| إكمال اختبار أسبوعي | 30 |
| تحسن مستوى CEFR | 50 |

### النماذج المطلوبة

```text
UserXP
Badge
UserBadge
DailyStreak
WeeklyChallenge
UserChallenge
```

---

## 7.6 Behavioral Analytics Engine

### الهدف

تحليل سلوك الطالب لاكتشاف النشاط، الانقطاع، التحسن، وخطر إلغاء الاشتراك.

### المتطلبات الوظيفية

| ID | المتطلب |
|---|---|
| BAE-001 | يجب إنشاء Daily Activity Snapshot لكل طالب نشط |
| BAE-002 | يجب حساب engagement_score |
| BAE-003 | يجب حساب churn_risk_score |
| BAE-004 | يجب تحديد الطلاب المعرضين للانقطاع |
| BAE-005 | يجب إرسال البيانات إلى Admin Dashboard |
| BAE-006 | يجب استخدام البيانات في Motivation Engine |

### نموذج النشاط اليومي

```text
LearnerActivitySnapshot
- user
- date
- lessons_completed
- quizzes_completed
- questions_answered
- correct_answers
- ai_messages_count
- speaking_minutes
- reading_minutes
- words_read
- listening_minutes
- xp_earned
- streak_days
- engagement_score
- churn_risk_score
```

---

## 7.7 Smart Motivation & Encouragement Engine

### الهدف

تحفيز الطالب برسائل ذكية وشخصية حسب نشاطه ومستواه وسلوكه.

### المتطلبات الوظيفية

| ID | المتطلب |
|---|---|
| MOT-001 | يجب توليد رسائل تحفيزية حسب النشاط |
| MOT-002 | يجب دعم رسائل الإنجاز |
| MOT-003 | يجب دعم رسائل العودة بعد الانقطاع |
| MOT-004 | يجب دعم رسائل السلسلة اليومية |
| MOT-005 | يجب اختيار tone مناسب للطالب |
| MOT-006 | يجب دعم العربية والإنجليزية |
| MOT-007 | يجب احترام تفضيلات الإشعارات |
| MOT-008 | يجب منع الإزعاج وكثرة الرسائل |

### أمثلة Triggers

| الشرط | الرسالة |
|---|---|
| ai_chat_minutes > 20 | Excellent speaking practice today! |
| words_read > 500 | Great reading progress! |
| current_streak = 7 | You are on a 7-day learning streak! |
| inactive_days >= 3 | Just 10 minutes today can rebuild your habit. |
| mastery_delta > 10 | Your skill progress improved this week. |

### النماذج المطلوبة

```text
MotivationMessage
MotivationPreference
```

---

## 8. إدارة الحسابات والطلاب

### المتطلبات

| ID | المتطلب |
|---|---|
| ACC-001 | يجب أن يستطيع الطالب إنشاء حساب |
| ACC-002 | يجب أن يستطيع الطالب تسجيل الدخول والخروج |
| ACC-003 | يجب دعم إعادة تعيين كلمة المرور |
| ACC-004 | يجب دعم تأكيد البريد الإلكتروني |
| ACC-005 | يجب أن يكون لكل طالب ملف Profile |
| ACC-006 | يجب أن يحتوي Profile على اللغة المفضلة |
| ACC-007 | يجب أن يحتوي Profile على حالة الاشتراك |

---

## 9. اختبار تحديد المستوى Placement

### الهدف

وضع الطالب في مستوى مناسب من البداية وبناء ملف تعلم أولي.

### المتطلبات

| ID | المتطلب |
|---|---|
| PLACE-001 | يجب وجود اختبار كتابي |
| PLACE-002 | يجب وجود اختبار شفهي |
| PLACE-003 | يجب تقييم Grammar و Vocabulary و Reading و Writing و Speaking |
| PLACE-004 | يجب تحديد مستوى CEFR |
| PLACE-005 | يجب حفظ نقاط القوة |
| PLACE-006 | يجب حفظ نقاط الضعف |
| PLACE-007 | يجب إنشاء StudentLearningProfile بعد الاختبار |
| PLACE-008 | يجب إنشاء SkillMastery أولي |
| PLACE-009 | يجب إنشاء توصيات أولية |
| PLACE-010 | يجب دعم إعادة الاختبار وفق قواعد محددة |

---

## 10. الدروس والمحتوى Curriculum

### مكونات الدرس

كل درس يجب أن يحتوي على:

- عنوان
- مستوى CEFR
- أهداف تعليمية
- مهارة أساسية
- Grammar focus
- Vocabulary focus
- Reading task
- Writing task
- Listening task
- Speaking task
- فيديو شرح قصير من المعلم
- Quiz
- توصيات ما بعد الدرس

### المتطلبات

| ID | المتطلب |
|---|---|
| LES-001 | يجب ربط الدرس بمستوى CEFR |
| LES-002 | يجب ربط الدرس بمهارة أو أكثر |
| LES-003 | يجب وجود Quiz بعد كل درس |
| LES-004 | يجب تحديث Progress عند إكمال الدرس |
| LES-005 | يجب تحديث Gamification بعد إكمال الدرس |
| LES-006 | يجب تحديث Recommendations بعد إكمال الدرس |

---

## 11. الكويز والاختبار الأسبوعي

### الكويز بعد كل درس

| ID | المتطلب |
|---|---|
| QUIZ-001 | يجب أن يحل الطالب Quiz بعد كل درس |
| QUIZ-002 | يجب حساب النتيجة والدقة |
| QUIZ-003 | يجب تحليل الإجابات الخاطئة |
| QUIZ-004 | يجب تحديث UserError و UserWeakness |
| QUIZ-005 | يجب تحديث theta_score |
| QUIZ-006 | يجب توليد feedback واضح |

### الاختبار الأسبوعي بعد كل 3 دروس

| ID | المتطلب |
|---|---|
| WEEK-001 | بعد كل 3 دروس مكتملة يجب إتاحة Weekly Assessment |
| WEEK-002 | يجب أن يغطي الاختبار الأسبوعي الدروس الأخيرة |
| WEEK-003 | يجب أن يحتوي على Grammar, Vocabulary, Reading, Writing, Listening, Speaking |
| WEEK-004 | يجب تحديث SkillMastery و Weaknesses بعده |
| WEEK-005 | يجب توليد تقرير أسبوعي للطالب |

---

## 12. AI Tutor

### الهدف

معلم ذكي يعرف مستوى الطالب ونقاط ضعفه ويقدم مساعدة مناسبة.

### المتطلبات

| ID | المتطلب |
|---|---|
| TUTOR-001 | يجب أن يستطيع الطالب محادثة AI Tutor |
| TUTOR-002 | يجب أن يستخدم AI Tutor مستوى CEFR |
| TUTOR-003 | يجب أن يستخدم AI Tutor نقاط الضعف |
| TUTOR-004 | يجب أن يستخدم آخر الأخطاء |
| TUTOR-005 | يجب أن يعطي شرحًا مناسبًا لمستوى الطالب |
| TUTOR-006 | يجب أن يولد micro-exercises عند الحاجة |
| TUTOR-007 | يجب تحليل رسائل الطالب وحفظ أخطائه |
| TUTOR-008 | يجب دعم fallback عند فشل AI |
| TUTOR-009 | يجب تنظيف النص قبل النطق أو العرض |

---

## 13. Text Humanization & Speech Sanitization

### الهدف

منع قراءة أو عرض نصوص تقنية للطالب مثل:

- underscore
- dash
- blank blank blank
- raw_event_names
- database_field_names
- JSON
- file paths

### المتطلبات

| ID | المتطلب |
|---|---|
| TXT-001 | يجب وجود خدمة TextHumanizer |
| TXT-002 | يجب تحويل snake_case إلى نص طبيعي |
| TXT-003 | يجب تحويل event names إلى نص مفهوم |
| TXT-004 | يجب دعم العربية والإنجليزية |
| TXT-005 | يجب تطبيق التنظيف قبل Voice output |
| TXT-006 | يجب تطبيق التنظيف على رسائل AI Tutor والتحفيز والإشعارات |

### أمثلة

| المدخل | المخرج |
|---|---|
| weekly_assessment_available | الاختبار الأسبوعي متاح الآن |
| payment_approved | تم قبول الدفع |
| cefr_level | مستوى اللغة الإنجليزية |
| theta_score | مؤشر مستوى التعلم |

---

## 14. المكتبة الرقمية Library

### الهدف

توفير محتوى قراءة واستماع داعم لتعلم اللغة.

### المتطلبات

| ID | المتطلب |
|---|---|
| LIB-001 | يجب دعم الكتب |
| LIB-002 | يجب دعم القصص القصيرة |
| LIB-003 | يجب دعم الروايات |
| LIB-004 | يجب دعم الفيديوهات الطويلة |
| LIB-005 | يجب ربط المحتوى بمستوى CEFR |
| LIB-006 | يجب استخراج مفردات جديدة من المحتوى |
| LIB-007 | يجب استخراج قواعد مهمة من المحتوى |
| LIB-008 | يجب توليد أسئلة comprehension |
| LIB-009 | يجب تتبع تقدم الطالب داخل المكتبة |

---

## 15. Notification Management System by Email

### الهدف

نظام إشعارات مركزي لا يعتمد على `send_mail` عشوائي داخل Views.

### أنواع الإشعارات

#### للطالب

- Welcome Email
- Email Verification
- Password Reset
- Placement Result
- Weakness Detected
- New Exercises
- Lesson Completed
- Weekly Assessment Available
- Weekly Summary
- Payment Submitted
- Payment Approved
- Payment Rejected
- Subscription Expiring
- Inactive Student Reminder

#### للإدارة

- New Student Registered
- New Payment Pending
- AI Failure
- High AI Usage
- At-risk Student
- Daily Admin Summary
- Weekly Admin Summary

### النماذج المطلوبة

```text
NotificationEvent
EmailNotification
NotificationPreference
NotificationTemplate optional
```

### المتطلبات

| ID | المتطلب |
|---|---|
| NOTIF-001 | يجب تسجيل كل حدث إشعار |
| NOTIF-002 | يجب تسجيل كل محاولة إرسال بريد |
| NOTIF-003 | يجب دعم Arabic/English email templates |
| NOTIF-004 | يجب دعم RTL/LTR داخل البريد |
| NOTIF-005 | يجب احترام تفضيلات المستخدم |
| NOTIF-006 | يجب تسجيل فشل البريد وإتاحة retry |
| NOTIF-007 | يجب منع التكرار والإزعاج |
| NOTIF-008 | يجب أن يظهر اسم المرسل Onlenco |

### إعداد اسم المرسل

يجب أن يكون:

```text
Onlenco <info@onlenco.com>
```

وليس:

```text
info
```

### شعار البريد

- يجب وضع شعار Onlenco داخل قالب البريد.
- أما شعار صندوق الوارد بجانب اسم المرسل فيحتاج إعدادات DNS مثل SPF/DKIM/DMARC/BIMI ولا يتم التحكم فيه من HTML فقط.

---

## 16. Smart Motivation & Encouragement System

هذه الميزة يجب أن تكون مرتبطة بـ Behavioral Analytics و Gamification و Notifications.

### المتطلبات

| ID | المتطلب |
|---|---|
| MOTIV-001 | يجب إنشاء رسائل تحفيزية حسب النشاط |
| MOTIV-002 | يجب منح XP حسب النشاط |
| MOTIV-003 | يجب منح Badges حسب الإنجاز |
| MOTIV-004 | يجب حساب Daily Streak |
| MOTIV-005 | يجب إنشاء Comeback messages للطلاب غير النشطين |
| MOTIV-006 | يجب دعم Adaptive Tone |
| MOTIV-007 | يجب إرسال الرسائل عبر in-app أو email حسب التفضيلات |

---

## 17. المدفوعات والاشتراكات

### الخطط المطلوبة

| الخطة | السعر | المدة |
|---|---:|---|
| Monthly Plan | 30,000 SDG | شهر واحد |
| 3-Month Plan | 50,000 SDG | 3 أشهر |

### المتطلبات

| ID | المتطلب |
|---|---|
| PAY-001 | يجب أن يستطيع الطالب اختيار خطة |
| PAY-002 | يجب أن يرفع الطالب إثبات دفع |
| PAY-003 | يجب التحقق من نوع وحجم الملف |
| PAY-004 | يجب أن يراجع Admin الدفع |
| PAY-005 | يجب قبول أو رفض الدفع |
| PAY-006 | عند القبول يجب تفعيل الاشتراك |
| PAY-007 | يجب حساب تاريخ انتهاء الاشتراك |
| PAY-008 | يجب إرسال إشعار للطالب عند القبول أو الرفض |
| PAY-009 | يجب منع غير المشترك من مزايا Premium إن وجدت |

---

## 18. Admin Control Panel لإدارة الطلاب

### الهدف

لوحة تحكم احترافية لإدارة رحلة الطالب بالكامل، وليست الاعتماد فقط على Django Admin.

### الصفحات الأساسية

1. Dashboard
2. Students List
3. Student 360 Profile
4. Payments Review
5. Learning Progress
6. AI Activity
7. Motivation & Gamification
8. Notifications
9. Reports
10. Admin Action Log

### Student Detail Tabs

- Overview
- Placement
- Learning Progress
- Weaknesses & Errors
- AI Tutor Activity
- Exercises
- Motivation & Gamification
- Payments & Subscription
- Notifications
- Admin Notes

### الأدوار الإدارية

| الدور | الصلاحيات |
|---|---|
| Super Admin | كامل الصلاحيات |
| Academic Admin | الطلاب والتعلم |
| Finance Admin | المدفوعات والاشتراكات |
| Support Admin | الدعم والإشعارات |
| Read-only Admin | عرض فقط |

### المتطلبات

| ID | المتطلب |
|---|---|
| ADMIN-001 | يجب منع غير staff من دخول اللوحة |
| ADMIN-002 | يجب وجود Students List مع Search/Filters |
| ADMIN-003 | يجب وجود Student 360 Profile |
| ADMIN-004 | يجب رؤية تقدم الطالب ونقاط ضعفه |
| ADMIN-005 | يجب رؤية المدفوعات والاشتراك |
| ADMIN-006 | يجب دعم إرسال إشعار للطالب |
| ADMIN-007 | يجب دعم تمديد الاشتراك حسب الصلاحية |
| ADMIN-008 | يجب تسجيل كل إجراء حساس في AdminActionLog |
| ADMIN-009 | يجب دعم CSV export |

---

## 19. التحليلات Analytics

### تحليلات الطالب

- المستوى الحالي
- التقدم داخل المستوى
- نقاط الضعف
- المهارات القوية
- XP
- Streak
- آخر توصيات
- نتائج الكويز
- النشاط الأسبوعي

### تحليلات الإدارة

| ID | المتطلب |
|---|---|
| ANA-001 | عدد الطلاب الكلي |
| ANA-002 | الطلاب النشطون اليوم |
| ANA-003 | توزيع CEFR |
| ANA-004 | أكثر نقاط الضعف شيوعًا |
| ANA-005 | معدل إكمال الدروس |
| ANA-006 | معدل استخدام AI Tutor |
| ANA-007 | الطلاب المعرضون للانقطاع |
| ANA-008 | إحصائيات المدفوعات |
| ANA-009 | AI usage and cost |
| ANA-010 | motivation engagement |

---

## 20. REST APIs

### الهدف

تجهيز النظام للتكامل مع Mobile App أو Frontend مستقل.

### API Groups

| المجموعة | أمثلة endpoints |
|---|---|
| Auth/Profile | `/api/v1/profile/` |
| Placement | `/api/v1/placement/submit/` |
| Learning | `/api/v1/learning/profile/` |
| Weaknesses | `/api/v1/learning/weaknesses/` |
| Exercises | `/api/v1/exercises/next/` |
| Attempts | `/api/v1/exercises/{id}/attempt/` |
| Tutor | `/api/v1/tutor/chat/` |
| Payments | `/api/v1/payments/` |
| Notifications | `/api/v1/notifications/` |
| Motivation | `/api/v1/motivation/` |
| Admin | `/api/v1/admin/students/` |

### متطلبات API

| ID | المتطلب |
|---|---|
| API-001 | يجب استخدام versioning |
| API-002 | يجب وجود Authentication |
| API-003 | يجب وجود Object-level permissions |
| API-004 | يجب منع الطالب من رؤية بيانات طالب آخر |
| API-005 | يجب توثيق API عبر OpenAPI/Swagger إن أمكن |

---

## 21. دعم العربية والإنجليزية

### المتطلبات

| ID | المتطلب |
|---|---|
| I18N-001 | يجب دعم العربية والإنجليزية في الواجهة |
| I18N-002 | يجب دعم RTL للعربية |
| I18N-003 | يجب دعم LTR للإنجليزية |
| I18N-004 | يجب ترجمة قوالب البريد |
| I18N-005 | يجب ترجمة رسائل النظام |
| I18N-006 | يجب ألا توجد نصوص hardcoded دون ترجمة |
| I18N-007 | يجب أن يختار النظام لغة البريد حسب تفضيل المستخدم |

---

## 22. الأمن والصلاحيات

### المتطلبات

| ID | المتطلب |
|---|---|
| SEC-001 | يجب عدم تشغيل DEBUG في الإنتاج |
| SEC-002 | يجب عدم استخدام ALLOWED_HOSTS = ["*"] في الإنتاج |
| SEC-003 | يجب حفظ SECRET_KEY في environment variables |
| SEC-004 | يجب حماية CSRF |
| SEC-005 | يجب تفعيل secure cookies في الإنتاج |
| SEC-006 | يجب حماية ملفات الدفع المرفوعة |
| SEC-007 | يجب منع تسريب بيانات طالب لطالب آخر |
| SEC-008 | يجب حماية Admin Panel بصلاحيات staff |
| SEC-009 | يجب تسجيل AdminActionLog للأفعال الحساسة |
| SEC-010 | يجب عدم عرض AI raw errors للمستخدم |
| SEC-011 | يجب تطبيق rate limiting على AI Tutor والتحليل |

---

## 23. متطلبات AI Failure Handling

لكل ميزة AI يجب اختبار الحالات التالية:

- Missing API key
- Invalid API key
- Timeout
- Malformed JSON
- Empty response
- Rate limit error
- Network failure

### السلوك المتوقع

| ID | المتطلب |
|---|---|
| AIF-001 | لا ينهار النظام عند فشل AI |
| AIF-002 | يعمل fallback آمن |
| AIF-003 | يتم تسجيل الخطأ |
| AIF-004 | يرى المستخدم رسالة لطيفة |
| AIF-005 | لا يتم عرض exception خام |

---

## 24. متطلبات النشر Deployment

### المتطلبات

| ID | المتطلب |
|---|---|
| DEP-001 | Dockerfile |
| DEP-002 | docker-compose |
| DEP-003 | PostgreSQL في الإنتاج |
| DEP-004 | Redis عند استخدام Celery أو Queue |
| DEP-005 | Gunicorn |
| DEP-006 | إعداد static files |
| DEP-007 | إعداد media files |
| DEP-008 | health check endpoint |
| DEP-009 | logging |
| DEP-010 | backup strategy للقاعدة والملفات |
| DEP-011 | .env.example |

---

## 25. متطلبات البريد والهوية Brand Email

### المتطلبات

| ID | المتطلب |
|---|---|
| EMAIL-001 | يجب أن يظهر اسم المرسل Onlenco |
| EMAIL-002 | يجب استخدام `Onlenco <info@domain.com>` |
| EMAIL-003 | يجب أن تكون رسائل المستخدم العربي بالعربية |
| EMAIL-004 | يجب دعم RTL داخل البريد العربي |
| EMAIL-005 | يجب إضافة شعار Onlenco داخل قالب البريد |
| EMAIL-006 | يجب تجهيز خطة SPF/DKIM/DMARC/BIMI لإظهار الشعار بجانب الرسائل عند دعم مزود البريد |

---

## 26. نماذج البيانات الأساسية

### 26.1 Learning Core

```text
StudentLearningProfile
Skill
GrammarTopic
SkillMastery
UserError
UserWeakness
AdaptiveExercise
ExerciseAttempt
LearningRecommendation
```

### 26.2 CEFR

```text
CEFRLevel
CEFRSkillDescriptor
CEFRProgressRule
```

### 26.3 Speech

```text
SpeakingAttempt
```

### 26.4 Gamification

```text
UserXP
Badge
UserBadge
DailyStreak
WeeklyChallenge
UserChallenge
```

### 26.5 Behavioral Analytics

```text
LearnerActivitySnapshot
```

### 26.6 Motivation

```text
MotivationMessage
MotivationPreference
```

### 26.7 Notifications

```text
NotificationEvent
EmailNotification
NotificationPreference
```

### 26.8 Payments

```text
SubscriptionPlan
Subscription
Payment
PaymentReview
```

### 26.9 Admin Panel

```text
AdminActionLog
AdminNote
StudentRiskProfile optional
```

---

## 27. سيناريوهات المستخدم الأساسية

## 27.1 رحلة طالب جديد

```text
1. يسجل الطالب حسابًا
2. يؤكد البريد الإلكتروني
3. يدخل اختبار تحديد المستوى الكتابي
4. يدخل اختبار speaking
5. يحصل على CEFR level
6. ينشأ StudentLearningProfile
7. تنشأ SkillMastery أولية
8. تنشأ UserWeakness أولية
9. تظهر توصيات أولى
10. يبدأ أول درس
11. يشاهد فيديو الشرح
12. يحل التمارين والكويز
13. تُحلل أخطاؤه
14. تُحدث نقاط ضعفه
15. يتغير theta_score
16. يحصل على XP
17. تظهر رسالة تحفيز
18. تصل رسالة بريد أو إشعار داخلي
```

## 27.2 رحلة طالب عائد

```text
1. يدخل الطالب بعد عدة أيام
2. يرى Dashboard يحتوي على XP و Streak و Weaknesses
3. يحل تمارين مخصصة
4. تتحسن SkillMastery
5. تقل UserWeakness
6. تزداد الصعوبة قليلًا
7. تتغير التوصيات
8. يحصل على Badge أو Motivation Message
```

## 27.3 رحلة دفع

```text
1. يختار الطالب الخطة الشهرية أو 3 أشهر
2. يرفع إثبات الدفع
3. يحصل على إشعار أن الطلب قيد المراجعة
4. يرى Admin الدفع pending
5. يوافق Admin أو يرفض
6. عند القبول يتم تفعيل الاشتراك
7. يصل بريد قبول الدفع للطالب
```

## 27.4 رحلة Admin

```text
1. يدخل Admin لوحة التحكم
2. يرى KPIs عامة
3. يبحث عن طالب
4. يفتح Student 360 Profile
5. يراجع المستوى والتقدم والأخطاء والمدفوعات
6. يرسل إشعارًا أو يمدد اشتراكًا حسب الصلاحية
7. يتم تسجيل الإجراء في AdminActionLog
```

---

## 28. Requirement Traceability Matrix مختصر

| المجال | متطلبات رئيسية | الحالة المتوقعة |
|---|---|---|
| Accounts | تسجيل، دخول، تحقق بريد، لغة المستخدم | إلزامي |
| Placement | كتابي، شفهي، CEFR، نقاط قوة/ضعف | إلزامي |
| Learning Core | Profile, Errors, Weaknesses, Mastery, Attempts | إلزامي |
| Adaptive Difficulty | theta, difficulty, recommendations | إلزامي |
| LLM | client, prompts, fallback, usage log | إلزامي |
| Speech | STT, transcript analysis, feedback | MVP إلزامي |
| Lessons | مهارات، فيديو، كويز، تقدم | إلزامي |
| Weekly Assessment | بعد كل 3 دروس | إلزامي |
| Gamification | XP, badges, streaks | إلزامي |
| Motivation | رسائل ذكية وتفضيلات | إلزامي |
| Notifications | Email/in-app, Arabic/English | إلزامي |
| Payments | خطط، إثبات دفع، موافقة Admin | إلزامي |
| Admin Panel | Student management 360 | إلزامي |
| Analytics | learning + behavior + payments | إلزامي |
| API | DRF endpoints + permissions | إلزامي للتوسع |
| Security | permissions, isolation, secure settings | إلزامي |
| Deployment | Docker, PostgreSQL, env, logging | إلزامي للإنتاج |

---

## 29. معايير القبول النهائية

لا يعتبر النظام جاهزًا إلا إذا كانت هذه الرحلة تعمل:

```text
Student Registration
→ Email Verification
→ Written + Speaking Placement
→ CEFR Level
→ StudentLearningProfile
→ Lessons
→ Quiz
→ Error Analysis
→ Weakness Update
→ SkillMastery Update
→ theta_score Update
→ Personalized Exercises
→ AI Tutor Personalized Response
→ XP/Badge/Streak Update
→ Motivation Message
→ Notification
→ Admin Analytics
```

### Gate 1 — Demo Ready

- التسجيل يعمل
- الدروس تعمل
- الكويز يعمل
- الدفع اليدوي يعمل
- لوحة Admin أساسية تعمل

### Gate 2 — Beta Ready

- Adaptive loop يعمل
- AI fallback يعمل
- Notifications تعمل
- Motivation تعمل
- Tests للرحلة الأساسية

### Gate 3 — Paid Users Ready

- Security جيد
- Payments مستقر
- Subscriptions تعمل
- User isolation مختبر
- Email Arabic/English مضبوط

### Gate 4 — Production Ready

- Docker
- PostgreSQL
- Logging
- Backups
- Monitoring
- Deploy settings آمنة
- Test coverage مقبول

---

## 30. خطة التنفيذ المرحلية

### Phase 0 — Audit & Foundation

- مراجعة الكود الحالي
- توثيق الفجوات
- ضبط settings
- إنشاء service layer
- إضافة tests أساسية

### Phase 1 — CEFR Engine

- CEFRLevel
- CEFRSkillDescriptor
- Progress rules
- ربط الدروس والتمارين بالمستوى

### Phase 2 — Adaptive Learning Engine

- StudentLearningProfile
- UserError
- UserWeakness
- SkillMastery
- AdaptiveExercise
- ExerciseAttempt
- LearningLoopService

### Phase 3 — LLM Engine

- LLM client
- Prompt builder
- Response validator
- Fallback
- Usage tracking

### Phase 4 — Placement + Speech MVP

- اختبار كتابي
- اختبار speaking
- Transcript analysis
- CEFR mapping

### Phase 5 — Lessons + Weekly Assessment

- lesson structure
- quiz integration
- weekly assessment after 3 lessons

### Phase 6 — Gamification + Behavioral Analytics

- XP
- badges
- streaks
- activity snapshots
- churn risk

### Phase 7 — Motivation + Notifications

- motivation rules
- email/in-app notifications
- Arabic/English templates

### Phase 8 — Admin Control Panel

- Dashboard
- Students List
- Student 360 Profile
- Payments
- Reports
- Action logs

### Phase 9 — API + Security + Deployment

- REST APIs
- permissions
- Docker
- production settings
- final launch gate

---

## 31. خطة الاختبار

### أوامر التحقق

```bash
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check
python manage.py migrate
python manage.py test
coverage run manage.py test
coverage report
```

### اختبارات إلزامية

| نوع الاختبار | أمثلة |
|---|---|
| Model tests | StudentLearningProfile, UserError, Payment |
| Service tests | ErrorAnalyzer, WeaknessEngine, MotivationEngine |
| View tests | Dashboard, Placement, Lessons |
| API tests | permissions, responses, validation |
| Security tests | user isolation, admin permissions |
| AI fallback tests | missing key, malformed JSON, timeout |
| Payment tests | submit, approve, reject, expiry |
| Notification tests | Arabic/English, sender name, retry |
| E2E tests | رحلة الطالب كاملة |

---

## 32. المخاطر الرئيسية

| الخطر | التأثير | التخفيف |
|---|---|---|
| الاعتماد الزائد على LLM | فشل أو تكلفة عالية | fallback + usage limits |
| ضعف جودة المحتوى التعليمي | نتائج تعلم ضعيفة | CEFR curriculum review |
| عدم اختبار user isolation | تسريب بيانات | permission tests |
| رسائل AI غير مناسبة | تجربة سيئة | prompt control + validation |
| email spam | إزعاج المستخدم | frequency limits |
| speaking assessment غير حقيقي | تضليل المنتج | توضيح MVP vs Advanced |
| لوحة Admin واسعة جدًا | تعقيد | تنفيذ تدريجي |
| عدم جاهزية production | مشاكل إطلاق | Docker + deploy checklist |

---

## 33. توصية نهائية

ينبغي بناء Onlenco كمنصة تعليم ذكية قائمة على البيانات، وليس كواجهة ChatGPT. الأولوية القصوى هي إكمال حلقة التعلم التكيفي:

```text
Placement → Profile → Errors → Weaknesses → Difficulty → Exercises → Recommendations → Motivation
```

بعد ذلك تأتي التحسينات التجارية مثل Admin Panel، Notifications، Payments، وAnalytics.

ميزة Onlenco الحقيقية ستكون في الجمع بين:

- CEFR Mapping
- Adaptive Learning
- AI Tutor
- Speech Practice
- Gamification
- Behavioral Analytics
- Smart Motivation

إذا تم تنفيذ هذه العناصر باختبارات واضحة وصلاحيات آمنة وتجربة مستخدم جيدة، يمكن أن تتحول Onlenco من منصة كورسات إلى نظام تعلم لغة ذكي قابل للتسويق والاشتراك.

---

## 34. ملحق: قائمة قبول مختصرة قبل الإطلاق

```text
[ ] التسجيل وتأكيد البريد يعملان
[ ] اسم مرسل البريد يظهر Onlenco
[ ] البريد العربي RTL يعمل
[ ] اختبار تحديد المستوى الكتابي يعمل
[ ] اختبار speaking MVP يعمل
[ ] CEFR يتم حسابه
[ ] StudentLearningProfile يتم إنشاؤه
[ ] UserError يتم إنشاؤه عند الخطأ
[ ] UserWeakness يتم تحديثه
[ ] SkillMastery يتم تحديثه
[ ] theta_score يتم تحديثه
[ ] تمارين مخصصة تظهر
[ ] AI Tutor يستخدم بيانات الطالب
[ ] الدروس تحتوي مهارات وفيديو وكويز
[ ] اختبار أسبوعي بعد 3 دروس
[ ] XP و Badges و Streak تعمل
[ ] Motivation messages تعمل
[ ] Notifications تعمل
[ ] المدفوعات اليدوية تعمل
[ ] Admin Panel يدير الطلاب
[ ] User isolation مختبر
[ ] AI fallback مختبر
[ ] Docker/Deployment جاهز
[ ] Tests passing
```

