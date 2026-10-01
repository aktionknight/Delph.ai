# Configure Delph Brand Logo as Deployment Tab Icon

**Date**: 2026-10-02
**Parent commit**: de36012

## Scope

Set the Delph.ai brand logo as the official browser tab icon (favicon) for both local execution and cloud deployments.

## Implemented Changes

- `apps/web/app/layout.tsx`: Added `icons` configuration to the root metadata object referencing `/logo.png` for primary browser tab icons, shortcuts, and Apple touch icons.
- `apps/web/app/icon.png`: Added file-based icon route for Next.js App Router, automatically serving and linking the favicon with proper MIME types.
- `apps/web/public/favicon.ico`: Provided static fallback asset for direct root `/favicon.ico` requests and legacy browser clients.

## Architectural Decisions

- Combined explicit metadata icon declarations with Next.js App Router file-based convention (`app/icon.png`) to ensure reliable icon resolution across static builds, SSR, and CDNs (e.g., Vercel).
- Used existing brand image asset to maintain unified visual branding.

## Verification

- `npm --prefix apps/web run typecheck` verified TypeScript type safety.
- `npm --prefix apps/web run build` completed production build and verified static route registration (`○ /icon.png`).
- Validated staging diff and commit hook requirements via `scripts/check_commit_docs.py`.

## Limitations and Next Steps

- Browser caches may retain old cached tab icons until refreshed or hard-reloaded.
