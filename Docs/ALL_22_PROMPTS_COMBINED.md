# Onlenco — All 22 Gap-Closing Prompts




---

# 0. Master Prompt — فحص شامل للنظام وتثبيت الخطة

```text
You are a senior Python/Django software architect and AI product engineer.

I have a Django project called Onlenco. It is an English learning platform with apps such as accounts, lessons, placement, tutor, dictionary, library, club, payments, and analytics.

The target product is an advanced AI-powered adaptive English learning system. It must learn from user mistakes, classify errors, predict weaknesses, adapt exercise difficulty, generate personalized exercises, and continuously update the student learning profile.

Your task:
1. Read the full codebase carefully.
2. Do not modify code yet.
3. Analyze the current architecture, apps, models, views, templates, services, settings, and tests.
4. Compare the current system with the target adaptive learning system.
5. Identify all missing gaps in:
   - Learning data model
   - Error analysis
   - Weakness prediction
   - Adaptive difficulty
   - Personalized exercise generation
   - AI tutor logic
   - Placement test
   - REST APIs
   - Analytics
   - Security
   - Testing
   - Deployment
   - UI/UX
   - i18n Arabic/English support
6. Create a phased implementation plan.
7. For each phase, list:
   - Files to create
   - Files to modify
   - Models to add
   - Services to add
   - APIs to add
   - Tests to add
   - Expected validation commands

Important constraints:
- Do not break existing pages.
- Do not remove existing apps unless necessary.
- Preserve current functionality.
- Use clean architecture, SOLID, DRY, service layer, and clear separation of concerns.
- Prefer incremental migration.
- Every implementation step must be testable.

Output:
- Current system summary
- Gap analysis table
- Priority ranking
- Phase-by-phase execution plan
- Risk assessment
- Recommended first implementation phase
```



---

# 1. Prompt — إصلاح الأساس المعماري والإعدادات

```text
You are a senior Django production architect.

Analyze and refactor the project settings and structure to make the system production-ready without changing business behavior.

Current problem:
The project is a working MVP but needs better production architecture, secure settings, environment separation, and maintainable configuration.

Tasks:
1. Inspect the current Django settings.
2. Split settings into:
   - config/settings/base.py
   - config/settings/development.py
   - config/settings/production.py
   - config/settings/test.py
3. Move all secrets to environment variables.
4. Remove unsafe defaults such as:
   - DEBUG=True by default
   - ALLOWED_HOSTS=["*"]
   - hardcoded SECRET_KEY
5. Configure:
   - PostgreSQL support
   - Static files
   - Media files
   - Logging
   - Email backend
   - CSRF trusted origins
   - Secure cookies for production
6. Keep SQLite allowed only for local development.
7. Add .env.example.
8. Make sure manage.py still works.
9. Add documentation in README for local setup.

Constraints:
- Do not remove current apps.
- Do not change business logic.
- Do not break templates.
- Use environment variables cleanly.
- Keep development simple.

Expected output:
- Modified files list
- New settings structure
- .env.example
- README setup section
- Validation commands:
  python manage.py check
  python manage.py makemigrations --check
  python manage.py migrate
  python manage.py test
```



---

# 2. Prompt — بناء Learning Core Data Model

```text
You are a senior Django backend engineer specializing in adaptive learning systems.

The current system has lessons, quizzes, placement tests, and AI tutor, but it lacks a real adaptive learning data model.

Your task is to create a new Django app called learning_core that contains the foundation for the AI adaptive learning engine.

Create models for:
1. Skill
   - name
   - category: grammar, vocabulary, pronunciation, listening, reading, writing, speaking
   - cefr_level
   - description
   - is_active

2. GrammarTopic
   - name
   - slug
   - cefr_level
   - description
   - related_skills

3. StudentLearningProfile
   - user
   - current_cefr_level
   - theta_score
   - learning_speed
   - confidence_score
   - last_activity_at
   - metadata JSON

4. SkillMastery
   - user
   - skill
   - mastery_score 0-100
   - attempts_count
   - correct_count
   - wrong_count
   - last_practiced_at

5. UserError
   - user
   - source_type: placement, quiz, tutor, writing, speaking, exercise
   - original_text
   - corrected_text
   - error_type: grammar, spelling, vocabulary, punctuation, word_order, pronunciation, comprehension
   - grammar_topic
   - skill
   - severity 1-10
   - explanation
   - ai_confidence
   - created_at

6. UserWeakness
   - user
   - skill
   - grammar_topic
   - weakness_score
   - frequency
   - severity_average
   - recency_score
   - priority_score
   - status: active, improving, resolved
   - updated_at

7. AdaptiveExercise
   - topic
   - skill
   - cefr_level
   - difficulty_score
   - question_type
   - question
   - options JSON
   - correct_answer
   - explanation
   - generated_by_ai
   - metadata JSON

8. ExerciseAttempt
   - user
   - exercise
   - user_answer
   - is_correct
   - score
   - time_spent_seconds
   - feedback
   - created_at

9. LearningRecommendation
   - user
   - recommendation_type
   - title
   - description
   - priority
   - related_skill
   - related_weakness
   - status

Also:
- Register models in admin.py.
- Add indexes where useful.
- Create migrations.
- Add tests for model creation and relationships.
- Do not break existing apps.

After implementation run:
python manage.py makemigrations
python manage.py migrate
python manage.py test learning_core
python manage.py check

Output:
- Files created
- Models added
- Migration name
- Tests added
- Any integration notes with existing apps
```



---

# 3. Prompt — محرك تحليل الأخطاء Error Analysis Engine

```text
You are a senior AI backend engineer.

Build an Error Analysis Engine for the Onlenco Django platform.

Goal:
When a student writes an answer, sentence, paragraph, or quiz response, the system must detect language errors and save structured UserError records.

Create a service:
learning_core/services/error_analyzer.py

The service must expose:
analyze_text(user, text, source_type="writing", context=None)

It should:
1. Send text to an OpenAI-compatible API if configured.
2. Return structured JSON with:
   - original_text
   - corrected_text
   - errors list
   - each error:
     - error_type
     - original_fragment
     - corrected_fragment
     - grammar_topic
     - skill_category
     - severity 1-10
     - explanation
     - confidence
3. Save each error as UserError.
4. If AI is not configured or fails, use a safe fallback heuristic analyzer.
5. Never crash the user flow because of AI failure.
6. Validate AI JSON strictly.
7. Add logging for AI failures.
8. Add tests for:
   - successful AI response
   - malformed AI response
   - fallback analyzer
   - UserError creation
   - empty text handling

Prompt for AI analyzer should be deterministic and return valid JSON only.

Important:
- Do not expose raw AI errors to users.
- Do not store API keys in code.
- Use service-layer architecture.
- Keep the service reusable from placement, quiz, tutor, and future writing modules.

Expected files:
- learning_core/services/error_analyzer.py
- learning_core/services/prompts.py
- learning_core/tests/test_error_analyzer.py

Validation:
python manage.py test learning_core
python manage.py check
```



---

# 4. Prompt — محرك نقاط الضعف Weakness Prediction Engine

```text
You are a senior machine learning engineer and Django backend developer.

Build a Weakness Prediction Engine for the Onlenco adaptive English learning platform.

Current gap:
The system stores quiz progress but does not convert student mistakes into weakness profiles.

Create:
learning_core/services/weakness_engine.py

Main function:
update_user_weaknesses(user)

Logic:
1. Read recent UserError records for the user.
2. Group errors by skill and grammar_topic.
3. Calculate:
   - frequency
   - average severity
   - recency score
   - priority score
4. Use the formula:
   priority_score = frequency_weight + severity_weight + recency_weight
5. Normalize weakness_score to 0-100.
6. Create or update UserWeakness records.
7. Mark old weaknesses as improving or resolved when error frequency drops.
8. Return top weaknesses sorted by priority.

Add function:
get_top_weaknesses(user, limit=3)

Initial implementation should be rule-based, not ML-heavy, because the project may not have enough historical data yet.

Later extension:
Prepare the service so Naive Bayes can be added after enough training data exists.

Also:
- Add tests using sample UserError data.
- Test priority ranking.
- Test weakness update.
- Test resolved/improving status.
- Connect it optionally after ExerciseAttempt and ErrorAnalysis.

Expected files:
- learning_core/services/weakness_engine.py
- learning_core/tests/test_weakness_engine.py

Validation:
python manage.py test learning_core
python manage.py check

Output:
- Explain the implemented scoring formula.
- Show examples of top 3 weaknesses generated from test data.
```



---

# 5. Prompt — محرك الصعوبة التكيفية Adaptive Difficulty / IRT

```text
You are a senior adaptive learning engineer.

Implement an Adaptive Difficulty Engine for Onlenco.

Goal:
The system must update the student's level dynamically after each exercise attempt.

Create:
learning_core/services/adaptive_difficulty.py

Use a simplified IRT-inspired model.

Data:
- StudentLearningProfile.theta_score
- AdaptiveExercise.difficulty_score
- ExerciseAttempt.is_correct
- ExerciseAttempt.score

Functions:
1. expected_score(theta, difficulty)
   Return probability of correct answer.

2. update_theta(user, exercise, attempt)
   Formula:
   theta_new = theta_old + alpha * (actual_score - expected_score)
   where alpha = 0.1 by default.

3. recommend_next_difficulty(user)
   Return a difficulty score slightly above current ability if user is performing well, or lower if struggling.

4. update_skill_mastery(user, skill, attempt)
   Update mastery score, attempts_count, correct_count, wrong_count.

5. get_learning_state(user)
   Return:
   - theta_score
   - CEFR level estimate
   - strongest skills
   - weakest skills
   - recommended difficulty

Requirements:
- Clamp theta_score to a safe range, for example -3 to +3.
- Clamp mastery_score to 0-100.
- Add tests for correct answer, wrong answer, repeated success, repeated failure.
- Do not break existing lesson quiz flow.
- Prepare integration points with ExerciseAttempt.

Expected files:
- learning_core/services/adaptive_difficulty.py
- learning_core/tests/test_adaptive_difficulty.py

Validation:
python manage.py test learning_core
python manage.py check

Output:
- Files changed
- Formula used
- Examples of theta updates
```



---

# 6. Prompt — توليد التمارين المخصصة Personalized Exercise Generator

```text
You are a senior AI product engineer.

Build a Personalized Exercise Generator for Onlenco.

Goal:
Generate English exercises based on the student's top weaknesses, CEFR level, and adaptive difficulty.

Create:
learning_core/services/exercise_generator.py

Main function:
generate_personalized_exercises(user, count_per_weakness=5)

Steps:
1. Load StudentLearningProfile.
2. Get top 3 UserWeakness records.
3. For each weakness:
   - determine skill
   - determine grammar topic
   - determine CEFR level
   - determine difficulty score
4. Use OpenAI-compatible API to generate exercises.
5. Validate JSON response.
6. Save generated exercises as AdaptiveExercise.
7. If AI fails, use local template-based fallback exercises.
8. Return list of generated exercises.

Exercise types:
- multiple_choice
- fill_blank
- correction
- sentence_building
- translation
- short_answer

AI output JSON format:
{
  "exercises": [
    {
      "question_type": "...",
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "...",
      "explanation": "...",
      "skill": "...",
      "grammar_topic": "...",
      "cefr_level": "A1/A2/B1/B2/C1",
      "difficulty_score": 0.0
    }
  ]
}

Requirements:
- No duplicate exercises in same batch.
- Store metadata including AI model name and prompt version.
- Add tests for AI success, AI failure, malformed JSON, fallback generation.
- Do not expose AI raw JSON directly to users.

Expected files:
- learning_core/services/exercise_generator.py
- learning_core/services/exercise_templates.py
- learning_core/tests/test_exercise_generator.py

Validation:
python manage.py test learning_core
python manage.py check

Output:
- Generated sample exercises
- Files changed
- How to call the service from views/API
```



---

# 7. Prompt — ربط النظام التكيفي مع اختبارات الدروس الحالية

```text
You are a senior Django engineer.

Integrate the new adaptive learning engine with the existing lessons and quizzes app.

Goal:
When a student answers lesson quiz questions, the system should:
1. Save the attempt.
2. Analyze wrong answers.
3. Update UserError.
4. Update UserWeakness.
5. Update SkillMastery.
6. Update theta_score.
7. Generate or recommend next exercises.

Tasks:
1. Inspect the existing lessons app models, views, and quiz submission flow.
2. Identify where quiz answers are submitted.
3. Add integration with:
   - ExerciseAttempt
   - ErrorAnalyzer
   - WeaknessEngine
   - AdaptiveDifficultyEngine
4. Do not break existing quiz UI.
5. Keep old LessonProgress working.
6. Add a service adapter if needed:
   lessons/services/adaptive_quiz_adapter.py
7. Add tests for:
   - correct quiz submission
   - wrong quiz submission
   - UserError created for wrong answer
   - UserWeakness updated
   - LessonProgress still works

Important:
- Use transactions where needed.
- AI failure must not break quiz submission.
- The student must still see normal quiz feedback.

Validation:
python manage.py test lessons learning_core
python manage.py check

Output:
- Modified files
- Integration points
- Tests added
- Risk notes
```



---

# 8. Prompt — تطوير Placement Test ليصبح تشخيصيًا

```text
You are a senior assessment and adaptive learning engineer.

Improve the existing placement test app.

Current issue:
Placement test only estimates CEFR level but does not create a full diagnostic profile.

Goal:
After placement test submission, the system should:
1. Estimate CEFR level.
2. Detect strengths and weaknesses.
3. Create StudentLearningProfile.
4. Create initial SkillMastery records.
5. Create initial UserWeakness records.
6. Recommend first learning path.
7. Save detailed diagnostic result.

Tasks:
1. Inspect the current placement app.
2. Keep existing UI working.
3. Extend placement logic to produce structured diagnostic JSON:
   - cefr_level
   - score
   - grammar_strengths
   - grammar_weaknesses
   - vocabulary_level
   - writing_quality
   - speaking_transcript_quality if available
   - recommended_lessons
   - recommended_exercises
4. Use ErrorAnalysisEngine on written answers.
5. Update StudentLearningProfile.theta_score.
6. Add tests for:
   - new user placement
   - existing user retake
   - AI placement success
   - AI placement fallback
   - weakness creation

Expected files:
- placement/services/diagnostic_engine.py
- placement/tests/test_diagnostic_placement.py
- possible updates to placement views/models

Validation:
python manage.py test placement learning_core
python manage.py check

Output:
- Explain how placement now initializes adaptive learning.
```



---

# 9. Prompt — بناء REST APIs باستخدام DRF

```text
You are a senior Django REST Framework API architect.

The current Onlenco system is mostly template-based. Build REST APIs without breaking the existing web UI.

Goal:
Expose the adaptive learning system through clean APIs for future mobile app, frontend app, and external integrations.

Tasks:
1. Install and configure Django REST Framework if not already installed.
2. Create API versioning structure:
   api/v1/
3. Add serializers and views for:
   - StudentLearningProfile
   - SkillMastery
   - UserError
   - UserWeakness
   - AdaptiveExercise
   - ExerciseAttempt
   - LearningRecommendation
4. Add endpoints:
   GET /api/v1/learning/profile/
   GET /api/v1/learning/weaknesses/
   GET /api/v1/learning/recommendations/
   POST /api/v1/exercises/generate/
   GET /api/v1/exercises/next/
   POST /api/v1/exercises/{id}/attempt/
   POST /api/v1/analyze-text/
   POST /api/v1/tutor/chat/
   POST /api/v1/placement/submit/
5. Add authentication using Django session auth first, and prepare for token auth later.
6. Add permissions so users only see their own data.
7. Add tests for API permissions and responses.
8. Add OpenAPI/Swagger documentation if possible.

Constraints:
- Do not remove existing templates.
- Do not expose other users' learning data.
- Keep APIs clean, predictable, and documented.

Expected files:
- api/v1/urls.py
- learning_core/api/serializers.py
- learning_core/api/views.py
- learning_core/tests/test_learning_api.py

Validation:
python manage.py test
python manage.py check

Output:
- Endpoint list
- Sample request/response
- Files changed
```



---

# 10. Prompt — تطوير AI Tutor ليصبح مدرسًا ذكيًا مرتبطًا بنقاط ضعف الطالب

```text
You are a senior AI tutor product engineer.

The current AI Tutor is a general chat. Improve it so it becomes personalized and connected to the student's learning profile.

Goal:
The AI Tutor should know:
- Student CEFR level
- Current weaknesses
- Recent errors
- Recent lessons
- Recommended practice
- Preferred language

Tasks:
1. Inspect the tutor app.
2. Create tutor/services/context_builder.py
3. Before sending a message to AI, build a safe context:
   - user CEFR level
   - top 3 weaknesses
   - recent UserError summaries
   - current lesson if available
   - language preference
4. Update tutor prompt so the AI:
   - explains simply
   - gives examples
   - corrects mistakes politely
   - does not give unrelated long answers
   - adapts explanation to CEFR level
   - can generate micro-exercises during chat
5. After each user message:
   - run ErrorAnalyzer on the student's English message
   - update weaknesses if needed
6. Add safeguards:
   - max context length
   - no raw private data
   - fallback response if AI fails
   - rate limiting placeholder
7. Add tests for:
   - context builder
   - tutor with weaknesses
   - AI failure fallback
   - user error creation from chat

Validation:
python manage.py test tutor learning_core
python manage.py check

Output:
- Updated tutor behavior
- Files changed
- Example prompt and response
```



---

# 11. Prompt — Learning Analytics Dashboard

```text
You are a senior Django analytics engineer and educational data analyst.

Improve the analytics app so it shows real learning analytics, not only business metrics.

Goal:
Admin and instructors should understand student progress, weaknesses, and system effectiveness.

Add analytics for:
1. Total active learners
2. CEFR distribution
3. Average mastery by skill
4. Top grammar weaknesses
5. Most common error types
6. Student improvement over time
7. Exercises generated by AI
8. Exercise success rate
9. Tutor usage
10. Placement test outcomes
11. At-risk students
12. Students with no progress in last 7 days

Tasks:
1. Inspect analytics app.
2. Add service:
   analytics/services/learning_analytics.py
3. Add queries using existing and new learning_core models.
4. Update admin analytics template.
5. Add charts using current frontend stack.
6. Add filters:
   - date range
   - CEFR level
   - skill
   - user
7. Add tests for analytics service.

Constraints:
- Keep page fast.
- Use aggregation queries.
- Avoid loading too many records into memory.
- Handle empty data gracefully.

Validation:
python manage.py test analytics learning_core
python manage.py check

Output:
- Dashboard metrics added
- Queries used
- Files changed
```



---

# 12. Prompt — UI/UX Gap Fixes للطالب

```text
You are a senior product designer and Django frontend engineer.

Improve the student learning experience in the existing Django templates.

Goal:
The student should clearly see:
- Current level
- Progress
- Weaknesses
- Recommended next practice
- Recent mistakes
- Personalized exercises
- AI tutor guidance

Tasks:
1. Inspect existing templates.
2. Improve dashboard/home for logged-in students.
3. Add sections:
   - My English Level
   - My Top Weaknesses
   - Recommended Practice
   - Continue Learning
   - Recent Mistakes
   - Ask AI Tutor
   - Weekly Progress
4. Use existing design style but make it cleaner and more professional.
5. Ensure responsive design for mobile and desktop.
6. Support Arabic and English layout.
7. Use Tailwind classes consistently.
8. Avoid heavy JavaScript unless needed.
9. Handle empty states beautifully:
   - New user without placement test
   - User without weaknesses
   - User without exercises
10. Add template tests or view tests where practical.

Constraints:
- Do not redesign everything from scratch.
- Improve incrementally.
- Do not break current navigation.

Validation:
python manage.py test
python manage.py check

Output:
- Templates modified
- Screens/pages improved
- Empty states added
```



---

# 13. Prompt — دعم عربي/إنجليزي احترافي i18n + RTL/LTR

```text
You are a senior Django i18n engineer.

Audit and improve Arabic/English support in Onlenco.

Goal:
The platform must support Arabic and English professionally, including translations and RTL/LTR layout.

Tasks:
1. Inspect all templates, views, forms, and static text.
2. Find hardcoded Arabic or English strings.
3. Convert strings to Django translation system using:
   - {% trans %}
   - {% blocktrans %}
   - gettext_lazy
4. Make layout direction dynamic:
   - dir="rtl" for Arabic
   - dir="ltr" for English
5. Ensure buttons, forms, cards, navigation, and dashboards work in both languages.
6. Update translation files.
7. Compile messages.
8. Add tests for language switching.
9. Fix any broken alignment in RTL/LTR.

Constraints:
- Do not remove current language switch behavior unless replacing it with better implementation.
- Do not hardcode Arabic inside JavaScript if avoidable.
- Avoid duplicated translation logic.

Validation:
python manage.py makemessages -l ar
python manage.py makemessages -l en
python manage.py compilemessages
python manage.py test
python manage.py check

Output:
- List of translated templates/files
- Remaining untranslated strings if any
- RTL/LTR fixes
```



---

# 14. Prompt — تحسين الأمن والصلاحيات

```text
You are a senior Django security engineer.

Audit and harden the Onlenco platform security.

Tasks:
1. Check settings for production security.
2. Review authentication and authorization.
3. Ensure users cannot access other users':
   - profile
   - placement results
   - tutor conversations
   - learning profile
   - errors
   - weaknesses
   - payments
4. Add object-level permission checks where needed.
5. Protect file uploads for payment screenshots.
6. Validate uploaded file types and size.
7. Add rate limiting plan for:
   - login
   - AI tutor
   - text analysis
   - exercise generation
8. Check CSRF usage.
9. Check admin access.
10. Check sensitive data exposure in templates and APIs.
11. Add security tests.

Expected improvements:
- Secure settings
- Permission checks
- Safer uploads
- API authorization
- No cross-user data leak

Validation:
python manage.py test
python manage.py check --deploy

Output:
- Security issues found
- Fixes applied
- Remaining risks
```



---

# 15. Prompt — تحسين نظام المدفوعات اليدوي

```text
You are a senior Django payments engineer.

Audit and improve the current manual payments system.

Current payment methods include Bankak, Fawry, and O-Cash with screenshot upload and admin approval.

Tasks:
1. Inspect payments app models, forms, views, admin, and tests.
2. Ensure payment flow is reliable:
   - user submits payment
   - screenshot uploaded safely
   - admin reviews
   - admin approves or rejects
   - subscription status updates correctly
3. Add validations:
   - amount required
   - transaction reference optional/required depending on method
   - screenshot file type
   - screenshot size
4. Add payment statuses:
   - pending
   - approved
   - rejected
   - needs_review
5. Add admin notes.
6. Add timestamps:
   - submitted_at
   - reviewed_at
7. Add tests for:
   - submit payment
   - approve payment
   - reject payment
   - invalid upload
   - subscription update
8. Ensure users cannot see other users' payments.

Validation:
python manage.py test payments
python manage.py check

Output:
- Payment flow summary
- Files modified
- Tests added
```



---

# 16. Prompt — بناء Recommendation Engine

```text
You are a senior recommendation systems engineer.

Build a recommendation engine for the Onlenco adaptive English platform.

Goal:
The system should recommend the best next activity for each student.

Create:
learning_core/services/recommendation_engine.py

Inputs:
- StudentLearningProfile
- SkillMastery
- UserWeakness
- Recent ExerciseAttempt
- Recent LessonProgress
- PlacementResult
- Tutor usage

Outputs:
LearningRecommendation records such as:
- Practice Past Tense
- Review Articles
- Take a speaking exercise
- Continue lesson X
- Ask tutor about Subject-Verb Agreement
- Retake placement test after 30 days

Logic:
1. Prioritize active high-score weaknesses.
2. Consider low mastery skills.
3. Avoid recommending completed/easy content repeatedly.
4. Recommend slightly challenging exercises.
5. Generate 3-5 recommendations.
6. Save recommendations.
7. Mark old recommendations as replaced or completed.

Add tests for:
- new user
- user with weaknesses
- user with no recent activity
- user who mastered a skill
- recommendation priority order

Validation:
python manage.py test learning_core
python manage.py check

Output:
- Recommendation rules
- Files created
- Example recommendations
```



---

# 17. Prompt — تحويل النظام إلى API-ready Product بدون كسر Templates

```text
You are a senior full-stack Django architect.

Refactor the system so every major user action has a service layer that can be reused by both Django templates and REST APIs.

Target actions:
1. Register user
2. Start placement test
3. Submit placement test
4. Start lesson
5. Submit quiz
6. Analyze writing text
7. Generate exercises
8. Submit exercise attempt
9. Chat with AI tutor
10. Submit payment
11. Approve payment
12. Load dashboard analytics

Tasks:
1. Inspect current views.
2. Identify business logic inside views.
3. Move business logic into service files.
4. Keep views thin.
5. Make services reusable from API views.
6. Add tests for services.
7. Ensure templates still work.

Expected service structure:
accounts/services/
placement/services/
lessons/services/
learning_core/services/
tutor/services/
payments/services/
analytics/services/

Constraints:
- Do not rewrite the whole system at once.
- Refactor incrementally.
- Keep behavior unchanged unless explicitly improved.

Validation:
python manage.py test
python manage.py check

Output:
- Views refactored
- Services created
- Before/after explanation
```



---

# 18. Prompt — Testing Master Plan + تنفيذ اختبارات

```text
You are a senior QA automation engineer for Django applications.

The current Onlenco project has very limited test coverage. Build a serious testing foundation.

Tasks:
1. Inspect existing tests.
2. Create a test plan covering:
   - accounts
   - lessons
   - placement
   - tutor
   - dictionary
   - library
   - club
   - payments
   - analytics
   - learning_core
   - APIs
3. Add tests for:
   - model behavior
   - service logic
   - permissions
   - views
   - forms
   - API endpoints
   - AI fallback behavior
4. Mock external AI calls.
5. Add factories or fixtures for users, lessons, quizzes, exercises, attempts.
6. Add coverage configuration.
7. Ensure tests are deterministic and fast.

Minimum required test cases:
- user registration and login
- placement submission
- lesson progress
- quiz answer submission
- wrong answer creates UserError
- weaknesses update after errors
- adaptive difficulty updates theta
- personalized exercises generated
- AI tutor fallback
- dictionary fallback
- payment submission and approval
- dashboard analytics empty state
- user cannot access another user's data

Validation:
python manage.py test
coverage run manage.py test
coverage report

Output:
- Tests added
- Coverage summary
- Critical flows covered
- Remaining testing gaps
```



---

# 19. Prompt — Seed Data للمهارات والقواعد والتمارين

```text
You are a senior educational content engineer.

Create seed data for the English learning system.

Goal:
The platform needs initial structured content for skills, grammar topics, CEFR levels, and fallback exercises.

Tasks:
1. Create management command:
   python manage.py seed_learning_core
2. Seed Skills:
   - Grammar
   - Vocabulary
   - Reading
   - Listening
   - Speaking
   - Writing
   - Pronunciation

3. Seed Grammar Topics:
   A1:
   - Verb to be
   - Present Simple
   - Articles
   - Basic Pronouns
   - Singular and Plural

   A2:
   - Past Simple
   - Future with going to
   - Comparatives
   - Prepositions of place/time
   - Countable and uncountable nouns

   B1:
   - Present Perfect
   - Modals
   - Conditionals type 1 and 2
   - Passive voice basics
   - Relative clauses

   B2:
   - Advanced conditionals
   - Reported speech
   - Complex sentence structure
   - Gerunds and infinitives
   - Discourse markers

4. Seed fallback AdaptiveExercise examples for each major topic.
5. Make command idempotent.
6. Add tests for command.

Validation:
python manage.py seed_learning_core
python manage.py test learning_core
python manage.py check

Output:
- Seeded topics count
- Seeded exercises count
- Files created
```



---

# 20. Prompt — Docker + Deployment Readiness

```text
You are a senior DevOps engineer for Django SaaS applications.

Prepare the Onlenco project for production deployment.

Tasks:
1. Add Dockerfile.
2. Add docker-compose.yml for:
   - web
   - PostgreSQL
   - Redis
3. Add gunicorn.
4. Add whitenoise or static file serving strategy.
5. Add environment variable support.
6. Add health check endpoint.
7. Add production run commands.
8. Add deployment README.
9. Add backup notes for database and media.
10. Add Celery placeholder if future async AI tasks are needed.
11. Ensure collectstatic works.
12. Ensure migrations run.

Validation:
docker compose build
docker compose up
python manage.py check --deploy

Output:
- Deployment files created
- Environment variables needed
- Production checklist
```



---

# 21. Prompt — AI Cost Control + Rate Limiting

```text
You are a senior AI platform engineer.

Add AI usage control to Onlenco.

Problem:
AI calls for tutor, text analysis, dictionary, and exercise generation can become expensive or abused.

Tasks:
1. Create model AIUsageLog:
   - user
   - feature: tutor, placement, dictionary, exercise_generation, error_analysis
   - prompt_tokens
   - completion_tokens
   - estimated_cost
   - success
   - error_message
   - created_at
2. Add service:
   core/services/ai_usage.py
3. Log all AI calls.
4. Add basic daily user limits:
   - free users
   - premium users
   - admin users
5. Add safe fallback when limit is exceeded.
6. Add tests for:
   - usage logging
   - limit exceeded
   - premium higher limits
   - AI failure logging
7. Do not block non-AI parts of the platform.

Validation:
python manage.py test
python manage.py check

Output:
- AI usage controls added
- Limits used
- Files changed
```



---

# 22. Prompt — Final System Audit بعد كل التنفيذ

```text
You are a senior software architect and QA lead.

Perform a final audit of the Onlenco platform after implementing adaptive learning features.

Do not modify code first. Inspect and report.

Check:
1. Architecture
2. Models
3. Services
4. APIs
5. Templates
6. Security
7. Tests
8. AI integration
9. Adaptive learning loop
10. Error analysis
11. Weakness prediction
12. Exercise generation
13. Tutor personalization
14. Placement diagnostics
15. Analytics
16. Deployment readiness
17. Documentation

Verify that the system now supports this full loop:
1. Student takes placement test
2. System estimates level
3. System detects weaknesses
4. Student receives exercises
5. Student attempts exercise
6. System checks answer
7. System analyzes mistakes
8. System updates weakness profile
9. System updates difficulty
10. System recommends next activity
11. AI Tutor uses the student's profile

Output:
- Passed checklist
- Failed checklist
- Critical bugs
- Missing requirements
- Suggested next sprint
- Commands run
- Final production readiness score out of 100
```
