# Campaign Launchpad

A connected campaign workspace: brand documents → strategy → creative direction → timeline → content → evaluation and repair → human approval → experiments → analytics and memory. The default runtime uses AI agents and private MongoDB accounts. Deterministic templates and simulated metrics exist only in explicit local demo mode; missing credentials never activate them silently.

## Setup

Requires Python 3.11+ and Node.js 22.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r apps/api/requirements.txt
npm --prefix apps/web ci
Copy-Item .env.example .env
# Edit .env, then:
.venv\Scripts\python scripts/dev.py
```

Set `GEMINI_API_KEY`, `MONGODB_URI`, and `MONGODB_DATABASE`. Use MongoDB Atlas or a replica set: campaign/asset mutations use transactions and optimistic revisions, including brand dependencies during publication. Open <http://localhost:3000>; API docs: <http://127.0.0.1:8000/docs>. Register, create a brand, and add factual sources before generating strategy. New accounts have empty private workspaces. Existing SQLite demo state is not migrated automatically.

The root `.env` is loaded by the API and development launcher. Restart servers after changes. Never commit credentials. For local HTTP use `COOKIE_SECURE=false`. Deployment requires HTTPS, `COOKIE_SECURE=true`, `DEMO_MODE=false`, and your exact browser origin in `FRONTEND_URL`. Set `BACKEND_URL` in the frontend build environment when building separately, because Next.js rewrites are compiled at build time. Set `DEMO_MODE=true` only for a local deterministic single-workspace demonstration.

## Providers and credentials

| Component | Implementation | Configuration |
| --- | --- | --- |
| Strategy / creative directions / timeline | Gemini structured outputs | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| Creative / evaluator (including repairs) | Gemini or Groq | Provider switches; Groq needs `GROQ_API_KEY` |
| Retrieval | Gemini embeddings, cosine similarity over Mongo-stored chunks | Same Gemini key; `GEMINI_EMBEDDING_MODEL` |
| Optional reranker | Cohere v2 Rerank | `COHERE_API_KEY`, `COHERE_RERANK_MODEL` |
| Images | Gemini selected, free-only guard enabled | Current Gemini image APIs have no free tier; image calls stay disabled |
| Voiceovers | Edge TTS or Gemini speech | `TTS_PROVIDER=edge` needs no API key; Gemini needs `GEMINI_TTS_MODEL` |
| Binary files | Mongo GridFS or private Cloudflare R2 | `OBJECT_STORAGE=mongo`, or `r2` and four `R2_*` settings |
| Profiles / sessions / campaigns / versions / experiments / traces / jobs | MongoDB | `MONGODB_URI`, `MONGODB_DATABASE` |

Gemini-only operation needs no other model key. Add `GROQ_API_KEY` to enable text failover after the Gemini model chain is exhausted. All five roles default to Gemini first; `<ROLE>_PROVIDER=groq` reverses the provider order for that role. Existing `WRITER_PROVIDER` / `REPAIR_PROVIDER` remain compatible when `CREATIVE_PROVIDER` is unset. Groq content and evaluation defaults are independently configured by `GROQ_CONTENT_MODEL` and `GROQ_EVALUATOR_MODEL`. Each role accepts `GROQ_<ROLE>_MODEL` or `GEMINI_<ROLE>_MODEL`, for example `GEMINI_STRATEGIST_MODEL`.

Text routing starts with `gemini-3.1-flash-lite`, then `gemini-3.5-flash-lite`, `gemini-3.8-flash`, and `gemini-3.5-flash`; Groq follows with `openai/gpt-oss-20b`, then `openai/gpt-oss-120b`. These use the providers' current [Gemini models](https://ai.google.dev/gemini-api/docs/models) and [Groq models](https://console.groq.com/docs/models), preferring lightweight models before stronger alternatives. The order is a configurable latency/quality policy, rather than a measured benchmark of your account. Free-tier access and remaining quota depend on your provider account.

Set `GEMINI_FALLBACK_MODELS` / `GROQ_FALLBACK_MODELS` to comma-separated ordered lists, or override them per role with `<PROVIDER>_<ROLE>_FALLBACK_MODELS` (roles: `STRATEGIST`, `MARKETING`, `CREATIVE`, `EVALUATOR`, `ANALYTICS`). Blank fallback lists mean primary model only. Each provider chain deduplicates models and caps its list at five. `AI_FALLBACK_ENABLED=false` disables both model and provider fallback; `AI_PROVIDER_FALLBACK_ENABLED=false` keeps model fallback within the selected provider only.

Quota limits, missing models, transient outages, timeouts and invalid structured output advance to the next model. Exhausted daily quotas and unavailable models cool down for an hour, transient outages for 30 seconds, and rate limits use provider backoff where available. Cooldowns are process-local and shared across roles using the same model. Routing defaults to seven total model attempts, a 45-second HTTP timeout per model, and a 150-second routing budget; the first provider reserves time and an attempt for a credentialed second provider. Configure these with `AI_MAX_MODEL_ATTEMPTS`, `AI_MODEL_TIMEOUT_SECONDS`, and `AI_REQUEST_TIMEOUT_SECONDS`. HTTP timeouts apply per network operation; this is not a hard wall-clock deadline for an entire multi-node campaign workflow. Successful run metadata records the actual provider/model and safe attempt history, without credentials or source text.

Safety blocks and invalid credentials/request configuration stop immediately. A valid evaluator rejection still enters the existing repair/human-review loop. If every usable model fails, the request reports provider exhaustion without generating demo content. Text failover includes media briefs, but image/audio generation stays with its configured adapter and retains the free-only Gemini image guard. Embeddings retain their configured Gemini model and bounded retries; Groq does not replace embeddings, and changing vector spaces would require reindexing stored sources.

[Pollinations' current API](https://gen.pollinations.ai/docs) uses a key; unlimited free no-key access is not assumed. [Cohere trial usage](https://docs.cohere.com/docs/how-does-cohere-pricing-work) is free but limited. [Edge TTS](https://github.com/rany2/edge-tts) is an unofficial online service integration without an API key; availability and usage rights are not guaranteed by this project. [R2 Standard storage](https://developers.cloudflare.com/r2/pricing/) includes 10 GB-month plus operation allowances with free direct egress; excess usage can cost money. MongoDB replaces Neon/Supabase and pgvector in this implementation.

Gemini image generation is configured with `IMAGE_PROVIDER=gemini`, `GEMINI_IMAGE_MODEL=gemini-3.1-flash-image`, and `GEMINI_IMAGE_ALLOW_PAID=false`. Google's [current API pricing](https://ai.google.dev/gemini-api/docs/pricing) lists no free tier for image generation. The guard rejects image generation before visual planning, provider calls or version changes. Paid image calls require an explicit configuration opt-in; no alternate provider is selected automatically.

## Workflow

1. Register/sign in; edit name, company, bio and timezone from the profile editor.
2. Add brand voice, approved claims, forbidden phrases and text/PDF sources. Uploads are limited to 5 MiB, 50 PDF pages and 100,000 extracted characters; a brand is limited to 750,000 source characters. Scanned PDFs need external OCR. Original uploaded files are private in account mode; chunks/embeddings live in MongoDB.
3. Generate strategy, review assumptions and source references, and choose a direction. Strategy edits retain history and clear the timeline; existing asset versions retain their generation context.
4. Generate/rebalance the timeline and edit items. Generate LinkedIn posts, Instagram scripts or X posts/threads.
5. The AI evaluator checks grounding, brand fit, platform fit, audience fit, claim safety and completeness alongside fixed safety/format validators. LangGraph permits at most two Creative repair attempts. All drafts/evaluations remain visible; exhausted failures become `needs_human_review` and remain blocked from approval and publication.
6. Edits/regeneration create immutable versions and invalidate approval. Current brand guardrails are checked again at approval and publication.
7. Generate optional images/voiceovers. Media creates a new version. Preview/listen and explicitly confirm media review before approving it. Automatic evaluation covers copy, not visual accuracy or speech fidelity.
8. Generate hook comparisons from an approved asset. AI variants start with zero results and separate evaluations; drafts are not approved or published. Import cumulative results with an evidence reference; prior snapshots remain in history.
9. Generate AI analytics and evidence-linked learnings. Save selected learnings to Brand Brain. Historical learnings inform strategy as hypotheses and are excluded from factual product claims.

Background agent operations persist job status and stream live SSE progress. A campaign allows one active background job at a time. Execution uses FastAPI background tasks in the server process, not a distributed queue. Failed/abandoned jobs remain inspectable; jobs without progress for 15 minutes are marked failed. After a disconnected stream, reload before retrying. `/jobs/{id}/stream` provides live progress; campaign `/stream` remains saved trace replay.

Publication records workflow status and does not post to social networks. Social OAuth/posting and automatic analytics need platform-specific credentials, permissions and adapters. JSON export includes campaign and brand state. AI agents never invent real performance.

## LangGraph architecture and layout

The five agents match blueprint sections 24–27: Strategist owns strategy and creative directions; Marketing owns timeline/channel sequencing; Creative owns copy, hook variants, revisions and media briefs; Evaluator owns the six quality dimensions; Analytics owns observations and learnings. Prompts live under `prompts/{strategist,marketing,creative,evaluator,analytics}` with the blueprint's named prompt files. Structured Pydantic schemas remain the provider boundary.

`apps/api/app/services/orchestrator.py` compiles real [LangGraph StateGraphs](https://docs.langchain.com/oss/python/langgraph/graph-api). The asset graph runs `load_campaign_state → retrieve_context → creative_generation → save_version → evaluate`, then conditionally loops through `repair → save_version → evaluate` or ends at human review. `save_version` stages immutable drafts; the API commits all versions, evaluations and campaign traces in one MongoDB transaction after graph success. A failed provider call leaves campaign/asset history unchanged. Partial revisions and hook experiments preserve other copy fields. Review is a persisted application boundary: approving the current evaluated version remains an explicit authenticated API action.

Shared state includes campaign ID, goal, audience, strategy, creative direction, timeline, approved current asset summaries, brand ID and campaign context. Retrieval runs once per generation graph, selecting eight candidates then up to four evidence chunks, with optional Cohere reranking. Historical learnings remain hypotheses. Only node progress metadata is exposed through SSE; raw graph state and source contents are not streamed. No hosted LangGraph service, LangSmith key or additional model API is required.

Backend implementations live in `api/`, `core/`, `models/`, `schemas/`, `services/`, `agents/`, `rag/` and `workers/`; old flat module imports remain compatibility shims. Frontend panels live in the blueprint's campaign, strategist, canvas, context, timeline, approval, trace, experiments and analytics component directories. Job streaming is in `apps/web/hooks/`; domain types are shared from `packages/shared-types/`.

`infra/docker/` contains API/web Dockerfiles and a local Compose configuration using the supplied Atlas/replica-set URI (`docker compose -f infra/docker/compose.yml up --build`). `infra/migrations/initialize_indexes.py` initializes the same Mongo indexes as API startup. Existing Mongo documents keep their aggregate shape and need no destructive schema migration. Docker execution and credentialed Mongo/index checks have not been run here.

Graphs execute within the existing background jobs. Campaign state, versions, approvals, traces and job status are Mongo-backed; LangGraph step checkpoints/resume and distributed crash recovery are not implemented. Interrupted executions must be inspected and retried; no automatic resume or auto-publication is implied.

## Verification

```powershell
.venv\Scripts\python -m pytest apps/api/tests -q
.venv\Scripts\python -m unittest discover -s scripts/tests -v
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

Offline tests use fixture model outputs and a Mongo-compatible test double for account/transaction contracts. They cover demo workflow, AI evaluation/repair, profiles/sessions, ownership, rollback/revision conflicts, live job events, imported metrics, provider validation, private R2 routing and media approval invalidation. They do not establish live provider availability/quality or actual Atlas transaction behavior. Credentialed checks are required before deployment.

Run live agent smoke queries with `.venv\Scripts\python scripts/check_agents.py --live`. The script uses configured providers and synthetic sources, checks the five agent roles plus directions, repairs, variants and visual planning, and never writes campaigns or publishes content. Use `--only timeline --duration 14` to isolate a two-week timeline. Calls consume text/embedding quota; paid images are excluded. Status output redacts credentials. Gemini response schemas resolve references and omit decoding-complex length/array bounds; the full Pydantic constraints still validate every response. This avoids the timeline HTTP 400 caused by the original wire schema, consistent with Google's [schema complexity guidance](https://ai.google.dev/gemini-api/docs/generate-content/structured-output#limitations).

Add `--probe-groq-fallback` to simulate exhausted Gemini text quota and exercise real Groq calls through the full agent workflow. The probe requires `GROQ_API_KEY`, keeps embeddings on real Gemini, labels the injected quota failure, and never edits `.env`. Its output includes each model's routing attempts. Use `--model <name>` for a smoke-process-only Gemini primary model override.

Use `--only analytics learning visual_plan` to rerun selected checks, or `--model gemini-3.1-flash-lite` to use a different Gemini text model for that smoke process without editing `.env`. Gemini transient quota retries honor server delays up to 60 seconds. A reported daily quota exhaustion fails immediately with an actionable message; it cannot recover through a short retry and never triggers an automatic model switch.

## Remaining production work

Public deployment, email verification/password recovery/OAuth/MFA, team permissions, distributed job recovery, central rate limits, monitoring, object lifecycle cleanup, Mongo-native vector indexing at scale, OCR, video generation, real posting/analytics and a provider-backed quality benchmark remain outside this MVP. Rate limits are per process. Source deletion removes retrieval metadata; original binaries need a lifecycle cleanup policy. Binary uploads and database writes use best-effort cleanup rather than a cross-service transaction.

## Repository records

[AGENTS.md](AGENTS.md) requires a new matching pair in `markdowns/PR_context/` and `markdowns/audits/` for every commit, included with that commit's implementation. The hook (`git config core.hooksPath .githooks`) and CI enforce the pair. User-owned `markdowns/globals` remains unchanged. The accompanying scoped review is not an exhaustive security audit.
