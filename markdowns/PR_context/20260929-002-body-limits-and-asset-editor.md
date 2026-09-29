# PR Context: Request body limits, asset editor component, and web stylesheet

- Parent commit: `26bc90a4dc69d9596759a2e85d481882295634bc`
- Topic: `body-limits-and-asset-editor`

## Scope

This commit introduces server-side request body bounding to prevent resource exhaustion from unmetered uploads, extracts and refines the candidate creative staging component (`AssetEditor`), adds the missing `globals.css` required for the Next.js frontend build, and fixes source form re-keying on brand selection.

## Implemented Changes

1. **Request Body Bounding (`apps/api/app/limits.py`, `apps/api/app/main.py`)**:
   - Implemented `BodyLimitMiddleware` to intercept POST/PATCH/PUT requests prior to multipart or body parsing.
   - Enforces a 5MB payload limit (+64KB overhead allowance) checking both `Content-Length` headers and streaming byte accumulation.
   - Responds with HTTP 413 (`Request exceeds the upload limit.`) when thresholds are breached, and HTTP 400 for malformed `Content-Length` values.
   - Wired middleware into FastAPI application startup.

2. **Evaluation Metric Naming (`apps/api/app/generation.py`)**:
   - Renamed check key from `source_grounding` to `source_references_valid` to clearly distinguish heuristic source reference validation from semantic source grounding.

3. **Backend Workflow Verification (`apps/api/tests/test_workflow.py`)**:
   - Added test coverage verifying that oversized multipart requests exceeding payload limits are rejected with HTTP 413.

4. **Asset Editor Staging (`apps/web/components/asset-editor.tsx`)**:
   - Implemented standalone `AssetEditor` component managing candidate creative drafting and evaluation display.
   - Supports editing hook, body, and CTA fields with character counting and dirty change tracking.
   - Provides safe clipboard copy with fallback error reporting.
   - Provides quick refine triggers (`hook`, `cta`, `all`) which increment asset version numbers.
   - Exposes version history, autonomous check statuses, human review decision controls (`approve`, `request-changes`, `reject`), and local demo publication recording.

5. **Brand Setup Stability (`apps/web/components/setup.tsx`)**:
   - Added `key={brand.id}` to `SourceForm` instances to ensure form input states reset when toggling between brands.
   - Adjusted brand voice text field `maxLength` to 200 characters.

6. **Web Stylesheet and Build Fix (`apps/web/app/globals.css`, `apps/web/package-lock.json`)**:
   - Created `globals.css` containing design variables, layout classes (sidebar, shell, topbar, cards, forms, badges, orbit visual, metrics, and campaign grid) to fix missing module compilation failures in `next build`.
   - Included `package-lock.json` to support reproducible `npm ci` execution in CI environments.

## Architectural Decisions

- **Streaming middleware vs route validation**: Bounding request bodies in Starlette middleware before multipart parsing prevents disk spooling attacks or memory leaks from malicious clients sending indefinite byte streams.
- **Controlled version immutability**: Edits and regenerations in `AssetEditor` produce new version numbers and reset approval statuses, ensuring that unreviewed revisions cannot be published.

## Verification Results

- **Backend Pytest**: `pytest apps/api/tests` passed (11/11 tests passing, including upload boundary tests).
- **Commit Docs Tests**: `python -m unittest discover -s scripts/tests -v` passed (12/12 tests passing).
- **TypeScript Typecheck**: `npm run typecheck` in `apps/web` passed with 0 errors.
- **Next.js Production Build**: `npm run build` in `apps/web` succeeded and generated static/dynamic routes.

## Limitations

- Body bounding uses an in-memory buffer (`bytearray`) during request intake suitable for local demo single-tenant instances, but production multi-tenant deployments should stream directly into ephemeral disk or object storage with backpressure.
- Semantic vector retrieval and external LLM orchestration remain mocked by deterministic templates.

## Next Steps

- Integrate external LLM provider integrations with fallback to deterministic generation when API keys are omitted.
- Add multi-tenant authorization boundaries and database migrations.
