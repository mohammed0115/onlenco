# Prompt 01 — End-to-End Scenario Tests

```text
You are a senior QA automation engineer for Django SaaS products.

Create and run end-to-end validation scenarios for Onlenco.

Test the full student journey and admin journey. Do not rely on isolated unit tests only.

Scenario 1: New student journey
1. Register a new student
2. Login
3. Take written placement test
4. Take speaking placement test
5. Receive CEFR level
6. StudentLearningProfile is created
7. Initial SkillMastery records are created
8. Weaknesses are created
9. Recommended lessons appear
10. Student opens a lesson
11. Student watches teacher video
12. Student completes reading/writing/listening/speaking tasks if implemented
13. Student takes quiz
14. Wrong answers create UserError
15. UserWeakness is updated
16. theta_score is updated
17. Personalized exercises are generated
18. Recommendations are updated
19. AI Tutor uses student profile
20. Student sees dashboard progress

Scenario 2: Returning student improvement journey
1. Login as existing student
2. Solve personalized exercises
3. Improve score
4. Weakness score decreases
5. SkillMastery increases
6. Difficulty increases
7. Recommendations change
8. Dashboard reflects improvement

Scenario 3: Admin journey
1. Admin logs in
2. Reviews students
3. Reviews payments
4. Approves manual payment
5. Checks subscription activation
6. Checks learning analytics
7. Checks AI usage
8. Checks at-risk students
9. Checks inactive students

Scenario 4: API journey
1. Authenticate user
2. Call learning profile API
3. Call weaknesses API
4. Generate exercises through API
5. Submit exercise attempt through API
6. Verify UserError and UserWeakness records
7. Verify another user cannot access the same data

For each scenario:
- State whether it passes or fails
- Mention exact files involved
- Mention database records created
- Mention API responses or page results
- Mention tests added
- Mention validation commands
- Provide failure details and required fixes

Validation commands to run or recommend:
python manage.py check
python manage.py makemigrations --check
python manage.py test
coverage run manage.py test
coverage report
```
