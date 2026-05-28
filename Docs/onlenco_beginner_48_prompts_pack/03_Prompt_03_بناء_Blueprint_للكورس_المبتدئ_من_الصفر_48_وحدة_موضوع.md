## Prompt 03 — بناء Blueprint للكورس المبتدئ من الصفر: 48 وحدة / موضوع

أنت خبير CEFR ومصمم مناهج إنجليزية ومهندس Django.

المشروع: Onlenco Academy

المطلوب:
بناء Blueprint كامل لكورس مبتدئ من الصفر بنفس حجم ومنهجية الكتاب المرجعي، لكن بمحتوى Onlenco أصلي.

اسم الكورس:
Onlenco Beginner English Foundation — American English

المستوى:
A0/A1 Beginner

الهيكل المطلوب:
- 1 Course
- 48 Learning Units / Topics
- كل Topic Unit عبارة عن درس كامل مستقل
- كل Topic Unit له Quiz
- كل Topic Unit له Listening + Speaking
- كل Topic Unit له Image Prompts + Audio Scripts
- Reviews بعد مجموعات من الوحدات

مهم:
- لا تنسخ أسماء الجمل من الكتاب.
- لا تنسخ التمارين.
- لا تستخدم صور الكتاب.
- لا تستخدم صوت الكتاب.
- استخدم نفس التدرج التعليمي فقط.
- المحتوى مناسب لطالب عربي يبدأ من الصفر.
- American English فقط.

اقترح خريطة 48 Learning Units / Topics بالترتيب التالي:

01. Introducing Yourself
02. Countries
03. Talking About Yourself
04. Family and Pets
05. Things You Have
06. Using Apostrophes
07. Everyday Things
08. Talking About Your Things
09. Jobs
10. Talking About Your Job
11. Telling the Time
12. Daily Routines
13. Describing Your Day
14. Describing Your Week
15. Negatives with To Be
16. More Negatives
17. Simple Questions
18. Answering Questions
19. Asking Questions
20. Around Town
21. Talking About Your Town
22. Using A, An, and The
23. Orders and Directions
24. Joining Sentences
25. Describing Places
26. Giving Reasons
27. Around the House
28. The Things I Have
29. What Do You Have?
30. Food and Drink
31. Counting
32. Measuring
33. Clothes
34. At the Store
35. Describing Things
36. Sports
37. Talking About Sports
38. Hobbies and Pastimes
39. Free Time
40. Likes and Dislikes
41. Music
42. Expressing Preference
43. Abilities
44. What You Can and Can’t Do
45. Describing Actions
46. Describing Ability
47. Wishes and Desires
48. Studying

لكل Topic Unit في الـ blueprint اكتب:
- unit_number
- title_en
- title_ar
- cefr_level
- estimated_minutes
- new_language
- vocabulary_focus
- new_skill
- grammar_focus
- pronunciation_focus إن وجد
- speaking_goal
- listening_goal
- image_idea
- audio_idea
- quiz_goal
- ai_tutor_goal
- checklist_items
- review_group

أنشئ ملف:
ONLENCO_BEGINNER_48_UNITS_BLUEPRINT.md

لا تكتب seed data الآن.
فقط Blueprint.

يجب أن توضح كيف سيتم تنفيذها في النظام:
الخيار A:
Course → 48 Lessons وتعرض في الواجهة باسم Learning Units

الخيار B:
إضافة LearningModule model إن كان النظام يحتاج فصلًا أوضح

قرر الأفضل حسب بنية المشروع الحالية.

التقرير النهائي بالعربي:
- عدد الوحدات
- هل الترتيب منطقي؟
- هل كل Topic له هدف تعليمي واضح؟
- هل مناسب للمبتدئ من الصفر؟
- هل النظام يحتاج LearningModule model؟
- ما الخطوة التالية؟
