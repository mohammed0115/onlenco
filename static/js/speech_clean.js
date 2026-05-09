/* speech_clean.js — strip text artefacts that TTS engines mispronounce.
 *
 * Why this exists: questions like "She _____ (not/like) spicy food." make
 * browser TTS say "blank blank blank" (the underscore run) and read the
 * scaffolding hint "(not/like)" out loud, which is noise for the learner.
 *
 * Public API (attached to window):
 *   onlencoSpeechClean(text, lang="auto") -> string
 *   onlencoSpeak(text, opts={}) -> void   // safe replacement for speak()
 */
(function (global) {
  'use strict';

  function clean(text, lang) {
    if (!text) return '';
    let out = String(text);

    // 1. Underscore-runs (`___` / `_____`) used as fill-in-the-blank
    //    placeholders. TTS otherwise says "blank blank blank". Replace
    //    with a short pause marker (TTS engines render "..." as a pause).
    out = out.replace(/_{2,}/g, ' ... ');
    out = out.replace(/\b_\b/g, ' ... ');

    // 2. Parenthetical hints ("(not/like)", "(forget)") are reader-scaffolding,
    //    not meant to be spoken. Drop them entirely.
    out = out.replace(/\([^()]*\)/g, ' ');

    // 3. Square-bracketed cues are usually editorial — drop too.
    out = out.replace(/\[[^\[\]]*\]/g, ' ');

    // 4. Strip URLs / file paths / JSON-ish blobs.
    out = out.replace(/https?:\/\/\S+|www\.\S+/gi, '');
    out = out.replace(/(^|\s)(?:\/|[A-Za-z]:\\)[^\s]+/g, ' ');
    out = out.replace(/\{[^{}]*\}/g, '');

    // 5. Markdown code (` … `, ``` … ```).
    out = out.replace(/```[\s\S]*?```/g, '');
    out = out.replace(/`[^`\n]+`/g, '');

    // 6. Literal "blank/null/undefined" runs.
    out = out.replace(/(?:^|[\s\-_]+)(?:blank|null|none|undefined)(?:[\s\-_]+(?:blank|null|none|undefined))*/gi, ' ');

    // 7. snake_case → spaces, camelCase → spaces.
    out = out.replace(/_+/g, ' ');
    out = out.replace(/(?<=[a-z0-9])([A-Z])/g, ' $1');

    // 8. Collapse whitespace + keep punctuation a TTS engine can pause on.
    out = out.replace(/\s+([.,!?؟،])/g, '$1');
    out = out.replace(/\s+/g, ' ').trim();

    return out;
  }

  function speak(text, opts) {
    opts = opts || {};
    if (!('speechSynthesis' in window)) return;
    const cleaned = clean(text);
    if (!cleaned) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(cleaned);
    u.lang = opts.lang || (/[؀-ۿ]/.test(cleaned) ? 'ar-SA' : 'en-US');
    u.rate = (typeof opts.rate === 'number') ? opts.rate : 1.0;
    if (opts.voice) {
      const v = window.speechSynthesis.getVoices().find(x => x.name === opts.voice);
      if (v) u.voice = v;
    }
    if (opts.onstart) u.onstart = opts.onstart;
    if (opts.onend)   u.onend   = opts.onend;
    if (opts.onerror) u.onerror = opts.onerror;
    speechSynthesis.speak(u);
  }

  global.onlencoSpeechClean = clean;
  global.onlencoSpeak = speak;
})(window);
