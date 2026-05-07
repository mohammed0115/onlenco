# Prompt 02 — Weekly Assessment Audit

```text
You are a senior educational assessment engineer and Django backend auditor.

Audit whether the weekly assessment requirement is fully implemented.

Requirement:
After every 3 completed lessons, the student should receive a weekly assessment or milestone assessment.

Verify:
1. Is there a WeeklyAssessment model?
2. Is there a WeeklyAssessmentAttempt model?
3. Is the system detecting every 3 completed lessons?
4. Is the assessment generated from recent lessons?
5. Does it include reading, writing, listening, speaking, grammar, and vocabulary?
6. Does it update SkillMastery?
7. Does it update UserWeakness?
8. Does it update theta_score?
9. Does it create UserError for wrong written answers?
10. Does it generate recommendations after completion?
11. Is there a student UI page?
12. Is there an API endpoint?
13. Are there admin views?
14. Are there tests?

If implemented:
- Show related models, services, views, APIs, templates, tests, and commands.

If partially implemented:
- Explain exactly what exists and what is missing.

If missing:
Propose the exact implementation:
- models
- services
- views
- APIs
- templates
- tests
- admin registration
- migration plan
- validation commands

Do not mark this requirement complete unless it is actually integrated with the learning loop.
```
