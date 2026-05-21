# TTS Sanitizer — Manual QA Checklist

The voice on `/daily` and `/weekly` must never read technical noise
(`_`, `UA`, `underscore`, `blank`, raw field keys). Sanitisation runs in
two layers:

- **Python** — `core/services/text_humanizer.py` → `humanize_for_speech()`
  (used server-side, e.g. the `exam_play` view builds `question_tts`).
- **Browser** — `static/js/speech_clean.js` → `onlencoSpeak()` /
  `onlencoSpeechClean()`. Loaded globally via `base.html`.

Every TTS call site goes through `onlencoSpeak()`. Never pass raw text to
`new SpeechSynthesisUtterance(...)` directly.

## Automated tests

```
python manage.py test core.tests.test_text_humanizer
```

## Manual checklist

### /daily
1. Open `/daily/`.
2. Press a "Listen" / 🔊 button on a vocabulary / speaking step.
3. Confirm the voice does NOT say: "underscore", "U A", "blank", "dash".
4. Confirm a fill-in-the-blank prompt (`She ___ home`) is read with the
   blank silent ("She home"), not "She underscore underscore home".

### /weekly
5. Open a weekly assessment (`/weekly/<id>/` → exam player).
6. Let a question auto-play, and press "Replay".
7. Confirm no technical token is spoken; raw keys like
   `weekly_assessment_available` are never read letter-by-letter.

### Quick token check
Paste into the browser console on either page:

```js
onlencoSpeechClean("UA_ user_answer ___ blank blank")   // → "your answer"
onlencoSpeechClean("weekly_assessment_available")        // → "weekly assessment is available"
onlencoSpeechClean("My name is Ahmed ___")               // → "My name is Ahmed"
```

If the output still contains `_`, `UA`, or `blank`, the cached old
`speech_clean.js` is being served — bump the `?v=` query string.
