# 19. Prompt — Seed Data للمهارات والقواعد والتمارين

```text
You are a senior educational content engineer.

Create seed data for the English learning system.

Goal:
The platform needs initial structured content for skills, grammar topics, CEFR levels, and fallback exercises.

Tasks:
1. Create management command:
   python manage.py seed_learning_core
2. Seed Skills:
   - Grammar
   - Vocabulary
   - Reading
   - Listening
   - Speaking
   - Writing
   - Pronunciation

3. Seed Grammar Topics:
   A1:
   - Verb to be
   - Present Simple
   - Articles
   - Basic Pronouns
   - Singular and Plural

   A2:
   - Past Simple
   - Future with going to
   - Comparatives
   - Prepositions of place/time
   - Countable and uncountable nouns

   B1:
   - Present Perfect
   - Modals
   - Conditionals type 1 and 2
   - Passive voice basics
   - Relative clauses

   B2:
   - Advanced conditionals
   - Reported speech
   - Complex sentence structure
   - Gerunds and infinitives
   - Discourse markers

4. Seed fallback AdaptiveExercise examples for each major topic.
5. Make command idempotent.
6. Add tests for command.

Validation:
python manage.py seed_learning_core
python manage.py test learning_core
python manage.py check

Output:
- Seeded topics count
- Seeded exercises count
- Files created
```
