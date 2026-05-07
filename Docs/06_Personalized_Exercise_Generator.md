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
