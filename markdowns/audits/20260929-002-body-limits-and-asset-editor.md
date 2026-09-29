# Commit Audit: Body limits, asset editor component, and web stylesheet

- Parent commit: `26bc90a4dc69d9596759a2e85d481882295634bc`
- Topic: `body-limits-and-asset-editor`

This audit reviews the changes in this commit for potential flaws, vulnerabilities, regressions, and remaining implementations. This is a targeted review of the commit scope, not an exhaustive security audit.

## Findings and Risk Review

### 1. In-memory buffering in `BodyLimitMiddleware`
- **Severity**: Low (Demo environment) / Medium (Production deployment)
- **Evidence**: `apps/api/app/limits.py` buffers incoming chunks into a `bytearray` up to `max_bytes` (5MB + 64KB) before re-emitting them via `bounded_receive`.
- **Mitigation**: The ceiling is strictly bounded at ~5.06MB per request, preventing memory exhaustion attacks in the current single-tenant demo. For high-concurrency production deployments, replace buffering with an asynchronous streaming wrapper that passes chunks to Starlette's parser while enforcing total byte count counters without duplicating memory.

### 2. Header parsing reliability
- **Severity**: Low
- **Evidence**: `int(headers.get(b"content-length", b"0"))` converts the byte header to integer and returns HTTP 400 upon `ValueError`. If multiple headers or chunked transfer-encoding are used without `content-length`, the streaming loop handles accumulation up to `max_bytes`.
- **Mitigation**: Both explicit declared lengths and chunked streams without declared lengths are capped by the accumulation loop.

### 3. Stale approvals and version invalidation
- **Severity**: Low / Verified Correct
- **Evidence**: In `apps/web/components/asset-editor.tsx`, `dirty` state disables approval and publishing actions until changes are submitted to the backend. The backend already creates a new version number upon edit and resets `approved` status, rejecting stale approvals with HTTP 409.

### 4. Clipboard API denial handling
- **Severity**: Low
- **Evidence**: `navigator.clipboard.writeText` may reject in insecure contexts (non-HTTPS) or if user permissions are denied.
- **Mitigation**: `AssetEditor` wraps clipboard writes in a try/catch block and displays a user-facing error notice advising manual selection and copy if clipboard access is rejected.

### 5. Stylesheet inclusion and UI regression
- **Severity**: Low
- **Evidence**: Adding `apps/web/app/globals.css` satisfies the `import "./globals.css"` dependency in `layout.tsx` and enables Next.js to complete the build successfully.
- **Mitigation**: Tested locally with `next build` which passed without warnings or build errors.

## Remaining Implementation

- Relational database schema migrations (Alembic) to supersede SQLite table creation.
- Real vector store embeddings for brand context retrieval.
- Multi-user authentication, JWT sessions, and workspace authorization guards.
- Live social platform API adapters for real publishing beyond simulated local state.

## Verification Run

- `pytest apps/api/tests` (11 passed).
- `python -m unittest discover -s scripts/tests -v` (12 passed).
- `npm run typecheck --prefix apps/web` (0 errors).
- `npm run build --prefix apps/web` (0 errors, build completed).
- Staged validation check: `python scripts/check_commit_docs.py --staged`.

## Tests Not Run

- Multi-client concurrent load and stress testing on `BodyLimitMiddleware`.
- End-to-end browser automation with Playwright/Cypress.
