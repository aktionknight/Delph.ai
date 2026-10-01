# Route Campaign Images Through Pollinations Only

**Date**: 2026-10-02
**Parent commit**: 13e9f87

## Scope

Replace Gemini image generation in the campaign media workflow with Pollinations as its sole image provider. Avoid using Gemini model routing or embeddings for image requests while retaining Gemini for text, retrieval, and optional speech.

## Implemented Changes

- `CreativeAgent.media` now sends image prompts directly to Pollinations and validates that returned content is a PNG or JPEG with a matching file signature.
- The image-specific LangGraph branch bypasses retrieval; image context construction also avoids the runtime context builder, which may invoke Gemini embeddings.
- The adapter now uses `https://gen.pollinations.ai/image/{prompt}` with a server-side Bearer token, retains bounded streaming and a 10 MiB response limit, and uses `flux` by default.
- Removed the Gemini image adapter, its dedicated tests, and the metadata checker. Updated remaining optional integration coverage for the missing-key message.
- Removed Gemini image configuration from `.env.example` and documented the Pollinations backend key and provider split in README.

## Architectural Decisions

- Pollinations is fixed as the sole image provider; no `IMAGE_PROVIDER` switch or Gemini image fallback remains.
- Image generation is decoupled from Gemini text routing and embedding retrieval. Voiceover narration and all non-image model workflows retain their existing behavior.
- The image key stays in backend environment configuration and is sent in an Authorization header rather than a query string.
- Strict PNG/JPEG validation remains in place; SVG and other active or unsupported formats are rejected.

## Verification

- `git diff --check` passed before commit preparation.
- Reviewed the staged implementation and searched for remaining `GEMINI_IMAGE`, `IMAGE_PROVIDER`, and old Pollinations endpoint references outside historical records.
- Automated test suite was not run.

## Limitations and Next Steps

- Deployment requires `POLLINATIONS_API_KEY` in Render (or the active backend host) and a backend redeploy. The secret was not available to inspect or configure here.
- Pollinations access, quotas, model availability, and pricing depend on the account. No live image request was made.
- Verify image generation in the deployed workflow after configuring the backend key; Gemini remains required for other configured features.
