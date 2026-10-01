# Audit: LinkedIn OAuth Proxy Callback

**Date**: 2026-10-02
**Commit topic**: linkedin-oauth-proxy-callback
**Severity**: Medium

## Findings

### 1. Cross-origin OAuth binding cookie — Medium

**Evidence**: The frontend starts OAuth through its `/api/*` proxy, which sets `social_oauth_linkedin` as a host-only cookie. A direct LinkedIn redirect to Render does not send a cookie scoped to the Vercel domain. The backend requires this cookie to match the OAuth state binding in `SocialAccounts.complete`, so the callback fails.

**Mitigation**: Register and configure the Vercel same-origin callback URL (`https://<frontend-origin>/api/connect/linkedin/callback`). The existing proxy strips `/api` and forwards the cookie and query string to Render.

### 2. Production return origin — Low

**Evidence**: Callback completion previously redirected using only `FRONTEND_URL`, which may still be a localhost value when a deployment uses `FRONTEND_URL_PRODUCTION`.

**Mitigation**: Prefer `FRONTEND_URL_PRODUCTION` for the post-OAuth return, retaining `FRONTEND_URL` as fallback. Keep the value a trusted frontend origin.

### 3. Client secret disclosed — High, operator action required

**Evidence**: The user-supplied screenshot visibly contains a LinkedIn primary client secret.

**Mitigation**: Regenerate the secret in LinkedIn and replace `LINKEDIN_CLIENT_SECRET` in Render. The exposed credential is not reproduced in this repository or this record.

## Tests Not Run

- Automated API and frontend proxy test suites were not run.
- A live LinkedIn OAuth round trip was not performed; Render/Vercel settings and product permissions are external to this workspace.

This is a focused configuration and code review, not an exhaustive security audit.
