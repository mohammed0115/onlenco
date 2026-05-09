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
    maxRecordingMs:     60_000,
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
    },
    ar: {
      idle:           'اضغط للتحدث',
      listening:      'أستمع إليك…',
      recording:      'جارٍ التسجيل…',
      transcribing:   'جارٍ تحويل الصوت إلى نص…',
      thinking:       'المعلم الذكي يفكر…',
      speaking:       'المعلم الذكي يتحدث…',
      error:          'حدث خطأ، يمكنك المحاولة مرة أخرى.',
      ready:          'جاهز',
      empty_audio:    'لم أسمع شيئًا واضحًا. حاول مرة أخرى.',
      mic_blocked:    'لم يتم السماح باستخدام الميكروفون. يمكنك الكتابة بدلًا من ذلك.',
      network:        'يوجد مشكلة في الاتصال. تحقق من الإنترنت.',
      ai_unavailable: 'المعلم الذكي غير متاح مؤقتًا. حاول مرة أخرى.',
      auth_expired:   'انتهت الجلسة. يرجى تسجيل الدخول مرة أخرى.',
      confirm_delete_voice: 'حذف كل تسجيلاتك الصوتية؟ سيبقى النص المكتوب.',
      voice_history_deleted: 'تم حذف التسجيلات الصوتية.',
    },
  };

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
  }

  /* ---- Chat rendering --------------------------------------------------- */

  function appendUserMessage(text) {
    if (!els.messages) return;
    const wrap = document.createElement('div');
    wrap.className = 'flex justify-end';
    const bubble = document.createElement('div');
    bubble.className = 'onlenco-bubble-user';
    bubble.dir = 'ltr';
    bubble.textContent = text;
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollToBottom();
  }

  function appendAIMessage(text, opts) {
    if (!els.messages) return;
    opts = opts || {};
    const wrap = document.createElement('div');
    wrap.className = 'flex justify-start';
    wrap.setAttribute('data-msg-role', 'assistant');
    if (opts.last) wrap.setAttribute('data-last-assistant', '');
    const bubble = document.createElement('div');
    bubble.className = 'onlenco-bubble-ai';
    bubble.dir = 'ltr';
    bubble.textContent = text;
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
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

  /* ---- Visualizer ------------------------------------------------------ */

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
        vizRaf = requestAnimationFrame(tick);
      };
      tick();
    } catch (e) { /* silent — visualizer is decorative */ }
  }

  function stopVisualizer() {
    if (vizRaf) { cancelAnimationFrame(vizRaf); vizRaf = null; }
    if (audioCtx) { try { audioCtx.close(); } catch(e){} audioCtx = null; }
    analyser = null;
    if (els.mic) els.mic.style.setProperty('--mic-level', '0');
  }

  /* ---- Network helpers ------------------------------------------------- */

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Accept':       'application/json',
      },
      body: JSON.stringify(body || {}),
    }).then(handleResponse);
  }

  function postMultipart(url, formData) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken':  getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Accept':       'application/json',
      },
      body: formData,
    }).then(handleResponse);
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
    // Premium voice: backend TTS (currently OpenAI-compatible). Falls
    // back to browser speechSynthesis on any error so a TTS outage
    // never silently drops the audio reply.
    if (!Config.voiceTtsUrl || !text) return browserSpeak(text, language);
    setState('speaking');
    return postJSON(Config.voiceTtsUrl, { text: text, language: language || 'en' })
      .then((j) => {
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
      .catch(() => browserSpeak(text, language));
  }

  function speakReply(text, language) {
    return Config.serverTts
      ? serverSpeak(text, language)
      : browserSpeak(text, language);
  }

  /* ---- Public actions -------------------------------------------------- */

  function appendStreamingBubble() {
    if (!els.messages) return null;
    const wrap = document.createElement('div');
    wrap.className = 'flex justify-start';
    wrap.setAttribute('data-msg-role', 'assistant');
    wrap.setAttribute('data-last-assistant', '');
    const bubble = document.createElement('div');
    bubble.className = 'onlenco-bubble-ai';
    bubble.dir = 'ltr';
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollToBottom();
    return bubble;
  }

  function sendText(text) {
    if (inFlight) return Promise.resolve();
    text = (text || '').trim();
    if (!text) return Promise.resolve();
    inFlight = true;

    appendUserMessage(text);
    broadcast('user', text);
    if (els.input) els.input.value = '';
    setState('thinking');

    if (Config.streaming && Config.chatStreamUrl && window.fetch) {
      return streamSend(text).catch(() => {
        // Streaming failed mid-flight; fall back to one-shot JSON so
        // the user still gets a reply even if the proxy strips SSE.
        return sendTextFallback(text, /*alreadyAppended*/ true);
      }).finally(() => {
        inFlight = false;
        if (state === 'thinking' || state === 'transcribing') setState('idle');
      });
    }
    return sendTextFallback(text, /*alreadyAppended*/ true).finally(() => {
      inFlight = false;
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
    }).then((j) => {
      if (j.conversation_id) {
        Config.conversationId = j.conversation_id;
        openBroadcast();
      }
      const ai = j.ai_message || {};
      const content = ai.content_humanized || ai.content || '';
      appendAIMessage(content, { last: true });
      broadcast('assistant', content);
      const speech = ai.speech_text || content;
      const lang = ai.language || (/[؀-ۿ]/.test(speech) ? 'ar' : 'en');
      return speakReply(speech, lang);
    }).catch((err) => {
      if (err && err.code === 401) return;
      const code = err && err.body && err.body.error;
      const key = code === 'ai_unavailable' ? 'ai_unavailable'
                : code === 'subscription_required' ? 'auth_expired'
                : 'error';
      handleError(err, key);
    });
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
      recordingStopTimer = setTimeout(() => stopRecording(), Config.maxRecordingMs);
    }).catch((err) => {
      // Most useful branch — surface the *actual* DOMException so users
      // know whether to allow permission, plug in a mic, or close other apps.
      console.error('[onlenco] getUserMedia failed:', err && err.name, err && err.message, err);
      stopVisualizer();
      const name = err && err.name;
      let msg;
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        msg = 'Microphone permission was denied. Click the mic/lock icon in the address bar to allow.';
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        msg = 'No microphone found. Plug one in or use the typed input.';
      } else if (name === 'NotReadableError' || name === 'TrackStartError') {
        msg = 'The microphone is in use by another app. Close it and try again.';
      } else if (name === 'OverconstrainedError') {
        msg = 'Mic constraints were too strict. Refresh and retry.';
      } else if (name === 'SecurityError') {
        msg = 'Browser blocked mic access (security). Use HTTPS or http://localhost.';
      } else {
        msg = 'Could not start recording: ' + (name || err && err.message || 'unknown error');
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

    if (!recordedChunks.length) { setState('idle'); return; }
    const mime = (mediaRecorder && mediaRecorder.mimeType) || 'audio/webm';
    const blob = new Blob(recordedChunks, { type: mime });
    recordedChunks = [];

    if (blob.size === 0) { setState('idle'); return; }

    setState('transcribing');
    const fd = new FormData();
    const ext = mime.includes('mp4') ? 'mp4' : (mime.includes('ogg') ? 'ogg' : 'webm');
    fd.append('audio', blob, `recording.${ext}`);

    postMultipart(Config.voiceTranscribeUrl, fd).then((j) => {
      const transcript = (j.transcript || '').trim();
      if (!transcript) {
        toast(j.message || t('empty_audio'));
        setState('idle');
        return;
      }
      appendUserMessage(transcript);
      broadcast('user', transcript);
      if (els.input) els.input.value = '';
      setState('thinking');

      // Prefer the streaming endpoint so the user hears the first token
      // in ~300 ms instead of waiting for the full reply. Fall back to
      // one-shot JSON if the proxy strips SSE.
      if (Config.voiceRespondStreamUrl) {
        return streamVoiceRespond(transcript, seconds).catch(() => {
          return voiceRespondFallback(transcript, seconds);
        });
      }
      return voiceRespondFallback(transcript, seconds);
    }).catch((err) => {
      if (err && err.code === 401) return;
      const code = err && err.body && err.body.error;
      const key = code === 'too_large' ? 'error'
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
    document.querySelectorAll('[data-prompt]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        if (els.input) {
          els.input.value = btn.getAttribute('data-prompt') || '';
          els.input.focus();
        }
      });
    });
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
