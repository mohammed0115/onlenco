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
