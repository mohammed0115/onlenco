## Prompt 09 — ربط AI Tutor بكل Learning Unit

أنت مهندس AI Tutor ومصمم تجربة تعليمية.

المشروع: Onlenco Academy

المطلوب:
ربط AI Tutor بكل Learning Unit بحيث لا يكون محادثة عامة، بل تدريب مرتبط بالدرس الحالي.

عند ضغط الطالب:
Practice with AI Tutor

يجب أن ينتقل AI Tutor بسياق الدرس:
- unit number
- lesson title
- cefr level
- new language
- vocabulary
- grammar focus
- speaking goal
- expected answers
- correction style
- student progress
- quiz performance إن وجد

قواعد AI Tutor:
- American English
- Beginner-friendly
- short sentences
- one correction at a time
- encourage student
- لا يخرج خارج موضوع الدرس
- لا يعطي إجابات طويلة
- لا يتكلم بسرعة
- يدعم الطالب العربي بشرح بسيط عند الحاجة
- لا يقول رموز أو underscores
- لا يقرأ placeholders بشكل مزعج

أضف service:
lesson_ai_context_builder.py

يبني prompt داخلي للـ AI Tutor من بيانات الدرس.

Prompt يجب أن يحتوي:
- System instruction
- Lesson context
- Allowed vocabulary
- Grammar focus
- Speaking task
- Correction rules
- Safety fallback
- Arabic support instruction
- Completion criteria

أضف tracking:
- started_at
- completed_at
- attempts
- tutor_feedback
- pronunciation_notes إن وجدت
- score إن وجد

أضف اختبارات:
- test_ai_tutor_receives_lesson_context
- test_ai_tutor_prompt_contains_vocabulary
- test_ai_tutor_prompt_contains_grammar_focus
- test_ai_tutor_uses_beginner_style
- test_ai_tutor_does_not_start_general_chat
- test_ai_tutor_tracks_lesson_practice_completion
- test_ai_tutor_supports_arabic_explanation_when_needed

التقرير النهائي بالعربي:
- كيف تم ربط AI Tutor بالدرس؟
- هل التدريب مرتبط بموضوع الدرس؟
- هل مناسب للمبتدئ؟
- هل يحفظ progress؟
- ما المشاكل المتبقية؟
