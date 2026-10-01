# Transpile Lucide React Package to Prevent Dev Server Vendor-Chunk Missing Module Errors

**Date**: 2026-10-02
**Parent commit**: 36f3994

## Scope

Resolve the runtime module error `Cannot find module './vendor-chunks/lucide-react.js'` when loading pages in Next.js development mode.

## Implemented Changes

- **Next.js Configuration (`apps/web/next.config.ts`)**:
  - Added `transpilePackages: ["lucide-react"]` to `nextConfig`.
  - Ensures Next.js compiles Lucide icon imports directly into application chunks rather than relying on dynamic, brittle vendor-chunk optimization (`./vendor-chunks/lucide-react.js`) that breaks when cache is regenerated or during hot reloads.

## Architectural Decisions

- Explicitly transpiling `lucide-react` eliminates runtime chunk desynchronization across both dev and production builds in Next.js 15 App Router without requiring changes to individual icon import statements or downstream components.

## Verification

- `npm --prefix apps/web run build` completed cleanly (all static and dynamic routes compiled with 0 errors).
- `npm --prefix apps/web run typecheck` passed with 0 errors.
- `npm --prefix apps/web test` passed (10/10 tests ok).
- Python test suite `.venv\Scripts\pytest` passed (142/142 tests ok).
- Validated staged diff and pre-commit documentation checks via `python scripts/check_commit_docs.py --staged`.

## Limitations and Next Steps

- The currently running background development process must be restarted for `next.config.ts` configuration changes to take effect in the active Node process.
