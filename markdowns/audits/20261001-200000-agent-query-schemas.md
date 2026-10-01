# Scoped review: Gemini query schemas

Parent: eba626b44542bc24e3435d7a91ebc67419a18bd8. This is not an exhaustive security audit.

## Findings

- **Low — Decoder constraints are intentionally looser than application contracts.** Evidence: wire schemas omit min/max string lengths, array sizes and numeric ranges. Mitigation: unchanged Pydantic validation rejects responses outside the original contracts before they reach campaign state; a regression test verifies day 91 fails. Required fields, types and additionalProperties rules remain. Existing evaluation and current-version approval/publication checks are untouched.
- **Low — Smoke queries consume configured provider quota.** Evidence: --live calls the actual text and embedding adapters. Mitigation: explicit live flag, small synthetic inputs, no persistence/publication, no paid image calls, and no secret values or source contents in status output. The script redacts known credential environment values from errors.
- **Low — Provider compatibility changes over time.** Evidence: Gemini accepted a compact schema that it rejected in its original Pydantic form; individual rejected keywords were not separately isolated. Mitigation: shared normalization for every Gemini agent output, 19 offline wire regressions, live synthetic checks and a repeatable smoke command. Model quality and provider capacity remain external dependencies.
- **Medium — Configured Gemini model has exhausted its daily free quota.** Evidence: provider quota violations identify a per-day limit of 20 requests for gemini-3.5-flash. Mitigation: daily limits fail immediately with a clear message rather than following misleading short RetryInfo delays; transient limits honor server-directed backoff up to 60 seconds. No automatic vendor/model or paid-tier switch is performed. Core requests cannot succeed on the exhausted model until quota resets or an explicitly configured alternative has available quota.

## Reviewed behavior and verification

Reviewed local reference resolution, recursion rejection, field/type preservation, unchanged local validation, blank role-model fallback, continued x-goog-api-key header use and absence of silent vendor/template fallback. Before/after timeline checks used the configured gemini-3.5-flash model, without editing credentials. The 14-day timeline also passed. 50 backend tests and syntax/whitespace checks passed. Tests stub the provider module's sleep alias, avoiding changes to the global time module used by MongoDB monitor threads; the final test run has no warnings.

Nine of 12 live paths passed on configured 3.5 Flash. Analytics, learning and visual planning encountered daily quota exhaustion; all three subsequently passed on 3.1 Flash-Lite through a smoke-process-only override. Thus every query path has a live successful result across these models, while those three remain unverified successfully on the exhausted default model. A 2.5 Flash probe was rejected as unavailable to this account (404); no application fallback uses that model. The .env and application provider choices remain unchanged.

No database migration, live Atlas transaction or concurrent account check was performed for this provider-only fix. Paid image/audio generation and optional provider accounts were not exercised. Synthetic live results are not an evaluation benchmark or a guarantee that every brand brief will pass semantic evaluation. No frontend logic changed, so frontend build/browser checks were not repeated.
