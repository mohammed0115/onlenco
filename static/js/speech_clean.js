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

  // ---------------------------------------------------------------------
  // Technical-key glossary — mirrors core/services/text_humanizer.py.
  // Raw payload keys (event names, model fields) sometimes leak into the
  // text that reaches TTS. Map them to human copy BEFORE underscores are
  // stripped, so a multi-word key still matches as a whole token.
  // ---------------------------------------------------------------------
  var TECH_GLOSSARY = {
    en: {
      'weekly_assessment_available': 'weekly assessment is available',
      'weekly_assessment_result':    'your weekly assessment results',
      'daily_learning_plan':         "today's learning plan",
      'weekly_assessment':           'weekly assessment',
      'placement_completed':         'placement test complete',
      'lesson_completed':            'lesson complete',
      'correct_answer':              'the correct answer',
      'user_answer':                 'your answer',
      'current_cefr_level':          'English level',
      'cefr_level':                  'English level',
      'theta_score':                 'learning ability score',
      'skill_mastery':               'skill progress',
      'user_weakness':               'learning focus area',
      'lesson_progress':             'lesson progress'
    },
    ar: {
      'weekly_assessment_available': 'الاختبار الأسبوعي متاح الآن',
      'weekly_assessment_result':    'نتائج اختبارك الأسبوعي',
      'daily_learning_plan':         'خطة اليوم',
      'weekly_assessment':           'الاختبار الأسبوعي',
      'placement_completed':         'اكتمل اختبار تحديد المستوى',
      'lesson_completed':            'اكتمل الدرس',
      'correct_answer':              'الإجابة الصحيحة',
      'user_answer':                 'إجابة الطالب',
      'current_cefr_level':          'مستوى اللغة الإنجليزية',
      'cefr_level':                  'مستوى اللغة الإنجليزية',
      'theta_score':                 'مؤشر التقدم',
      'skill_mastery':               'تقدم المهارة',
      'user_weakness':               'نقطة تحتاج إلى تحسين',
      'lesson_progress':             'تقدم الدرس'
    }
  };

  // Hard-banned technical prefixes (UA_user_answer, DB_id, …) — these are
  // never meaningful to a learner; remove the whole token.
  var HARD_BANNED_RE = /\b(?:UA|DB|ID|PK|FK|ENUM|CTX|SQL)_[A-Za-z0-9_]+\b/gi;

  function applyGlossary(text, lang) {
    var map = (lang === 'ar') ? TECH_GLOSSARY.ar : TECH_GLOSSARY.en;
    // Longest keys first so "weekly_assessment_available" wins over the
    // shorter "weekly_assessment".
    var keys = Object.keys(map).sort(function (a, b) { return b.length - a.length; });
    var out = text;
    keys.forEach(function (key) {
      out = out.replace(new RegExp('\\b' + key + '\\b', 'gi'), map[key]);
    });
    return out;
  }

  function clean(text, lang) {
    if (!text) return '';
    let out = String(text);

    // 0. Remove invisible direction/control characters and pasted HTML.
    out = out.replace(/[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]/g, '');
    out = out.replace(/<[^>]+>/g, ' ');
    out = out.replace(/&(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);/g, ' ');

    // 0a. Remove hard-banned technical identifiers entirely
    //     ("UA_user_answer", "DB_id_42") \u2014 these would otherwise survive
    //     to step 1 as "ua user answer".
    out = out.replace(HARD_BANNED_RE, ' ');

    // 0b. Map known technical keys ("weekly_assessment_available",
    //     "cefr_level", \u2026) to human copy. Runs BEFORE the underscore
    //     strip so multi-word keys still match as a whole token.
    out = applyGlossary(out, lang);

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
    // Pick the glossary language from the requested voice language so a
    // leaked key is humanised in the language the engine will speak.
    const langCode = String(opts.lang || '').toLowerCase().indexOf('ar') === 0 ? 'ar' : 'en';
    const cleaned = clean(text, langCode);
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
