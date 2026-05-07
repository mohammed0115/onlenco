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
