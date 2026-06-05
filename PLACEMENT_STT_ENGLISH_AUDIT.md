# Audit — Force English STT for Placement Speaking

> Scope: STT language only. NOT touching tutor-auto-start. No deploy / no push.

## 1. Where is the Realtime session created?
`tutor/services/realtime_session.py` → `request_ephemeral_session(*, system_prompt, voice)`
([realtime_session.py:283](tutor/services/realtime_session.py#L283)) — POSTs to
OpenAI GA `…/realtime/client_secrets` with a `session` payload. Called once from
`tutor/api/views.py::voice_call_session` ([tutor/api/views.py:933](tutor/api/views.py#L933))
for every voice call (placement + regular AI tutor).

## 2. Where is `input_audio_transcription` set?
In that payload under `session.audio.input.transcription`
([realtime_session.py:309](tutor/services/realtime_session.py#L309)):
```python
"transcription": {"model": "whisper-1"},
```

## 3. Is there a `language` parameter currently?
**No.** Only `{"model": "whisper-1"}`. Whisper therefore AUTO-DETECTS the spoken
language, which mis-fires on short utterances ("36 years old" → Turkish
"36 yıl sonra").

## 4. Can we pass `language="en"`?
**Yes.** The Realtime transcription config accepts an ISO-639-1 `language`
field (e.g. `"transcription": {"model": "whisper-1", "language": "en"}`). It is
optional and provider-supported, so we can add it for placement only.

## 5. Where are transcripts stored?
The browser's realtime client transcribes via Whisper and POSTs the turns to
`voice_call_log`, which persists them as `TutorMessage(role="user", content=…)`
([tutor/api/views.py:392](tutor/api/views.py#L392)). `placement_voice_finalise` →
`map_speaking_transcript` reads those and aligns them to questions.

## 6. Where can we detect a non-English / doubtful transcript?
At scoring time in `placement/services/speaking_eval.py` — before/after the
meaning evaluation. A cheap heuristic flags foreign-script characters
(e.g. `ı ş ç ö ü`, Arabic letters) or known foreign tokens (`yıl`, `sonra`).

## 7. Safe fix plan
- Add `language` arg to `request_ephemeral_session`; set the transcription
  `language` only when provided.
- In `voice_call_session`, pass `settings.PLACEMENT_STT_LANGUAGE` (default `"en"`)
  **only when `is_placement_call`** → regular AI tutor is untouched (auto-detect),
  so future Arabic tutoring sessions still work.
- Add setting `PLACEMENT_STT_LANGUAGE = "en"`.
- `speaking_eval`: when a non-empty answer looks non-English → mark it
  `stt_uncertain` with a moderate (not failing, not perfect) score instead of a
  confident "wrong", so an STT slip never hard-penalizes the learner. Age-number
  answers ("36" / "thirty six" / "36 years old") are already handled by the
  meaning evaluator; the lenient heuristic also credits them.
- Placement stays `source == "placement_voice"`; all placement AI/STT keeps
  `enforce_minutes=False` → never consumes paid AI-Tutor minutes.

## 8. Migration needed?
**No.** Settings + service/view + scoring changes only — no model/schema change.
