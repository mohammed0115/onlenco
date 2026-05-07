# ADR 0003: Every AI service must have a deterministic fallback

Date: 2026-05-07
Status: Accepted

## Context

Onlenco depends on third-party AI for placement scoring, error analysis,
exercise generation, dictionary lookups, tutor chat, and library content
extraction. AI calls fail (rate limits, network blips, regional outages,
schema drift). Onlenco students often have unstable internet and cannot
re-run a failed action.

## Decision

Every AI service module exposes a single public function that **always
returns** a sensible value:

1. If `AI_API_KEY` is unset → use the deterministic fallback path.
2. If the AI HTTP call raises or returns malformed JSON → log and use
   the fallback.
3. If the user is over their per-feature daily limit
   (`core.services.ai_usage.is_within_limit`) → use the fallback.

Fallbacks are pure-Python heuristics that produce schema-compatible output
(e.g. regex error rules; template exercises; word-count-based fluency
score; chapter-keyword vocabulary extractor). They do not call out and
they are deterministic.

All four states (success, network failure, malformed JSON, no key) are
covered by tests using `unittest.mock.patch` on `requests.post`.

## Consequences

- A user is never blocked by AI failure. They get a degraded but coherent
  result.
- The team can deploy without AI keys for staging/demo environments.
- AI cost is bounded: cap by feature, log per call, and the system still
  works at zero spend.
- Trade-off: fallback quality is much lower than AI quality, so feature
  responses must signal "fallback used" via metadata for analytics
  (`metadata.source = "fallback"` on AdaptiveExercise, etc.).
