# Gemini 2.5 Flash Image wiring

Parent observed: d1e017b. No Git commit created by Codex; existing staged/unstaged work preserved.

## Scope and implementation

Wired the explicitly requested gemini-2.5-flash-image model into the existing campaign static generation workflow using the same server-side GEMINI_API_KEY. Updated the ignored local .env's IMAGE_PROVIDER, GEMINI_IMAGE_MODEL, GEMINI_IMAGE_FALLBACK_MODELS and GEMINI_IMAGE_ALLOW_PAID settings while preserving all credentials. Local canvas image requests are enabled with the paid-image opt-in; the sample .env retains false as the safe default. This follows the user's image-model request after the prior explanation that Gemini image API access is paid. No billable image-generation request was performed during implementation.

Google's current pricing/deprecation page schedules 2.5 Flash Image shutdown on October 2, 2026. Added gemini-3.1-flash-lite-image as an image-specific fallback so the primary can fail over after shutdown/unavailability, quota/outage errors or invalid image data. Native requests use generateContent with responseModalities TEXT/IMAGE, and accept PNG/JPEG inline image data with size/signature validation. Thought image parts are excluded. Provider safety blocks terminate rather than switching models. Image routing uses its own model chain and existing bounded routing/cooldowns; it never inherits text fallbacks or switches to Groq. Actual model/usage/attempt history remains in media metadata.

The campaign context, custom design prompt, timeline mapping, private blob storage and immutable version approval requirements remain connected. Canvas help text and README now describe enabled configured-image use and paid access without implying a free image tier. Added scripts/check_image_models.py for metadata-only key/model checks without image generation, database writes or publication.

## Verification

- Full backend suite: 109 passed, including six new image adapter cases covering selected endpoint/key reuse, wire config, shutdown/quota/invalid-image failover, fail-closed safety, and isolation from text fallback lists.
- TypeScript typecheck passed; Python compilation and diff whitespace checks passed.
- Read-only live metadata checks using the existing key returned HTTP 200 and generateContent support for both gemini-2.5-flash-image and gemini-3.1-flash-lite-image. The first restricted-network attempt could not reach the endpoint; the permitted rerun succeeded.
- No live image generation, paid speech, database mutation or publication occurred.

## Limitations and next steps

Model metadata access verifies authentication and listed capabilities but does not prove paid-tier billing eligibility, remaining image quota or visual output quality. Actual image generation may incur charges after the user clicks the canvas generation control. Keep GEMINI_IMAGE_ALLOW_PAID=false to disable those calls. Google references: https://ai.google.dev/gemini-api/docs/image-generation and https://ai.google.dev/gemini-api/docs/pricing.

Restart the development launcher to reload .env settings. After October 2, use the configured replacement as primary if retiring the legacy model. Human inspection and explicit approval of the resulting image version remain required.
