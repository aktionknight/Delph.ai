# Gemini agent request schema repair and live smoke verification

Parent: eba626b44542bc24e3435d7a91ebc67419a18bd8. No commit made in this session.

## Scope and implementation

Investigated the reported Gemini HTTP 400 during timeline generation. Reproduced the error with synthetic campaign inputs and the configured gemini-3.5-flash model. The original generateContent request transmitted the full Pydantic JSON schema, including nested $defs/$ref references, string bounds, numeric ranges and a 90-item timeline maximum. Replacing that wire schema with a compact, resolved schema made the same query succeed. The experiment establishes a schema-related incompatibility but does not isolate a single rejected keyword.

Added core/gemini_schema.py to resolve local references and omit length, array-count and numeric-bound constraints from Gemini's structured decoding schema. Preserved object properties, required fields, primitive types, enums and additionalProperties rules. Unsupported recursive/unresolved references fail locally. Kept application-side Pydantic validation unchanged; invalid day 91 remains rejected. No unstructured output, deterministic generation, model switching or safety fallback was introduced. Empty per-role model settings now use the configured default instead of requesting an empty model name.

Added scripts/check_agents.py: explicit --live execution with synthetic brand sources and campaign inputs, status-only credential-redacted output, configured provider routing, and no database writes or publication. Covers strategy/directions, timeline, LinkedIn content, Instagram Reel, X post/thread, evaluation, repair, hook variant graph, analytics, learning and visual planning. --only timeline --duration 14 reproduces the common two-week scheduling path. Selected checks and an explicit smoke-process-only --model override allow bounded retests without editing .env. Existing retrieval calls exercise live document/query embeddings. Paid media generation is excluded; image safeguards remain in place. README documents schema normalization and the reusable smoke commands.

Live checks exposed a second issue: Gemini daily free-tier quota exhaustion was being retried as if it were a transient rate limit. Retries now honor bounded Retry-After/Google RetryInfo delays, while daily quota exhaustion or delays over 60 seconds fail without premature repeated calls. Daily quota messages explicitly distinguish waiting for a reset from a short retry. Runtime provider/model selection remains unchanged; there is no automatic fallback.

## Verification

- Before fix: live timeline failed with Gemini HTTP 400 / invalid argument.
- After fix: live 3-day and 14-day timelines passed using gemini-3.5-flash.
- Offline backend tests: 50 passed, including 19 wire-schema/request regressions and two rate-limit retry tests. The final run has no warnings.
- Python syntax checks passed; tracked diff whitespace check passed.
- Nine live checks passed on configured gemini-3.5-flash: strategy/directions, timeline, LinkedIn copy, Instagram Reel, X post, X thread, evaluation, repair and variant graph.
- Remaining analytics, learning and visual-plan checks first hit the configured model's reported daily 20-request free-tier limit. Their query formats then all passed on gemini-3.1-flash-lite via the explicit smoke-process override. All 12 query paths have a successful live result, but three were not verified successfully on 3.5 Flash due to exhausted quota. A 2.5 Flash probe returned 404 because this account cannot use that model; it is not configured as a runtime fallback.

## Decisions, limitations and next steps

The provider schema constrains response shape; Pydantic remains authoritative for all field and array limits, followed by existing campaign/evaluation guardrails. Simplifying Gemini decoding constraints follows Google's documented schema complexity guidance: https://ai.google.dev/gemini-api/docs/generate-content/structured-output#limitations.

Live checks use a small synthetic fixture and prove current request compatibility, not universal model accuracy, quota availability or production readiness. Atlas transactions and optional Groq/Cohere/R2 integrations are not exercised by these Gemini smoke calls. No credentials or provider-generated campaign content are stored in this record. Retry a failed timeline from the UI after the API reloads the changed module and the configured model's quota becomes available. The current 3.5 Flash quota remains exhausted; model overrides used in testing do not alter application configuration.
