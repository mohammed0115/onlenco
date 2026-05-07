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
