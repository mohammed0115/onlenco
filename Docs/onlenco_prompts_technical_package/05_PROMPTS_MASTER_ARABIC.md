# 05_PROMPTS_MASTER_ARABIC.md

## Prompt 0 — تثبيت الرؤية والسيناريو النهائي

```text
أنت مهندس برمجيات معماري Senior Software Architect.

لدينا منصة اسمها Onlenco لتعلم اللغة الإنجليزية بالذكاء الاصطناعي. المطلوب تحويل السيناريو المرفق إلى نظام إنتاجي حقيقي.

الرؤية:
Onlenco ليست مجرد منصة دروس، بل تجربة تعلم ذكية تشبه اللعبة، تبدأ باختبار تحديد مستوى، ثم تبني رحلة تعلم شخصية للطالب، وتتابع أخطاءه ونقاط ضعفه، وتقدم له دروساً وتمارين وAI Tutor ومحادثة صوتية وتقييم نطق وتحفيز ذكي.

الشخصيات الأساسية:
1. Student / Learner
2. Academic Admin / Teacher
3. Finance Admin
4. Super Admin
5. Content Manager

المحركات الأساسية:
1. LLM Engine
2. Adaptive Learning Engine
3. CEFR Mapping Engine
4. Speech Recognition & Speaking Assessment Engine
5. Gamification Engine
6. Behavioral Analytics Engine
7. Smart Motivation & Encouragement Engine

الهيكل التعليمي المعتمد:
CEFR Level → Unit → 3 Lessons → Activities → Quiz → Progress Update

المطلوب:
- راجع المشروع الحالي.
- لا تكتب كود عشوائي.
- أنشئ خطة تنفيذ واضحة.
- اقترح هيكل apps احترافي داخل Django.
- حدد النماذج الأساسية، الخدمات، APIs، الاختبارات، والمهام الخلفية.
- لا تعتمد على Django Admin فقط، بل نريد Admin Dashboard مخصص للمنصة.
- يجب دعم العربية والإنجليزية من البداية.
- يجب دعم RTL/LTR.
- يجب تجهيز النظام ليعمل Web ثم Mobile API لاحقاً.

اخرج لي:
1. CURRENT_ONLENCO_SYSTEM_AUDIT.md
2. TARGET_ARCHITECTURE.md
3. DATABASE_MODEL_PLAN.md
4. API_CONTRACTS_PLAN.md
5. EXECUTION_PHASES.md
```

---

## Prompt 1 — إعادة هيكلة المشروع Architecture

```text
أنت Django Senior Backend Architect.

المطلوب إعادة تنظيم مشروع Onlenco بهيكل احترافي Production-ready.

اعتمد هذا التقسيم:

apps/accounts
apps/organizations
apps/curriculum
apps/placement
apps/learning_profiles
apps/lessons
apps/exercises
apps/assessments
apps/ai_tutor
apps/speech_assessment
apps/adaptive_learning
apps/cefr_mapping
apps/gamification
apps/motivation
apps/behavioral_analytics
apps/digital_library
apps/weekly_club
apps/subscriptions
apps/payments
apps/notifications
apps/academic_admin
apps/finance_admin
apps/dashboards
apps/reports

المطلوب:
1. إنشاء الهيكل بدون كسر المشروع.
2. فصل domain logic عن views.
3. إنشاء services.py أو services/ لكل app.
4. إنشاء selectors.py للاستعلامات.
5. إنشاء serializers.py للـ API.
6. إنشاء urls.py لكل app.
7. إنشاء tests لكل app.
8. تجهيز Celery للمهام الطويلة مثل AI analysis, speech processing, notifications.
9. تجهيز PostgreSQL كقاعدة أساسية.
10. تجهيز Redis للـ cache و Celery broker.
11. تجهيز settings منفصلة: base/development/production/test.
12. تجهيز .env.example.

المخرجات:
- بنية ملفات نظيفة.
- README لكل app يشرح مسؤوليته.
- عدم وضع business logic داخل views.
- عدم استخدام كود مكرر.
- الالتزام بـ SOLID و DRY.
```

---

## Prompt 2 — Accounts, Roles & Permissions

```text
أنت Django Security Engineer.

المطلوب بناء نظام حسابات وصلاحيات لمنصة Onlenco.

الأدوار:
1. Student
2. Academic Admin
3. Finance Admin
4. Super Admin
5. Content Manager

المطلوب:
1. Custom User Model يعتمد على email.
2. Roles واضحة.
3. Permissions لكل API.
4. لا يستطيع الطالب رؤية بيانات طالب آخر.
5. لا يستطيع Academic Admin مراجعة المدفوعات.
6. لا يستطيع Finance Admin تعديل المحتوى التعليمي.
7. لا يستطيع Content Manager رؤية إيصالات الدفع.
8. Super Admin يرى كل شيء.
9. دعم preferred_language: ar/en.
10. دعم account status: active/suspended/pending.

APIs:
- register
- login
- logout
- me
- update profile
- change password

اختبارات:
- student isolation
- role permissions
- login/register
- protected endpoints
```

---

## Prompt 3 — بناء Curriculum: Level → Unit → 3 Lessons

```text
أنت خبير EdTech وDjango Backend Engineer.

المطلوب بناء نظام Curriculum لمنصة Onlenco.

القاعدة المعتمدة:
CEFR Level → Unit → 3 Lessons

المستويات:
A0, A1, A2, B1, B2, C1, C2

كل Level يحتوي على عدة Units.
كل Unit تحتوي إلزامياً على 3 Lessons أو أقل في مرحلة التحرير، ولا يتم نشر Unit إلا إذا اكتملت 3 Lessons.
كل Lesson يحتوي على:
- title_ar
- title_en
- description_ar
- description_en
- short_video_url
- grammar_focus
- vocabulary_focus
- speaking_goal
- listening_goal
- reading_goal
- writing_goal
- cefr_level
- order
- is_active

المطلوب:
1. إنشاء models:
   - CEFRLevel
   - Unit
   - Lesson
   - LessonActivity
   - LessonQuiz
   - QuizQuestion
   - QuizAnswer
2. فرض قاعدة أن كل Unit لا تتجاوز 3 دروس.
3. API لإرجاع المنهج حسب مستوى الطالب.
4. API لبدء درس.
5. API لإنهاء درس.
6. API لإرجاع تقدم الطالب داخل الوحدة.
7. Seed data لمستويات A0 و A1 و A2 كبداية.
8. Tests للتأكد من:
   - كل Unit لا تتجاوز 3 دروس.
   - لا يمكن نشر Unit بدون 3 دروس.
   - لا يمكن ربط Lesson بمستوى CEFR غير صحيح.
   - ترتيب الدروس يعمل.
```

---

## Prompt 4 — اختبار تحديد المستوى الكتابي

```text
أنت Senior Django Engineer وخبير Assessment Systems.

المطلوب بناء اختبار تحديد المستوى الكتابي لمنصة Onlenco.

الاختبار في النسخة الأولى يكون:
- Multiple Choice Questions
- سهل في البداية
- يتدرج من A0 إلى C2
- يختبر Grammar, Vocabulary, Reading, Sentence Structure

المطلوب:
1. إنشاء module داخل placement باسم written_test.
2. إنشاء models:
   - PlacementTest
   - PlacementQuestion
   - PlacementChoice
   - PlacementAttempt
   - PlacementAnswer
   - PlacementResult
3. كل سؤال يجب أن يحتوي:
   - skill_type: grammar/vocabulary/reading/writing
   - cefr_level
   - difficulty
   - question_text_ar
   - question_text_en
   - choices
   - correct_choice
   - explanation_ar
   - explanation_en
4. إنشاء API:
   - start placement test
   - submit answer
   - finish test
   - get written score
5. حساب النتيجة:
   - score per skill
   - estimated CEFR level
   - weak areas
   - strong areas
6. إنشاء seed questions:
   - 20 سؤال A0
   - 20 سؤال A1
   - 20 سؤال A2
7. الاختبار يجب أن يكون قابلاً للتوسع لاحقاً Adaptive Test.
8. أضف tests كاملة.
```

---

## Prompt 5 — اختبار تحديد المستوى الشفهي مع AI Avatar

```text
أنت AI Product Engineer متخصص في Voice AI وDjango APIs.

المطلوب بناء نظام اختبار تحديد المستوى الشفهي في Onlenco.

التجربة المطلوبة:
- يظهر للطالب AI Tutor Avatar.
- الشخصية تتحدث بالصوت.
- تتحرك الشفاه والعيون في الواجهة.
- تسأل الطالب أسئلة بسيطة.
- الطالب يرد بالصوت.
- النظام يحول الصوت إلى نص.
- النظام يحلل:
  - pronunciation
  - fluency
  - grammar
  - vocabulary
  - confidence
  - response relevance

المطلوب Backend:
1. إنشاء models:
   - SpeakingPlacementSession
   - SpeakingQuestion
   - SpeakingAnswer
   - SpeakingAssessmentResult
2. إنشاء services:
   - SpeechToTextService
   - PronunciationScoringService
   - SpeakingLevelEstimator
   - AvatarPromptService
3. إنشاء API:
   - start speaking test
   - get next speaking question
   - upload audio answer
   - get speaking feedback
   - finish speaking test
4. الأسئلة الأولية:
   - What is your name?
   - Where are you from?
   - How old are you?
   - What do you do?
   - Why do you want to learn English?
   - Describe your daily routine.
5. يجب أن يكون الاختبار تدريجياً:
   - إذا الطالب ضعيف، ابق في A0/A1.
   - إذا جيد، انتقل لأسئلة A2/B1.
6. لا تربط النظام بمزود واحد فقط.
   أنشئ provider interface بحيث يمكن استخدام OpenAI أو Google أو Azure أو مزود آخر.
7. أضف mock provider للاختبارات.
8. أضف tests.
```

---

## Prompt 6 — إنشاء Student Learning Profile

```text
أنت Senior Backend Engineer.

المطلوب بناء Student Learning Profile بعد اختبار تحديد المستوى.

بعد انتهاء:
1. Written Placement Test
2. Speaking Placement Test

يجب إنشاء ملف تعلم ذكي للطالب يحتوي على:
- final_cefr_level
- written_score
- speaking_score
- grammar_score
- vocabulary_score
- reading_score
- writing_score
- pronunciation_score
- fluency_score
- weak_skills
- strong_skills
- recommended_start_level
- recommended_first_unit
- recommended_first_lesson
- learning_goal
- confidence_score
- theta_score

المطلوب:
1. إنشاء app learning_profiles.
2. إنشاء models:
   - StudentLearningProfile
   - StudentSkillMastery
   - StudentWeakness
   - StudentStrength
   - StudentLearningRecommendation
3. إنشاء service:
   - LearningProfileBuilderService
4. ربطه مع placement.
5. بعد نهاية الاختبار يتم إنشاء profile تلقائياً.
6. إنشاء API:
   - get my learning profile
   - update learning goal
   - get recommended next lesson
7. أضف tests.
```

---

## Prompt 7 — CEFR Mapping Engine

```text
أنت EdTech Standards Engineer.

المطلوب بناء CEFR Mapping Engine.

المحرك يجب أن يربط كل شيء بمستوى CEFR:
- Student
- Level
- Unit
- Lesson
- Activity
- Exercise
- Quiz Question
- Placement Question
- Library Item
- Speaking Question

المطلوب:
1. إنشاء app cefr_mapping.
2. إنشاء models أو shared choices:
   - CEFRLevel: A0, A1, A2, B1, B2, C1, C2
   - CEFRSkillDescriptor
3. إنشاء services:
   - CEFRPlacementEstimator
   - CEFRProgressEvaluator
   - CEFRContentMatcher
4. إنشاء API:
   - get CEFR levels
   - get descriptors by level
   - get content by CEFR
5. ضمان أن أي Lesson أو Exercise بدون CEFR level لا يتم نشره.
6. أضف validation و tests.
```

---

## Prompt 8 — Adaptive Learning Engine

```text
أنت Adaptive Learning Engineer.

المطلوب بناء Adaptive Learning Engine لمنصة Onlenco.

المحرك يجب أن:
- يتابع أخطاء الطالب.
- يصنف الخطأ: Grammar, Vocabulary, Pronunciation, Listening, Reading, Writing.
- يحدث Skill Mastery.
- يحدث theta_score.
- يقترح تمارين إضافية.
- يحدد الدرس التالي المناسب.
- يزيد أو يقلل صعوبة التمارين.

المطلوب:
1. إنشاء app adaptive_learning.
2. إنشاء models:
   - UserError
   - UserWeakness
   - SkillMastery
   - AdaptiveRecommendation
   - DifficultyAdjustmentLog
3. إنشاء services:
   - ErrorClassifierService
   - SkillMasteryUpdater
   - NextLessonRecommender
   - RemedialExerciseGenerator
4. عند كل Quiz أو Exercise:
   - سجل الخطأ.
   - حدث المهارة.
   - حدث profile.
   - اقترح next action.
5. API:
   - get my weaknesses
   - get recommended exercises
   - get next lesson
6. أضف tests.
```

---

## Prompt 9 — Lessons, Exercises & Quizzes

```text
أنت Senior EdTech Backend Engineer.

المطلوب بناء نظام الدروس والتمارين والكويزات.

كل Lesson يحتوي على:
- فيديو شرح قصير
- Vocabulary section
- Grammar section
- Listening activity
- Reading activity
- Writing activity
- Speaking activity
- Quiz بعد الدرس

المطلوب:
1. models:
   - LessonProgress
   - ActivityAttempt
   - QuizAttempt
   - QuizAnswerAttempt
2. API:
   - start lesson
   - get lesson activities
   - submit activity
   - start quiz
   - submit quiz answer
   - finish quiz
   - complete lesson
3. عند نهاية الكويز:
   - تحديث Learning Profile
   - إرسال الأخطاء إلى Adaptive Learning
   - منح XP
   - تحديث streak
4. يجب دعم العربية والإنجليزية.
5. أضف tests.
```

---

## Prompt 10 — AI Tutor نصي وصوتي

```text
أنت AI Tutor Systems Engineer.

المطلوب بناء AI Tutor في Onlenco.

AI Tutor يجب أن:
- يعرف مستوى الطالب.
- يعرف أخطاء الطالب السابقة.
- يعرف الدرس الحالي.
- يعرف نقاط الضعف.
- يتحدث بالعربية عند الشرح إذا احتاج الطالب.
- يدرب الطالب بالإنجليزية.
- يعطي micro-exercises.
- يصحح pronunciation feedback عند وجود صوت.
- يسجل كل استخدام في AIUsageLog.

المطلوب:
1. إنشاء app ai_tutor.
2. إنشاء models:
   - AITutorSession
   - AITutorMessage
   - AITutorVoiceMessage
   - AIUsageLog
   - MicroExercise
3. إنشاء services:
   - TutorContextBuilder
   - TutorPromptBuilder
   - TutorResponseService
   - TutorSafetyService
   - TutorUsageTracker
4. إنشاء APIs:
   - start tutor session
   - send text message
   - send voice message
   - get tutor feedback
   - generate micro exercise
5. لا تجعل LLM يعرف كل شيء مباشرة.
   ابني context من:
   - learning profile
   - current lesson
   - recent mistakes
   - CEFR level
6. أضف limits للاستخدام حسب subscription plan.
7. أضف tests.
```

---

## Prompt 11 — Speech Assessment Engine

```text
أنت Speech AI Engineer.

المطلوب بناء Speech Assessment Engine مستقل داخل Onlenco.

المحرك مسؤول عن:
- استقبال صوت الطالب.
- تحويل الصوت إلى نص.
- تقييم النطق.
- تقييم الطلاقة.
- مقارنة النص المطلوب بالنطق الفعلي.
- استخراج الكلمات التي نطقها خطأ.
- تقديم feedback بسيط للطالب.

المطلوب:
1. إنشاء app speech_assessment.
2. إنشاء models:
   - SpeechAttempt
   - PronunciationIssue
   - SpeakingFeedback
3. إنشاء provider interface:
   - BaseSpeechProvider
   - MockSpeechProvider
   - OpenAISpeechProvider لاحقاً
4. إنشاء scoring:
   - pronunciation_score
   - fluency_score
   - accuracy_score
   - pace_score
5. API:
   - submit speech attempt
   - get speech feedback
6. دعم lesson speaking exercises و placement speaking test.
7. أضف tests باستخدام mock audio result.
```

---

## Prompt 12 — Gamification Engine

```text
أنت Gamification Product Engineer.

المطلوب بناء Gamification Engine لمنصة Onlenco.

العناصر:
- XP Points
- Badges
- Daily Streak
- Weekly Challenges
- Lesson Completion Rewards
- Speaking Practice Rewards
- Club Participation Rewards

المطلوب:
1. إنشاء app gamification.
2. إنشاء models:
   - XPTransaction
   - Badge
   - UserBadge
   - DailyStreak
   - Challenge
   - ChallengeProgress
3. أحداث تمنح XP:
   - إكمال درس.
   - إكمال كويز.
   - ممارسة Speaking.
   - حضور نادي المخاطبة.
   - المحافظة على streak.
4. API:
   - get my XP
   - get my badges
   - get leaderboard لاحقاً
   - get daily streak
5. ربطه مع lessons, quizzes, ai_tutor, weekly_club.
6. أضف tests.
```

---

## Prompt 13 — Smart Motivation & Encouragement

```text
أنت Behavioral Product Engineer.

المطلوب بناء Smart Motivation & Encouragement Engine.

المحرك يرسل رسائل ذكية حسب:
- نشاط الطالب.
- مستواه.
- أخطائه.
- تقدمه.
- انقطاعه.
- إكمال درس صعب.
- انخفاض الحماس.
- قرب انتهاء الاشتراك.

أنواع الرسائل:
- تهنئة.
- تشجيع.
- تذكير.
- هدف يومي.
- عودة بعد انقطاع.
- نصيحة تعليمية.

المطلوب:
1. إنشاء app motivation.
2. إنشاء models:
   - MotivationMessageTemplate
   - UserMotivationMessage
   - MotivationTrigger
3. إنشاء services:
   - MotivationTriggerEvaluator
   - PersonalizedMessageBuilder
   - MotivationDispatchService
4. دعم العربية والإنجليزية.
5. ربطها مع notifications.
6. API:
   - get my motivation messages
   - mark message as read
7. Celery task يومي لفحص الطلاب وإرسال الرسائل.
8. أضف tests.
```

---

## Prompt 14 — Behavioral Analytics Engine

```text
أنت Data Product Engineer.

المطلوب بناء Behavioral Analytics Engine.

المحرك يجب أن يحلل:
- login frequency
- lessons completed
- quiz attempts
- speaking practice count
- AI tutor usage
- days inactive
- improvement rate
- churn_risk_score
- engagement_score

المطلوب:
1. إنشاء app behavioral_analytics.
2. إنشاء models:
   - StudentActivityLog
   - EngagementSnapshot
   - ChurnRiskSnapshot
   - LearningProgressSnapshot
3. إنشاء services:
   - ActivityTracker
   - EngagementScoreCalculator
   - ChurnRiskCalculator
   - ProgressAnalyzer
4. Celery task يومي:
   - احسب engagement_score
   - احسب churn_risk_score
   - أرسل تنبيه للمعلم إذا الطالب معرض للانقطاع
5. API للـ Admin:
   - students at risk
   - engagement overview
   - progress trends
6. أضف tests.
```

---

## Prompt 15 — لوحة الطالب Student Dashboard

```text
أنت Senior Frontend + Django Templates Engineer.

المطلوب بناء Student Dashboard لمنصة Onlenco.

الواجهة يجب أن تكون حديثة مثل الصور المرفقة:
- ألوان زرقاء وبيضاء.
- إحساس AI Learning.
- Progress cards.
- AI Tutor card.
- Current Unit card.
- Next Lesson card.
- XP and Streak.
- Speaking practice shortcut.
- Weekly Club invitation.
- Motivation messages.

المطلوب:
1. بناء dashboard responsive.
2. دعم Arabic/English.
3. دعم RTL/LTR.
4. عرض:
   - CEFR level
   - current unit
   - lesson progress
   - XP
   - badges
   - daily streak
   - weak skills
   - recommended next lesson
5. لا تجعلها مجرد HTML ثابت.
   اربطها بالـ APIs أو selectors.
6. أضف frontend tests إن وجدت.
```

---

## Prompt 16 — لوحة المعلم Academic Admin

```text
أنت Senior Product Engineer.

المطلوب بناء Academic Admin Dashboard.

المعلم يجب أن يستطيع:
1. مشاهدة الطلاب الجدد.
2. فتح Student Learning Profile.
3. مشاهدة نتائج placement.
4. مشاهدة نقاط الضعف.
5. مشاهدة speaking feedback.
6. تعيين تمارين إضافية.
7. إرسال رسالة شخصية للطالب.
8. مشاهدة الطلاب المعرضين للانقطاع.
9. إدارة نادي المخاطبة الأسبوعي.
10. إضافة ملاحظات إدارية على الطالب.

المطلوب:
- app academic_admin
- models:
  - AcademicNote
  - AssignedExercise
  - TeacherStudentMessage
- APIs:
  - list students
  - get student profile
  - assign exercise
  - create academic note
  - send message
  - list at-risk students
- Dashboard UI احترافي.
- Tests.
```

---

## Prompt 17 — Finance Admin + Payments + Bankak

```text
أنت Senior FinTech Backend Engineer.

المطلوب بناء نظام المدفوعات والاشتراكات في Onlenco.

في المرحلة الأولى الدفع يدوي:
- الطالب يحول عبر Bankak أو وسيلة محلية.
- يرفع صورة الإيصال.
- Finance Admin يراجع الإيصال.
- عند الموافقة يتم تفعيل الاشتراك أو نادي المخاطبة.

المطلوب:
1. إنشاء apps:
   - subscriptions
   - payments
   - finance_admin
2. models:
   - SubscriptionPlan
   - UserSubscription
   - PaymentReceipt
   - PaymentReview
   - ClubPayment
3. حالات الدفع:
   - pending
   - under_review
   - approved
   - rejected
4. API:
   - list plans
   - subscribe
   - upload receipt
   - get payment status
   - finance review payment
5. عند الموافقة:
   - تفعيل الاشتراك.
   - إرسال notification.
   - فتح المحتوى أو النادي.
6. أضف audit log.
7. أضف tests.
```

---

## Prompt 18 — Weekly English Club

```text
أنت EdTech Product Engineer.

المطلوب بناء Weekly English Club module.

المميزات:
- إنشاء جلسة نادي أسبوعية.
- تحديد topic.
- تحديد CEFR target level.
- تحديد Google Meet link.
- تحديد المقاعد المتاحة.
- فتح التسجيل.
- دفع رسوم رمزية.
- تفعيل الطالب بعد مراجعة الدفع.
- تسجيل الحضور.
- إضافة ملاحظات بعد الجلسة.

المطلوب:
1. إنشاء app weekly_club.
2. models:
   - WeeklyClubSession
   - ClubRegistration
   - ClubAttendance
   - ClubFeedback
3. API:
   - list upcoming clubs
   - register for club
   - upload club payment receipt
   - get my club registrations
   - admin approve registration
   - teacher add feedback
4. ربطه مع gamification:
   - الطالب يحصل XP عند الحضور.
5. ربطه مع notifications:
   - إرسال رابط الحضور بعد الموافقة.
6. Tests.
```

---

## Prompt 19 — Digital Library

```text
أنت EdTech Content Engineer.

المطلوب بناء Digital Library داخل Onlenco.

المكتبة تحتوي:
- قصص قصيرة.
- كتب مبسطة.
- فيديوهات طويلة.
- مقالات.
- Vocabulary extraction.
- Grammar extraction.
- أسئلة فهم.

كل عنصر يجب أن يكون مربوطاً بـ CEFR Level.

المطلوب:
1. إنشاء app digital_library.
2. models:
   - LibraryItem
   - LibraryCategory
   - ExtractedVocabulary
   - ExtractedGrammarPoint
   - ComprehensionQuestion
   - UserLibraryProgress
3. API:
   - list library items by CEFR
   - open item
   - mark progress
   - get vocabulary
   - answer comprehension questions
4. AI Service:
   - extract vocabulary
   - extract grammar
   - generate questions
5. Tests.
```

---

## Prompt 20 — Notifications + Emails

```text
أنت Backend Engineer متخصص Notifications.

المطلوب بناء Notification Management System.

أنواع الإشعارات:
- Welcome Email
- Placement Completed
- New Recommended Lesson
- Motivation Message
- Subscription Expiring
- Payment Approved
- Payment Rejected
- Weekly Club Invitation
- Club Link Sent
- Teacher Message
- At-risk student alert للمعلم

المطلوب:
1. إنشاء app notifications.
2. models:
   - Notification
   - EmailTemplate
   - NotificationPreference
   - NotificationLog
3. دعم:
   - in-app notifications
   - email
   - future SMS/WhatsApp provider interface
4. دعم العربية والإنجليزية.
5. استخدام Celery للإرسال.
6. APIs:
   - get notifications
   - mark as read
   - update preferences
7. Tests.
```

---

## Prompt 21 — Admin Dashboard بدل Django Admin

```text
أنت Senior Full Stack Engineer.

المطلوب بناء Admin Panel مخصص لمنصة Onlenco بدلاً من الاعتماد على Django Admin فقط.

الأدوار:
1. Super Admin
2. Academic Admin
3. Finance Admin
4. Content Manager

كل دور يرى ما يخصه فقط.

Super Admin:
- users overview
- revenue overview
- engagement overview
- subscriptions
- AI usage
- churn risk
- platform settings

Academic Admin:
- students
- learning profiles
- placement results
- weak skills
- assigned exercises
- weekly club
- academic notes

Finance Admin:
- payment receipts
- payment reviews
- subscription activation
- club payment approval

Content Manager:
- CEFR levels
- units
- lessons
- exercises
- quizzes
- library items

المطلوب:
- بناء dashboards منفصلة.
- تطبيق permissions قوية.
- APIs منفصلة.
- UI responsive.
- RTL/LTR.
- Tests للـ permissions.
```

---

## Prompt 22 — REST API Contracts

```text
أنت API Architect.

المطلوب إنشاء API Documentation كاملة لمنصة Onlenco.

اكتب endpoints لكل modules:

accounts
curriculum
placement
learning_profiles
lessons
exercises
assessments
ai_tutor
speech_assessment
adaptive_learning
cefr_mapping
gamification
motivation
behavioral_analytics
digital_library
weekly_club
subscriptions
payments
notifications
academic_admin
finance_admin
dashboards

لكل endpoint اكتب:
- Method
- URL
- Auth required
- Permissions
- Request body
- Response body
- Error cases
- Example JSON

المطلوب إنشاء ملف:
docs/API_CONTRACTS.md

ويجب تجهيز OpenAPI/Swagger لاحقاً.
```

---

## Prompt 23 — واجهات Onlenco حسب الصور المرفقة

```text
أنت Senior UI/UX Engineer.

المطلوب بناء واجهات Onlenco مستوحاة من الصور المرفقة.

الهوية:
- Brand: Onlenco
- Primary color: modern blue
- White/soft blue background
- AI learning feeling
- Friendly, global, supportive
- Student-centered
- Game-like not boring training

الواجهات المطلوبة:
1. Landing Page
2. Student Dashboard
3. Placement Test Page
4. Speaking Test with AI Avatar
5. AI Tutor Chat Page
6. Lesson Page
7. Unit Progress Page
8. Weekly English Club Page
9. Academic Admin Dashboard
10. Finance Admin Dashboard
11. Super Admin Dashboard

المطلوب:
- Responsive design.
- Arabic/English.
- RTL/LTR.
- Clean cards.
- Smooth animations.
- Progress rings.
- XP badges.
- Speaking microphone UI.
- Avatar area جاهز للدمج مع خدمة AI Avatar لاحقاً.
- لا تستخدم تصميم تقليدي ممل.
```

---

## Prompt 24 — Seed Data احترافي

```text
أنت Data Engineer لمنصة EdTech.

المطلوب إنشاء seed data لمنصة Onlenco.

البيانات المطلوبة:
1. CEFR levels: A0 to C2
2. لكل مستوى:
   - 2 Units كبداية
   - كل Unit بها 3 Lessons
3. لكل Lesson:
   - 5 vocabulary words
   - grammar focus
   - speaking goal
   - 5 quiz questions
4. Placement written questions:
   - A0: 20
   - A1: 20
   - A2: 20
5. Speaking placement questions:
   - A0/A1/A2/B1
6. Badges:
   - First Lesson
   - First Speaking Practice
   - 3-Day Streak
   - Weekly Club Participant
7. Subscription plans:
   - Free Trial
   - Monthly
   - Quarterly
8. Email templates:
   - welcome
   - placement completed
   - payment approved
   - motivation reminder

المطلوب:
- management command:
  python manage.py seed_onlenco_core
- يجب أن يكون idempotent.
- لا يكرر البيانات إذا تم تشغيله أكثر من مرة.
- Tests.
```

---

## Prompt 25 — Security + Permissions

```text
أنت Security Engineer.

المطلوب مراجعة صلاحيات Onlenco.

الأدوار:
- Student
- Academic Admin
- Finance Admin
- Super Admin
- Content Manager

المطلوب:
1. لا يستطيع الطالب رؤية بيانات طالب آخر.
2. لا يستطيع Academic Admin مراجعة المدفوعات.
3. لا يستطيع Finance Admin تعديل المحتوى الأكاديمي.
4. لا يستطيع Content Manager رؤية إيصالات الدفع.
5. Super Admin يرى كل شيء.
6. حماية ملفات الصوت والإيصالات.
7. حماية API من الاستخدام الزائد.
8. Rate limiting للـ AI Tutor.
9. Audit log للعمليات الحساسة.
10. Tests لكل permission.
```

---

## Prompt 26 — QA Testing

```text
أنت QA Automation Engineer.

المطلوب بناء خطة اختبارات شاملة لمنصة Onlenco.

اختبر السيناريو الكامل:

Student Journey:
1. register
2. receive welcome notification
3. start placement written test
4. finish written test
5. start speaking test
6. upload voice answer
7. get CEFR level
8. create learning profile
9. see recommended unit
10. complete lesson
11. complete quiz
12. get XP
13. use AI Tutor
14. receive motivation message
15. register weekly club
16. upload payment receipt
17. get approved
18. attend club
19. receive feedback

Academic Admin Journey:
1. login
2. view new students
3. open student profile
4. review weaknesses
5. assign exercise
6. send message
7. manage weekly club
8. add feedback

Finance Admin Journey:
1. login
2. view pending receipts
3. approve receipt
4. activate subscription
5. reject invalid receipt

Super Admin Journey:
1. view platform analytics
2. view subscriptions
3. view churn risk
4. view AI usage

المطلوب:
- Unit tests
- Integration tests
- API tests
- Permission tests
- E2E test scenarios
- إنشاء ملف docs/QA_TEST_PLAN.md
```

---

## Prompt 27 — Deployment Production

```text
أنت DevOps Engineer.

المطلوب تجهيز Onlenco للتشغيل Production.

Stack:
- Django
- Django REST Framework
- PostgreSQL
- Redis
- Celery
- Nginx
- Docker
- Docker Compose
- Gunicorn
- Static/Media handling

المطلوب:
1. Dockerfile production-ready.
2. docker-compose.yml للتطوير.
3. docker-compose.prod.yml للإنتاج.
4. إعداد .env.example.
5. إعداد logging.
6. إعداد health checks.
7. إعداد migrations.
8. إعداد collectstatic.
9. إعداد Celery worker.
10. إعداد Celery beat.
11. إعداد backup strategy.
12. إعداد docs/DEPLOYMENT.md.
13. CI/CD لاحقاً.
```
