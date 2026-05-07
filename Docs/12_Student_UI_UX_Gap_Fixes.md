# 12. Prompt — UI/UX Gap Fixes للطالب

```text
You are a senior product designer and Django frontend engineer.

Improve the student learning experience in the existing Django templates.

Goal:
The student should clearly see:
- Current level
- Progress
- Weaknesses
- Recommended next practice
- Recent mistakes
- Personalized exercises
- AI tutor guidance

Tasks:
1. Inspect existing templates.
2. Improve dashboard/home for logged-in students.
3. Add sections:
   - My English Level
   - My Top Weaknesses
   - Recommended Practice
   - Continue Learning
   - Recent Mistakes
   - Ask AI Tutor
   - Weekly Progress
4. Use existing design style but make it cleaner and more professional.
5. Ensure responsive design for mobile and desktop.
6. Support Arabic and English layout.
7. Use Tailwind classes consistently.
8. Avoid heavy JavaScript unless needed.
9. Handle empty states beautifully:
   - New user without placement test
   - User without weaknesses
   - User without exercises
10. Add template tests or view tests where practical.

Constraints:
- Do not redesign everything from scratch.
- Improve incrementally.
- Do not break current navigation.

Validation:
python manage.py test
python manage.py check

Output:
- Templates modified
- Screens/pages improved
- Empty states added
```
