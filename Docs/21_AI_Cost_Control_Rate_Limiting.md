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
