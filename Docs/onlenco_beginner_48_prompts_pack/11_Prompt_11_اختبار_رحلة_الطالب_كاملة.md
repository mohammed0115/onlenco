## Prompt 11 — اختبار رحلة الطالب كاملة

أنت QA Engineer محترف تختبر كأنك طالب حقيقي.

المشروع: Onlenco Academy

المطلوب:
اختبار رحلة الطالب الكاملة لكورس Beginner المكون من 48 Learning Units.

اختبر السيناريو:

Flow 1:
Register
→ Verify Email
→ Choose Start from Beginner
→ Dashboard
→ Beginner Course appears
→ Open Unit 1
→ View learning content
→ Play image/audio if available
→ Start Quiz
→ Submit Quiz
→ Practice with AI Tutor
→ Complete Unit 1
→ Move Unit 2
→ Continue until first Review opens

Flow 2:
Logout
→ Login again
→ لا يظهر Placement إجباريًا
→ يرجع الطالب للكورس والتقدم الصحيح

Flow 3:
Open Learning Unit without media
→ يجب ألا يحدث Internal Server Error

Flow 4:
Open Learning Unit with generated media
→ image appears
→ audio player works
→ quiz works

Flow 5:
Arabic UI
→ RTL works
→ Arabic content appears
→ English content remains LTR

Flow 6:
Quiz
→ questions appear
→ answer validation works
→ score saved
→ progress updated

Flow 7:
AI Tutor
→ receives lesson context
→ does not start generic chat
→ asks lesson-based questions
→ saves attempt/progress

Flow 8:
Review
→ locked before required units
→ unlocks after required units
→ saves score

افحص:
- 500 errors
- missing template variables
- wrong queryset
- missing media fallback
- quiz not linked
- AI tutor not linked
- progress not saved
- placement showing incorrectly
- RTL/LTR issues
- audio player errors
- image fallback errors
- duplicate seed data

اكتب تقرير بالعربي:
# تقرير QA رحلة الطالب — Onlenco Beginner 48 Units

جدول:
| Flow | النتيجة | المشاكل | الأولوية | الحل المقترح |

رتب المشاكل:
P0 = يكسر الرحلة
P1 = مهم جدًا
P2 = تحسين
P3 = لاحقًا

لا تصلح الكود إلا إذا طلبت منك.
فقط افحص واكتب التقرير.
