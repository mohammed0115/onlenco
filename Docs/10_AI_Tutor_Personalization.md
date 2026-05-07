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
