# Audit: Pollinations-Only Campaign Image Routing

**Date**: 2026-10-02
**Commit topic**: pollinations-only-image-routing
**Severity**: Low to Medium

## Findings

### 1. Image provider and Gemini bypass — Low

**Evidence**: `apps/api/app/agents/creative.py` routes `kind == "image"` directly to `pollinations_image`; `apps/api/app/services/orchestrator.py` sends image jobs around `retrieve_context`. The image path no longer imports or calls the Gemini image helper.

**Mitigation**: Keep the provider fixed to Pollinations as requested. Verify the image branch in deployment because automated tests were not run for this change.

### 2. External prompt disclosure — Medium

**Evidence**: The Pollinations prompt includes campaign goal, brand name, custom media instructions, body copy, and caption. These values are sent to the configured Pollinations API.

**Mitigation**: Do not include confidential or personal information in campaign goals, copy, or custom image instructions unless permitted by the workspace's data policy. Consider prompt minimization or an explicit disclosure if campaign data sensitivity requirements change.

### 3. Credential handling — Low

**Evidence**: `apps/api/app/core/providers.py` reads `POLLINATIONS_API_KEY` server-side and sends it as a Bearer header. The key is absent from `.env.example` values and is not placed in the URL.

**Mitigation**: Configure the real key only in the backend deployment secret store. Avoid logging authorization headers or provider request URLs containing campaign prompts.

### 4. Provider response handling — Low

**Evidence**: The adapter checks HTTP status, streams with a 10 MiB cap, and the creative agent requires PNG/JPEG MIME and matching signatures before returning an asset.

**Mitigation**: Unsupported formats and oversized outputs are rejected. Upstream rate limits, malformed responses, and service outages remain possible and have no image-provider fallback by design.

### 5. Operational readiness — Medium

**Evidence**: The backend fails clearly when `POLLINATIONS_API_KEY` is unset. This workspace cannot confirm the deployed Render secret, Pollinations account balance, or model access.

**Mitigation**: Add the key to the backend host, redeploy, and verify one image generation through the campaign workflow. Keep the key out of Vercel public environment variables.

## Tests Not Run

- Automated API test suite and live Pollinations request were not run.
- Production deployment and credential configuration were not verified.

This is a focused change review, not an exhaustive security audit.
