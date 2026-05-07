# ADR 0001: Monolithic Django with explicit service layer

Date: 2026-05-07
Status: Accepted

## Context

Onlenco has bilingual templates, a heavy admin surface, an adaptive learning
engine, and a future need for mobile clients. The team is small.

## Decision

Stay on a single Django project. Each Django app owns its models, views,
templates, and admin. Business logic is extracted into a `services/` module
per app and is the only thing called from both views and DRF API views. Models
expose small domain methods (e.g. `PaymentSubmission.approve(reviewer)`); they
do not orchestrate cross-aggregate workflows.

## Consequences

- One process, one deploy, one migrations DAG. Simpler ops.
- API and template stacks share the same service code → no duplicate logic.
- Refactoring to microservices later is possible because services are already
  decoupled from views; we'd promote a `services/` module to a remote API
  before extracting it.
- Trade-off: long-running AI calls block request workers. Mitigated by
  scoped DRF throttles, AI usage logging, and a Redis container ready for
  Celery if/when async generation becomes critical.
