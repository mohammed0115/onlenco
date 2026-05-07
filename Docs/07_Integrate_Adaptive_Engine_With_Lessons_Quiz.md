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
