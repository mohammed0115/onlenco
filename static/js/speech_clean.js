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

    // 0. Remove invisible direction/control characters and pasted HTML.
    out = out.replace(/[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]/g, '');
    out = out.replace(/<[^>]+>/g, ' ');
    out = out.replace(/&(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);/g, ' ');

    // 1. Underscore-runs (`___` / `_____`) used as fill-in-the-blank
    //    placeholders. Remove them entirely; users do not want TTS to
    //    read "underscore", "blank", or a literal pause marker.
    out = out.replace(/_+/g, ' ');

    // 1b. Literal labels for punctuation/technical markers. AI output can
    //     contain "comma" or "UA" as metadata; spoken audio should not.
    out = out.replace(
      /\b(?:u\s*a|ua|new\s*line|newline|comma|commas|underscore|underscores|dash|dashes|hyphen|hyphens|minus\s+sign|minus|slash|slashes|backslash|back\s+slash|colon|colons|semicolon|semicolons|period|periods|full\s+stop|full\s+stops|question\s+mark|exclamation\s+mark|dot|dots|quote|quotes|quotation|quotations|open\s+quote|close\s+quote|apostrophe|apostrophes|bracket|brackets|open\s+bracket|close\s+bracket|parenthesis|parentheses|open\s+parenthesis|close\s+parenthesis|asterisk|asterisks|star|stars|hash|hashtag|at\s+sign|ampersand|equals|equal\s+sign|plus|plus\s+sign|pipe|vertical\s+bar|tilde|backtick)\b/gi,
      ' '
    );

    // 1c. Decorative/math/code symbols that TTS engines often read aloud.
    //     Keep normal sentence punctuation (.,!?،؟) because it helps pacing.
    out = out.replace(/[#@\$€£¥₹₿^&*+=<>|~`\\\/{}\[\]•·…§©®™✓✔✕✖✗✘→←↑↓↔⇒⇐⇔★☆♥♦♣♠■□▪▫▲▼◆◇●○◦°]+/g, ' ');

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
    out = out.replace(/(?<=[a-z0-9])([A-Z])/g, ' $1');

    // 8. Collapse whitespace + keep punctuation a TTS engine can pause on.
    out = out.replace(/\s+([.,!?؟،])/g, '$1');
    out = out.replace(/(^|[\s])[,.;:!?؟،]+(?=\s|$)/g, ' ');
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
