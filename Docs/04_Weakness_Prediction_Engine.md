# 4. Prompt — محرك نقاط الضعف Weakness Prediction Engine

```text
You are a senior machine learning engineer and Django backend developer.

Build a Weakness Prediction Engine for the Onlenco adaptive English learning platform.

Current gap:
The system stores quiz progress but does not convert student mistakes into weakness profiles.

Create:
learning_core/services/weakness_engine.py

Main function:
update_user_weaknesses(user)

Logic:
1. Read recent UserError records for the user.
2. Group errors by skill and grammar_topic.
3. Calculate:
   - frequency
   - average severity
   - recency score
   - priority score
4. Use the formula:
   priority_score = frequency_weight + severity_weight + recency_weight
5. Normalize weakness_score to 0-100.
6. Create or update UserWeakness records.
7. Mark old weaknesses as improving or resolved when error frequency drops.
8. Return top weaknesses sorted by priority.

Add function:
get_top_weaknesses(user, limit=3)

Initial implementation should be rule-based, not ML-heavy, because the project may not have enough historical data yet.

Later extension:
Prepare the service so Naive Bayes can be added after enough training data exists.

Also:
- Add tests using sample UserError data.
- Test priority ranking.
- Test weakness update.
- Test resolved/improving status.
- Connect it optionally after ExerciseAttempt and ErrorAnalysis.

Expected files:
- learning_core/services/weakness_engine.py
- learning_core/tests/test_weakness_engine.py

Validation:
python manage.py test learning_core
python manage.py check

Output:
- Explain the implemented scoring formula.
- Show examples of top 3 weaknesses generated from test data.
```
