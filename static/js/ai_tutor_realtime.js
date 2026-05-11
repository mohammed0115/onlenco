/* Onlenco AI Tutor — live voice-call (OpenAI Realtime).
 *
 * Browser establishes a WebRTC peer directly with OpenAI's Realtime API
 * using a short-lived `client_secret` minted by our /voice-call/session/
 * endpoint. The audio path is browser ↔ OpenAI; Django sees only the
 * token request and the post-call log.
 *
 * Public surface (window.onlencoCall):
 *   .init(opts)     wire up the page once the DOM is ready
 *   .startCall()    begin a session
 *   .endCall()      tear down + log usage
 */
(function (global) {
  'use strict';

  // OpenAI's Realtime SDP endpoint. The model name is appended as a query
  // param — same value the server returns in the session response.
  const REALTIME_BASE = 'https://api.openai.com/v1/realtime';

  const Config = {
    sessionUrl:     null,
    logUrl:         null,
    conversationId: null,
    backUrl:        null,
    language:       'en',
  };

  const STRINGS = {
    en: {
      idle_title:        'Tap to call Layla',
      idle_sub:          "She'll greet you and start a real English conversation.",
      connecting_title:  'Connecting…',
      connecting_sub:    'Setting up your call. Hang on a moment.',
      live_title:        'On a call with Layla',
      live_sub:          'Speak naturally. She listens and replies as you talk.',
      ended_title:       'Call ended',
      ended_sub:         'Tap to call again.',
      mic_blocked:       'Microphone permission was blocked. Allow it in the browser to start the call.',
      no_mic:            'No microphone was detected. Plug one in and try again.',
      ai_unavailable:    'The voice tutor is temporarily unavailable. Please try the chat instead.',
      limit_reached:     "You've reached today's voice-call limit. Switch back to the chat tutor.",
      network:           'Network problem. Check your connection and try again.',
      mute_on:           'Mute',
      mute_off:          'Unmute',
    },
    ar: {
      idle_title:        'اضغط لبدء المكالمة مع ليلى',
      idle_sub:          'ستحييك وتبدأ محادثة إنجليزية حقيقية.',
      connecting_title:  'جارٍ الاتصال…',
      connecting_sub:    'جارٍ تجهيز المكالمة، لحظة من فضلك.',
      live_title:        'مكالمة مع ليلى',
      live_sub:          'تحدّث بطبيعية. ستستمع وتردّ أثناء كلامك.',
      ended_title:       'انتهت المكالمة',
      ended_sub:         'اضغط للاتصال مرة أخرى.',
      mic_blocked:       'تم رفض إذن الميكروفون. اسمح به من المتصفح ثم حاول مرة أخرى.',
      no_mic:            'لم يتم العثور على ميكروفون. وصّل واحدًا وحاول مجدداً.',
      ai_unavailable:    'المعلم الصوتي غير متاح مؤقتًا. جرّب المحادثة النصية.',
      limit_reached:     'لقد استهلكت دقائق المكالمة اليومية. استخدم المحادثة النصية.',
      network:           'مشكلة في الشبكة. تحقق من الاتصال وحاول مرة أخرى.',
      mute_on:           'كتم',
      mute_off:          'إلغاء الكتم',
    },
  };

  function t(key) {
    const lang = Config.language === 'ar' ? 'ar' : 'en';
    return (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.en[key] || key;
  }

  // ----- Element refs (filled in init) ---------------------------------

  const els = {};

  // ----- WebRTC state ---------------------------------------------------

  let peer = null;
  let dataChannel = null;
  let micStream = null;
  let aiAnalyser = null;
  let aiAudioCtx = null;
  let aiVizRaf = null;
  let timerInterval = null;
  let callStartedAt = 0;
  let maxSessionSeconds = 900;         // server overrides
  let maxSessionTimer = null;
  let isMuted = false;
  // Live transcript collected from data-channel events. Sent to the
  // server on hang-up so the conversation list reflects what was said.
  const transcriptTurns = [];
  // Map item id → role so we can attach delta events to the right entry.
  const itemRoles = new Map();

  // ----- State machine --------------------------------------------------

  function setState(next) {
    if (els.card) els.card.dataset.state = next;
    const titleKey = next + '_title';
    const subKey = next + '_sub';
    if (els.title) els.title.textContent = t(titleKey);
    if (els.sub)   els.sub.textContent   = t(subKey);
    // Toggle the start vs. end button.
    if (els.startBtn) els.startBtn.hidden = (next !== 'idle' && next !== 'ended' && next !== 'error');
    if (els.endBtn)   els.endBtn.hidden   = !(next === 'connecting' || next === 'listening'
                                              || next === 'thinking' || next === 'speaking');
    if (els.muteBtn)  els.muteBtn.hidden  = els.endBtn ? els.endBtn.hidden : true;
    if (els.timer)    els.timer.hidden    = !(next === 'listening' || next === 'thinking' || next === 'speaking');
  }

  function showError(msg) {
    if (!els.error) return;
    els.error.hidden = false;
    els.error.textContent = msg;
  }

  function clearError() {
    if (els.error) { els.error.hidden = true; els.error.textContent = ''; }
  }

  // ----- Networking helpers --------------------------------------------

  function getCSRFToken() {
    const cookie = (document.cookie.split('; ').find(c => c.startsWith('csrftoken=')) || '').split('=')[1];
    return cookie || '';
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type':     'application/json',
        'X-CSRFToken':      getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Accept':           'application/json',
      },
      body: JSON.stringify(body || {}),
    }).then(async (r) => {
      if (!r.ok) {
        let body = null;
        try { body = await r.json(); } catch (e) {}
        const err = new Error(body && body.error || 'http ' + r.status);
        err.code = (body && body.error) || r.status;
        err.status = r.status;
        throw err;
      }
      return r.json();
    });
  }

  // ----- Session lifecycle ---------------------------------------------

  async function startCall() {
    clearError();
    setState('connecting');
    transcriptTurns.length = 0;
    itemRoles.clear();

    let sessionInfo;
    try {
      sessionInfo = await postJSON(Config.sessionUrl, { conversation_id: Config.conversationId });
    } catch (e) {
      console.error('[onlenco-call] session request failed:', e);
      const code = e && e.code;
      if (code === 'limit_reached')        showError(t('limit_reached'));
      else if (code === 'subscription_required') showError(t('ai_unavailable'));
      else if (code === 'ai_unavailable')  showError(t('ai_unavailable'));
      else                                 showError(t('network'));
      setState('error');
      return;
    }

    if (typeof sessionInfo.max_session_seconds === 'number') {
      maxSessionSeconds = sessionInfo.max_session_seconds;
    }

    // Capture mic. We request audio only — no video ever.
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      console.error('[onlenco-call] mic getUserMedia failed:', e);
      showError(e && e.name === 'NotFoundError' ? t('no_mic') : t('mic_blocked'));
      setState('error');
      return;
    }

    // Build the peer connection. Audio flows in both directions over a
    // single RTCPeerConnection — OpenAI sends Layla's voice on the
    // remote audio track; we add the user's mic on a sender.
    peer = new RTCPeerConnection();

    peer.ontrack = (ev) => {
      if (els.audio && ev.streams && ev.streams[0]) {
        els.audio.srcObject = ev.streams[0];
        attachAiVisualizer(ev.streams[0]);
      }
    };

    peer.oniceconnectionstatechange = () => {
      const s = peer && peer.iceConnectionState;
      if (s === 'failed' || s === 'disconnected' || s === 'closed') {
        // Network dropped or the remote tore down — end gracefully.
        if (els.card && els.card.dataset.state !== 'idle' && els.card.dataset.state !== 'ended') {
          endCall(/* userInitiated */ false);
        }
      }
    };

    micStream.getAudioTracks().forEach((track) => {
      peer.addTrack(track, micStream);
    });

    // Open a data channel for events (transcripts, response.done, etc).
    dataChannel = peer.createDataChannel('oai-events');
    dataChannel.onopen = () => {
      // Push any client-side overrides as a session.update event.
      // Server already configured the bulk of the session, but we add
      // a brief instruction nudge so Layla opens the call herself.
      try {
        dataChannel.send(JSON.stringify({
          type: 'response.create',
          response: { modalities: ['audio', 'text'] },
        }));
      } catch (e) {}
    };
    dataChannel.onmessage = handleRealtimeEvent;
    dataChannel.onerror = (e) => console.warn('[onlenco-call] data channel error:', e);

    // Standard SDP offer/answer dance with OpenAI's Realtime endpoint.
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);

    let sdpResp;
    try {
      sdpResp = await fetch(`${REALTIME_BASE}?model=${encodeURIComponent(sessionInfo.model || '')}`, {
        method: 'POST',
        body: offer.sdp,
        headers: {
          'Authorization': `Bearer ${sessionInfo.client_secret}`,
          'Content-Type':  'application/sdp',
        },
      });
    } catch (e) {
      console.error('[onlenco-call] SDP fetch failed:', e);
      showError(t('network'));
      setState('error');
      teardownPeer();
      return;
    }

    if (!sdpResp.ok) {
      const text = await sdpResp.text().catch(() => '');
      console.error('[onlenco-call] SDP rejected', sdpResp.status, text);
      showError(t('ai_unavailable'));
      setState('error');
      teardownPeer();
      return;
    }

    const answerSdp = await sdpResp.text();
    await peer.setRemoteDescription({ type: 'answer', sdp: answerSdp });

    // Connection live — switch to listening + start the timer.
    setState('listening');
    callStartedAt = Date.now();
    startTimer();

    // Auto end after the server-imposed cap so a forgotten tab can't
    // burn minutes for hours.
    if (maxSessionTimer) clearTimeout(maxSessionTimer);
    maxSessionTimer = setTimeout(() => endCall(false), maxSessionSeconds * 1000);
  }

  // ----- Realtime event router -----------------------------------------

  function handleRealtimeEvent(ev) {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    const type = msg && msg.type;
    if (!type) return;

    // High-frequency lifecycle events let us flip the orb between
    // listening / thinking / speaking states for visual feedback.
    if (type === 'input_audio_buffer.speech_started') {
      setState('listening');
    } else if (type === 'input_audio_buffer.speech_stopped') {
      setState('thinking');
    } else if (type === 'response.audio.delta' || type === 'response.output_audio.delta') {
      if (els.card && els.card.dataset.state !== 'speaking') setState('speaking');
    } else if (type === 'response.done' || type === 'response.audio.done' || type === 'response.output_audio.done') {
      setState('listening');
    }

    // Track item creation so we know which role each delta belongs to.
    if (type === 'conversation.item.created') {
      const item = msg.item || {};
      if (item.id && (item.role === 'user' || item.role === 'assistant')) {
        itemRoles.set(item.id, item.role);
      }
    }

    // Accumulate user transcript (whisper-1 finalising the input audio).
    if (type === 'conversation.item.input_audio_transcription.completed') {
      const text = (msg.transcript || '').trim();
      if (text) appendTranscript('user', text);
    }

    // Accumulate Layla's text (audio stream has its own text channel).
    if (type === 'response.audio_transcript.done' || type === 'response.output_audio_transcript.done') {
      const text = (msg.transcript || '').trim();
      if (text) appendTranscript('assistant', text);
    }
  }

  function appendTranscript(role, text) {
    transcriptTurns.push({ role, content: text });
    if (!els.transcript) return;
    if (els.transcript.hidden) els.transcript.hidden = false;

    const line = document.createElement('div');
    line.className = 'onlenco-call-line ' + (role === 'user' ? 'is-user' : 'is-assistant');
    const label = (Config.language === 'ar')
      ? (role === 'user' ? 'أنت: ' : 'ليلى: ')
      : (role === 'user' ? 'You: ' : 'Layla: ');
    const strong = document.createElement('strong');
    strong.textContent = label;
    line.appendChild(strong);
    line.appendChild(document.createTextNode(text));
    els.transcript.appendChild(line);
    els.transcript.scrollTop = els.transcript.scrollHeight;
  }

  // ----- AI audio visualizer (drives orb pulse) ------------------------

  function attachAiVisualizer(stream) {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      aiAudioCtx = new Ctx();
      const src = aiAudioCtx.createMediaStreamSource(stream);
      aiAnalyser = aiAudioCtx.createAnalyser();
      aiAnalyser.fftSize = 256; aiAnalyser.smoothingTimeConstant = 0.7;
      src.connect(aiAnalyser);
      const buf = new Uint8Array(aiAnalyser.frequencyBinCount);
      const tick = () => {
        if (!aiAnalyser) return;
        aiAnalyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        const level = Math.min(1, rms * 3.5);
        if (els.orb) els.orb.style.setProperty('--orb-level', level.toFixed(3));
        aiVizRaf = requestAnimationFrame(tick);
      };
      tick();
    } catch (e) { /* visualizer is decorative */ }
  }

  function stopAiVisualizer() {
    if (aiVizRaf) { cancelAnimationFrame(aiVizRaf); aiVizRaf = null; }
    if (aiAudioCtx) { try { aiAudioCtx.close(); } catch (e) {} aiAudioCtx = null; }
    aiAnalyser = null;
    if (els.orb) els.orb.style.setProperty('--orb-level', '0');
  }

  // ----- Timer ----------------------------------------------------------

  function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
  }

  function updateTimer() {
    if (!els.timer) return;
    const sec = Math.max(0, Math.floor((Date.now() - callStartedAt) / 1000));
    const m = Math.floor(sec / 60).toString().padStart(2, '0');
    const s = (sec % 60).toString().padStart(2, '0');
    els.timer.textContent = `${m}:${s}`;
  }

  function stopTimer() {
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  }

  // ----- Mute -----------------------------------------------------------

  function toggleMute() {
    if (!micStream) return;
    isMuted = !isMuted;
    micStream.getAudioTracks().forEach(t => { t.enabled = !isMuted; });
    if (els.muteBtn)   els.muteBtn.setAttribute('aria-pressed', String(isMuted));
    if (els.muteIcon)  els.muteIcon.setAttribute('data-lucide', isMuted ? 'mic-off' : 'mic');
    if (els.muteLabel) els.muteLabel.textContent = isMuted ? t('mute_off') : t('mute_on');
    if (window.lucide) try { window.lucide.createIcons({ root: els.muteBtn }); } catch (e) {}
  }

  // ----- Teardown -------------------------------------------------------

  function teardownPeer() {
    if (maxSessionTimer) { clearTimeout(maxSessionTimer); maxSessionTimer = null; }
    stopTimer();
    stopAiVisualizer();
    if (dataChannel) { try { dataChannel.close(); } catch (e) {} dataChannel = null; }
    if (peer) { try { peer.close(); } catch (e) {} peer = null; }
    if (micStream) {
      micStream.getTracks().forEach(t => { try { t.stop(); } catch (e) {} });
      micStream = null;
    }
    if (els.audio) {
      try { els.audio.srcObject = null; } catch (e) {}
    }
  }

  function endCall(/* userInitiated */) {
    if (!peer && !micStream) return;       // already torn down
    const seconds = callStartedAt ? Math.max(1, Math.round((Date.now() - callStartedAt) / 1000)) : 0;
    const turns = transcriptTurns.slice();

    teardownPeer();
    setState('ended');

    // Fire-and-forget log so the soft cap counter advances and the
    // conversation gets the spoken turns persisted.
    if (Config.logUrl) {
      postJSON(Config.logUrl, {
        conversation_id: Config.conversationId,
        seconds: seconds,
        transcript: turns,
      }).catch((e) => {
        console.warn('[onlenco-call] log post failed:', e);
      });
    }
  }

  // ----- Wire-up --------------------------------------------------------

  function init(opts) {
    Object.assign(Config, opts || {});
    els.card       = document.getElementById('callCard');
    els.orb        = document.getElementById('callOrb');
    els.title      = document.getElementById('callTitle');
    els.sub        = document.getElementById('callSub');
    els.timer      = document.getElementById('callTimer');
    els.transcript = document.getElementById('callTranscript');
    els.startBtn   = document.getElementById('startCallBtn');
    els.endBtn     = document.getElementById('endCallBtn');
    els.muteBtn    = document.getElementById('muteBtn');
    els.muteIcon   = document.getElementById('muteIcon');
    els.muteLabel  = document.getElementById('muteLabel');
    els.audio      = document.getElementById('callAudio');
    els.error      = document.getElementById('callError');

    setState('idle');

    // Browser support gate. WebRTC + getUserMedia + RTCDataChannel are
    // all required; if any is missing, fall back to a clear error.
    const supported = !!(window.RTCPeerConnection
                         && navigator.mediaDevices
                         && navigator.mediaDevices.getUserMedia);
    if (!supported) {
      showError(t('mic_blocked'));
      if (els.startBtn) els.startBtn.disabled = true;
      return;
    }

    if (els.startBtn) {
      els.startBtn.addEventListener('click', (e) => { e.preventDefault(); startCall(); });
    }
    if (els.endBtn) {
      els.endBtn.addEventListener('click', (e) => { e.preventDefault(); endCall(true); });
    }
    if (els.muteBtn) {
      els.muteBtn.addEventListener('click', (e) => { e.preventDefault(); toggleMute(); });
    }

    // Hang up if the user navigates away — avoids burning minutes after
    // they've left the page.
    window.addEventListener('pagehide', () => endCall(false));
    window.addEventListener('beforeunload', () => endCall(false));
  }

  global.onlencoCall = {
    init:      init,
    startCall: startCall,
    endCall:   () => endCall(true),
  };

})(window);
