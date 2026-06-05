# Audit — Tutor auto-starts the voice call

> Scope: make the AI tutor speak first when the session is ready. NOT touching
> STT, speaking_eval, voice/avatar compatibility, or the placement gate logic.
> No deploy / no push.

## 1. Where is the Realtime session created?
Two halves:
- **Server:** `tutor/api/views.py::voice_call_session` mints the ephemeral
  client_secret via `tutor/services/realtime_session.py::request_ephemeral_session`
  and returns a JSON config to the browser.
- **Client (WebRTC):** `static/js/ai_tutor_realtime.js::startCall` builds the
  `RTCPeerConnection`, adds the mic track, opens a data channel `oai-events`,
  and does the SDP offer/answer relay.

## 2. Where does the system know the session is ready?
Client-side: `dataChannel.onopen` ([ai_tutor_realtime.js:286](static/js/ai_tutor_realtime.js#L286))
fires once the realtime data channel is established; the SDP answer is applied
just after. Realtime lifecycle events then arrive via `dataChannel.onmessage`
→ `handleRealtimeEvent`.

## 3. Is there a session-ready / response event?
Yes, over the data channel: `session.created` / `session.updated`,
`response.created` / `response.done`, `conversation.item.created`,
`response.audio.delta`, `input_audio_buffer.speech_started/stopped`, etc.
`handleRealtimeEvent` ([ai_tutor_realtime.js:375](static/js/ai_tutor_realtime.js#L375))
already routes several of these.

## 4. Where can the tutor's first message be sent?
There is ALREADY an attempt: on `dataChannel.onopen` the client sends a generic
`{"type":"response.create","response":{"modalities":["audio","text"]}}`
([ai_tutor_realtime.js:291](static/js/ai_tutor_realtime.js#L291)). It relies
purely on the system prompt to make the tutor open, which is not reliable — the
reported symptom is the tutor waiting for the student.

**Fix:** send a `response.create` that carries an EXPLICIT opening instruction
("Begin now… do not wait for the student to speak first"), differentiated for
placement vs regular, delivered from the server in the session config.

## 5. Preventing a duplicate first message on refresh / reconnect
- Each "Start call" builds a brand-new session + peer + data channel, so a
  refresh = a new call = a fresh opening (correct).
- Within one session we add a one-shot client flag `openingSent` so the opening
  is sent only once even if both `dataChannel.onopen` AND a `session.created`
  event try to trigger it. No server-side/session DB state is needed (the call
  is ephemeral); this satisfies the "tutor_start_message_sent" requirement.

## 6. Safe implementation plan
1. **Server** (`voice_call_session`): add `auto_start: true` and
   `opening_instruction` to the JSON response — placement vs regular text.
   - placement: greet briefly + ask the first question; never wait for the student.
   - regular: greet warmly + ask what they'd like to practice.
2. **Client** (`ai_tutor_realtime.js`): on session-ready, send `response.create`
   with `response.instructions = openingInstruction`, guarded by `openingSent`;
   also trigger on the `session.created`/`session.updated` event for robustness.
   Bump the cache-busting `?v=`.
3. **Template** (`voice_call.html`): add the Arabic "the tutor starts" line for
   placement (the "listen then answer" helper already exists). Pass the opening
   text through from the session config (already returned by the server).
4. **No gate change:** silence *before* the tutor asks is simply "not answered
   yet" (the gate only counts answers at finalise), so the existing
   completed_by_answers / unable_to_answer_after_retries / failed_system /
   admin_override logic is untouched.
5. **No minutes change:** placement stays `source=="placement_voice"` with
   `enforce_minutes=False` → still never consumes paid AI-Tutor minutes; regular
   keeps its plan-minute rules.

## 7. Migration needed?
**No.** JS + view response + template + a couple of tests. No schema change.
