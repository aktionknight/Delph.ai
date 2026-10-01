# Review: lightweight models and provider failover

Parent: 294182b. Scope is the routing change described in the matching context record. This is a targeted implementation review, not an exhaustive security audit. No commit made in this session.

## Findings and mitigations

- Medium — Free quota can exhaust across every model/provider. Evidence: the uninterrupted live Groq burst passed six checks before both models rate-limited. Mitigation: ordered fallback, cooldowns, bounded attempts and explicit exhaustion errors; remaining six checks passed after the short limit window. No guarantee of unlimited/free availability is made.
- Medium — RAG remains dependent on Gemini embedding capacity. Evidence: ContextRetriever uses the fixed embedding model; no Groq embedding equivalent is configured. Mitigation: retain a compatible vector space and document this limitation rather than silently mixing incompatible embeddings. An alternate embedding provider would require a planned reindex.
- Medium — Cooldowns are local to each API process; concurrent instances can independently retry an exhausted model. Evidence: ModelPool uses an in-memory map with a lock. Mitigation: thread-safe updates within a process, bounded routing, shared state across roles; distributed coordination remains future work.
- Low — Routing timeout is not an absolute campaign deadline. Evidence: HTTPX timeout governs individual network operations, while a graph can execute several validated queries and embeddings. Mitigation: cap HTTP timeout and total attempts, check monotonic routing deadlines before each model, reserve capacity for the second provider, document practical scope.
- Low — Lightweight models can produce incomplete, unsupported or lower-quality responses. Evidence: a real Groq visual-plan response failed validation. Mitigation: Pydantic validation advances to the next model; existing grounding rules, AI evaluation, repair and explicit human approval remain authoritative. Valid evaluator rejection does not trigger model shopping.
- Informational — Safety errors must not be bypassed by failover. Evidence: tests cover prompt/response safety blocks and ensure neither another model nor provider is invoked. HTTP 400/401 configuration errors also stop, except explicitly classified generated-JSON or retired-model Groq errors.
- Informational — Secrets and source contents must not enter routing telemetry. Evidence: attempts store only provider/model/status/reason/duration; tests verify fixture secrets are absent. Ignored .env was changed only for known non-secret model settings; credentials were not printed or included in records.

## Verification and omissions

84 offline tests passed before the subsequent canvas feature work. All 12 synthetic query paths passed live on the configured Gemini chain. All 12 passed through real Groq fallback across two batches, with deliberately simulated Gemini text exhaustion clearly labeled. Tests cover global attempts, reserved secondary time, cooldown expiry, role overrides, malformed output, fail-closed safety, missing credentials, disabled fallback and Groq backoff/error classification.

Paid image generation, speech synthesis, R2, live MongoDB transactions, distributed behavior, sustained load and provider-backed quality benchmarking were not exercised by this change's live smoke checks. The 3.8 Flash and 3.5 Flash fallback endpoints were not invoked successfully during this run. No generated campaign content or credentials are included in the record.
