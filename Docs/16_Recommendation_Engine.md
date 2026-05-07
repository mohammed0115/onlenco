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
