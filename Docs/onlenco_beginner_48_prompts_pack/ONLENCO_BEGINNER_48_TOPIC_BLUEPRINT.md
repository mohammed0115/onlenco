# Onlenco Beginner — 48-Topic Curriculum Blueprint

**Course:** Onlenco Beginner English Foundation — American English
**Audience:** Arabic-speaking absolute beginners
**Total topics:** 48 (Topic 01 = Gold Reference; 02-48 generated via `seed_beginner_48_topics`)
**Content origin:** 100% Onlenco-original. No copying from EFE / DK / Duolingo / any other source.

---

## Difficulty bands (used by the seed generator)

| Range | CEFR | Allowed challenge question types | Forbidden | Notes |
|---|---|---|---|---|
| **Topics 01-12** | A0 | tap_choice, image_choice, sound_to_word, word_bank_sentence (simple), match_pairs, fill_blank_card (1 word), conversation_reply (simple), speak_this_sentence, ai_roleplay_prompt | ❌ listen_and_type, ❌ translate_to_english, ❌ full-sentence typing | Recognition over production. Max 3 speaking placeholders. |
| **Topics 13-24** | A0+/A1 early | + question_transform (simple), + translate_to_english (only as accepted_answers list, never free-typed) | ❌ listen_and_type | Productive output starts in small, scaffolded chunks. |
| **Topics 25-36** | A1 basic | + table_sentence_builder, + mini_story_choice, + listen_and_type (1 short sentence with pending-audio fallback) | — | Multi-clause grammar. |
| **Topics 37-48** | A1 | + frequency_scale, + mistake_correction, + full mix | — | Full A1 toolkit. |

## Universal rules (every Topic)
- ≥ 1 listening question. ≥ 1 speaking placeholder. ≤ 3 speaking placeholders per challenge.
- First question = easy (difficulty ≤ 0.3). Last question = speaking / roleplay.
- Vocabulary + grammar + communication coverage in every challenge.
- 8-12 questions per challenge.
- Every question has `metadata.skills` ≥ 1 code from the taxonomy.
- All seeded topics: `status="pending_review"`, `is_active=True` — hidden from students via `published_lesson_queryset()`.

---

## The 48 Topics

| # | Title EN | Title AR | CEFR | Primary skill(s) | Question count |
|---|---|---|---|---|---|
| 01 | Introducing Yourself | التعريف بنفسك | A0 | greetings, to_be_names | 10 (Gold Reference) |
| 02 | Saying Hello and Goodbye | تحية ووداع | A0 | greetings | 8-10 |
| 03 | Spelling Your Name | تهجئة اسمك | A0 | spelling_names, alphabet | 8-10 |
| 04 | Countries and Nationalities | الدول والجنسيات | A0 | nationality, to_be_names | 8-10 |
| 05 | Talking About Age | الحديث عن العمر | A0 | to_be_age, numbers_basic | 8-10 |
| 06 | Basic Personal Information | معلومات شخصية أساسية | A0 | numbers_basic, spelling_names | 8-10 |
| 07 | Family Words | كلمات العائلة | A0 | family_words | 8-10 |
| 08 | Pets and Simple Descriptions | الحيوانات الأليفة وأوصاف بسيطة | A0 | pets_animals, adjectives_basic | 8-10 |
| 09 | Things You Have | أشياء تملكها | A0 | have_has, everyday_objects | 8-10 |
| 10 | Possessive Adjectives | صفات الملكية | A0 | possessive_adjectives | 8-10 |
| 11 | This and That | This / That | A0 | this_that | 8-10 |
| 12 | These and Those | These / Those | A0 | these_those | 8-10 |
| 13 | Everyday Objects | الأدوات اليومية | A0+ | everyday_objects | 9-11 |
| 14 | Apostrophe S | علامة الملكية 's | A1- | apostrophe_s | 9-11 |
| 15 | Common Jobs | المهن الشائعة | A1- | jobs | 9-11 |
| 16 | Workplaces | أماكن العمل | A1- | workplaces, jobs | 9-11 |
| 17 | Telling the Time | قول الوقت | A1- | telling_time, numbers_basic | 9-11 |
| 18 | Daily Routines | الروتين اليومي | A1- | daily_routine, present_simple | 9-11 |
| 19 | My Day | يومي | A1- | daily_routine | 9-11 |
| 20 | My Week | أسبوعي | A1- | daily_routine, present_simple | 9-11 |
| 21 | Negatives with To Be | نفي be | A1- | negatives_to_be | 9-11 |
| 22 | Present Simple Negatives | المضارع البسيط (نفي) | A1- | present_simple_negative | 9-11 |
| 23 | Yes / No Questions | أسئلة نعم/لا | A1- | yes_no_questions, short_answers | 9-11 |
| 24 | Short Answers | إجابات قصيرة | A1- | short_answers | 9-11 |
| 25 | Question Words | أدوات الاستفهام | A1 | question_words | 10-12 |
| 26 | Places in Town | أماكن المدينة | A1 | directions | 10-12 |
| 27 | There Is / There Are | There is / are | A1 | there_is_are | 10-12 |
| 28 | A / An / The | أدوات التعريف والتنكير | A1 | articles_a_an_the | 10-12 |
| 29 | Directions and Instructions | الاتجاهات والتعليمات | A1 | directions | 10-12 |
| 30 | Joining Sentences with And / But | And / But | A1 | conjunctions_and_but | 10-12 |
| 31 | Describing Places | وصف الأماكن | A1 | adjectives_basic, there_is_are | 10-12 |
| 32 | Giving Reasons with Because | because (السبب) | A1 | because_reasons | 10-12 |
| 33 | Rooms and Furniture | الغرف والأثاث | A1 | everyday_objects | 10-12 |
| 34 | Have and Has | have / has | A1 | have_has, third_person_s | 10-12 |
| 35 | Asking What People Have | السؤال عمّا يملكه الناس | A1 | have_has, question_words | 10-12 |
| 36 | Food and Drink | الطعام والشراب | A1 | food_drink | 10-12 |
| 37 | Countable and Uncountable Nouns | العد / غير العد | A1 | countable_uncountable | 10-12 |
| 38 | How Much / How Many | How much / many | A1 | how_much_many | 10-12 |
| 39 | Clothes | الملابس | A1 | clothes | 10-12 |
| 40 | Shopping | التسوّق | A1 | shopping | 10-12 |
| 41 | Describing Things with Adjectives | الوصف بالصفات | A1 | adjectives_basic | 10-12 |
| 42 | Sports | الرياضات | A1 | sports | 10-12 |
| 43 | Talking About Sports | الحديث عن الرياضات | A1 | sports, likes_dislikes | 10-12 |
| 44 | Hobbies and Free Time | الهوايات ووقت الفراغ | A1 | hobbies | 10-12 |
| 45 | Adverbs of Frequency | ظروف التكرار | A1 | adverbs_frequency, present_simple | 10-12 |
| 46 | Likes and Dislikes | أحب / لا أحب | A1 | likes_dislikes, favorite | 10-12 |
| 47 | Can and Cannot | can / can't | A1 | can_cannot | 10-12 |
| 48 | Studying and Future Goals | الدراسة والأهداف المستقبلية | A1 | studying_subjects, would_like_want | 10-12 |

---

## Review Checkpoints (placeholder — see ONLENCO_BEGINNER_REVIEW_CHECKPOINTS.md)

| # | Range | Title |
|---|---|---|
| Review 1 | 01-06 | First Steps Review |
| Review 2 | 07-12 | Family + Demonstratives Review |
| Review 3 | 13-18 | Work + Time Review |
| Review 4 | 19-24 | Present Simple Review |
| Review 5 | 25-30 | Places + Connectors Review |
| Review 6 | 31-36 | Description + Possession Review |
| Review 7 | 37-42 | Quantity + Shopping Review |
| Review 8 | 43-48 | Habits + Goals Review |

(Models for full assessments don't exist yet — see review-checkpoints document for the TODO.)

---

## Onlenco cast (rotating)
**Amani · Yusuf · Noor · Kareem · Salma · Omar · Layla · Tarek · Hala · Rashid**

Every dialogue/question must rotate through these. No external character names.
