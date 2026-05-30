# Onlenco Beginner — Review Checkpoints (Blueprint)

**Status:** Blueprint only — assessment-model implementation is TODO Phase 11+.

The 48 Topics naturally cluster into 8 review checkpoints (every 6 topics).
This document holds the spec so when an Assessment / Review model becomes
available, the data is ready to seed.

| Review # | Range  | Title                                | Skills focus                                                                       |
|----------|--------|--------------------------------------|-----------------------------------------------------------------------------------|
| Review 1 | 01–06  | First Steps                          | greetings, to_be_names, spelling_names, nationality, to_be_age, numbers_basic     |
| Review 2 | 07–12  | Family + Demonstratives              | family_words, pets_animals, have_has, possessive_adjectives, this_that, these_those |
| Review 3 | 13–18  | Work + Time                          | everyday_objects, apostrophe_s, jobs, workplaces, telling_time, daily_routine     |
| Review 4 | 19–24  | Present Simple                       | daily_routine, present_simple, negatives_to_be, present_simple_negative, yes_no_questions, short_answers |
| Review 5 | 25–30  | Places + Connectors                  | question_words, directions, there_is_are, articles_a_an_the, conjunctions_and_but |
| Review 6 | 31–36  | Description + Possession             | adjectives_basic, because_reasons, everyday_objects, have_has, food_drink         |
| Review 7 | 37–42  | Quantity + Shopping                  | countable_uncountable, how_much_many, clothes, shopping, adjectives_basic, sports |
| Review 8 | 43–48  | Habits + Goals                       | sports, hobbies, adverbs_frequency, likes_dislikes, can_cannot, studying_subjects |

## TODO (post Prompt 10)
- Add a `CourseReview` (or similar) model row per checkpoint.
- Generate ~8 mixed-skill review questions per checkpoint from the topics
  it covers.
- Add a review-launcher card on the lesson_detail page that appears
  after the user completes the last topic in a cluster.
- Status = pending_review until a teacher approves.

(The `courses.CourseReview*` models already exist in Phase 10's audit —
they're used by `seed_onlenco_beginner_reviews.py` already. Wiring them
to the 8 checkpoints above is straightforward but out of scope for
Prompt 10. The blueprint above is enough to brief Phase 11.)
