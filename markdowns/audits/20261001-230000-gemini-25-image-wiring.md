# Review: Gemini 2.5 Flash Image wiring

Parent observed: d1e017b. Targeted review of the image integration; not an exhaustive security audit. No Git commit created by Codex.

## Findings and mitigations

- Medium — The requested primary image model is scheduled to shut down on October 2, 2026. Evidence: Google's current pricing/deprecation notice. Mitigation: separately configured 3.1 Flash-Lite Image fallback, recoverable 404 handling and preserved actual-model provenance. The request does not silently substitute a text model or Groq.
- Medium — Gemini image requests can incur charges and require model/billing access. Evidence: paid-image local opt-in and no free image tier in current official pricing. Mitigation: explicit server opt-in, safe false sample default, visible UI/docs explanation, no billable live implementation probe, and bounded retry/fallback budget. Metadata HTTP 200 is not claimed to prove billing eligibility.
- Low — Returned image bytes can be incomplete, mismatched or large. Evidence: native mixed text/image parts and base64 response boundary. Mitigation: skip thought parts, require successful completion, restrict PNG/JPEG MIME/signatures, limit encoded/decoded size, validate base64 and advance only on recoverable output errors. Full pixel/decompression validation remains outside this adapter.
- Informational — Safety blocks must not be bypassed by model fallback. Evidence: prompt and image response safety classifications terminate routing; dedicated test verifies only one model invocation.
- Informational — Keys remain server-side. Evidence: existing GeminiProvider header authentication is reused, frontend never receives a key, metadata checker emits only model/status/capability, .env remains ignored, and tests verify fixture keys are absent from media metadata.
- Informational — Generated media does not authorize publication. Evidence: existing immutable media version workflow and all-media review acknowledgement remain in place; earlier media history and approval regressions continue passing.

## Verification and omissions

109 backend tests and frontend typecheck passed. Read-only metadata checks returned HTTP 200/generateContent support for both configured image models with the existing key. Python compilation and whitespace checks passed. No real image generation, billing-capability probe, visual quality check, browser interaction, live Mongo/R2 roundtrip or publication was performed. The latest frontend change is help copy; no additional production build was required after the previously passing canvas build. Sustained quotas, distributed cooldowns and image content safety beyond provider blocks/human review remain unverified.
