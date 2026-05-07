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
