# Scoped audit: production API gateway and origin configuration

Review scope: the deployment routing fix associated with `20261002-vercel-render-routing`. This is a bounded code/behavior review, not an exhaustive security audit.

## Findings and mitigations

- **High correctness — production gateway selected localhost.** Live Vercel response exposed DNS_HOSTNAME_RESOLVED_PRIVATE; the rewrite's configuration differed from the route handler. Removed the rewrite and unified runtime configuration. Tests and built route manifest verify the repair locally. Remote fix still requires deployment.
- **High correctness — text conversion damaged binary assets.** Previous proxy used request.text/response.text for uploads and all downloads. Stream passthrough now preserves original bytes and streaming progress. Tests compare binary PDF/multipart bytes and preserve attachment headers. An actual built Next.js server smoke passed.
- **Medium security/correctness — configured production origin was ignored.** ALLOWED_ORIGINS did not feed backend CORS or write guards, allowing production preflight/login to fail despite configured screenshots. Both now use one validated exact allowlist. Tests cover accepted configured production origins and rejected untrusted origins/wildcard/path/credential configurations. Preserve strict HttpOnly cookies and server-side workspace ownership.
- **Medium — proxy redirects/headers.** Upstream redirects are returned to the browser rather than followed with forwarded cookies. Hop-by-hop, client-supplied forwarding, and stale content encoding/length headers are removed. Error messages avoid leaking internal exception details or credentials. Upstream session cookies remain separate.
- **Low observability — root-path probes returned 404.** GET/HEAD `/` and `/health` now return successful service responses. Root is informational and does not certify model/database readiness; inspect the existing health JSON configuration fields.

## Remaining constraints and checks

- Local repairs have not been deployed; final production login, cookie persistence, media download, upload size and SSE behavior require verification on the hosted domains after redeploy.
- Direct Render health checks timed out from this environment. Startup logs show a valid port binding, but independent live API readiness remains unverified. Retain `/health` as Render health path and inspect startup/database errors if it remains unavailable.
- Vercel function duration, streaming and payload limits depend on project settings/plan. The route requests 300 seconds and fetch uses a bounded timeout; platform limits can be lower. Existing background jobs remain the mechanism for long generation.
- Existing per-process auth/rate limits, MongoDB transaction and private object storage behavior remain outside this routing fix. A reverse proxy can consolidate client source addresses; centralized/user-aware production rate limiting remains future hardening.
- Portable PDF/ZIP output remains protected by existing ownership and storage reads. Regression tests and synthetic artifacts do not establish availability of real production binaries or model media quality.

## Verification

136 backend tests, 10 proxy tests, frontend types/build, real local production-server smoke, and whitespace checks passed. Synthetic four-page campaign PDF rendered and inspected; deliverables ZIP generated. No live account changes, publications, paid model calls, or secret values were emitted. Project global markdowns were left untouched. No commit or deployment was performed.
