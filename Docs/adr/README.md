# Architecture Decision Records

Short documents capturing significant architecture choices for Onlenco. Each
ADR is dated, numbered, and stored under `Docs/adr/`.

| # | Title | Status |
|---|---|---|
| [0001](0001-monolith-django-with-service-layer.md) | Monolithic Django with explicit service layer | Accepted |
| [0002](0002-adaptive-engine-rule-based-first.md) | Adaptive engine is rule-based first; ML is opt-in later | Accepted |
| [0003](0003-ai-fallback-strategy.md) | Every AI service must have a deterministic fallback | Accepted |

## When to write a new ADR

Write one when a decision is hard to reverse, affects multiple apps, locks
in a vendor, or contradicts an obvious default. Don't write one for choices
already implied by a framework convention.
