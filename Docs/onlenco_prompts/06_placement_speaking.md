# 06 — Speaking Part of the Placement Test

## Context

The **Onlenco** placement test currently asks 4 written questions (2 MCQs + 2
free-text). The original technical document specified "AI Placement Test
(written + speaking)" — the speaking half is missing. This prompt adds it.

Project conventions:
- `{% load i18n_dict %}` plus `{% t "key" %}` and `{% t_either "en" "ar" %}`.
- Tailwind via Play CDN + `static/css/onlenco.css`.
- Component classes: `.btn`, `.btn-hero`, `.btn-outline`, `.card`, `.badge`.
- Lucide icons.
- AI service: see `placement/services.py` — uses an OpenAI-compatible endpoint
  with function calling, falls back to a deterministic heuristic when no key.
- The existing placement view: `placement/views.py` `placement(request)`,
  template `templates/placement/placement.html`.

## Goal

Add a 5th task to the placement test: a 30-60 second spoken response. The
user records audio in the browser using `MediaRecorder`, the audio is
auto-transcribed with the Web Speech API client-side (no upload), and the
transcript is fed into the existing AI assessor along with the written
answers. The model gets both `written_score` and `speaking_score`.

The audio file itself is **not** uploaded to the server — only the
transcript is sent. This keeps storage and privacy concerns simple.

## Spec

### View changes — `placement/views.py`

The current view collects `q1`, `q2`, `q3`, `q4`. Add a `q5_transcript`
field that comes from the form as a hidden `<input>` populated by JS.

Validation rules:
- `q5_transcript` must be ≥ 30 characters (about 6-8 words). If shorter,
  return the form with an error message: "Please record a longer spoken
  answer (at least 5 sentences)."
- All other validation rules unchanged.

Pass `q5` to `assess()` alongside the other answers.

### Service changes — `placement/services.py`

Update `_build_user_prompt()` to include the new question:

```python
def _build_user_prompt(answers: dict) -> str:
    return (
        "Learner answers:\n"
        f"1. Grammar MCQ ('She ___ to school every day'): {answers.get('q1','')}\n"
        f"2. Grammar MCQ (which is correct): {answers.get('q2','')}\n"
        f"3. Free writing about hobbies: {answers.get('q3','')}\n"
        f"4. Past tense description (yesterday): {answers.get('q4','')}\n"
        f"5. Spoken response transcript (talked for ~45 seconds about their daily routine): "
        f"{answers.get('q5','')}\n\n"
        "Use answers 1-4 to score 'written_score' and answer 5 to score "
        "'speaking_score'. Each is 0-100. Return CEFR level and short feedback."
    )
```

Update `_heuristic_fallback()` to score `speaking_score` from `q5` length and
sentence variety (mirror the q4 logic). Currently it just returns
`written_score - 10` — replace with a real (heuristic) calculation.

### Template changes — `templates/placement/placement.html`

After Q4, add **Q5: Speaking task**:

```html
<div class="space-y-3">
  <p class="text-base font-semibold">5. {% t "pl.q5" %}</p>
  <p class="text-sm text-muted-foreground">{% t "pl.q5_intro" %}</p>

  <div class="card p-5 bg-muted/30">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-3">
        <button type="button" id="rec-toggle" class="btn btn-hero">
          <i data-lucide="mic" class="h-4 w-4"></i>
          <span id="rec-label">{% t "pl.q5_record" %}</span>
        </button>
        <span id="rec-timer" class="text-sm text-muted-foreground" hidden>0:00</span>
      </div>
      <span id="rec-status" class="text-sm text-muted-foreground"></span>
    </div>
    <textarea id="q5-transcript-display" rows="5" readonly
              dir="ltr" class="font-mono text-sm"
              placeholder="{% t 'pl.q5_transcript_hint' %}"></textarea>
    <input type="hidden" name="q5_transcript" id="q5-transcript">
  </div>
  <p class="text-xs text-muted-foreground">{% t "pl.q5_note" %}</p>
</div>
```

Add a JS block that wires up the speech recognition. It must:

1. Feature-detect `window.SpeechRecognition || window.webkitSpeechRecognition`.
   If unsupported, hide the record button and show: "Your browser doesn't
   support voice recording. Please type your answer instead." with a
   fallback `<textarea name="q5_transcript">`.
2. On record start: change button to "Stop", show timer ticking up,
   `recognition.lang = 'en-US'`, `recognition.continuous = true`,
   `recognition.interimResults = true`.
3. As partial results arrive, append to the transcript display (and to the
   hidden input).
4. Stop after either:
   - User clicks "Stop"
   - 60 seconds elapsed (auto-stop with a "Time's up!" status)
5. After stop, button label becomes "Re-record" and clicking it clears the
   transcript and starts fresh.

Keep the script self-contained in the template — no new files. About 60
lines of vanilla JS.

### i18n strings — add to `core/translations.py`

```python
"pl.q5":              {"en": "Speaking task — record yourself in English",
                       "ar": "مهمة تحدث — سجّل نفسك بالإنجليزية"},
"pl.q5_intro":        {"en": "Talk for about 45 seconds about your typical day. "
                              "What time do you wake up? What do you usually eat? "
                              "What do you do in the evenings?",
                       "ar": "تحدث لمدة 45 ثانية تقريباً عن يومك المعتاد. متى تستيقظ؟ "
                              "ماذا تأكل عادةً؟ ماذا تفعل في المساء؟"},
"pl.q5_record":       {"en": "Start recording",        "ar": "ابدأ التسجيل"},
"pl.q5_stop":         {"en": "Stop",                   "ar": "إيقاف"},
"pl.q5_rerecord":     {"en": "Record again",           "ar": "إعادة التسجيل"},
"pl.q5_transcript_hint": {"en": "Your speech will appear here as you talk.",
                          "ar": "سيظهر كلامك هنا أثناء التحدث."},
"pl.q5_note":         {"en": "Audio is processed in your browser. We only store the transcript.",
                       "ar": "تتم معالجة الصوت في متصفحك. نحن نخزن النص فقط."},
"pl.q5_unsupported":  {"en": "Your browser doesn't support voice recording. "
                              "Please type your answer below instead.",
                       "ar": "متصفحك لا يدعم تسجيل الصوت. يرجى كتابة إجابتك أدناه بدلاً من ذلك."},
"pl.q5_too_short":    {"en": "Please record a longer spoken answer (at least 5 sentences).",
                       "ar": "يرجى تسجيل إجابة شفهية أطول (5 جمل على الأقل)."},
"pl.q5_recording":    {"en": "Recording…",             "ar": "جاري التسجيل…"},
"pl.q5_done":         {"en": "Recording complete",     "ar": "اكتمل التسجيل"},
```

## Acceptance criteria

A reviewer should be able to:

1. Open `/placement/` while logged in.
2. Fill in Q1–Q4.
3. See Q5 with a "Start recording" button and a placeholder textarea.
4. Click "Start recording" → browser asks for mic permission → granted.
5. Speak for ~30 seconds → see live transcription appear in the textarea.
6. Click "Stop" → button becomes "Record again" and transcript is preserved.
7. Submit the form → AI returns a CEFR level whose `speaking_score` reflects
   the recorded answer (try recording very little — score should be lower).
8. Open the page in a browser without speech-recognition support (Firefox
   on Linux is one) → see the fallback message and a textarea instead of
   the record button.
9. Submit with a too-short transcript → see the validation error.
10. Submit successfully → land on the result page with the CEFR level.

In `/admin/`, the new placement result row's `transcript` JSON should now
include a `q5` field with the spoken transcript.

## Out of scope

- No server-side audio upload, transcription, or storage.
- No multi-language support for speech recognition (English only).
- No accent grading, prosody analysis, or pronunciation scoring beyond what
  the LLM can infer from the transcript.
- No ability to upload pre-recorded audio.

## Style guide

- Mic button: `.btn-hero` with the Lucide `mic` icon. When recording, swap
  to a "stop" state with `mic-off` icon and a subtle red pulse on the
  button background.
- Timer format: `M:SS`, monospace.
- Transcript textarea: monospace font, `dir="ltr"`, read-only-ish (the user
  doesn't type — the JS fills it).

## What to deliver

A patched `onlenco_django.zip` with:

- Updated `placement/views.py` to handle q5
- Updated `placement/services.py` for the new prompt and improved fallback
- Updated `templates/placement/placement.html` with the recording UI + JS
- New i18n strings in `core/translations.py`

`python manage.py check` clean. The placement flow still works in browsers
without speech-recognition support (graceful fallback to typing).
