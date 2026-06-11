/* Onlenco AI Tutor — voice + chat SPA controller.
 *
 * Drives the no-page-refresh chat flow by orchestrating fetch() calls to
 * /api/v1/tutor/* endpoints, the MediaRecorder, and a 7-state machine
 * (idle/listening/recording/transcribing/thinking/speaking/error). All
 * state lives on the DOM via `data-state` attributes so the CSS does
 * the visuals without JS rewrites.
 *
 * Public API attached to window.onlencoTutor:
 *   .init(opts)         one-time wire-up
 *   .sendText(text)     send a typed message
 *   .startRecording()   begin MediaRecorder + visualizer
 *   .stopRecording()    stop + upload + transcribe + reply
 *   .setState(name)     manual state override (mostly for debugging)
 */
(function (global) {
  'use strict';

  /* ---- Config + state -------------------------------------------------- */

  const Config = {
    chatSendUrl:        null,
    chatStreamUrl:      null,   // /api/v1/tutor/chat/stream/  (typewriter SSE)
    voiceTranscribeUrl: null,
    voiceRespondUrl:    null,
    voiceRespondStreamUrl: null,
    voiceTtsUrl:        null,
    voiceHistoryUrl:    null,
    sanitizeUrl:        null,
    conversationId:     null,
    language:           'en',
    serverTts:          false,
    streaming:          true,   // typewriter on by default; falls back if SSE fails
    // Recording stays live until the user explicitly hits Stop. The 5
    // minute hard cap is a safety net so a forgotten/stuck recording
    // can't grow unbounded in memory — normal use never reaches it.
    maxRecordingMs:     300_000,
    // Silence-based auto-stop is OFF: per user request the mic only
    // ends when the Stop button is pressed. The VAD threshold below is
    // still here so it can be re-enabled by setting `autoStopOnSilence`
    // to true, but the runtime check skips the cutoff when it's false.
    autoStopOnSilence:  false,
    silenceMinRecordMs: 1200,
    silenceHangoverMs:  1500,
    silenceLevel:       0.04,
    glossary:           null,
  };

  // Cross-tab sync channel — same conversation in two tabs stays in
  // step. Native to all evergreen browsers (Safari 15.4+); we feature-
  // detect so older Safari just falls back to single-tab behaviour.
  let bcast = null;
  function openBroadcast() {
    if (bcast || !window.BroadcastChannel || Config.conversationId == null) return;
    try {
      bcast = new BroadcastChannel('onlenco-tutor-' + Config.conversationId);
      bcast.onmessage = (ev) => {
        const m = ev && ev.data;
        if (!m || m.tabId === tabId) return;
        if (m.type === 'message' && m.role && m.content) {
          (m.role === 'user' ? appendUserMessage : appendAIMessage)(m.content);
        }
      };
    } catch (e) { bcast = null; }
  }
  function broadcast(role, content) {
    if (!bcast) return;
    try {
      bcast.postMessage({type: 'message', role: role, content: content, tabId: tabId});
    } catch (e) {}
  }
  const tabId = Math.random().toString(36).slice(2);

  // Strings split EN/AR. The page picks via Config.language.
  const STRINGS = {
    en: {
      idle:           'Tap to talk',
      listening:      'Listening…',
      recording:      'Recording…',
      transcribing:   'Transcribing…',
      thinking:       'Tutor is thinking…',
      speaking:       'Tutor is speaking…',
      error:          'Something went wrong — try again.',
      ready:          'Ready',
      empty_audio:    "I didn't catch that — could you try again?",
      mic_blocked:    'Microphone access was blocked. You can keep chatting by typing.',
      network:        'Network problem — check your connection.',
      ai_unavailable: 'The AI tutor is temporarily unavailable.',
      auth_expired:   'Your session expired — please sign in again.',
      confirm_delete_voice: 'Delete all your voice recordings? Transcripts will stay.',
      voice_history_deleted: 'Voice recordings deleted.',
      timeout:        'That took too long — please try again.',
    },
    ar: {
      idle:           'اضغط للتسجيل',
      listening:      'أستمع إليك…',
      recording:      'جاري التسجيل...',
      ready_to_send:  'تم التسجيل',
      uploading:      'جاري إرسال الصوت...',
      transcribing:   'جاري فهم صوتك...',
      thinking:       'المساعد يرد الآن...',
      speaking:       'المساعد يرد الآن...',
      error:          'حدث خطأ، يمكنك المحاولة مرة أخرى.',
      ready:          'تم التسجيل',
      empty_audio:    'لم أستطع فهم الصوت بوضوح. حاول مرة أخرى بجملة قصيرة.',
      mic_blocked:    'لم يتم السماح باستخدام الميكروفون. فعّل الإذن وحاول مرة أخرى.',
      no_mic:         'لم يتم العثور على ميكروفون.',
      too_short:      'الصوت قصير جدًا، حاول مرة أخرى.',
      too_long:       'وصلت للحد الأقصى للتسجيل.',
      daily_limit:    'انتهى وقت المساعد الذكي اليومي في خطتك.',
      provider_error: 'لم أستطع فهم الصوت بوضوح. حاول مرة أخرى بجملة قصيرة.',
      unsupported:    'المتصفح لا يدعم التسجيل الصوتي. جرّب متصفحًا آخر.',
      network:        'تعذر إرسال الصوت. تحقق من الاتصال وحاول مرة أخرى.',
      ai_unavailable: 'المساعد الذكي غير متاح مؤقتًا. حاول مرة أخرى.',
      auth_expired:   'انتهت الجلسة. يرجى تسجيل الدخول مرة أخرى.',
      confirm_delete_voice: 'حذف كل تسجيلاتك الصوتية؟ سيبقى النص المكتوب.',
      voice_history_deleted: 'تم حذف التسجيلات الصوتية.',
      timeout:        'استغرق الأمر وقتًا طويلًا، حاول مرة أخرى.',
      remaining_label: 'الوقت المتبقي اليوم',
    },
  };

  // Backend error_code → STRINGS key, so the student always sees a clear
  // Arabic message and never a raw code (Prompt 17.3 C/G).
  const ERROR_CODE_KEYS = {
    DAILY_LIMIT_REACHED:        'daily_limit',
    MICROPHONE_TOO_SHORT:       'too_short',
    TRANSCRIPTION_FAILED:       'provider_error',
    NETWORK_OR_PROVIDER_ERROR:  'network',
  };

  function formatClock(totalSeconds) {
    const s = Math.max(0, Math.floor(Number(totalSeconds) || 0));
    const mm = String(Math.floor(s / 60)).padStart(2, '0');
    const ss = String(s % 60).padStart(2, '0');
    return mm + ':' + ss;
  }

  // Update the "remaining time today" display + lock the mic at zero, using
  // the backend usage snapshot — the single source of truth (Prompt 17.3 E).
  function applyUsage(resp) {
    if (!resp || resp.remaining_seconds == null) return;
    const remaining = Number(resp.remaining_seconds) || 0;
    const el = document.getElementById('voiceRemaining');
    if (el) {
      el.textContent = t('remaining_label') + ': ' + formatClock(remaining);
      el.hidden = false;
    }
    const mic = els.mic || document.getElementById('micButton');
    if (mic) {
      if (remaining <= 0) {
        mic.setAttribute('disabled', 'disabled');
        mic.setAttribute('aria-disabled', 'true');
        toast(t('daily_limit'));
      } else {
        mic.removeAttribute('disabled');
        mic.removeAttribute('aria-disabled');
      }
    }
  }

  function t(key) {
    const lang = Config.language === 'ar' ? 'ar' : 'en';
    return (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.en[key] || key;
  }

  let state = 'idle';
  let mediaRecorder = null;
  let mediaStream = null;
  let recordedChunks = [];
  let recordingStart = 0;
  let recordingStopTimer = null;
  let audioCtx = null, analyser = null, vizRaf = null;
  // Carry-over flags for the in-flight send so streamSend / fallback
  // know whether the message originated from a voice transcript.
  let pendingSpeakingSeconds = 0;
  let pendingVoiceMode = false;

  // Live in-browser speech recognition (Web Speech API). When available,
  // we run it alongside MediaRecorder so the user sees their words land
  // in a placeholder bubble as they speak — no waiting for the upstream
  // Whisper round-trip on stop. MediaRecorder still uploads the audio
  // for SpeakingAttempt persistence in the background.
  let speechRecog = null;          // SpeechRecognition instance
  let liveTranscript = '';         // accumulated final segments
  let liveInterim = '';            // current interim hypothesis
  let liveBubble = null;           // bubble element being filled live
  let livePlaceholderRow = null;   // row container so we can remove on cancel
  let liveStarted = false;         // was the recognition actually started?

  // Continuous-conversation auto-commit. While recording, every time
  // the user stops speaking for ~1.2 s, the accumulated transcript is
  // committed as a turn and sent to the AI immediately. Recording does
  // NOT stop — the next utterance starts a fresh user bubble. This is
  // how a phone-call style flow works: the AI is replying while the
  // student is gathering their next thought.
  const COMMIT_PAUSE_MS = 1200;
  const MIN_COMMIT_CHARS = 3;
  let commitTimer = null;
  let inFlight = false;          // guards against double submits

  /* ---- DOM refs -------------------------------------------------------- */

  let els = {};
  function qs(sel) { return document.querySelector(sel); }

  /* ---- CSRF helper ----------------------------------------------------- */

  function getCSRFToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    const cookie = (document.cookie.split('; ').find(c => c.startsWith('csrftoken=')) || '').split('=')[1];
    return cookie || '';
  }

  /* ---- State machine --------------------------------------------------- */

  function setState(next) {
    state = next;
    if (els.mic) els.mic.setAttribute('data-state', next);
    if (els.status) {
      els.status.setAttribute('data-state', next);
      const label = els.status.querySelector('.onlenco-status-label');
      if (label) label.textContent = t(next);
    }
    if (els.thinking) els.thinking.hidden = (next !== 'thinking' && next !== 'transcribing');
    // Reveal a prominent Stop button during the live recording states
    // so users have an obvious way to end short utterances early. Hidden
    // again as soon as we leave the recording flow so it doesn't clutter
    // the composer.
    if (els.stop) {
      els.stop.hidden = !(next === 'listening' || next === 'recording');
    }
  }

  /* ---- Chat rendering --------------------------------------------------- */

  // The welcome state is server-rendered inside #chatMessages on a brand
  // new conversation. Once the user sends anything we strip it so it
  // doesn't sit between the new bubbles and the previous ones — both
  // text and voice paths funnel through this helper.
  function dismissWelcome() {
    const w = document.getElementById('welcomeState');
    if (w && w.parentNode) w.parentNode.removeChild(w);
  }

  function appendUserMessage(text) {
    if (!els.messages) return;
    dismissWelcome();
    const row = document.createElement('div');
    row.className = 'onlenco-row onlenco-row-user';
    const wrap = document.createElement('div');
    wrap.className = 'onlenco-bubble-wrap';
    const meta = document.createElement('div');
    meta.className = 'onlenco-bubble-meta';
    meta.textContent = (Config.language === 'ar') ? 'أنت' : 'You';
    const bubble = document.createElement('div');
    bubble.className = 'onlenco-bubble-user';
    bubble.dir = 'ltr';
    bubble.textContent = text;
    wrap.appendChild(meta);
    wrap.appendChild(bubble);
    row.appendChild(wrap);
    els.messages.appendChild(row);
    scrollToBottom();
  }

  function _buildAIBubble(opts) {
    // Shared between the streaming pipeline and the one-shot fallback so
    // the rendered DOM looks identical in both paths (avatar + meta +
    // bubble), which keeps the CSS rules trivial.
    opts = opts || {};
    const row = document.createElement('div');
    row.className = 'onlenco-row onlenco-row-ai';
    row.setAttribute('data-msg-role', 'assistant');
    if (opts.last) row.setAttribute('data-last-assistant', '');
    const avatar = document.createElement('div');
    avatar.className = 'onlenco-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.innerHTML = '<i data-lucide="sparkles" class="h-4 w-4"></i>';
    const wrap = document.createElement('div');
    wrap.className = 'onlenco-bubble-wrap';
    const meta = document.createElement('div');
    meta.className = 'onlenco-bubble-meta';
    meta.textContent = (Config.language === 'ar') ? 'المعلم' : 'Tutor';
    const bubble = document.createElement('div');
    bubble.className = 'onlenco-bubble-ai';
    bubble.dir = 'ltr';
    wrap.appendChild(meta);
    wrap.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(wrap);
    return { row: row, bubble: bubble };
  }

  function appendAIMessage(text, opts) {
    if (!els.messages) return;
    dismissWelcome();
    const { row, bubble } = _buildAIBubble(opts);
    bubble.textContent = text;
    els.messages.appendChild(row);
    if (window.lucide) try { window.lucide.createIcons({ root: row }); } catch(e){}
    scrollToBottom();
  }

  function scrollToBottom() {
    if (els.scroller) els.scroller.scrollTop = els.scroller.scrollHeight;
  }

  /* ---- Toast ----------------------------------------------------------- */

  let toastEl = null;
  let toastTimer = null;
  function toast(msg, ms) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'onlenco-toast';
      // Click anywhere on the toast to dismiss — useful for long
      // diagnostic strings that would otherwise overlap the input.
      toastEl.addEventListener('click', () => toastEl.classList.remove('is-shown'));
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add('is-shown');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('is-shown'), ms || 4000);
  }
  // Persistent toast for permission/setup errors — stays up 12s and is
  // dismissable by tap. Long enough that users can read the actionable
  // hint ("click the mic/lock icon to allow").
  function toastPersistent(msg) { toast(msg, 12000); }

  function handleError(err, key) {
    setState('error');
    toast(t(key || 'error'));
    setTimeout(() => { if (state === 'error') setState('idle'); }, 800);
  }

  /* ---- Visualizer + VAD + elapsed counter ------------------------------ */

  // The RAF loop does three jobs in one pass: drive the orb pulse
  // (--mic-level), track the time since the last loud sample for VAD
  // auto-stop, and update the elapsed-seconds counter shown in the
  // status pill. Sharing the AnalyserNode means the cost is unchanged
  // versus the old visualizer-only loop.
  let lastVoiceAt = 0;       // ms timestamp of last above-threshold sample
  let elapsedRaf = 0;        // last UI update time, used to throttle counter

  function startVisualizer(stream) {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      audioCtx = new Ctx();
      const src = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256; analyser.smoothingTimeConstant = 0.7;
      src.connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);
      lastVoiceAt = Date.now();
      elapsedRaf = 0;
      const tick = () => {
        if (!analyser) return;
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        const level = Math.min(1, rms * 3.2);
        if (els.mic) els.mic.style.setProperty('--mic-level', level.toFixed(3));

        const now = Date.now();
        // Only the elapsed counter runs in the loop now. Silence-based
        // auto-stop is disabled by default (Config.autoStopOnSilence)
        // so the mic continues until the user presses Stop.
        if (state === 'recording') {
          const elapsed = now - recordingStart;

          if (Config.autoStopOnSilence) {
            if (rms > Config.silenceLevel) lastVoiceAt = now;
            const silentFor = now - lastVoiceAt;
            if (elapsed >= Config.silenceMinRecordMs &&
                silentFor >= Config.silenceHangoverMs) {
              stopRecording();
            }
          }

          // Update the elapsed-seconds counter at most ~4× per second.
          // Rendered into the status pill label, so no extra DOM nodes.
          if (now - elapsedRaf > 250) {
            elapsedRaf = now;
            updateElapsedLabel(elapsed);
          }
        }
        vizRaf = requestAnimationFrame(tick);
      };
      tick();
    } catch (e) { /* silent — visualizer is decorative */ }
  }

  function updateElapsedLabel(elapsedMs) {
    if (!els.status) return;
    const label = els.status.querySelector('.onlenco-status-label');
    if (!label) return;
    const sec = Math.floor(elapsedMs / 1000);
    const base = (Config.language === 'ar') ? 'جارٍ التسجيل' : 'Recording';
    // No "/ Xs" suffix any more — recording continues until the user
    // presses Stop, so showing a remaining-time fraction would lie.
    const hint = (Config.language === 'ar')
      ? 'اضغط إيقاف عند الانتهاء'
      : 'tap Stop when done';
    label.textContent = `${base} · ${sec}s · ${hint}`;
  }

  function stopVisualizer() {
    if (vizRaf) { cancelAnimationFrame(vizRaf); vizRaf = null; }
    if (audioCtx) { try { audioCtx.close(); } catch(e){} audioCtx = null; }
    analyser = null;
    if (els.mic) els.mic.style.setProperty('--mic-level', '0');
  }

  /* ---- Network helpers ------------------------------------------------- */

  // Single timeout knob for non-streaming requests. SSE responses set
  // their own timeouts via the upstream LLM call; this only protects
  // the JSON one-shot fallbacks (transcribe, send, voice respond, tts).
  // 20s is generous enough for a slow STT+chat round trip without
  // letting users stare at a frozen UI forever.
  const FETCH_TIMEOUT_MS = 20000;

  function _withTimeout(p, controller, ms) {
    const id = setTimeout(() => { try { controller.abort(); } catch(e){} }, ms);
    return p.finally(() => clearTimeout(id));
  }

  function postJSON(url, body) {
    const controller = new AbortController();
    return _withTimeout(fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Accept':       'application/json',
      },
      body: JSON.stringify(body || {}),
      signal: controller.signal,
    }), controller, FETCH_TIMEOUT_MS).then(handleResponse).catch((e) => {
      if (e && e.name === 'AbortError') {
        const err = new Error('timeout'); err.code = 'timeout'; throw err;
      }
      throw e;
    });
  }

  function postMultipart(url, formData) {
    const controller = new AbortController();
    return _withTimeout(fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken':  getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Accept':       'application/json',
      },
      body: formData,
      signal: controller.signal,
    }), controller, FETCH_TIMEOUT_MS).then(handleResponse).catch((e) => {
      if (e && e.name === 'AbortError') {
        const err = new Error('timeout'); err.code = 'timeout'; throw err;
      }
      throw e;
    });
  }

  function handleResponse(r) {
    if (r.status === 401 || r.status === 403) {
      // Authentication expired or wrong owner — show toast, no reload.
      return r.json().catch(() => ({})).then((j) => {
        toast(t('auth_expired'));
        const e = new Error('auth'); e.code = r.status; e.body = j; throw e;
      });
    }
    if (!r.ok) {
      return r.json().catch(() => ({})).then((j) => {
        const e = new Error(j.message || 'http ' + r.status);
        e.code = r.status; e.body = j; throw e;
      });
    }
    return r.json();
  }

  /* ---- Speech synthesis: browser default, server TTS opt-in ------------ */

  function browserSpeak(text, language) {
    if (!('speechSynthesis' in window) || !text) return Promise.resolve();
    return new Promise((resolve) => {
      try {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = language === 'ar' ? 'ar-SA' : 'en-US';
        u.rate = 1.0;
        u.onstart = () => setState('speaking');
        u.onend   = () => { setState('idle'); resolve(); };
        u.onerror = () => { setState('idle'); resolve(); };
        window.speechSynthesis.speak(u);
      } catch (e) { resolve(); }
    });
  }

  function serverSpeak(text, language) {
    // Premium voice: backend TTS (currently OpenAI-compatible). The
    // round-trip can take 5-6 s, which feels slow when the user wants
    // instant audio. We race the fetch against a 2.5 s deadline: if
    // server TTS hasn't returned by then, we kick off the browser TTS
    // so playback starts immediately. The server fetch is abandoned —
    // the user gets quality on a fast network, latency on a slow one.
    if (!Config.voiceTtsUrl || !text) return browserSpeak(text, language);
    setState('speaking');
    let fellBack = false;
    const fallbackDelay = 2500;
    const fallbackTimer = setTimeout(() => {
      fellBack = true;
      browserSpeak(text, language);
    }, fallbackDelay);

    return postJSON(Config.voiceTtsUrl, { text: text, language: language || 'en' })
      .then((j) => {
        clearTimeout(fallbackTimer);
        // Browser TTS already started — don't double-speak. Drop the
        // server payload and let speechSynthesis carry the reply.
        if (fellBack) return;
        const b64 = j && j.audio_b64;
        if (!b64) { setState('idle'); return; }
        return new Promise((resolve) => {
          const player = els.audioPlayer || new Audio();
          player.src = `data:audio/${j.format || 'mp3'};base64,${b64}`;
          player.onended = () => { setState('idle'); resolve(); };
          player.onerror = () => { setState('idle'); resolve(); };
          player.play().catch(() => { setState('idle'); resolve(); });
        });
      })
      .catch(() => {
        clearTimeout(fallbackTimer);
        if (fellBack) return;            // browser TTS already speaking
        return browserSpeak(text, language);
      });
  }

  function speakReply(text, language) {
    return Config.serverTts
      ? serverSpeak(text, language)
      : browserSpeak(text, language);
  }

  /* ---- Public actions -------------------------------------------------- */

  function appendStreamingBubble() {
    if (!els.messages) return null;
    dismissWelcome();
    const { row, bubble } = _buildAIBubble({ last: true });
    els.messages.appendChild(row);
    if (window.lucide) try { window.lucide.createIcons({ root: row }); } catch(e){}
    scrollToBottom();
    return bubble;
  }

  function sendText(text) {
    if (inFlight) return Promise.resolve();
    text = (text || '').trim();
    if (!text) return Promise.resolve();
    inFlight = true;

    // If this text came from a voice transcript, the recording duration
    // is stored on the textarea's dataset by handleRecordingStop. Pull
    // it out here so the chat endpoint can credit speaking minutes,
    // then clear it so the next typed message doesn't reuse the value.
    let speakingSeconds = 0;
    if (els.input && els.input.dataset && els.input.dataset.speakingSeconds) {
      speakingSeconds = parseInt(els.input.dataset.speakingSeconds, 10) || 0;
      delete els.input.dataset.speakingSeconds;
    }
    pendingSpeakingSeconds = speakingSeconds;
    pendingVoiceMode = speakingSeconds > 0;

    appendUserMessage(text);
    broadcast('user', text);
    if (els.input) {
      els.input.value = '';
      // Reset autogrow back to a single row.
      try {
        els.input.dispatchEvent(new Event('input', { bubbles: true }));
      } catch (e) {}
    }
    setState('thinking');

    if (Config.streaming && Config.chatStreamUrl && window.fetch) {
      return streamSend(text).catch(() => {
        // Streaming failed mid-flight; fall back to one-shot JSON so
        // the user still gets a reply even if the proxy strips SSE.
        return sendTextFallback(text, /*alreadyAppended*/ true);
      }).finally(() => {
        inFlight = false;
        pendingSpeakingSeconds = 0;
        pendingVoiceMode = false;
        if (state === 'thinking' || state === 'transcribing') setState('idle');
      });
    }
    return sendTextFallback(text, /*alreadyAppended*/ true).finally(() => {
      inFlight = false;
      pendingSpeakingSeconds = 0;
      pendingVoiceMode = false;
      if (state === 'thinking') setState('idle');
    });
  }

  function streamVoiceRespond(transcript, seconds) {
    return fetch(Config.voiceRespondStreamUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Accept':       'text/event-stream',
      },
      body: JSON.stringify({
        conversation_id: Config.conversationId,
        transcript: transcript,
        speaking_seconds: seconds,
      }),
    }).then((r) => {
      if (r.status === 401 || r.status === 403) {
        toast(t('auth_expired'));
        const e = new Error('auth'); e.code = r.status; throw e;
      }
      if (!r.ok) {
        return r.json().catch(() => ({})).then((j) => {
          const e = new Error(j.error || 'http ' + r.status);
          e.code = r.status; throw e;
        });
      }
      const reader = r.body.getReader();
      const decoder = new TextDecoder('utf-8');
      const bubble = appendStreamingBubble();
      let buffer = '';
      let finalContent = '', finalSpeech = '', finalLang = Config.language || 'en';

      function pump() {
        return reader.read().then(({ value, done }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = buffer.indexOf('\n\n')) !== -1) {
            const raw = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const line = raw.split('\n').find(l => l.startsWith('data: '));
            if (!line) continue;
            try {
              const ev = JSON.parse(line.slice(6));
              handleStreamEvent(ev, bubble);
              if (ev.type === 'done') {
                finalContent = ev.content_humanized || ev.content || finalContent;
                finalSpeech = ev.speech_text || finalSpeech;
                finalLang = ev.language || finalLang;
              }
            } catch (e) {}
          }
          return pump();
        });
      }
      return pump().then(() => {
        if (finalContent) broadcast('assistant', finalContent);
        return speakReply(finalSpeech || finalContent, finalLang);
      });
    });
  }

  function voiceRespondFallback(transcript, seconds) {
    return postJSON(Config.voiceRespondUrl, {
      conversation_id: Config.conversationId,
      transcript: transcript,
      speaking_seconds: seconds,
    }).then((resp) => {
      if (resp.conversation_id) {
        Config.conversationId = resp.conversation_id;
        openBroadcast();
      }
      applyUsage(resp);   // refresh remaining-time display (Prompt 17.3 E)
      const ai = resp.ai_message || {};
      const content = ai.content_humanized || ai.content || '';
      appendAIMessage(content, { last: true });
      broadcast('assistant', content);
      const speech = ai.speech_text || content;
      const lang = ai.language || Config.language;
      return speakReply(speech, lang);
    });
  }

  function streamSend(text) {
    return fetch(Config.chatStreamUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Accept':       'text/event-stream',
      },
      body: JSON.stringify({
        conversation_id: Config.conversationId,
        message: text,
        // Forward voice-mode flag + duration so the server uses the
        // shorter voice-mode token cap and credits speaking minutes.
        voice: pendingVoiceMode,
        speaking_seconds: pendingSpeakingSeconds,
      }),
    }).then((r) => {
      if (r.status === 401 || r.status === 403) {
        toast(t('auth_expired'));
        const e = new Error('auth'); e.code = r.status; throw e;
      }
      if (!r.ok) {
        return r.json().catch(() => ({})).then((j) => {
          const e = new Error(j.error || 'http ' + r.status);
          e.code = r.status; e.body = j; throw e;
        });
      }
      const reader = r.body.getReader();
      const decoder = new TextDecoder('utf-8');
      const bubble = appendStreamingBubble();
      let buffer = '';
      let finalContent = '';
      let finalSpeech = '';
      let finalLang = Config.language || 'en';

      function pump() {
        return reader.read().then(({ value, done }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          // SSE events are separated by a blank line.
          let idx;
          while ((idx = buffer.indexOf('\n\n')) !== -1) {
            const raw = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const line = raw.split('\n').find(l => l.startsWith('data: '));
            if (!line) continue;
            try {
              const ev = JSON.parse(line.slice(6));
              handleStreamEvent(ev, bubble);
              if (ev.type === 'done') {
                finalContent = ev.content_humanized || ev.content || finalContent;
                finalSpeech = ev.speech_text || finalSpeech;
                finalLang = ev.language || finalLang;
              }
            } catch (e) { /* skip malformed event */ }
          }
          return pump();
        });
      }
      return pump().then(() => {
        if (finalContent) broadcast('assistant', finalContent);
        return speakReply(finalSpeech || finalContent, finalLang);
      });
    });
  }

  function handleStreamEvent(ev, bubble) {
    if (!bubble) return;
    if (ev.type === 'start') {
      if (ev.conversation_id) Config.conversationId = ev.conversation_id;
      openBroadcast();
      bubble.textContent = '';
    } else if (ev.type === 'token') {
      bubble.textContent += ev.token || '';
      scrollToBottom();
    } else if (ev.type === 'done') {
      // Replace the streamed plain text with the humanised version
      // so any glossary substitutions (event names → readable copy)
      // land before the final paint.
      bubble.textContent = ev.content_humanized || ev.content || bubble.textContent;
    }
  }

  function sendTextFallback(text, alreadyAppended) {
    return postJSON(Config.chatSendUrl, {
      conversation_id: Config.conversationId,
      message: text,
      voice: pendingVoiceMode,
      speaking_seconds: pendingSpeakingSeconds,
    }).then((j) => {
      if (j.conversation_id) {
        Config.conversationId = j.conversation_id;
        openBroadcast();
      }
      applyUsage(j);   // refresh remaining-time display (Prompt 17.3 E)
      const ai = j.ai_message || {};
      const content = ai.content_humanized || ai.content || '';
      appendAIMessage(content, { last: true });
      broadcast('assistant', content);
      const speech = ai.speech_text || content;
      const lang = ai.language || (/[؀-ۿ]/.test(speech) ? 'ar' : 'en');
      return speakReply(speech, lang);
    }).catch((err) => {
      if (err && err.code === 401) return;
      const body = (err && err.body) || {};
      // Prefer the backend's explicit error_code + Arabic message so the
      // student never sees a raw code (Prompt 17.3 C/G).
      if (body.error_code && ERROR_CODE_KEYS[body.error_code]) {
        if (body.error_code === 'DAILY_LIMIT_REACHED') applyUsage({ remaining_seconds: 0 });
        handleError(err, ERROR_CODE_KEYS[body.error_code]);
        return;
      }
      const code = body.error;
      const key = err && err.code === 'timeout' ? 'timeout'
                : code === 'daily_limit_reached' ? 'daily_limit'
                : code === 'ai_unavailable' ? 'ai_unavailable'
                : code === 'subscription_required' ? 'auth_expired'
                : 'error';
      handleError(err, key);
    });
  }

  /* ---- Live in-browser speech recognition ------------------------------ */

  function _SpeechRecogCtor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function liveRecogSupported() {
    return !!_SpeechRecogCtor();
  }

  function startLiveRecognition() {
    const Ctor = _SpeechRecogCtor();
    if (!Ctor) return false;          // caller falls back to Whisper

    // Reset live transcript state for the new turn.
    liveTranscript = '';
    liveInterim = '';
    liveStarted = false;

    // Create the live placeholder bubble that fills in word by word.
    dismissWelcome();
    livePlaceholderRow = document.createElement('div');
    livePlaceholderRow.className = 'onlenco-row onlenco-row-user';
    const wrap = document.createElement('div');
    wrap.className = 'onlenco-bubble-wrap';
    const meta = document.createElement('div');
    meta.className = 'onlenco-bubble-meta';
    meta.textContent = (Config.language === 'ar') ? 'أنت' : 'You';
    liveBubble = document.createElement('div');
    liveBubble.className = 'onlenco-bubble-user';
    liveBubble.dir = 'ltr';
    liveBubble.dataset.live = '1';
    // Initial placeholder so the bubble isn't empty before the first word
    // is recognised. Uses a subtle dot pulse via inline style — no extra
    // CSS dependency.
    liveBubble.innerHTML = '<span style="opacity:.55">' +
      ((Config.language === 'ar') ? 'يستمع…' : 'Listening…') +
      '</span>';
    wrap.appendChild(meta);
    wrap.appendChild(liveBubble);
    livePlaceholderRow.appendChild(wrap);
    if (els.messages) {
      els.messages.appendChild(livePlaceholderRow);
      scrollToBottom();
    }

    try {
      speechRecog = new Ctor();
      // Always recognize English. This is an English-tutor product:
      // students speak English to practice, even when the UI is in
      // Arabic. Forcing 'en-US' prevents Chrome from trying to parse
      // their English speech as Arabic on AR-locale pages.
      speechRecog.lang = 'en-US';
      speechRecog.continuous = true;
      speechRecog.interimResults = true;
      speechRecog.maxAlternatives = 1;
    } catch (e) {
      console.warn('[onlenco] SpeechRecognition init failed:', e);
      return false;
    }

    speechRecog.onresult = (ev) => {
      // The Web Speech API delivers an array of results; each has either
      // final or interim text. We accumulate finals and replace the
      // interim segment so the bubble stays a single coherent string.
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        const txt = r[0] && r[0].transcript ? r[0].transcript : '';
        if (r.isFinal) {
          liveTranscript = (liveTranscript + ' ' + txt).trim();
        } else {
          interim += txt;
        }
      }
      liveInterim = interim.trim();
      const composed = (liveTranscript + ' ' + liveInterim).trim();
      if (liveBubble) {
        if (composed) {
          liveBubble.textContent = composed;
        } else {
          liveBubble.innerHTML = '<span style="opacity:.55">' +
            ((Config.language === 'ar') ? 'يستمع…' : 'Listening…') +
            '</span>';
        }
      }
      scrollToBottom();

      // Schedule auto-commit on pause: every time we get new audio we
      // push the deadline back. When the user stops talking long enough
      // for the timer to fire, the accumulated transcript is sent to
      // the AI and a fresh live bubble starts for the next utterance.
      // The mic itself keeps running.
      if (state === 'recording') {
        if (commitTimer) clearTimeout(commitTimer);
        const willHave = (liveTranscript + ' ' + liveInterim).trim();
        if (willHave.length >= MIN_COMMIT_CHARS) {
          commitTimer = setTimeout(commitLiveTurn, COMMIT_PAUSE_MS);
        }
      }
    };

    speechRecog.onerror = (ev) => {
      // `no-speech` and `aborted` are expected lifecycle events, not
      // errors worth toasting. Real errors (network, not-allowed) are
      // logged but the audio path still flows so we can fall back.
      const code = ev && ev.error;
      if (code && code !== 'no-speech' && code !== 'aborted') {
        console.warn('[onlenco] speech recognition error:', code);
      }
    };

    speechRecog.onend = () => {
      // Chrome stops the recognizer after extended pauses even with
      // continuous=true. While the user is still recording we want
      // the live transcript to keep flowing, so restart it.
      if (state === 'recording') {
        try { speechRecog.start(); } catch (e) { /* ignore — will retry on next event */ }
      }
    };

    try {
      speechRecog.start();
      liveStarted = true;
      return true;
    } catch (e) {
      console.warn('[onlenco] speechRecog.start() threw:', e);
      return false;
    }
  }

  function stopLiveRecognition() {
    if (commitTimer) { clearTimeout(commitTimer); commitTimer = null; }
    if (!speechRecog) return;
    try {
      // Mute the auto-restart in onend before stopping.
      speechRecog.onend = null;
      speechRecog.stop();
    } catch (e) {}
    speechRecog = null;
  }

  function clearLiveBubble() {
    if (livePlaceholderRow && livePlaceholderRow.parentNode) {
      livePlaceholderRow.parentNode.removeChild(livePlaceholderRow);
    }
    livePlaceholderRow = null;
    liveBubble = null;
  }

  // Send whatever the user has said so far to the AI without stopping
  // the recording. This is what produces the phone-call feel: the AI
  // replies *while* the user is still in mid-conversation, instead of
  // waiting for them to press Stop.
  function commitLiveTurn() {
    if (commitTimer) { clearTimeout(commitTimer); commitTimer = null; }
    const text = (liveTranscript + ' ' + liveInterim).trim();
    if (!text || text.length < MIN_COMMIT_CHARS) return;

    // Lock the current bubble as a committed user message and detach
    // our live references so the next utterance gets a fresh bubble.
    if (liveBubble) {
      liveBubble.textContent = text;
      delete liveBubble.dataset.live;
    }
    livePlaceholderRow = null;
    liveBubble = null;
    liveTranscript = '';
    liveInterim = '';

    broadcast('user', text);

    // Fire the chat stream request without flipping global state to
    // 'thinking' — recording is still live and that state takes
    // precedence. The thinking indicator strip provides the secondary
    // affordance for the in-flight reply.
    if (els.thinking) els.thinking.hidden = false;
    pendingSpeakingSeconds = Math.max(1, Math.round((Date.now() - recordingStart) / 1000));
    pendingVoiceMode = true;

    const send = (Config.streaming && Config.chatStreamUrl)
      ? streamSend(text).catch(() => sendTextFallback(text, true))
      : sendTextFallback(text, true);

    Promise.resolve(send).finally(() => {
      pendingSpeakingSeconds = 0;
      pendingVoiceMode = false;
      if (els.thinking) els.thinking.hidden = true;
    });

    // Open a fresh live bubble for the next utterance so the user sees
    // their continued speech without interruption. We do not call
    // setState — the mic stays in 'recording' state.
    const row = document.createElement('div');
    row.className = 'onlenco-row onlenco-row-user';
    const wrap = document.createElement('div');
    wrap.className = 'onlenco-bubble-wrap';
    const meta = document.createElement('div');
    meta.className = 'onlenco-bubble-meta';
    meta.textContent = (Config.language === 'ar') ? 'أنت' : 'You';
    const bub = document.createElement('div');
    bub.className = 'onlenco-bubble-user';
    bub.dir = 'ltr';
    bub.dataset.live = '1';
    bub.innerHTML = '<span style="opacity:.55">' +
      ((Config.language === 'ar') ? 'يستمع…' : 'Listening…') +
      '</span>';
    wrap.appendChild(meta);
    wrap.appendChild(bub);
    row.appendChild(wrap);
    if (els.messages) {
      els.messages.appendChild(row);
      scrollToBottom();
    }
    livePlaceholderRow = row;
    liveBubble = bub;
  }

  function startRecording() {
    // State guard: if we got stuck in `thinking` because a previous
    // request never resolved, don't refuse — let the user try again.
    if (state === 'recording' || state === 'listening' || state === 'transcribing') {
      console.warn('[onlenco] mic click ignored; state =', state);
      return;
    }

    // Secure-context + API support: fail loudly so users can see why.
    if (!window.isSecureContext) {
      const msg = 'Microphone needs HTTPS or http://localhost. ' +
                  'Current origin is not a secure context, so the browser blocks the mic.';
      console.error('[onlenco]', msg, location.href);
      toastPersistent(msg);
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.error('[onlenco] navigator.mediaDevices.getUserMedia missing');
      toastPersistent(t('mic_blocked'));
      return;
    }
    if (!window.MediaRecorder) {
      console.error('[onlenco] MediaRecorder API not available');
      toastPersistent(t('mic_blocked'));
      return;
    }

    setState('listening');
    console.log('[onlenco] requesting mic permission…');
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      console.log('[onlenco] mic granted, starting recorder');
      mediaStream = stream;
      recordedChunks = [];
      const mime = pickMime();
      try {
        mediaRecorder = mime
          ? new MediaRecorder(stream, { mimeType: mime })
          : new MediaRecorder(stream);
      } catch (e) {
        console.error('[onlenco] MediaRecorder constructor failed:', e);
        stream.getTracks().forEach(tr => tr.stop());
        stopVisualizer();
        toastPersistent('This browser cannot record audio (' + e.message + '). Please type instead.');
        setState('idle');
        return;
      }
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) recordedChunks.push(e.data);
      };
      mediaRecorder.onstop = handleRecordingStop;
      mediaRecorder.onerror = (e) => {
        console.error('[onlenco] MediaRecorder error:', e);
      };
      mediaRecorder.start(250);
      recordingStart = Date.now();
      setState('recording');
      startVisualizer(stream);
      // Kick off the in-browser live recognition. If it works, the
      // bubble fills as the user speaks and on stop we send the
      // accumulated transcript straight to the AI (skipping the slow
      // Whisper round-trip). If unsupported / fails to start, we fall
      // back to Whisper inside handleRecordingStop.
      startLiveRecognition();
      recordingStopTimer = setTimeout(() => stopRecording(), Config.maxRecordingMs);
    }).catch((err) => {
      // Most useful branch — surface the *actual* DOMException so users
      // know whether to allow permission, plug in a mic, or close other apps.
      console.error('[onlenco] getUserMedia failed:', err && err.name, err && err.message, err);
      stopVisualizer();
      const name = err && err.name;
      let msg;
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        msg = t('mic_blocked');
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        msg = t('no_mic');
      } else if (name === 'NotReadableError' || name === 'TrackStartError') {
        msg = t('no_mic');
      } else if (name === 'SecurityError') {
        msg = t('unsupported');
      } else {
        msg = t('error');
      }
      toastPersistent(msg);
      setState('error');
      setTimeout(() => { if (state === 'error') setState('idle'); }, 800);
    });
  }

  function pickMime() {
    if (!window.MediaRecorder) return '';
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
    for (const m of candidates) {
      try { if (MediaRecorder.isTypeSupported(m)) return m; } catch(e){}
    }
    return '';
  }

  function stopRecording() {
    if (state !== 'recording' && state !== 'listening') return;
    if (recordingStopTimer) { clearTimeout(recordingStopTimer); recordingStopTimer = null; }
    try { mediaRecorder && mediaRecorder.stop(); } catch (e) {}
  }

  function handleRecordingStop() {
    const seconds = Math.max(1, Math.round((Date.now() - recordingStart) / 1000));
    if (mediaStream) {
      mediaStream.getTracks().forEach(t => t.stop());
      mediaStream = null;
    }
    stopVisualizer();
    stopLiveRecognition();

    // Capture whatever the live recognizer collected before we tear it
    // down. Browser STT was running while the user spoke, so we already
    // have a transcript with zero extra latency on stop.
    const liveText = (liveTranscript + ' ' + liveInterim).trim();
    const liveRow = livePlaceholderRow;
    const liveBub = liveBubble;
    livePlaceholderRow = null;
    liveBubble = null;
    liveTranscript = '';
    liveInterim = '';

    // Build the audio blob (still used for SpeakingAttempt persistence).
    const mime = (mediaRecorder && mediaRecorder.mimeType) || 'audio/webm';
    const blob = recordedChunks.length ? new Blob(recordedChunks, { type: mime }) : null;
    recordedChunks = [];

    // Fast path: live in-browser recognition produced text. Fire the AI
    // streaming request immediately — no Whisper round-trip — and
    // upload the audio in parallel for SpeakingAttempt storage.
    if (liveText) {
      if (liveBub) {
        // Lock in the final text and clear the live marker so the bubble
        // is treated like any committed user message.
        liveBub.textContent = liveText;
        delete liveBub.dataset.live;
      }
      broadcast('user', liveText);
      if (els.input) els.input.value = '';
      setState('thinking');

      // Background audio upload: don't block the AI request. Fire-and-
      // forget so SpeakingAttempt rows still get the recording.
      if (blob && blob.size > 0) {
        const fd = new FormData();
        const ext = mime.includes('mp4') ? 'mp4' : (mime.includes('ogg') ? 'ogg' : 'webm');
        fd.append('audio', blob, `recording.${ext}`);
        // Mark the upload so the server can opt to skip Whisper if we
        // ever add a "transcript hint" payload. For now it just stores.
        postMultipart(Config.voiceTranscribeUrl, fd).catch(() => {});
      }

      // Pump straight into the chat-stream pipeline (same path as a
      // typed message). voice=true keeps the reply short + counts the
      // speaking minutes for activity stats.
      pendingSpeakingSeconds = seconds;
      pendingVoiceMode = true;
      const chain = (Config.streaming && Config.chatStreamUrl)
        ? streamSend(liveText).catch(() => sendTextFallback(liveText, true))
        : sendTextFallback(liveText, true);
      return Promise.resolve(chain).finally(() => {
        pendingSpeakingSeconds = 0;
        pendingVoiceMode = false;
        if (state === 'thinking' || state === 'transcribing') setState('idle');
      });
    }

    // No live transcript (browser STT unsupported or no speech detected).
    // Fall back to Whisper via the existing voice/transcribe endpoint.
    if (liveRow && liveRow.parentNode) liveRow.parentNode.removeChild(liveRow);

    if (!blob || blob.size === 0) { setState('idle'); return; }

    setState('transcribing');
    const fd = new FormData();
    const ext = mime.includes('mp4') ? 'mp4' : (mime.includes('ogg') ? 'ogg' : 'webm');
    fd.append('audio', blob, `recording.${ext}`);

    // Optimistic placeholder bubble for the Whisper path so the user
    // still sees immediate feedback while STT is in flight.
    dismissWelcome();
    const placeholderRow = document.createElement('div');
    placeholderRow.className = 'onlenco-row onlenco-row-user';
    const placeholderWrap = document.createElement('div');
    placeholderWrap.className = 'onlenco-bubble-wrap';
    const placeholderMeta = document.createElement('div');
    placeholderMeta.className = 'onlenco-bubble-meta';
    placeholderMeta.textContent = (Config.language === 'ar') ? 'أنت' : 'You';
    const placeholderBubble = document.createElement('div');
    placeholderBubble.className = 'onlenco-bubble-user';
    placeholderBubble.dir = 'ltr';
    placeholderBubble.innerHTML = '<i data-lucide="loader-2" class="h-4 w-4 animate-spin"></i> ' +
                                  ((Config.language === 'ar') ? 'جارٍ التحويل…' : 'Transcribing…');
    placeholderWrap.appendChild(placeholderMeta);
    placeholderWrap.appendChild(placeholderBubble);
    placeholderRow.appendChild(placeholderWrap);
    if (els.messages) {
      els.messages.appendChild(placeholderRow);
      if (window.lucide) try { window.lucide.createIcons({ root: placeholderRow }); } catch(e){}
      scrollToBottom();
    }

    postMultipart(Config.voiceTranscribeUrl, fd).then((j) => {
      const transcript = (j.transcript || '').trim();
      if (!transcript) {
        if (placeholderRow.parentNode) placeholderRow.parentNode.removeChild(placeholderRow);
        toast(j.message || t('empty_audio'));
        setState('idle');
        return;
      }
      placeholderBubble.textContent = transcript;
      broadcast('user', transcript);
      if (els.input) els.input.value = '';
      setState('thinking');

      if (Config.voiceRespondStreamUrl) {
        return streamVoiceRespond(transcript, seconds).catch(() => {
          return voiceRespondFallback(transcript, seconds);
        });
      }
      return voiceRespondFallback(transcript, seconds);
    }).catch((err) => {
      if (placeholderRow && placeholderRow.parentNode) {
        placeholderRow.parentNode.removeChild(placeholderRow);
      }
      if (err && err.code === 401) return;
      const code = err && err.body && err.body.error;
      const key = err && err.code === 'timeout' ? 'timeout'
                : code === 'too_large' ? 'error'
                : code === 'ai_unavailable' ? 'ai_unavailable'
                : code === 'stt_unavailable' ? 'ai_unavailable'
                : 'network';
      handleError(err, key);
    }).finally(() => {
      if (state !== 'speaking' && state !== 'idle') setState('idle');
    });
  }

  /* ---- Wire up --------------------------------------------------------- */

  function init(opts) {
    Object.assign(Config, opts || {});
    els.mic       = qs('#micButton');
    els.stop      = qs('#stopRecordingBtn');
    els.input     = qs('#messageInput');
    els.sendBtn   = qs('#sendMessageBtn');
    els.messages  = qs('#chatMessages');
    els.scroller  = qs('#chatScroll');
    els.status    = qs('#voiceStatus');
    els.thinking  = qs('#thinking-indicator');
    els.audioPlayer = qs('#aiAudioPlayer');
    els.serverTtsToggle = qs('#serverTtsToggle');
    els.voiceFallback = qs('#voice-fallback');
    els.deleteHistoryBtn = qs('#deleteVoiceHistoryBtn');

    setState('idle');
    openBroadcast();   // multi-tab: subscribe to this conversation's channel

    // Server TTS toggle: persisted in localStorage so the choice
    // survives reloads. Default is browser speechSynthesis (free).
    if (els.serverTtsToggle) {
      const saved = localStorage.getItem('onlenco.tutor.serverTts');
      Config.serverTts = saved === '1';
      els.serverTtsToggle.checked = Config.serverTts;
      els.serverTtsToggle.addEventListener('change', () => {
        Config.serverTts = els.serverTtsToggle.checked;
        localStorage.setItem('onlenco.tutor.serverTts', Config.serverTts ? '1' : '0');
      });
    }

    // Voice support detection: iOS Safari < 14.5 lacks MediaRecorder.
    // We hide the mic button + show a "type instead" banner up front so
    // students don't tap a dead button.
    const supportsRecording = !!(window.MediaRecorder
                                 && navigator.mediaDevices
                                 && navigator.mediaDevices.getUserMedia);
    if (!supportsRecording) {
      if (els.mic) els.mic.hidden = true;
      if (els.voiceFallback) els.voiceFallback.hidden = false;
    }

    // "Delete my voice history" — privacy control.
    if (els.deleteHistoryBtn) {
      els.deleteHistoryBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (!confirm(t('confirm_delete_voice'))) return;
        fetch(Config.voiceHistoryUrl, {
          method: 'DELETE',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
          },
        }).then((r) => {
          if (r.ok) toast(t('voice_history_deleted'));
          else toast(t('error'));
        }).catch(() => toast(t('network')));
      });
    }

    if (els.sendBtn) {
      els.sendBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (els.input) sendText(els.input.value);
      });
    }
    if (els.input) {
      els.input.addEventListener('keydown', (e) => {
        // Enter sends; Shift+Enter inserts a newline.
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendText(els.input.value);
        }
      });
    }
    if (els.mic) {
      els.mic.addEventListener('click', (e) => {
        e.preventDefault();
        if (state === 'recording' || state === 'listening') {
          stopRecording();
        } else if (state === 'thinking' || state === 'speaking') {
          // A previous request is still in flight (or TTS is playing).
          // Cancel speech and let the user start a new recording — the
          // alternative is the mic button looking dead, which is worse.
          if ('speechSynthesis' in window) window.speechSynthesis.cancel();
          inFlight = false;
          startRecording();
        } else {
          startRecording();
        }
      });
    }
    if (els.stop) {
      els.stop.addEventListener('click', (e) => {
        e.preventDefault();
        stopRecording();
      });
    }
    // Suggested prompts now auto-send: less friction for new students
    // and removes the "type into the box first" puzzle. The button text
    // already matches what they want to ask, so there's no value in
    // making them edit it before submitting.
    document.querySelectorAll('[data-prompt]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const prompt = btn.getAttribute('data-prompt') || '';
        if (!prompt) return;
        if (els.input) els.input.value = prompt;
        sendText(prompt);
      });
    });

    // Textarea auto-grow: keeps the composer feeling like a modern chat
    // without exploding past max-height (handled by CSS).
    if (els.input) {
      const grow = () => {
        els.input.style.height = 'auto';
        els.input.style.height = Math.min(els.input.scrollHeight, 128) + 'px';
      };
      els.input.addEventListener('input', grow);
      grow();
    }

    scrollToBottom();
  }

  // ---- Spec-aligned public surface ----
  // The internals above use short Onlenco names (init / setState / sendText).
  // The names below are aliases so external code (and the project spec)
  // can use the canonical voice-UX vocabulary without us renaming every
  // internal callsite.
  function sendAudioToBackend(blob) {
    if (!blob) return Promise.resolve();
    const fd = new FormData();
    const mime = blob.type || 'audio/webm';
    const ext = mime.includes('mp4') ? 'mp4' : (mime.includes('ogg') ? 'ogg' : 'webm');
    fd.append('audio', blob, `recording.${ext}`);
    setState('transcribing');
    return postMultipart(Config.voiceTranscribeUrl, fd);
  }
  function playAIAudio(audioUrlOrBlob) {
    if (!audioUrlOrBlob || !els.audioPlayer) return Promise.resolve();
    return new Promise((resolve) => {
      const player = els.audioPlayer;
      player.src = (typeof audioUrlOrBlob === 'string')
        ? audioUrlOrBlob
        : URL.createObjectURL(audioUrlOrBlob);
      player.onended = () => { setState('idle'); resolve(); };
      player.onerror = () => { setState('idle'); resolve(); };
      setState('speaking');
      player.play().catch(() => { setState('idle'); resolve(); });
    });
  }
  function showVoiceAnimation(s) { setState(s); }
  function stopVoiceAnimation() { stopVisualizer(); setState('idle'); }

  global.onlencoTutor = {
    // Spec-named API
    initVoiceTutor:     init,
    startRecording:     startRecording,
    stopRecording:      stopRecording,
    sendAudioToBackend: sendAudioToBackend,
    sendTextMessage:    sendText,
    appendUserMessage:  appendUserMessage,
    appendAIMessage:    appendAIMessage,
    playAIAudio:        playAIAudio,
    setTutorState:      setState,
    showVoiceAnimation: showVoiceAnimation,
    stopVoiceAnimation: stopVoiceAnimation,
    handleError:        handleError,
    // Backwards-compatible short names
    init:               init,
    sendText:           sendText,
    setState:           setState,
  };
})(window);
