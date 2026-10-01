# Route LinkedIn OAuth Through the Vercel Proxy

**Date**: 2026-10-02
**Parent commit**: 3475486

## Scope

Correct the production LinkedIn OAuth callback configuration so the browser returns to the same Vercel origin that initiated OAuth and owns the temporary OAuth binding cookie.

## Implemented Changes

- The callback completion redirect now prefers `FRONTEND_URL_PRODUCTION`, falling back to `FRONTEND_URL` for local or legacy configuration.
- `.env.example` documents that production `LINKEDIN_REDIRECT_URI` must be the Vercel same-origin proxy URL, registered identically in LinkedIn.
- LinkedIn's existing proxy route maps `/api/connect/linkedin/callback` to the backend `/connect/linkedin/callback`, forwarding query parameters and cookies.

## Architectural Decisions

- OAuth initiation and callback use the Vercel origin so the browser sends the host-only OAuth binding cookie on callback; Vercel forwards it to the backend.
- Do not register the direct Render callback for this browser flow because the browser will not send a Vercel host-only cookie to Render.
- The callback's frontend redirect uses the production frontend origin when configured.

## Verification

- Reviewed the Next.js proxy path rewriting and `Set-Cookie`/request-cookie forwarding behavior.
- `git diff --check` passed.
- Automated tests were not run.

## Limitations and Next Steps

- Update both LinkedIn's authorized redirect URLs and Render's `LINKEDIN_REDIRECT_URI` to the identical Vercel URL, for example `https://<your-app>.vercel.app/api/connect/linkedin/callback`.
- Set `FRONTEND_URL_PRODUCTION` on Render to the Vercel origin, redeploy, and reconnect.
- Rotate the LinkedIn client secret exposed in the supplied screenshot, then update `LINKEDIN_CLIENT_SECRET` in Render. No credentials were read or changed here.
