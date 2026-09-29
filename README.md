# Campaign Launchpad

A connected campaign workspace based on the [technical blueprint](markdowns/globals/campaign_launchpad_technical_implementation.md). This first implementation is a **local, single-workspace demo**: persistent campaign state, source context, deterministic strategy/content generation, evaluation, version-specific human approval, and simulated experiments and analytics.

## Run locally

Requires Python 3.11+ and Node.js 22 with npm. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r apps/api/requirements.txt
npm --prefix apps/web ci
python scripts/dev.py
```

On macOS/Linux, substitute `.venv/bin/python` for `.venv\Scripts\python`.

Open <http://localhost:3000>. API documentation is at <http://127.0.0.1:8000/docs>. Both development servers bind to loopback. Ctrl+C stops both servers. SQLite persists local state across restarts; generated database files are ignored by Git. No model credentials are needed for demo mode.

To run servers separately:

```powershell
.venv\Scripts\python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
npm --prefix apps/web run dev -- --hostname 127.0.0.1 --port 3000
```

The frontend proxies `/api/*` to the backend. Set `BACKEND_URL` in the web process environment if the API runs elsewhere. The backend accepts `DATABASE_URL` for database configuration. Do not commit local environment files or keys.

## Walk through the workflow

1. Review the seeded brand and add product/brand context as text or a PDF.
2. Create a campaign with a brief, audience, goal, platforms, and duration.
3. Generate a strategy, inspect assumptions and sources, and select a creative direction.
4. Generate a campaign timeline and platform content.
5. Demonstrate a failed claim check and repair; inspect the version history and trace.
6. Edit content and explicitly approve its current passing version. An edit requires a new approval.
7. Create hook experiments, inspect clearly labeled simulated metrics, and save a learning to the brand.

The publish action records local publication state; it does not post to social networks. JSON export provides the campaign state for inspection or handoff.

## Verification

```powershell
.venv\Scripts\python -m pytest apps/api/tests -q
python -m unittest discover -s scripts/tests -v
npm --prefix apps/web run build
```

## Commit documentation

[AGENTS.md](AGENTS.md) requires a **new matching pair of markdown records in every commit**:

- `markdowns/PR_context/<timestamp>-<topic>.md`: latest implementation context, decisions, tests, limitations, next steps.
- `markdowns/audits/<timestamp>-<topic>.md`: flaws, vulnerabilities, mitigations, and remaining work.

Include the pair with the changes they describe. Existing records must not be reused as a substitute. Enable the local hook after cloning:

```powershell
git config core.hooksPath .githooks
```

The pre-commit hook and GitHub Actions check the record pairs. Hooks can be bypassed locally; make the CI check required in GitHub branch protection for server-side enforcement. `markdowns/globals` is user-owned and must remain unchanged unless explicitly requested.

## Scope still to implement

Hosted authentication and workspace authorization, external LLM providers, embedding/vector retrieval, normalized production schema and migrations, distributed background jobs, live progress streaming, richer editors/media generation, real social publishing/metrics, and public deployment remain future phases. The current evaluator uses bounded deterministic rules; it is not a general factual verifier. Do not expose this unauthenticated demo as a public service.
