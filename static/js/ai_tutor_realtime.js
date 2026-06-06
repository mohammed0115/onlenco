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

  // GA Realtime SDP endpoint. Old Beta URL ``/v1/realtime`` (with or
  // without ``?model=...``) returns ``beta_api_shape_disabled`` since
  // the GA migration. The new endpoint is ``/v1/realtime/calls`` and
  // the model is implicit in the ek_ session — no query param needed.
  const REALTIME_BASE = 'https://api.openai.com/v1/realtime/calls';

  const Config = {
    sessionUrl:     null,
    logUrl:         null,
    cancelStaleUrl: null,
    sdpRelayUrl:    null,  // optional — when set, route SDP via Django
    conversationId: null,
    backUrl:        null,
    // Placement Part 2 only: the closing phrases the interviewer is prompted
    // to say after question 5. When one is heard we end the call and route to
    // the result. Setting this also marks the call as "placement", so it
    // routes to backUrl whenever the call ends. Null = normal AI-tutor call.
    autoEndPhrases: null,
    language:       'en',
    tutorNameEn:    'Layla',
    tutorNameAr:    'ليلى',
  };

  let autoEndScheduled = false;
  let isUnloading = false;

  // Strings use {name} as a placeholder for the chosen tutor (Layla /
  // Omar / Sara). Arabic strings stay gender-neutral so the same copy
  // works for any avatar — verb-y phrases are rephrased to neutral
  // forms ("جارٍ تحضير الرد" rather than "تجهّز إجابتها").
  const STRINGS = {
    en: {
      idle_title:        'Tap to call {name}',
      idle_sub:          "Your teacher will greet you and start a real English conversation.",
      connecting_title:  'Connecting…',
      connecting_sub:    'Setting up your call. Hang on a moment.',
      tutor_starting_title: 'Getting your tutor ready…',
      tutor_starting_sub:   '{name} will start and ask the first question. Just listen.',
      tutor_speaking_title: '{name} is speaking',
      tutor_speaking_sub:   'Listen to the question…',
      listening_for_student_title: 'Your turn',
      listening_for_student_sub:   'Now answer with one word or a short sentence.',
      student_speaking_title: 'Listening…',
      student_speaking_sub:   'Go ahead — {name} can hear you.',
      listening_title:   'Listening…',
      listening_sub:     'Go ahead — {name} can hear you.',
      thinking_title:    'Thinking…',
      thinking_sub:      '{name} is preparing a reply.',
      speaking_title:    '{name} is speaking',
      speaking_sub:      'Listen — your turn next.',
      live_title:        'On a call with {name}',
      live_sub:          'Speak naturally. Your teacher listens and replies as you talk.',
      ended_title:       'Call ended',
      ended_sub:         'Tap to call again.',
      error_title:       'Something went wrong',
      error_sub:         'See the message below and try again.',
      mic_blocked:       'Microphone permission was blocked. Allow it in the browser to start the call.',
      no_mic:            'No microphone was detected. Plug one in and try again.',
      ai_unavailable:    'The voice tutor is temporarily unavailable. Please try the chat instead.',
      limit_reached:     "You've reached today's voice-call limit. Switch back to the chat tutor.",
      concurrent_session: 'Another voice call is still open. We tried to clean it up — please tap Start again.',
      network:           'Network problem. Check your connection and try again.',
      mute_on:           'Mute',
      mute_off:          'Unmute',
    },
    ar: {
      idle_title:        'اضغط لبدء المكالمة مع {name}',
      idle_sub:          'سيرحّب بك معلمك ويبدأ محادثة إنجليزية حقيقية.',
      connecting_title:  'جارٍ الاتصال…',
      connecting_sub:    'جارٍ تجهيز المكالمة، لحظة من فضلك.',
      tutor_starting_title: 'جارٍ تجهيز المدرس الذكي…',
      tutor_starting_sub:   'سيبدأ {name} ويطرح السؤال الأول. فقط استمع.',
      tutor_speaking_title: 'يتحدّث {name}',
      tutor_speaking_sub:   'استمع إلى السؤال…',
      listening_for_student_title: 'دورك الآن',
      listening_for_student_sub:   'الآن أجب بصوتك بكلمة أو جملة قصيرة.',
      student_speaking_title: 'جارٍ الاستماع…',
      student_speaking_sub:   'تفضّل بالحديث — {name} ينصت إليك.',
      listening_title:   'جارٍ الاستماع…',
      listening_sub:     'تفضّل بالحديث — {name} ينصت إليك.',
      thinking_title:    'تفكير…',
      thinking_sub:      'جارٍ تحضير الرد…',
      speaking_title:    'يتحدّث {name}',
      speaking_sub:      'استمع — دورك بعدها.',
      live_title:        'مكالمة مع {name}',
      live_sub:          'تحدّث بطبيعية. معلمك ينصت ويردّ أثناء كلامك.',
      ended_title:       'انتهت المكالمة',
      ended_sub:         'اضغط للاتصال مرة أخرى.',
      error_title:       'حدث خطأ',
      error_sub:         'راجع الرسالة أدناه وحاول مرة أخرى.',
      mic_blocked:       'تم رفض إذن الميكروفون. اسمح به من المتصفح ثم حاول مرة أخرى.',
      no_mic:            'لم يتم العثور على ميكروفون. وصّل واحدًا وحاول مجدداً.',
      ai_unavailable:    'المعلم الصوتي غير متاح مؤقتًا. جرّب المحادثة النصية.',
      limit_reached:     'لقد استهلكت دقائق المكالمة اليومية. استخدم المحادثة النصية.',
      concurrent_session: 'مكالمة سابقة لم تُغلق. تم إغلاقها — اضغط ابدأ مرة أخرى.',
      network:           'مشكلة في الشبكة. تحقق من الاتصال وحاول مرة أخرى.',
      mute_on:           'كتم',
      mute_off:          'إلغاء الكتم',
    },
  };

  function t(key) {
    const lang = Config.language === 'ar' ? 'ar' : 'en';
    const raw = (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.en[key] || key;
    const name = lang === 'ar' ? (Config.tutorNameAr || 'ليلى') : (Config.tutorNameEn || 'Layla');
    return raw.replace(/\{name\}/g, name);
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
  let openingSent = false;             // one-shot guard: tutor opens the call once
  let tutorHasSpoken = false;          // the tutor must speak BEFORE we listen
  let currentPhase = 'idle';           // logical call phase (see PHASE_VISUAL)
  let placementQuestions = [];         // [{id, order, cues:[...]}] for live binding
  let placementAnswerUrl = null;       // POST endpoint to save a per-question answer
  let pqIndex = -1;                    // index of the question being asked right now
  let activeSessionInfo = null;        // populated by startCall, read by endCall
  // Live transcript collected from data-channel events. Sent to the
  // server on hang-up so the conversation list reflects what was said.
  const transcriptTurns = [];
  // Map item id → role so we can attach delta events to the right entry.
  const itemRoles = new Map();

  // ----- State machine --------------------------------------------------
  // Logical PHASES (call flow) are kept separate from the VISUAL data-state
  // the CSS keys off, so we can show "the tutor is starting" without entering
  // the student-listening look. The tutor ALWAYS speaks before we listen.
  //   connecting → tutor_starting → tutor_speaking → listening_for_student
  //   → student_speaking → thinking → tutor_speaking → … → ended
  const PHASE_VISUAL = {
    idle: 'idle',
    connecting: 'connecting',
    tutor_starting: 'connecting',          // warm orb, NO listening rings
    tutor_speaking: 'speaking',
    listening_for_student: 'listening',
    student_speaking: 'listening',
    thinking: 'thinking',
    ended: 'ended',
    error: 'error',
  };

  function dlog() {
    if (!(Config.debug || global.__onlencoCallDebug)) return;
    try { console.log.apply(console, ['[onlenco-call]'].concat([].slice.call(arguments))); } catch (e) {}
  }

  function setPhase(phase) {
    currentPhase = phase;
    const visual = PHASE_VISUAL[phase] || phase;
    if (els.card) { els.card.dataset.state = visual; els.card.dataset.phase = phase; }
    if (els.title) els.title.textContent = t(phase + '_title');
    if (els.sub)   els.sub.textContent   = t(phase + '_sub');
    // Toggle the start vs. end button (driven by the VISUAL state).
    if (els.startBtn) els.startBtn.hidden = (visual !== 'idle' && visual !== 'ended' && visual !== 'error');
    if (els.endBtn)   els.endBtn.hidden   = !(visual === 'connecting' || visual === 'listening'
                                              || visual === 'thinking' || visual === 'speaking');
    if (els.muteBtn)  els.muteBtn.hidden  = els.endBtn ? els.endBtn.hidden : true;
    if (els.timer)    els.timer.hidden    = !(visual === 'listening' || visual === 'thinking' || visual === 'speaking');
  }

  // Back-compat shim: a few call sites still pass visual names directly.
  function setState(next) { setPhase(next); }

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
        // Server may include a human-readable, already-localised message
        // (e.g. placement safety-quota limits) — surface it verbatim.
        err.detail = body && body.message ? String(body.message) : '';
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
    openingSent = false;   // fresh session → the tutor opens once
    tutorHasSpoken = false; // never enter "listening" before the tutor speaks
    pqIndex = -1;          // no placement question asked yet

    let sessionInfo;
    try {
      sessionInfo = await postJSON(Config.sessionUrl, { conversation_id: Config.conversationId });
      activeSessionInfo = sessionInfo;
      placementQuestions = (sessionInfo && sessionInfo.placement_questions) || [];
      placementAnswerUrl = (sessionInfo && sessionInfo.placement_answer_url) || null;
    } catch (e) {
      console.error('[onlenco-call] session request failed:', e);
      const code = e && e.code;
      const placementCodes = [
        'placement_disabled', 'placement_max_attempts',
        'placement_max_minutes', 'placement_cooldown',
      ];
      if (placementCodes.indexOf(code) !== -1) showError((e && e.detail) || t('limit_reached'));
      else if (code === 'limit_reached')        showError((e && e.detail) || t('limit_reached'));
      else if (code === 'subscription_required') showError(t('ai_unavailable'));
      else if (code === 'ai_unavailable')  showError(t('ai_unavailable'));
      else if (code === 'concurrent_session') {
        // A previous session was left "in_progress" (browser closed mid-call,
        // network glitch, etc.). The backend will auto-cancel it after 10
        // minutes; for an immediate retry we ping the cancel endpoint and
        // re-attempt once.
        if (Config.cancelStaleUrl) {
          try {
            await postJSON(Config.cancelStaleUrl, {});
            // single retry after cleanup
            sessionInfo = await postJSON(Config.sessionUrl, { conversation_id: Config.conversationId });
            activeSessionInfo = sessionInfo;
          } catch (retryErr) {
            showError(t('concurrent_session') || t('ai_unavailable'));
            setState('error');
            return;
          }
        } else {
          showError(t('concurrent_session') || t('ai_unavailable'));
          setState('error');
          return;
        }
      }
      else                                 showError(t('network'));
      if (!activeSessionInfo) {
        setState('error');
        return;
      }
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
    dataChannel.onopen = () => { maybeSendOpening(); };
    dataChannel.onmessage = handleRealtimeEvent;
    dataChannel.onerror = (e) => console.warn('[onlenco-call] data channel error:', e);

    // Standard SDP offer/answer dance. We route the SDP through Django's
    // /voice-call/sdp/ relay rather than fetching api.openai.com directly:
    //   * keeps the ek_ token off the wire after the session POST
    //   * sidesteps the GA-era CORS tightening that turned previously
    //     working browser→OpenAI POSTs into opaque failures
    //   * surfaces upstream errors in our server logs instead of a
    //     generic "ai_unavailable" toast
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);

    let sdpResp;
    const sdpUrl = Config.sdpRelayUrl || REALTIME_BASE;
    const useRelay = !!Config.sdpRelayUrl;
    try {
      if (useRelay) {
        sdpResp = await fetch(sdpUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
            'Accept': 'application/sdp, text/plain, */*',
          },
          body: JSON.stringify({
            client_secret: sessionInfo.client_secret,
            model:         sessionInfo.model || '',
            sdp:           offer.sdp,
          }),
        });
      } else {
        sdpResp = await fetch(sdpUrl, {
          method: 'POST',
          body: offer.sdp,
          headers: {
            'Authorization': `Bearer ${sessionInfo.client_secret}`,
            'Content-Type':  'application/sdp',
          },
        });
      }
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

    // Connection live. The TUTOR opens the call, so we DON'T enter the
    // student-listening state yet — we show "tutor is starting" until the
    // tutor's first audio arrives. (Previously this set 'listening' here,
    // which wrongly told the student to speak first.)
    setPhase('tutor_starting');
    dlog('connection live → tutor_starting (waiting for tutor to speak)');
    callStartedAt = Date.now();
    startTimer();

    // Auto end after the server-imposed cap so a forgotten tab can't
    // burn minutes for hours. We pass userInitiated=true so the
    // backUrl navigation still fires — for placement Part 2 the
    // student needs to land on the finalise page even when the 5-min
    // cap (not their finger on the End button) closed the call.
    if (maxSessionTimer) clearTimeout(maxSessionTimer);
    maxSessionTimer = setTimeout(() => endCall(true), maxSessionSeconds * 1000);
  }

  // ----- Auto-start: the tutor speaks first ----------------------------
  // Fire ONCE per session (guarded), as soon as the session is ready. The
  // student never has to start the conversation. The opening instruction is
  // provided by the server (placement asks the first question; regular AI
  // tutor greets and asks what to practise).
  function maybeSendOpening() {
    if (openingSent || !dataChannel || dataChannel.readyState !== 'open') return;
    const info = activeSessionInfo || {};
    dlog('auto_start', info.auto_start, '| opening_instruction', info.opening_instruction);
    if (info.auto_start === false) return;
    openingSent = true;
    const response = { modalities: ['audio', 'text'] };
    if (info.opening_instruction) response.instructions = info.opening_instruction;
    try {
      dlog('dataChannel open → sending opening response.create');
      dataChannel.send(JSON.stringify({ type: 'response.create', response: response }));
    } catch (e) { openingSent = false; }   // allow a retry if the send failed
  }

  // ----- Realtime event router -----------------------------------------

  function handleRealtimeEvent(ev) {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    const type = msg && msg.type;
    if (!type) return;

    // The session is fully configured server-side → safe to open the call.
    if (type === 'session.created' || type === 'session.updated') {
      maybeSendOpening();
    }

    // High-frequency lifecycle events let us flip the orb between
    // tutor-speaking / listening / thinking states. CRITICAL: we never enter
    // a student-listening phase until the tutor has actually spoken — the
    // tutor opens the call.
    if (type === 'response.audio.delta' || type === 'response.output_audio.delta') {
      // The tutor's voice is playing.
      if (!tutorHasSpoken) { tutorHasSpoken = true; dlog('assistant started (first audio)'); }
      if (currentPhase !== 'tutor_speaking') setPhase('tutor_speaking');
    } else if (type === 'response.done' || type === 'response.audio.done' || type === 'response.output_audio.done') {
      // A tutor turn finished. Only NOW is it the student's turn to answer.
      if (tutorHasSpoken) {
        dlog('assistant done → switching to listening_for_student');
        setPhase('listening_for_student');
      }
    } else if (type === 'input_audio_buffer.speech_started') {
      // The student started speaking — but ignore any audio BEFORE the tutor
      // has spoken (stray noise / early mic), so we never show "your turn"
      // prematurely.
      if (tutorHasSpoken) setPhase('student_speaking');
    } else if (type === 'input_audio_buffer.speech_stopped') {
      if (tutorHasSpoken) setPhase('thinking');
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
      if (text) {
        appendTranscript('user', text);
        savePlacementAnswer(text);   // bind FINAL student transcript to the live question
      }
    }

    // Accumulate Layla's text (audio stream has its own text channel).
    if (type === 'response.audio_transcript.done' || type === 'response.output_audio_transcript.done') {
      const text = (msg.transcript || '').trim();
      if (text) {
        tutorHasSpoken = true;   // a tutor turn was transcribed → it spoke
        appendTranscript('assistant', text);
        maybeAdvancePlacementQuestion(text);   // tutor asked the next question?
        maybeAutoEnd(text);
      }
    }
  }

  // ----- Placement live answer binding ---------------------------------
  // The tutor asks the 5 questions in order. When an assistant turn asks the
  // NEXT question (cue match), advance the pointer; each FINAL student
  // transcript is then POSTed with that exact question_id, so answers are
  // bound at listening time — never reconstructed from the whole conversation.
  function maybeAdvancePlacementQuestion(assistantText) {
    if (!placementQuestions.length) return;
    const nxt = pqIndex + 1;
    if (nxt >= placementQuestions.length) return;
    const cues = (placementQuestions[nxt] && placementQuestions[nxt].cues) || [];
    const low = (assistantText || '').toLowerCase();
    if (cues.some((c) => c && low.indexOf(c) !== -1)) {
      pqIndex = nxt;
    }
  }

  function savePlacementAnswer(studentText, attempt) {
    if (!placementAnswerUrl || pqIndex < 0 || !placementQuestions.length) return;
    const q = placementQuestions[pqIndex];
    if (!q || !q.id) return;
    postJSON(placementAnswerUrl, { question_id: q.id, transcript: studentText })
      .catch((e) => {
        // Do NOT advance on failure — retry once, then warn.
        if (!attempt) {
          setTimeout(() => savePlacementAnswer(studentText, true), 800);
        } else {
          console.warn('[onlenco-call] placement answer save failed for q', q.id, e);
        }
      });
  }

  function appendTranscript(role, text) {
    transcriptTurns.push({ role, content: text });
    if (!els.transcript) return;
    if (els.transcript.hidden) els.transcript.hidden = false;

    const line = document.createElement('div');
    line.className = 'onlenco-call-line ' + (role === 'user' ? 'is-user' : 'is-assistant');
    const tutorLabel = (Config.language === 'ar')
      ? (Config.tutorNameAr || 'ليلى')
      : (Config.tutorNameEn || 'Layla');
    const label = (Config.language === 'ar')
      ? (role === 'user' ? 'أنت: ' : tutorLabel + ': ')
      : (role === 'user' ? 'You: ' : tutorLabel + ': ');
    const strong = document.createElement('strong');
    strong.textContent = label;
    line.appendChild(strong);
    line.appendChild(document.createTextNode(text));
    els.transcript.appendChild(line);
    els.transcript.scrollTop = els.transcript.scrollHeight;
  }

  // Placement Part 2: end the call + go to the result ONLY when the
  // interviewer speaks its prompted closing line (after question 5). We do
  // not count turns — the model emits several transcript events per turn, so
  // a counter would cut the test short. Navigate explicitly after the closing
  // audio plays so teardown timing can't swallow the redirect.
  function maybeAutoEnd(assistantText) {
    if (autoEndScheduled) return;
    const phrases = Config.autoEndPhrases || [];
    if (!phrases.length) return;
    const lower = (assistantText || '').toLowerCase();
    if (!phrases.some((p) => lower.indexOf(String(p).toLowerCase()) !== -1)) return;
    autoEndScheduled = true;
    setTimeout(() => {
      try { endCall(true); } catch (e) {}
      if (Config.backUrl) window.location.href = Config.backUrl;
    }, 4500);
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

  function endCall(userInitiated) {
    if (!peer && !micStream) return;       // already torn down
    const seconds = callStartedAt ? Math.max(1, Math.round((Date.now() - callStartedAt) / 1000)) : 0;
    const turns = transcriptTurns.slice();

    teardownPeer();
    setState('ended');

    // Fire-and-forget log so the AITutorSession is closed and the
    // conversation gets the spoken turns persisted. Forward the
    // ``tutor_session_id`` returned by the session endpoint so the
    // server closes the exact row instead of falling back to a
    // "find the user's open session" lookup.
    const sessionId = activeSessionInfo && activeSessionInfo.tutor_session_id;
    // We navigate to backUrl AFTER the log post resolves so the
    // server-side evaluation has time to run BEFORE the next page
    // reads it (placement_voice_finalise reads VoiceCallEvaluation).
    // For pagehide / beforeunload we skip the navigation — the page
    // is already on its way out. For a PLACEMENT call (autoEndPhrases set)
    // we always route to the result when the call ends for ANY reason
    // (closing signal, daily-minutes cap, dropped connection) — the
    // finalise page gracefully handles a short call. The normal AI-tutor
    // call still only navigates when the user hangs up.
    const isPlacement = !!Config.autoEndPhrases;
    const shouldNavigate = Config.backUrl && !isUnloading && (userInitiated || isPlacement);
    if (Config.logUrl) {
      const p = postJSON(Config.logUrl, {
        conversation_id: Config.conversationId,
        tutor_session_id: sessionId,
        seconds: seconds,
        transcript: turns,
      }).catch((e) => {
        console.warn('[onlenco-call] log post failed:', e);
      });
      if (shouldNavigate) {
        p.finally(() => { window.location.href = Config.backUrl; });
      }
    } else if (shouldNavigate) {
      window.location.href = Config.backUrl;
    }
    activeSessionInfo = null;
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
    // they've left the page. Mark unloading first so we don't try to
    // navigate to a result page the browser is already leaving.
    window.addEventListener('pagehide', () => { isUnloading = true; endCall(false); });
    window.addEventListener('beforeunload', () => { isUnloading = true; endCall(false); });
  }

  global.onlencoCall = {
    init:      init,
    startCall: startCall,
    endCall:   () => endCall(true),
  };

})(window);
