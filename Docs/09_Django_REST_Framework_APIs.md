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
