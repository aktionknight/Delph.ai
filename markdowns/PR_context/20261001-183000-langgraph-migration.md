# LangGraph migration aligned with the campaign blueprint

Parent: eba626b44542bc24e3435d7a91ebc67419a18bd8. No commit made in this session.

## Scope and changes

Migrated the previously implemented AI/MongoDB runtime to LangGraph and the directory layout in the current user-owned technical implementation specification. Preserved the user's existing specification edits. Backend code now lives in api, core, models, schemas, services, agents, rag and workers; legacy imports remain compatibility shims. The ASGI entry point delegates to api/routes.py.

Five distinct agents follow blueprint ownership: Strategist owns positioning and directions; Marketing owns timelines; Creative owns content, repair, variants and media briefs; Evaluator owns six quality dimensions; Analytics owns observations and learnings. Removed writer, repair, visual and memory as separate agent identities. Canonical CREATIVE_PROVIDER is supported, with legacy writer/repair provider switches retained when it is unset.

CampaignOrchestrator compiles StateGraphs with shared campaign channels, explicit load/retrieval/agent nodes, separate strategy and direction nodes, and conditional asset evaluation/repair edges. Async methods match the blueprint interface; synchronous graph invocation supports existing FastAPI worker/route contracts. Graph nodes emit progress metadata through existing Mongo-backed jobs and persist campaign traces on successful completion.

The asset graph stages immutable drafts, evaluates each and retries Creative repair at most twice. Passing drafts end at needs_review; exhausted failures end at needs_human_review. API persistence atomically commits the full version/evaluation history with campaign state. Human approval remains an authenticated, current-version action and cannot be inferred from graph completion. Provider failures leave caller aggregates untouched. Partial revisions and experiment hooks retain other copy fields; experiment generation histories are preserved. Evaluation receives current campaign audience and requires grounding, brand_fit, platform_fit, audience_fit, claim_safety and completeness.

Moved prompts into the blueprint's external prompt directories and added Analytics prompts. Pydantic schemas stay authoritative. Retrieval selects eight candidates and up to four final chunks, with optional Cohere reranking. Approved asset summaries are derived from current version approvals, never copied into the database as independent authority. Deterministic generation remains explicitly demo-only; mandatory rule validators remain safety checks.

Frontend panels now follow campaign, strategist, canvas, context, timeline, approval, trace, experiments and analytics directories. Extracted SSE job handling into hooks and domain types into packages/shared-types. Added infra/docker API/web Dockerfiles, a local Compose configuration for a supplied MongoDB URI, and an idempotent index initializer under infra/migrations. Existing Mongo aggregate shapes and version/approval history are retained; no destructive data migration is required. Fixed the SQLite demo path after moving its model module.

## Verification

- Backend pytest: 29 passed, including eight new graph/approval contract tests.
- Repository commit-documentation checks: 12 passed. The first sandbox run could not launch Git's shell signal pipe; the approved rerun passed.
- Frontend TypeScript check and Next.js production build passed. The sandbox build could not spawn workers; the approved rerun passed.
- pip check: no broken requirements.
- Tracked diff whitespace check passed before this record was added; final check follows.
- No live credentials/provider requests, Atlas transaction execution, Docker builds, browser visual verification or index migration execution were performed.

## Decisions, limitations and next steps

MongoDB remains the canonical database for profiles, sessions, campaign state, assets, versions, approvals, metrics and traces. LangGraph is a local library and needs no hosted service or new API key. Graph step checkpoints/resume and distributed job recovery are not implemented. Human review is a persisted API boundary, rather than a resumable LangGraph interrupt. Version nodes stage drafts until successful atomic persistence; failed execution drafts are not stored as partial campaign state.

Gemini's existing free-only image guard is preserved before graph retrieval/provider calls; images remain unavailable without explicit paid opt-in. No alternate image provider is selected automatically. Gemini text/embedding and MongoDB credentials are sufficient for the existing core workflow; Groq, Cohere and R2 remain optional.

Next steps: credentialed Gemini/Atlas workflow checks, Docker smoke tests, then a Mongo checkpoint/recovery design if durable step-level resume is needed. Social publishing, imported analytics automation, distributed rate limits and the earlier documented production authentication gaps remain incomplete.
