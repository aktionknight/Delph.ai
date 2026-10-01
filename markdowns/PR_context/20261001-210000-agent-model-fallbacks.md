# Lightweight models and ordered provider failover

Parent: 294182b. No commit made in this session.

## Scope and implemented changes

Added per-role ordered text-model routing for all five agents, with Gemini first and optional Groq failover. Defaults: gemini-3.1-flash-lite → gemini-3.5-flash-lite → gemini-3.8-flash → gemini-3.5-flash → openai/gpt-oss-20b → openai/gpt-oss-120b. This is a configurable latency/quality policy rather than an account-specific performance benchmark. Updated the ignored local .env's non-secret model settings and .env.example; preserved credentials, storage, embedding and image configuration.

Provider adapters validate structured responses before returning success. Recoverable quota, missing/retired model, outage, network, truncated and malformed output errors advance to the next model. Model lists deduplicate, cap fanout and accept role-specific overrides. Cooldowns are shared by model across roles within each application process. Gemini daily quotas and missing models cool down for an hour; transient failures use shorter cooldowns. Groq respects bounded Retry-After values. Known Groq generated-JSON failures and decommissioned-model HTTP 400 codes are recoverable; other request/credential errors stop. Provider safety blocks stop without vendor switching.

A shared routing budget bounds total attempts and available time, reserving an attempt and time for a credentialed secondary provider. Defaults: seven attempts, 45-second HTTP-operation timeout, 150-second routing budget. Successful runs retain actual model/provider, safe routing attempts and cumulative duration; campaign trace displays provider and fallback steps. Evaluation rejection stays in the existing repair/human-review workflow. No silent deterministic generation or automatic approval is introduced.

Extended scripts/check_agents.py with safe per-call routing output and --probe-groq-fallback. The probe explicitly simulates only Gemini text quota exhaustion while making real Groq and Gemini embedding calls. No database writes, publication or image calls are performed.

## Verification

- Offline backend checks: 84 passed, covering every agent role's cross-provider failover, model order and deduplication, quota cooldown/expiry, transient errors, invalid structured output, safety/configuration stops, budgets, missing keys, disabling fallback, evaluator rejection and Groq backoff/error classification.
- Live configured Gemini smoke: all 12 checks passed. A real Flash-Lite outage recovered through gemini-3.5-flash-lite; subsequent queries skipped the cooling model.
- Live Groq probe: first six checks passed; later six initially failed when both Groq models were rate-limited while Gemini was deliberately unavailable. After the short rate-limit window, all six remaining checks passed. All 12 query paths therefore have successful real Groq results across two batches, not one uninterrupted burst. Real Groq 20B rate limits recovered through 120B, and a malformed 20B visual-plan response recovered through validated 120B output.
- No live 3.8 Flash or 3.5 Flash fallback success was needed in these tests. Model availability is configurable and account-dependent.
- Initial restricted-network live attempt failed to reach the embedding provider; rerunning with network permission succeeded.

## Architectural decisions, limitations and next steps

Image and audio generation retain their selected adapters and Gemini free-only image guard. Text failover covers media briefs. Embeddings retain their configured Gemini vector space and bounded retries; Groq does not replace embeddings. A Gemini embedding outage or exhausted embedding quota can still stop retrieval even if Groq text capacity is available.

Cooldowns are process-local rather than distributed. Timeouts apply per HTTP operation rather than enforcing a hard deadline on an entire multi-node campaign workflow. Both provider accounts can exhaust their free capacity; the application reports that state honestly. Account access, sustained burst capacity, model quality and production resilience are not guaranteed by synthetic smoke checks. Backend/provider changes did not require frontend rebuilding at this point. Add a distributed rate limiter/circuit state and broader quality fixtures if deploying beyond the MVP.

Model references: https://ai.google.dev/gemini-api/docs/models and https://console.groq.com/docs/models. Rate-limit reference: https://console.groq.com/docs/rate-limits. Restart the application to reload .env settings.
