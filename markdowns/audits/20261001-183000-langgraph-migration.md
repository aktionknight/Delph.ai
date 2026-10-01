# Scoped review: LangGraph migration

Parent: eba626b44542bc24e3435d7a91ebc67419a18bd8. This is a scoped implementation review, not an exhaustive security audit.

## Findings and mitigations

- **Medium — Live service integration unverified.** Evidence: all AI/account tests use fixture providers and a Mongo-compatible test double; no Gemini key or Atlas execution was used. Mitigation: structured provider output validation, fail-closed errors, retained ownership/revision transaction contracts and explicit setup requirements. Required follow-up: credentialed strategy, timeline, repaired asset and concurrent Atlas transaction checks.
- **Medium — No durable graph step recovery.** Evidence: StateGraphs compile without a checkpointer, and workers use in-process FastAPI background tasks. Persisted jobs/traces do not resume a crashed model operation. Mitigation: atomic terminal campaign persistence, failure status, bounded repair, existing abandoned-job handling and documented manual retry. Add Mongo-backed step checkpoints and idempotent recovery before claiming resumable/distributed orchestration.
- **Medium — Media accuracy still relies on human review.** Evidence: text evaluation does not inspect generated image pixels or speech fidelity. Mitigation: media revisions invalidate current approval; media approval requires explicit media_reviewed. The Gemini free-only guard executes before embedding/planning/image calls. Preserve these checks in future checkpoint/resume work.
- **Low — Infrastructure artifacts not executed.** Evidence: new Dockerfiles, Compose wiring and index initializer were reviewed but not built/run. Mitigation: exclude secrets/dependencies through .dockerignore, use non-root runtime users, limit local exposed ports to loopback, retain Atlas/replica-set requirement and keep the index initializer idempotent. Run Docker and Atlas smoke checks with credentials before deployment.
- **Low — External prompts must ship with the backend.** Evidence: core/prompts.py reads root-relative prompt files. Mitigation: missing prompt files raise safe AgentError; API Dockerfile copies prompts to the matching repository layout; offline graph tests load the actual prompt files.
- **Low — Compatibility imports increase maintenance surface.** Evidence: legacy flat modules delegate to canonical packages; app.main aliases the application factory module. Mitigation: existing end-to-end tests retain the old import contracts while graph tests target canonical services. Remove compatibility shims only as a separately announced breaking change.

## Correctness and regression checks

Reviewed conditional edges, two-repair exhaustion, strategy/direction ownership, shared campaign state, model routing, partial edits, trace propagation, graph failure isolation, version history, persisted human-review status and publication guards. New tests show two repairs produce exactly three failed versions, preserve them through API reload, and reject both approval and publication. Missing audience_fit checks fail evaluation. Provider failure leaves caller campaign/brand/asset dictionaries unchanged. Partial CTA revision preserves hook/body/citations and prior approval history. Agent suite compilation performs no provider calls.

The successful provider generation trace is committed with version history; node progress streams only role/status metadata and never raw graph state. Current audience context is supplied on fresh approval/publication evaluation. Approval remains separate from graph review nodes. Existing ownership, authentication, media invalidation, revision conflict, provider validation and imported metric tests also pass.

## Verification and exclusions

29 backend tests passed, 12 repository checks passed, frontend type checking and production build passed, and pip dependency consistency passed. Sandbox process-launch failures were retried through the approved escalation mechanism and passed. No credentialed model quality evaluation, actual MongoDB replica-set transaction/concurrency test, Docker execution, browser visual test, load test or exhaustive security assessment was run. Existing MVP authentication/team/session/distributed-rate-limit and storage lifecycle limitations remain as documented in README.md; the migration does not resolve them.
