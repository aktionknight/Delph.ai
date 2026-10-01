# Vercel-to-Render routing repair

Parent reviewed: `98b574a`. This task leaves changes in the working tree; it does not create a commit or deploy either service. Existing formatting edits in routes/config were preserved. User-owned global specifications were not edited.

## Problem and evidence

The production frontend `https://delph-ai-beta.vercel.app/api/health` returned HTTP 404 with `X-Vercel-Error: DNS_HOSTNAME_RESOLVED_PRIVATE`. The frontend had competing routes: an external rewrite used BACKEND_URL (defaulting to 127.0.0.1:8000), while the newer catch-all handler used NEXT_PUBLIC_API_URL. The user's screenshots showed NEXT_PUBLIC_API_URL correctly set on Vercel, but BACKEND_URL settings on Render could not configure Vercel's build-time rewrite. The rewrite could intercept requests before the dynamic route handler.

Render logs showed successful binding on 0.0.0.0:10000 and application startup. GET/HEAD requests to `/` returned 404 because no root route existed; that alone did not demonstrate deployment failure. Direct Render health probes from this environment timed out, so live Render health was not independently confirmed.

Primary platform reference: https://vercel.com/docs/errors/dns_hostname_resolved_private describes private-address external rewrite failures. Render port-binding reference: https://render.com/docs/web-services#port-binding.

## Implemented changes

- Removed the external `/api/*` rewrite. The existing Next.js catch-all handler is the sole API gateway.
- Added a server-side gateway with runtime BACKEND_URL, BACKEND_URL_PRODUCTION, then existing NEXT_PUBLIC_API_URL compatibility. Production missing configuration returns actionable 503; local development retains localhost. Configured targets must be HTTP(S) origins without path/query/credentials.
- Forwarded request and response bodies as streams, preserving multipart and PDF/ZIP/image/audio bytes and early SSE progress. Preserved backend statuses, attachment headers and separate session cookies. Removed hop-by-hop and stale encoding/length headers, disabled fetch caching, and used manual redirects.
- Added explicit GET/HEAD health/root support for Render probes.
- Made CORS and write-origin checks share the actual ALLOWED_ORIGINS/FRONTEND_URL/FRONTEND_URL_PRODUCTION configuration, normalized and validated as exact origins.
- Added proxy and deployment regression tests plus frontend tests in CI. Updated README and environment-template deployment guidance.

## Verification

- Full offline backend suite: **136 passed**.
- Frontend proxy tests: **10 passed**, covering runtime target selection, production missing config, query/path routing, cookies, original binary/multipart bytes, streaming, errors and headers.
- TypeScript typecheck and production Next.js build passed. The build manifest contains the dynamic `/api/[...path]` route and no external rewrites.
- Actual production Next.js server smoke against an offline local backend passed: runtime URL selection, `/api` removal, query preservation, PDF byte equality, multipart bytes, and cookie forwarding. Test services ran without terminal windows and were stopped afterward.
- Existing deliverables/PDF functionality was also exercised offline. A synthetic four-page PDF and deliverables ZIP were generated under ignored `.local/exports-qa`; all PDF pages were rendered and visually inspected, with an image preview on page 2. No external generation or production account mutation was performed.
- `git diff --check` passed. Sandbox worker-spawn restrictions required approved reruns of frontend tests/build.

## Deployment handoff

Ship these code changes and redeploy Vercel and Render. The user's existing Vercel NEXT_PUBLIC_API_URL value is compatible; server-only BACKEND_URL is the preferred alternative, set on Vercel to `https://delph-ai-egjc.onrender.com`. Render must allow `https://delph-ai-beta.vercel.app` in FRONTEND_URL or ALLOWED_ORIGINS, retain MongoDB/model configuration, use COOKIE_SECURE=true/DEMO_MODE=false, and use `/health` as health-check path. Check backend `/health` and frontend `/api/health` after deployment. No hosted settings, Git history, or remote deployments were changed by this task.
