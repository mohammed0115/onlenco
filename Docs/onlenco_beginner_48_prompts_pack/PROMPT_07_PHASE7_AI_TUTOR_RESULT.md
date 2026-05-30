# تقرير Prompt 07 — AI Tutor inside Challenges

**التاريخ:** 2026-05-30
**المرحلة:** Phase 7 — ربط AI Tutor بتجربة Challenge في 6 لحظات تعليمية فقط
**الحالة:** ✅ مكتمل + اختبارات خضراء (602 اختبار في `tutor` + `courses` + `motivation` + `learning_core` — كلها ناجحة)
**المبدأ:** AI تحسين اختياري، الـ fallback القاعدي مضمون دائماً، صفر اعتماد على AI لاكتمال الـ Challenge.

---

## 1) الملخّص التنفيذي

### قبل Prompt 07
- `tutor` app موجود كصفحة chat **منفصلة** (`/tutor/`) — غير مربوطة بـ Challenge.
- `factory/services/llm_router.py` و `tutor/services/_chat.py` يحملان عقد OpenAI-compatible جاهز (`AI_API_KEY` + `AI_API_BASE`).
- Subscription minutes tracking موجود لكن غير مربوط بـ Challenge.
- `ChallengeAnswer.feedback_en/ar` موجود (rule-based).
- `StudentMistake.explanation_en/ar` موجود (Phase 6).
- **لا يوجد** AI داخل تجربة الـ Challenge — الطالب يخرج إلى صفحة chat منفصلة.

### بعد Prompt 07
- ✅ **6 لحظات تعليمية فقط** — wrong answer explanation، speaking feedback، short roleplay، end-of-challenge advice، mistake explanation، conversation enhancement (placeholder).
- ✅ **Context builder** مُحكَم — يقدّم فقط ما يحتاجه AI: lesson + question + skill + answer + mistake_type. لا PII، لا history، لا HTML، لا underscores.
- ✅ **3 نماذج جديدة** في `tutor`: `ChallengeAIInteraction`, `AIShortRoleplaySession`, `AIShortRoleplayMessage`.
- ✅ **Guardrails صارمة:** `CHALLENGE_AI_ENABLED`، per-session cap (5)، daily cap (30)، روليبلاي turns cap (5).
- ✅ **Fallback rule-based** لكل use case — يعمل حتى لو AI_API_KEY فارغ أو الـ LLM يفشل.
- ✅ **4 endpoints آمنة** — login_required + ownership + POST only + لا يقبل raw prompt من العميل.
- ✅ **UI** — زر "Explain with AI Tutor" في feedback card الخاطئة + قسم نصيحة في الـ summary.
- ✅ **29 اختبار جديد** + كل المراحل السابقة سليمة = **602 اختبار** كلها خضراء.

### هل أصبح AI Tutor داخل تجربة Challenge؟
نعم — وبشكل مُحكَم. لا يخرج الطالب من البطاقة. لا يضغط زر AI إلا إذا أراد. الـ Challenge لا يعتمد على AI لإكمال السؤال. الردود قصيرة، beginner-friendly، American English، عربية مختصرة عند الحاجة فقط.

---

## 2) الملفات المعدلة أو المنشأة

### ملفات جديدة (5)

| الملف | الدور |
|---|---|
| `tutor/migrations/0005_aishortroleplaysession_aishortroleplaymessage_and_more.py` | 3 جداول جديدة |
| `tutor/services/challenge_ai_context.py` | Context builder + prompt assembly + hash |
| `tutor/services/ai_usage_guard.py` | feature flag + per-session + daily caps + record |
| `tutor/services/challenge_rule_fallbacks.py` | عبارات قاعدية لكل use case |
| `tutor/services/challenge_tutor_service.py` | dispatcher رئيسي مع 6 entry points |
| `tutor/tests/test_challenge_ai_phase7.py` | 29 اختبار |
| `Docs/.../PROMPT_07_PHASE7_AI_TUTOR_RESULT.md` | هذا التقرير |

### ملفات مُحدَّثة (5)

| الملف | التعديل | السبب |
|---|---|---|
| `tutor/models.py` | إضافة 3 models: ChallengeAIInteraction (audit log), AIShortRoleplaySession (turns_count/max_turns), AIShortRoleplayMessage | البنية المطلوبة |
| `courses/urls.py` | 4 routes جديدة: ai_explain_wrong_answer, ai_roleplay_start, ai_roleplay_message, ai_end_advice | endpoints |
| `courses/views.py` | 4 views جديدة + `_get_owned_session` helper + `JsonResponse` import | تنفيذ الـ endpoints مع ownership |
| `templates/courses/challenge/components/feedback_card.html` | زر "Explain with AI Tutor" + container للنتيجة | UI الـ wrong answer |
| `templates/courses/challenge_session.html` | JS لزر AI explain + CSS لـ `.onlenco-ch-ai-*` | wiring |
| `templates/courses/challenge_summary.html` | قسم AI Tutor advice + JS + CSS + CSRF sink | end-of-challenge advice |
| `templates/courses/question_renderers/speaking_placeholder.html` | تمييز ai_roleplay_prompt + نص أوضح | الـ speaking card |

---

## 3) AI Context Builder

ملف: `tutor/services/challenge_ai_context.py`

### ماذا يجمع؟
```python
{
  "user_lang_pref":   "en" | "ar",
  "user_level":       "A0".."C2" (إن وُجد learning_profile),
  "lesson_title":     مُنظَّف من HTML,
  "cefr_level":       A0..C2,
  "question_type":    "tap_choice"..,
  "question_text":    plain text (HTML stripped, underscores stripped),
  "question_text_ar": مماثل,
  "correct_answer":   مُنظَّف,
  "user_answer":      مُنظَّف,
  "is_correct":       bool | None,
  "skill_codes":      ["greetings", "to_be_names"],
  "mastery":          {"greetings": 65.0},
  "mistake_type":     "wrong_choice" | "" ,
  "interaction_type": "wrong_answer_explanation" | ...,
}
```

### كيف يحافظ على السياق؟
- يستقي الـ skills عبر `learning_core.services.skill_resolver.get_question_skills(question)`.
- يستقي الـ mistake_type من `StudentMistake` (الخاص بنفس المستخدم + نفس السؤال + غير mastered).
- يستقي الـ mastery من `SkillMastery` بـ filter على skill_codes فقط — لا تاريخ كامل.

### كيف يمنع البيانات الزائدة؟
- **لا email، لا username، لا names** — الـ context لا يحوي أي PII.
- **لا history للأسئلة الأخرى**.
- `_clean()` يستخدم regex لإزالة `<tags>` و underscores وملء whitespace.
- `render_user_prompt(ctx)` يُنتج plain text فقط — لا JSON، لا code fences، لا markdown.
- `system_prompt()` يحدّد تعليمات صارمة: "American English", "beginner", "3-4 sentences max", "no symbols/underscores", "no JSON".
- `hash_prompt(prompt)` يعيد SHA-256 مختصر (32 char) للـ deduplication بدون تسريب المحتوى.

### اختبارات
- `test_context_contains_lesson_question_skill` ✅
- `test_context_strips_html_and_underscores` ✅
- `test_context_does_not_include_email_or_pii` ✅
- `test_render_user_prompt_is_plain_text` ✅
- `test_hash_prompt_is_stable` ✅

---

## 4) AI Tutor Service

ملف: `tutor/services/challenge_tutor_service.py`

### النمط المشترك (`_dispatch`)
كل use case يمر بنفس الـ pipeline:
1. **Guardrail check** — `can_call_challenge_ai(user, session, type)`.
2. لو blocked → record + return fallback.
3. Build context → `render_user_prompt(ctx)` → `hash_prompt`.
4. Try LLM (`_call_llm` — timeout 12s، max_tokens 220، temperature 0.4).
5. Post-process — strip code fences + underscores.
6. `_split_bilingual(text, ctx)` — يكتشف غير-ASCII كـ AR.
7. Record + return `{en, ar, status, reason}`.
8. عند exception → fallback + status=failed + record.

### 6 use cases

#### `explain_wrong_answer(user, challenge_answer)`
- interaction_type=`wrong_answer_explanation`
- output: 1-2 جمل لماذا الإجابة خطأ + قاعدة واحدة + مثال واحد.
- fallback: من `challenge_rule_fallbacks.wrong_answer_explanation(ctx)` حسب الـ mistake_type.

#### `generate_speaking_feedback(user, challenge_answer, transcript="")`
- interaction_type=`speaking_feedback`
- output: 3 bullets max — pronunciation focus.
- transcript اختياري (الـ STT غير مُدمَج بعد، fallback يعمل بدونه).

#### `start_short_roleplay(user, session, question)`
- ينشئ `AIShortRoleplaySession` بـ `max_turns=5`.
- يضيف أول AI message في `AIShortRoleplayMessage`.
- يرفع `turns_count` إلى 1.
- لو AI off → fallback opener: "Let's practice. Imagine we just met. Say hello and tell me your name."

#### `continue_short_roleplay(user, roleplay_session, user_message)`
- يتحقق من ownership + status=active + turns < max.
- يضيف user message ثم يستدعي `_dispatch` (interaction=`roleplay`).
- يحفظ AI reply.
- يرفع `turns_count`.
- لو وصل لـ max → status=completed + رسالة ختام.

#### `generate_end_challenge_advice(user, session)`
- يستخدم آخر `ChallengeAnswer` كـ context (لو موجود).
- fallback: 3 فروع حسب `session.wrong_count` (0/1-2/>2).

#### `generate_mistake_explanation(user, mistake)`
- يستدعى من review queue.
- يحفظ النتيجة في `StudentMistake.explanation_en/ar` مباشرة.
- fallback: نصيحة قصيرة تذكِّر بالإجابة الصحيحة.

### حدود الردود (مَفروضة من system prompt + max_tokens=220)
- Wrong answer: 40-60 كلمة.
- Speaking: 3 bullets max.
- Roleplay turn: جملة قصيرة واحدة.
- End advice: جملة أو اثنتان.

---

## 5) Models

### `ChallengeAIInteraction`
audit log لكل استدعاء AI من داخل Challenge.

| Field | Type | الوصف |
|---|---|---|
| user | FK User | المستخدم |
| session | FK ChallengeSession (nullable) | الجلسة |
| question | FK LessonQuestion (nullable) | السؤال |
| challenge_answer | FK ChallengeAnswer (nullable) | الإجابة |
| interaction_type | choice (6 أنواع) | wrong_answer_explanation / speaking_feedback / roleplay / end_advice / mistake_explanation / conversation_enhancement |
| prompt_hash | char(64) | SHA-256 (32 char) — للـ dedup بدون تسريب |
| response_en | text | الرد الإنجليزي |
| response_ar | text | الرد العربي |
| status | choice | success / fallback / failed / skipped |
| tokens_used | uint nullable | لاحتساب التكلفة |
| latency_ms | uint nullable | للأداء |
| error_code | char(40) | اسم الـ exception أو machine code للـ guardrail |
| metadata | JSON | إضافات (roleplay_id...) |
| created_at | datetime | تلقائي |

**Indexes:** (user, -created_at), (session, -created_at), (interaction_type, -created_at).

### `AIShortRoleplaySession`
| Field | Type | الوصف |
|---|---|---|
| user, challenge_session, question | FKs | السياق |
| status | choice | active / completed / abandoned |
| turns_count | uint | عدد الـ turns حتى الآن |
| max_turns | uint8 | افتراضي 5 |
| started_at, completed_at | datetime | تتبع الـ lifecycle |
| metadata | JSON | إضافات |

### `AIShortRoleplayMessage`
| Field | Type | الوصف |
|---|---|---|
| roleplay_session | FK | الجلسة |
| sender | choice | user / ai |
| message | text | المحتوى |
| created_at | datetime | تلقائي |

### Migration: `tutor/migrations/0005_aishortroleplaysession_aishortroleplaymessage_and_more.py`

---

## 6) Guardrails / Limits

ملف: `tutor/services/ai_usage_guard.py`

### Settings (كلها قابلة للـ override)
| Setting | Default | الدور |
|---|---|---|
| `CHALLENGE_AI_ENABLED` | True | المفتاح العام |
| `AI_API_KEY` | "" | إذا فارغ → AI معطّل |
| `CHALLENGE_AI_MAX_CALLS_PER_SESSION` | 5 | حماية ضد الـ rapid clicks |
| `CHALLENGE_AI_DAILY_LIMIT_PER_USER` | 30 | حماية الفاتورة |
| `CHALLENGE_AI_MAX_ROLEPLAY_TURNS` | 5 | حد طول الـ roleplay |
| `CHALLENGE_AI_TIMEOUT_SECONDS` | 12 | حماية UX |
| `CHALLENGE_AI_MAX_TOKENS` | 220 | حد طول الرد |

### Dynamic re-read
الدوال تقرأ `settings` في كل استدعاء (لا cache module-level) → `@override_settings(...)` في الـ tests يعمل فوراً.

### Public API
- `is_enabled()` → `bool` (CHALLENGE_AI_ENABLED AND AI_API_KEY).
- `can_call_challenge_ai(user, session, type)` → `(bool, reason)` — reasons: `ai_disabled`, `session_limit`, `daily_limit`, `ok`.
- `record_ai_call(...)` → `ChallengeAIInteraction` — يحفظ كل محاولة بسجل.
- `get_remaining_ai_calls(user, session)` → dict للـ UI footer (الكل remaining/limit).

### Ownership Checks
- `_get_owned_session(request, session_id, lesson)` في `courses/views.py` يفلتر بـ `user=request.user` ثم يتأكد من `lesson_id` — **404 لو ليس مالكاً** (لا 403 — لا enumeration).
- الـ answer يجب أن ينتمي لنفس الـ session.
- الـ roleplay يجب أن ينتمي للـ user + لنفس الـ challenge_session.
- الـ message body **لا يقبل** أي `prompt` أو `system` — العميل يمرر فقط `message` للـ roleplay continue.

---

## 7) UI داخل Challenge

### Wrong Feedback Card
ملف: `templates/courses/challenge/components/feedback_card.html`
- زر `<button data-ai-explain>` يظهر تحت الإجابة الصحيحة.
- النص: "Explain with AI Tutor" / "اشرح لي الخطأ".
- icon: `sparkles`.
- container `[data-ai-explain-out]` للنتيجة (hidden مبدئياً).

JS في `challenge_session.html`:
- `fetch(POST)` مع CSRF token.
- `is-loading` class على الزر.
- يضيف paragraph للـ EN + paragraph للـ AR (دير صحيح).
- `is-fallback` class عند status=fallback/failed لإظهار الـ warning style.

### Speaking Card
ملف: `templates/courses/question_renderers/speaking_placeholder.html`
- pill صريحة:
  - `speak_this_sentence` / `pronunciation_check` → "AI speaking feedback coming soon" / "تقييم النطق الذكي قادم قريباً"
  - `ai_roleplay_prompt` → "Short AI roleplay — coming soon inside the card"
- self-check checkbox يبقى المرفأ الآمن.

### Roleplay Card
الـ endpoint جاهز (`ai_roleplay_start` + `ai_roleplay_message`).
الـ UI integration in-card يأتي في تحديث UI لاحق (placeholder الآن — لا يخسر الطالب).

### Summary — AI advice card
ملف: `templates/courses/challenge_summary.html`
- section بـ gradient أصفر/ذهبي.
- زر "Get one quick tip" / "احصل على نصيحة سريعة".
- container hidden — يظهر بعد الـ fetch.
- يستخدم نفس JS pattern (CSRF + fetch + EN/AR paragraphs).

---

## 8) Integration مع Mastery / Mistakes

### عند wrong answer
- الـ AI explanation يربط بـ `ChallengeAnswer.pk` + `ChallengeSession.pk` في الـ ledger.
- الـ `StudentMistake` (من Phase 6) موجود مسبقاً — الـ AI يقرأ `mistake_type` لاختيار تعليمة أفضل.
- `generate_mistake_explanation` يحفظ النتيجة في `StudentMistake.explanation_en/ar` مباشرة.

### تأثير على mastery؟
- **لا** — Phase 7 لا يغيّر `SkillMastery`.
- Mastery يُحدَّث فقط عبر `mastery_service.process_challenge_answer(answer)` كما في Phase 6.
- AI feedback لا يبتلع XP ولا يمنح badge.

### ما تم تأجيله
- 🔜 ربط speaking feedback بـ pronunciation skill mastery (يحتاج STT حقيقي).
- 🔜 منح XP صغير عند إكمال roleplay (يحتاج policy واضحة).
- 🔜 conversation_reply enhancement (الـ stub موجود في الـ interaction_type).

---

## 9) Fallbacks

النظام يعمل بشكل كامل في الحالات التالية:

### 1. `CHALLENGE_AI_ENABLED=False`
- زر Explain يظهر لكن الرد دائماً rule-based.
- summary advice دائماً rule-based.
- `ChallengeAIInteraction` يُسجَّل بـ `status="fallback"` + `error_code="ai_disabled"`.
- لا 5xx، لا blocking.

### 2. `AI_API_KEY=""`
- نفس مسار 1.
- `is_enabled()` يعود False فوراً.

### 3. LLM timeout (>12s)
- `_call_llm` يرفع exception.
- `_dispatch` يصطاد + يستخدم fallback.
- يُسجَّل `status="failed"` + `error_code="HTTPError"` أو `RuntimeError`.

### 4. Limit reached
- `can_call_challenge_ai` يرجع `(False, "session_limit")` أو `"daily_limit"`.
- الـ UI تعرض نفس الزر، لكن الرد fallback مع رسالة:
  - EN: "AI help is available again later. You can continue the challenge."
  - AR: "مساعدة الذكاء الاصطناعي ستكون متاحة لاحقاً. يمكنك متابعة التحدي."

### 5. Missing context
- لو السؤال ليس له skill ولا metadata: الـ context builder يستخدم fallback skill `general_beginner`.
- لو الـ `correct_answer` فارغ: الـ rule-based يقول "(see answer)".

### 6. Roleplay max_turns reached
- `continue_short_roleplay` يرفع status=completed + رسالة:
  - EN: "Great practice — that's enough for now. Try the next card!"
  - AR: "تدريب ممتاز — يكفي الآن. جرّب البطاقة التالية!"

---

## 10) الاختبارات

| Test class | عدد | النتيجة |
|---|---|---|
| ContextBuilderTests | 5 | ✅ |
| GuardrailTests | 4 | ✅ |
| FallbackTests | 2 | ✅ |
| TutorServiceFallbackTests | 4 | ✅ |
| RoleplaySessionTests | 4 | ✅ |
| EndpointTests | 8 | ✅ |
| ChallengeIntegrationStableTests | 2 | ✅ |
| **مجموع Phase 7** | **29** | **✅** |

### تفصيل الاختبارات

**Context:**
- `test_context_contains_lesson_question_skill` ✅
- `test_context_strips_html_and_underscores` ✅
- `test_context_does_not_include_email_or_pii` ✅
- `test_render_user_prompt_is_plain_text` ✅
- `test_hash_prompt_is_stable` ✅

**Guardrails:**
- `test_ai_disabled_blocks_call` ✅
- `test_no_api_key_blocks_call` ✅
- `test_session_limit_blocks_extra_calls` ✅
- `test_daily_limit_blocks_extra_calls` ✅

**Fallbacks:**
- `test_wrong_answer_fallback_for_known_mistake_types` ✅
- `test_end_advice_three_branches` ✅

**Tutor service:**
- `test_explain_wrong_answer_returns_fallback` ✅
- `test_explain_wrong_answer_uses_llm_when_available` ✅
- `test_llm_failure_falls_back_and_records` ✅
- `test_end_challenge_advice_works_without_ai` ✅

**Roleplay:**
- `test_roleplay_session_starts` ✅
- `test_roleplay_message_falls_back_without_api_key` ✅
- `test_roleplay_turn_limit_enforced` ✅
- `test_other_user_cannot_continue_my_roleplay` ✅

**Endpoints:**
- `test_ai_explain_endpoint_returns_json` ✅
- `test_other_user_cannot_access_my_explanation` ✅
- `test_answer_must_belong_to_session` ✅
- `test_roleplay_start_endpoint` ✅
- `test_roleplay_message_endpoint_empty_message_rejected` ✅
- `test_ai_advice_endpoint` ✅
- `test_login_required_on_explain` ✅
- `test_no_raw_prompt_accepted_from_client` ✅

**Regression:**
- `test_challenge_lifecycle_works_when_ai_off` ✅
- `test_summary_renders_ai_advice_section` ✅

### Regression السابقة كلها سليمة
- 18 challenge engine tests ✅
- 39 question types tests ✅
- 34 UI polish tests ✅
- 38 rewards Phase 5 tests ✅
- 38 mastery Phase 6 tests ✅
- 144 motivation suite ✅
- 278 courses suite ✅
- 153 learning_core suite ✅

---

## 11) أوامر الاختبار ونتائجها

```bash
$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check
System check identified no issues (0 silenced).

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test tutor.tests.test_challenge_ai_phase7
Ran 29 tests in 14.908s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test tutor.tests.test_challenge_ai_phase7 courses motivation learning_core
Ran 602 tests in 97.970s
OK
```

أوامر تشغيلية للإنتاج:

```bash
python manage.py migrate tutor

# لتفعيل AI:
# في .env / settings:
#   AI_API_KEY=sk-...
#   AI_API_BASE=https://api.openai.com/v1
#   TUTOR_TEXT_MODEL=gpt-4o-mini
#   CHALLENGE_AI_ENABLED=True
#   (افتراضات أخرى: 5 calls/session, 30/day, 5 turns roleplay)
```

---

## 12) المشاكل المتبقية

### P0 — حاسمة
لا يوجد.

### P1 — مهمّة لـ Phase 8
- 🔜 **Roleplay UI in-card** — الـ endpoints جاهزة لكن لا يوجد بعد widget chat-style داخل البطاقة. حالياً: الـ roleplay يُطلَق من API لكن العرض البصري لا يزال على speaking_placeholder.
- 🔜 **Speaking STT** — speak_this_sentence و pronunciation_check ما زالا self-check فقط؛ AI feedback يحتاج STT حقيقي.
- 🔜 **Auto-fire end advice** — حالياً يحتاج ضغط زر؛ يمكن جعله lazy-load auto عند وصول الـ summary.

### P2 — تحسينات Phase 8+
- 🔜 ربط speaking feedback بـ `SkillMastery` لمهارات pronunciation.
- 🔜 منح XP صغير عند إكمال roleplay (policy needed).
- 🔜 conversation_reply enhancement (interaction_type موجود، الـ logic لاحقاً).
- 🔜 Rate limiting per IP بدلاً من per user فقط.
- 🔜 Streaming token responses بدلاً من single-shot (تحسين UX).
- 🔜 لوحة admin: `ChallengeAIInteraction` للـ moderation.

### P3 — تحسينات صغيرة
- إضافة tooltip على الزر يعرض `get_remaining_ai_calls()`.
- إضافة preference في profile لتعطيل AI لمستخدم واحد.
- backoff exponential عند timeout.
- caching للـ explanations عبر `prompt_hash` (نفس prompt = نفس reply).

### لم يُنفَّذ — TODO واضح
- ❌ Real-time voice avatar / lip-sync.
- ❌ TTS generation للـ AI replies.
- ❌ Full STT (الـ speaking لا يزال self-check).
- ❌ OpenAI realtime voice streaming.
- ❌ AI curriculum generation.
- ❌ Teacher analytics للـ AI usage.
- ❌ Long chat sessions (cap is 5 turns).
- ❌ Image generation.

---

## 13) القرار النهائي

✅ **AI Tutor inside Challenges جاهز للانتقال إلى Prompt 08**.

كل acceptance criteria محقّقة:
1. ✅ AI context builder موجود (`challenge_ai_context.py`).
2. ✅ AI tutor service موجود (`challenge_tutor_service.py` بـ 6 entry points).
3. ✅ Wrong answer explanation يعمل (LLM أو fallback).
4. ✅ Speaking card تعمل بوضوح + pill شفّافة.
5. ✅ AI roleplay short session يعمل (لو AI on) أو fallback opener (لو off).
6. ✅ End challenge advice يعمل rule-based دائماً + LLM عند الإمكان.
7. ✅ AI disabled لا يكسر Challenge (اختبار مخصّص).
8. ✅ AI failure لا يكسر Challenge (mocked exception in test).
9. ✅ Limits/guardrails موجودة + دقيقة (4 settings).
10. ✅ AI interactions محفوظة في `ChallengeAIInteraction`.
11. ✅ StudentMistake.explanation_en/ar يُملأ من `generate_mistake_explanation`.
12. ✅ Challenge Engine لا يزال يعمل (18 + 38 + 34 سابقة + 2 regression جديدة).
13. ✅ Question Types لا تزال تعمل (39 اختبار سابق + الـ speaking updates).
14. ✅ Rewards System لا يزال يعمل (38 + 144 motivation).
15. ✅ Mastery Engine لا يزال يعمل (38 + 153 learning_core).
16. ✅ Classic Quiz لا يزال يعمل.
17. ✅ 602 اختبار تمر.
18. ✅ `manage.py check` clean.

---

## 14) توصية المرحلة التالية

النظام جاهز للانتقال إلى **Prompt 08 — Super Lesson 01** عند الموافقة.

### ما قد يُبنى في Phase 8 (مقترح أولي)
- **Super Lesson 01:** درس متعدد المراحل يجمع كل ما بُنِيَ — Stepper + Question Types + Adaptive Mastery + AI Tutor + Rewards.
- **Lesson-to-Challenge flow:** يبدأ من intro → vocabulary → examples → dialogue → quiz كـ challenge.
- **AI scenes:** roleplay مدمج في الـ dialogue stage.
- **Mastery-driven branching:** الدرس يفترق حسب أداء الطالب.
- **Onlenco-original content:** الشخصيات (أماني، يوسف، نور، كريم، سلمى، عمر، ليلى، طارق، هالة، رشيد) — سيناريو أصلي 100%.

**لن أنتقل تلقائياً.** أنتظر مراجعة هذا التقرير من المستخدم أوّلاً.

---

**انتهى التقرير. جاهز للدمج في `main` ومراجعة Phase 7.**
