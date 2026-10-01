# Campaign Launchpad — Technical Implementation Blueprint
## Production-Ready Hackathon MVP

---

# 0. Executive Summary

**Campaign Launchpad** is an AI-native campaign operating system for brands, creators, founders, and small marketing teams.

The product takes a user from:

```text
Campaign Brief
    ↓
Brand / Product Context
    ↓
Strategy
    ↓
Creative Direction
    ↓
Campaign Timeline
    ↓
Platform-Specific Content
    ↓
Quality Evaluation
    ↓
Human Approval
    ↓
A/B Experiments
    ↓
Campaign Analytics
    ↓
Campaign Memory
```

The key product distinction is that this is **not merely an AI content generator**.

It is a **stateful, traceable, human-in-the-loop campaign workflow** where strategy, content, brand context, evaluation, approval, and analytics are connected through one campaign state.

For the hackathon, the MVP should prioritize:

1. A coherent end-to-end workflow
2. Strong agent orchestration
3. Grounded generation using brand context
4. Human approval
5. Evaluation and visible failure recovery
6. A polished, deployable UI
7. Real metrics wherever possible
8. Mocked or simulated integrations only where production integration would consume disproportionate time

---

# 1. MVP Goals

## 1.1 What the MVP must prove

The MVP must demonstrate that Campaign Launchpad can:

- Create a campaign from a short brief
- Ingest brand and product documents
- Retrieve relevant context
- Generate campaign strategy
- Suggest creative directions
- Build a campaign timeline
- Create platform-specific content
- Evaluate generated content
- Catch and repair a bad generation
- Wait for human approval
- Generate A/B variants
- Display campaign performance
- Store useful campaign learnings

## 1.2 What does NOT need to be fully productionized for the hackathon

Do not let these block the demo:

- Real posting to every social platform
- Real-time analytics ingestion from all platforms
- Full multi-user workspace permissions
- Advanced billing
- Complex role-based access control
- Perfect image/video generation
- Long-running autonomous agents
- Fully automated retraining
- Enterprise-grade observability stack
- Multi-region deployment

These can be architecturally supported while being partially mocked.

---

# 2. Recommended Technology Stack

## Frontend

### Core
- **Next.js 15 / React**
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui** for primitive components
- **Framer Motion** for subtle interaction animations
- **TanStack Query** for API state
- **Zustand** for transient local UI state

### Rich editor / canvas
Choose one:
- **Tiptap** for structured text editing
- **Lexical** if deeper editor customization is needed

For hackathon speed: **Tiptap**.

## Backend

- **FastAPI**
- **Pydantic v2**
- **Uvicorn**
- **Motor / Beanie** (async MongoDB ODM & driver)

FastAPI is a good fit because the project needs typed APIs, AI orchestration, streaming, and Pydantic-native structured outputs.

## Primary Database

- **MongoDB** (MongoDB Atlas or self-hosted)

Use it for:
- Users
- Workspaces
- Brands
- Campaigns
- Assets
- Approval history
- Agent runs
- Evaluation traces
- Experiments
- Metrics
- Campaign learnings

MongoDB's flexible document model natively handles deeply nested campaign state (`campaign_state`), agent logs (`input_json`, `output_json`), and rich asset revisions without complex relational joins.

## Vector Store

Recommended: **MongoDB Atlas Vector Search**
(Alternative for local/standalone development: **Qdrant** or **Chroma**)

Why:
- **Atlas Vector Search**: Unified database — store documents and vector embeddings in the same collection (`document_chunks`). Query with native `$vectorSearch` aggregation stage alongside metadata filters (`brand_id`, `source_type`). Zero synchronization overhead between business data and vectors, with a free M0 cluster tier.
- **Qdrant (Alternative)**: Dedicated high-performance vector engine with rich payload filtering, generous cloud free tier, and easy local Docker setup.
- **Chroma (Local/Dev Alternative)**: Fast, lightweight embedded vector database ideal for rapid offline local prototyping.

## File Storage

Recommended: **Cloudflare R2** (10 GB free forever, zero egress fees, S3-compatible)
Alternatives:
- AWS S3
- Supabase Storage

Store:
- PDFs
- generated images
- audio
- exported campaign packs
- uploaded brand references

## Model Layer

Create a provider abstraction.

```text
Strategy Model
→ higher-reasoning LLM (e.g. Gemini 2.0 Flash / Pro)

Content Model
→ strong writing LLM (e.g. Gemini / Groq Llama 3.3 70B)

Evaluator Model
→ lower-cost, ultra-fast structured-output LLM (e.g. Groq Llama 3.1 8B)

Embedding Model
→ text embeddings (e.g. Gemini text-embedding-004 / FastEmbed)

Reranker Model (Optional)
→ Cohere Rerank v3.5 (free trial)

Image Model
→ image generation (e.g. Pollinations.ai Flux / SDXL)

Voice Model
→ TTS / cloned voice (e.g. edge-tts / ElevenLabs)
```

Example interface:

```python
class ModelRouter:
    async def generate_strategy(...)
    async def generate_content(...)
    async def evaluate_content(...)
    async def embed(...)
```

Do not tie business logic to one model provider.

## Background Jobs

Use:
- Redis
- Dramatiq or Celery

For a hackathon:
- FastAPI BackgroundTasks are acceptable for very small jobs
- Dramatiq + Redis is better if document ingestion and media generation become asynchronous

## Streaming

Use **Server-Sent Events (SSE)** for:
- retrieving context
- building strategy
- checking claims
- regenerating a failed asset
- preparing approval

SSE is simpler than WebSockets for one-way progress updates.

---

# 3. High-Level Architecture

```text
                        ┌─────────────────────┐
                        │       FRONTEND      │
                        │ Next.js + TypeScript│
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │     API GATEWAY     │
                        │      FastAPI        │
                        └──────────┬──────────┘
                                   │
           ┌───────────────────────┼────────────────────────┐
           │                       │                        │
           ▼                       ▼                        ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│ Campaign Service   │  │ Context / RAG      │  │ Agent Orchestrator │
└─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘
          │                        │                       │
          ▼                        ▼                       ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│ MongoDB            │  │ Atlas Vector Search│  │ Model Router       │
│ campaign state     │  │ (or Qdrant/Chroma) │  │ LLM / image / TTS  │
└────────────────────┘  └────────────────────┘  └────────────────────┘

                    ┌──────────────────────────────┐
                    │      BACKGROUND WORKERS      │
                    │ ingestion / media / eval     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        FILE STORAGE          │
                    │       S3 / R2 / Supabase     │
                    └──────────────────────────────┘
```

---

# 4. Core Domain Model

The **Campaign** should be the central domain object.

Core entities:

```text
User
Workspace
Brand
BrandSource
Campaign
CampaignBrief
CampaignStrategy
CreativeDirection
CampaignTimeline
ContentAsset
AssetVersion
Approval
AgentRun
EvaluationRun
TraceEvent
Experiment
ExperimentVariant
MetricSnapshot
CampaignLearning
```

---

# 5. Suggested Database Schema (MongoDB Collections)

In MongoDB, these entities map cleanly to collections and document models (implemented via **Beanie `Document`** or Pydantic/Motor). The `_json` fields become native BSON nested subdocuments or lists without relational join overhead.

## users

```text
id
email
name
created_at
```

## workspaces

```text
id
name
owner_user_id
created_at
```

## brands

```text
id
workspace_id
name
description
voice_profile_json
audience_profile_json
visual_profile_json
guardrails_json
created_at
updated_at
```

## brand_sources

```text
id
brand_id
source_type
file_url
filename
status
metadata_json
created_at
```

Possible `source_type` values:

```text
brand_guideline
product_document
audience_research
previous_campaign
website
manual_note
```

## document_chunks

```text
id
brand_source_id
brand_id
text
embedding
metadata_json
created_at
```

Example metadata:

```json
{
  "page": 4,
  "section": "Tone of Voice",
  "source_name": "Brand Guidelines.pdf"
}
```

## campaigns

```text
id
workspace_id
brand_id
name
status
goal
duration_days
start_date
campaign_state_json
created_at
updated_at
```

Statuses:

```text
draft
planning
generating
review
live
completed
archived
```

## campaign_briefs

```text
id
campaign_id
brief_text
target_audience
platforms_json
objective_json
assumptions_json
created_at
```

## campaign_strategies

```text
id
campaign_id
positioning
core_message
audience_summary
goals_json
content_pillars_json
strategy_json
version
created_at
```

## creative_directions

```text
id
campaign_id
name
description
rationale
selected
source_refs_json
created_at
```

## timeline_items

```text
id
campaign_id
day_index
scheduled_at
stage
platform
asset_type
objective
status
metadata_json
```

## content_assets

```text
id
campaign_id
timeline_item_id
platform
asset_type
status
current_version_id
created_at
updated_at
```

Statuses:

```text
draft
evaluating
failed
needs_review
approved
rejected
published
```

## asset_versions

```text
id
content_asset_id
version_number
content_json
source_context_json
created_by
created_at
```

`created_by`:

```text
ai
human
system
```

## approvals

```text
id
content_asset_id
asset_version_id
user_id
decision
feedback
created_at
```

Decisions:

```text
approved
rejected
changes_requested
```

## agent_runs

```text
id
campaign_id
agent_type
input_json
output_json
status
started_at
completed_at
```

Agent types:

```text
strategist
creative
marketing
evaluator
analytics
```

## trace_events

```text
id
agent_run_id
campaign_id
content_asset_id
event_type
message
status
metadata_json
timestamp
```

## evaluation_runs

```text
id
content_asset_id
asset_version_id
evaluation_type
score_json
passed
failure_reason
created_at
```

## experiments

```text
id
campaign_id
name
platform
variable
status
created_at
```

## experiment_variants

```text
id
experiment_id
content_asset_id
label
variant_metadata_json
created_at
```

## metric_snapshots

```text
id
campaign_id
content_asset_id
experiment_variant_id
metric_type
metric_value
captured_at
```

## campaign_learnings

```text
id
campaign_id
learning_type
statement
evidence_json
confidence
created_at
```

---

# 6. System Decomposition

Top-down module split:

```text
1. Authentication + Workspace
2. Campaign Dashboard
3. Campaign Creation
4. Brand Brain
5. Context / RAG
6. AI Strategist
7. Creative Direction
8. Campaign Timeline
9. Content Canvas
10. Media Generation
11. Evaluation / Quality Gate
12. Human Approval
13. Trace Viewer
14. A/B Experiments
15. Analytics
16. Campaign Memory
17. Export / Publish Layer
18. Observability
```

---

# 7. Module 1 — Authentication & Workspace

## MVP scope
Implement:
- email or OAuth login
- one workspace per user
- one or more brands
- workspace-level campaign listing

Use:
- Clerk
- Supabase Auth
- Auth.js

Hackathon preference: **Clerk or Supabase Auth**

## API

```text
POST /auth/login
GET /me
GET /workspaces/current
GET /brands
POST /brands
```

---

# 8. Module 2 — Campaign Dashboard

Display:
- active campaigns
- recent campaigns
- pending approvals
- A/B tests
- campaign metrics
- AI observations

Backend service:

```python
class DashboardService:
    def get_workspace_summary(...)
    def get_recent_campaigns(...)
    def get_pending_approvals(...)
    def get_active_experiments(...)
    def get_campaign_insights(...)
```

API:

```text
GET /dashboard
```

For the hackathon, if real platform analytics is unavailable:
- seed realistic metrics
- clearly mark them as demo data
- keep numbers deterministic across every screen

---

# 9. Module 3 — Campaign Creation

User flow:

```text
New Campaign
    ↓
Brief
    ↓
Goal
    ↓
Audience
    ↓
Platforms
    ↓
Duration
    ↓
Brand Context
    ↓
AI Assumptions
    ↓
Create Campaign
```

Create:

```python
class CampaignService:
    def create_campaign(...)
    def update_brief(...)
    def infer_missing_context(...)
    def get_campaign(...)
    def update_campaign_state(...)
```

Assumption output:

```json
{
  "target_audience": "small marketing teams",
  "tone": ["confident", "conversational"],
  "campaign_goal": "awareness",
  "assumptions": [
    {
      "field": "audience",
      "value": "small marketing teams",
      "confidence": 0.82
    }
  ]
}
```

Always show inferred assumptions to the user.

---

# 10. Module 4 — Brand Brain

Responsibilities:

```text
Identity
Voice
Audience
Visual language
Guardrails
Approved claims
Source documents
Historical campaigns
```

Structured brand profile:

```json
{
  "voice": {
    "tone": ["confident", "human", "technical"],
    "sentence_style": "short",
    "forbidden_phrases": [],
    "preferred_phrases": []
  },
  "audience": {
    "primary": "small marketing teams",
    "pain_points": [],
    "goals": []
  },
  "visual": {
    "style": ["minimal", "editorial"],
    "colors": [],
    "references": []
  },
  "guardrails": {
    "unsupported_claims_forbidden": true,
    "banned_topics": []
  }
}
```

API:

```text
GET /brands/{brand_id}
PATCH /brands/{brand_id}
POST /brands/{brand_id}/sources
GET /brands/{brand_id}/sources
DELETE /brands/{brand_id}/sources/{source_id}
```

---

# 11. Module 5 — Document Ingestion + RAG

Pipeline:

```text
Upload
 ↓
Store
 ↓
Extract
 ↓
Normalize
 ↓
Chunk
 ↓
Embed
 ↓
Store vectors
 ↓
Retrieve
```

PDF parsing:
- PyMuPDF
- pypdf
- Docling
- LlamaParse

Hackathon recommendation: **PyMuPDF**

Chunking:
- 600–1000 tokens
- 100–150 token overlap

Store page, section, and source metadata.

Retrieval:
1. embed query (e.g. Gemini `text-embedding-004` or FastEmbed)
2. vector similarity search top 8 (via MongoDB `$vectorSearch` pipeline stage or Qdrant/Chroma) pre-filtered by `brand_id`
3. rerank or LLM-select top 4 (via Cohere Rerank v3.5 or prompt selection)
4. return citation metadata

Use separate retrieval categories:
- brand voice
- product facts
- audience
- previous campaigns
- campaign-specific sources

---

# 12. Module 6 — AI Strategist

Purpose:
- positioning
- audience framing
- value proposition
- key message
- content pillars
- creative directions

Input:

```json
{
  "campaign_brief": "...",
  "brand_profile": {},
  "retrieved_context": [],
  "campaign_goal": "awareness",
  "duration_days": 14,
  "platforms": ["instagram", "linkedin", "x"]
}
```

Structured output:

```json
{
  "positioning": "...",
  "core_message": "...",
  "audience_summary": "...",
  "content_pillars": [],
  "creative_directions": [
    {
      "name": "Problem-first",
      "description": "...",
      "rationale": "...",
      "source_refs": []
    }
  ],
  "risks": []
}
```

Strategist flow:
1. parse brief
2. retrieve context
3. generate structured strategy
4. expose assumptions
5. expose sources
6. let user edit
7. persist selected strategy

---

# 13. Module 7 — Creative Direction

Creative directions are campaign-level choices, not just post styles.

Examples:
- Problem-first
- Founder-led
- Educational
- Contrarian
- Community-led
- Product-led

Store each direction and let the user select one.

Every subsequent content generation request should inherit the selected direction.

---

# 14. Module 8 — Marketing Timeline

Purpose:
Create a launch strategy, not just a calendar.

Timeline stages:

```text
Awareness
Education
Trust
Reveal
Proof
Objection handling
Conversion
```

Marketing Agent input:

```json
{
  "strategy": {},
  "creative_direction": {},
  "duration_days": 14,
  "platforms": ["instagram", "linkedin", "x"],
  "campaign_goal": "awareness"
}
```

Output:

```json
{
  "timeline": [
    {
      "day": 1,
      "stage": "awareness",
      "platform": "instagram",
      "asset_type": "reel",
      "objective": "surface audience pain point",
      "brief": "..."
    }
  ]
}
```

Allow rebalance if:
- duration changes
- platform changes
- creative direction changes
- content gets delayed

Never overwrite already approved content automatically.

---

# 15. Module 9 — Content Canvas

Supported asset types:

```text
Instagram Reel
Instagram Carousel
Instagram Story
LinkedIn Post
X Post
X Thread
Video Script
Audio Script
Image Creative
Headline
CTA
```

Structured asset example:

```json
{
  "hook": "...",
  "voiceover": "...",
  "scene_breakdown": [],
  "caption": "...",
  "cta": "...",
  "hashtags": []
}
```

Generation pipeline:

```text
Timeline Item
    ↓
Load Campaign State
    ↓
Retrieve Brand Context
    ↓
Retrieve Product Context
    ↓
Load Creative Direction
    ↓
Generate Content
    ↓
Save Asset Version
    ↓
Run Evaluation
    ↓
Pass → Human Review
Fail → Repair
```

Controls:
- regenerate asset
- regenerate hook
- regenerate CTA
- make more conversational
- make more technical
- create variant
- convert platform

API:

```text
POST /campaigns/{id}/assets
POST /assets/{id}/generate
POST /assets/{id}/regenerate
POST /assets/{id}/variants
POST /assets/{id}/convert
GET /assets/{id}
```

---

# 16. Module 10 — Media Generation

Image generation:
- social graphics
- thumbnails
- carousel backgrounds
- campaign hero images

Voice:
- standard TTS first
- optional authorized custom voice later

Video:
For the MVP, focus on:
- scene plan
- voiceover
- image assets
- subtitles
- optional generated clip

Do not let full video generation become a project sinkhole unless it is central to the demo.

---

# 17. Module 11 — Quality Gate / Evaluation

This is one of the strongest hackathon features.

Checks:

```text
1. Grounding
2. Brand Fit
3. Platform Fit
4. Audience Fit
5. Claim Safety
6. Content Completeness
```

Architecture:

```text
Generated Asset
     ↓
Rule-Based Checks
     ↓
Claim Extraction
     ↓
Evidence Retrieval
     ↓
LLM Evaluator
     ↓
Pass / Fail
     ↓
Trace Event
```

Grounding evaluator:
1. extract factual claims
2. retrieve evidence
3. assess support
4. mark unsupported claims
5. return source references

Example:

```json
{
  "passed": false,
  "unsupported_claims": [
    {
      "claim": "18-hour battery life",
      "evidence_found": false
    }
  ]
}
```

Brand-fit checks:
- tone
- preferred vocabulary
- banned phrases
- positioning

Platform-fit checks:
- X character count
- LinkedIn formatting
- Reel hook presence
- estimated script duration
- CTA
- caption

Failure recovery:

```text
fail
 ↓
emit trace
 ↓
build correction prompt
 ↓
regenerate problematic section only
 ↓
evaluate again
```

Set:

```text
MAX_RETRIES = 2
```

After that:
- mark `needs_human_review`

---

# 18. Module 12 — Human Approval

State machine:

```text
draft
 ↓
evaluating
 ↓
needs_review
 ↓
approved
 ↓
published
```

Alternative paths:
- changes_requested → draft
- rejected

API:

```text
POST /assets/{id}/approve
POST /assets/{id}/request-changes
POST /assets/{id}/reject
```

If the user says:
> Keep the hook, make the CTA less sales-heavy.

Only regenerate the CTA.

Version every revision.

---

# 19. Module 13 — Trace Viewer

Purpose:
Expose what happened inside the system.

Suggested trace events:

```text
brief_loaded
context_retrieval_started
context_retrieved
strategy_loaded
generation_started
generation_completed
evaluation_started
grounding_failed
brand_fit_failed
regeneration_started
evaluation_passed
approval_requested
approved
published
```

Use SSE:

```text
GET /campaigns/{id}/stream
```

The UI renders these events live.

---

# 20. Module 14 — A/B Experiments

MVP flow:
1. choose an asset
2. choose variable
3. create variants
4. attach metrics
5. compare
6. save observed learning

Variables:
- Hook
- CTA
- Visual
- Caption
- Opening sentence
- Creative direction

Variant generation:

```json
{
  "asset_id": "...",
  "variable": "hook",
  "count": 3
}
```

Try to hold constant:
- audience
- platform
- posting window
- campaign objective

If metrics are simulated, label them as demo data.

---

# 21. Module 15 — Analytics

MVP metrics:

```text
Reach
Impressions
Engagement
CTR
Conversions
Saves
Shares
Comments
```

Possible data strategies:

### Option A
Seeded demo metrics

### Option B
One real social platform integration

### Option C
Deterministic campaign simulator

Recommended for the hackathon:
**seeded metrics + deterministic simulator**

Create:

```python
class AnalyticsService:
    def get_campaign_summary(...)
    def get_platform_breakdown(...)
    def get_asset_performance(...)
    def get_experiment_results(...)
    def generate_observations(...)
```

AI should report evidence-bounded observations, not overclaim causality.

---

# 22. Module 16 — Campaign Memory

Purpose:
Turn campaign results into reusable knowledge.

Learning types:

```text
creative_pattern
audience_signal
platform_signal
content_type_signal
negative_signal
```

Generate from:
- strategy
- performance
- experiments
- approvals

Example:

```json
[
  {
    "type": "creative_pattern",
    "statement": "Problem-first hooks had stronger observed engagement.",
    "evidence": [],
    "confidence": 0.78
  }
]
```

Let the user choose:
- Save to Brand Brain
- Keep in Campaign Only
- Dismiss

Do not auto-promote every observation into brand truth.

---

# 23. Module 17 — Publish / Export Layer

Hackathon MVP:
- copy content
- download image
- download audio
- export campaign pack
- mark as published

Optional:
- LinkedIn API
- X API
- Instagram API

Do not block the project on social platform API approvals.

---

# 24. Agent Architecture

Use only agents with distinct responsibilities.

## Strategist Agent
Owns:
- positioning
- campaign strategy
- creative direction

## Marketing Agent
Owns:
- sequencing
- timeline
- channel mix

## Creative Agent
Owns:
- content generation
- variants
- platform conversion

## Evaluator Agent
Owns:
- grounding
- brand fit
- audience fit
- platform fit

## Analytics Agent
Owns:
- observations
- experiment summaries
- campaign learnings

---

# 25. Shared Campaign State

All agents operate on the same campaign state:

```json
{
  "campaign_id": "...",
  "goal": "awareness",
  "audience": "...",
  "strategy": {},
  "creative_direction": {},
  "timeline": [],
  "approved_assets": [],
  "brand_id": "...",
  "campaign_context": {}
}
```

This prevents agents from becoming disconnected chatbots.

---

# 26. Orchestration Design

Create:

```python
class CampaignOrchestrator:
    async def build_campaign_strategy(...)
    async def generate_timeline(...)
    async def generate_asset(...)
    async def evaluate_asset(...)
    async def repair_asset(...)
    async def create_experiment(...)
    async def generate_learnings(...)
```

Example asset pipeline:

```python
async def generate_asset(asset_id):
    asset = load_asset(asset_id)
    campaign = load_campaign(asset.campaign_id)

    context = retrieve_context(
        brand_id=campaign.brand_id,
        query=build_asset_context_query(asset)
    )

    draft = await creative_agent.generate(
        campaign=campaign,
        asset=asset,
        context=context
    )

    save_version(draft)

    evaluation = await evaluator.run(draft, context)

    if evaluation.passed:
        set_status(asset, "needs_review")
        emit_trace("approval_requested")
    else:
        repaired = await repair_asset(draft, evaluation)
        save_version(repaired)
        await reevaluate(repaired)
```

---

# 27. Prompt Architecture

Keep prompts outside route handlers:

```text
prompts/
    strategist/
        system.txt
        strategy.txt
    creative/
        instagram_reel.txt
        linkedin_post.txt
        x_thread.txt
    evaluator/
        grounding.txt
        brand_fit.txt
        audience_fit.txt
    marketing/
        timeline.txt
```

Every prompt should define:
- role
- objective
- campaign state
- retrieved context
- constraints
- output schema
- failure conditions

---

# 28. Structured LLM Output

Use Pydantic models.

```python
class CreativeDirection(BaseModel):
    name: str
    description: str
    rationale: str
    source_refs: list[str]

class StrategyOutput(BaseModel):
    positioning: str
    core_message: str
    audience_summary: str
    content_pillars: list[str]
    creative_directions: list[CreativeDirection]
```

Reject malformed model output and retry.

---

# 29. API Surface

Suggested REST surface:

```text
/auth/*
/workspaces/*
/brands/*
/campaigns/*
/assets/*
/experiments/*
/analytics/*
```

Campaign endpoints:

```text
POST   /campaigns
GET    /campaigns
GET    /campaigns/{id}
PATCH  /campaigns/{id}
POST   /campaigns/{id}/strategy
POST   /campaigns/{id}/timeline
POST   /campaigns/{id}/timeline/rebalance
GET    /campaigns/{id}/trace
GET    /campaigns/{id}/analytics
POST   /campaigns/{id}/learnings
```

---

# 30. Frontend Route Structure

```text
/
├── dashboard
├── brands
│   └── [brandId]
│       └── brain
├── campaigns
│   ├── new
│   └── [campaignId]
│       ├── strategy
│       ├── canvas
│       ├── timeline
│       ├── approvals
│       ├── experiments
│       ├── analytics
│       ├── trace
│       └── memory
```

---

# 31. Frontend Component Structure

```text
components/
├── campaign/
│   ├── CampaignHeader
│   ├── CampaignSidebar
│   ├── CampaignStatus
│   └── CampaignMetricCard
├── strategist/
│   ├── StrategistChat
│   ├── DirectionCard
│   └── StrategyPanel
├── canvas/
│   ├── AssetCard
│   ├── AssetEditor
│   ├── AssetInspector
│   └── PlatformTabs
├── context/
│   ├── SourceCard
│   ├── ContextSidebar
│   └── CitationDrawer
├── timeline/
│   ├── Timeline
│   └── TimelineItem
├── approval/
│   ├── ApprovalQueue
│   └── ApprovalPanel
├── trace/
│   ├── TraceTimeline
│   └── TraceEvent
├── experiments/
│   ├── ExperimentBuilder
│   └── VariantCard
└── analytics/
    ├── CampaignMetrics
    ├── PlatformChart
    └── InsightCard
```

---

# 32. State Management

Use:
- **TanStack Query** for server state
- **Zustand** for transient UI state

Server state:
- campaign
- assets
- sources
- timeline
- experiments
- analytics

Local state:
- selected asset
- active inspector
- sidebars
- draft form data
- modal state

---

# 33. Error Handling

Handle:
- LLM timeout
- malformed JSON
- no retrieved context
- evaluation failed
- image generation failed
- file parsing failed
- provider rate limit

Avoid generic errors.

Prefer:

```text
Brand context could not be retrieved.
Retry generation without source grounding?
```

---

# 34. Security & Data Handling

Production-minded MVP requirements:
- signed upload URLs
- file type validation
- file size limits
- sanitize filenames
- workspace ownership checks
- protect model API keys
- rate-limit generation endpoints
- never expose private system prompts directly
- store only required user content

---

# 35. Observability

For hackathon:
- Sentry
- structured logs
- agent trace collection

Optional:
- Langfuse
- Helicone

Track:
- model latency
- token usage
- retrieval hits
- evaluation failures
- regeneration count
- human approval rate

---

# 36. Testing Strategy

## Unit tests

Test:
- campaign state transitions
- timeline helpers
- platform validators
- claim extraction
- approval rules
- experiment calculations

## Integration tests

Test:
- PDF upload → embedding
- campaign → strategy
- asset → evaluation
- failed evaluation → repair
- approval → state update
- experiment → metrics

## End-to-end test

Golden path:

```text
Create campaign
Upload brand PDF
Generate strategy
Select direction
Generate timeline
Generate LinkedIn asset
Trigger unsupported claim
Evaluator catches it
Regenerate
Human approves
Generate variants
Show analytics
Create learning
```

---

# 37. Hackathon Evaluation Set

Create:
- 10–20 campaign briefs

Include:
- product launch
- creator campaign
- B2B SaaS
- consumer app
- fashion brand
- technical product
- conflicting context
- missing context
- unsupported claims

Metrics:
- brand-fit pass rate
- grounding pass rate
- platform-fit pass rate
- human approval pass rate
- average retries
- time from brief to approved asset

Baseline:
Compare a generic LLM response against the Campaign Launchpad pipeline using the same brief.

---

# 38. Deployment Architecture

Frontend:
- Vercel

Backend:
- Railway
- Render
- Fly.io

Hackathon preference:
**Railway or Render**

Database & Vector Search:
- MongoDB Atlas (M0 free tier cluster with native Atlas Vector Search)
- Self-hosted MongoDB + Qdrant / Chroma

Recommendation:
**MongoDB Atlas (M0 cluster with Vector Search)**

Redis:
- Upstash Redis

Storage:
- Cloudflare R2 (10 GB free, 0 egress fees)
- Supabase Storage

---

# 39. Environment Variables

```text
MONGODB_URI
DATABASE_NAME
REDIS_URL
JWT_SECRET

# Model Providers
GEMINI_API_KEY
GROQ_API_KEY
COHERE_API_KEY

# Cloudflare R2 / S3-Compatible Storage
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_PUBLIC_URL

FRONTEND_URL
BACKEND_URL
```

---

# 40. CI/CD

GitHub Actions:

```text
push
 ↓
lint
 ↓
typecheck
 ↓
tests
 ↓
build
 ↓
deploy
```

Frontend:
- Vercel auto-deploy

Backend:
- Railway / Render auto-deploy

---

# 41. Suggested Repository Structure

```text
campaign-launchpad/
│
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── lib/
│   │
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   ├── core/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   ├── agents/
│       │   ├── rag/
│       │   └── workers/
│       └── tests/
│
├── packages/
│   └── shared-types/
│
├── prompts/
│   ├── strategist/
│   ├── creative/
│   ├── marketing/
│   └── evaluator/
│
├── infra/
│   ├── docker/
│   └── migrations/
│
└── README.md
```

---

# 42. MVP Roadmap

## Phase 0 — Skeleton

Goal:
Deploy the empty frontend and backend.

Tasks:
- repo setup
- auth
- database
- deployment
- design system
- campaign schema

Deliverable:
A user can log in and create an empty campaign.

## Phase 1 — Campaign Core

Implement:
- new campaign
- campaign brief
- campaign state
- workspace UI

Deliverable:
Campaign exists as persistent state.

## Phase 2 — Brand Brain + RAG

Implement:
- PDF upload
- parsing
- chunking
- embedding
- retrieval
- source UI

Deliverable:
AI strategy can use uploaded brand context.

## Phase 3 — Strategist

Implement:
- assumptions
- positioning
- content pillars
- creative directions
- strategy editing

Deliverable:
Campaign gets a structured strategy.

## Phase 4 — Marketing Timeline

Implement:
- timeline generator
- campaign stages
- platform mapping
- editing
- rebalance

Deliverable:
Campaign gets a launch plan.

## Phase 5 — Content Canvas

Implement:
- LinkedIn
- Instagram Reel script
- X post/thread
- versioning
- regeneration

Deliverable:
Campaign produces platform-specific content.

## Phase 6 — Evaluation

Implement:
- grounding
- brand fit
- platform fit
- failure recovery
- trace events

Deliverable:
System visibly catches one bad generation.

## Phase 7 — Human Approval

Implement:
- approval queue
- approve
- reject
- request changes
- version history

Deliverable:
Human control is explicit and auditable.

## Phase 8 — Experiments

Implement:
- hook variants
- experiment object
- metrics
- comparison

Deliverable:
User can run a small A/B workflow.

## Phase 9 — Analytics + Memory

Implement:
- campaign metrics
- asset performance
- observations
- campaign learning
- save to Brand Brain

Deliverable:
Campaign closes the learning loop.

## Phase 10 — Polish

Implement:
- streaming progress
- transitions
- error states
- demo seed data
- responsive polish
- demo shortcuts

---

# 43. Suggested Hackathon Build Order

If time is tight:

## Priority 1
- campaign creation
- brand context ingestion
- strategy

## Priority 2
- timeline
- content generation

## Priority 3
- evaluation
- trace
- human approval

## Priority 4
- experiment
- analytics

## Priority 5
- media generation
- campaign memory

This order protects the end-to-end story.

---

# 44. Golden Demo Scenario

Use one controlled campaign:

```text
Product:
AI content tool for small marketing teams

Goal:
Build awareness + early signups

Duration:
14 days

Platforms:
Instagram
LinkedIn
X
```

Upload:
- Brand Guidelines.pdf
- Product Brief.pdf
- Audience Research.pdf

Demo sequence:
1. create campaign
2. show Brand Brain
3. ask Strategist for positioning
4. select Problem-first
5. generate 14-day timeline
6. generate Instagram Reel, LinkedIn Post, X Thread
7. trigger an unsupported claim
8. show evaluator fail
9. show repair
10. request a CTA change
11. approve
12. generate 3 hook variants
13. show experiment metrics
14. show analytics
15. save campaign learning

---

# 45. The Most Important Engineering Principle

Do not build:

```text
chatbot
+
image generator
+
calendar
+
analytics dashboard
```

as disconnected features.

Build:

```text
ONE CAMPAIGN STATE
        ↓
EVERY FEATURE READS IT
        ↓
EVERY ACTION UPDATES IT
```

The campaign is the product.

---

# 46. Suggested MVP Success Criteria

Before demo day:

```text
[ ] User can create campaign
[ ] User can upload brand PDF
[ ] PDF becomes retrievable context
[ ] AI generates strategy
[ ] User chooses creative direction
[ ] AI generates timeline
[ ] AI generates at least 3 platform asset types
[ ] Sources used are visible
[ ] Evaluator catches one real failure
[ ] Regeneration repairs the failure
[ ] Human approval changes state
[ ] User creates A/B variants
[ ] Dashboard displays experiment results
[ ] Campaign analytics page loads
[ ] Campaign learning can be saved
[ ] App is deployed publicly
[ ] Demo dataset is deterministic
```

---

# 47. Final Architecture Summary

```text
                         CAMPAIGN LAUNCHPAD
                                │
                                ▼
                       ┌─────────────────┐
                       │ CAMPAIGN STATE  │
                       └────────┬────────┘
                                │
        ┌───────────────────────┼────────────────────────┐
        │                       │                        │
        ▼                       ▼                        ▼
┌───────────────┐      ┌────────────────┐      ┌────────────────┐
│ BRAND BRAIN   │      │ AGENT LAYER    │      │ ANALYTICS      │
│               │      │                │      │                │
│ documents     │      │ strategist     │      │ metrics        │
│ voice         │      │ marketing      │      │ experiments    │
│ audience      │      │ creative       │      │ learnings      │
│ history       │      │ evaluator      │      │                │
└───────┬───────┘      └───────┬────────┘      └───────┬────────┘
        │                      │                       │
        └──────────────┬───────┴───────────┬───────────┘
                       │                   │
                       ▼                   ▼
               ┌───────────────┐   ┌───────────────┐
               │ CONTENT       │   │ QUALITY GATE  │
               │ CANVAS        │   │               │
               └───────┬───────┘   └───────┬───────┘
                       │                   │
                       └─────────┬─────────┘
                                 ▼
                         ┌───────────────┐
                         │ HUMAN REVIEW  │
                         └───────┬───────┘
                                 ▼
                         ┌───────────────┐
                         │ LAUNCH / TEST │
                         └───────┬───────┘
                                 ▼
                         ┌───────────────┐
                         │ LEARN         │
                         └───────────────┘
```

---

# 48. Final Recommendation

For the hackathon, the strongest version of Campaign Launchpad is the one where the judges can visibly understand:

```text
What context the AI used
Why it made a decision
What it generated
How it was evaluated
Where it failed
How it recovered
Where the human approved
What happened after launch
What the system learned
```

The core experience to protect above everything else is:

> **One brief → one campaign brain → one connected workflow → measurable output.**
