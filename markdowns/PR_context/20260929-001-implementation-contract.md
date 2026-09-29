# Initial implementation contract

This workspace began with only the global blueprint and no Git metadata. This record defines the first local MVP slice, not a completed production release.

## Shared API contract

FastAPI serves unprefixed JSON endpoints on port 8000. Next.js runs on 3000 and rewrites `/api/:path*` to the backend, so browser calls use `/api`. Default operation is a single-workspace local demo, deterministic generation, and explicitly simulated analytics. Use SQLite persistence locally through SQLAlchemy with DATABASE_URL override. No third-party credentials are required for the demo.

All IDs are strings. Timestamps are ISO strings. Mutations return the updated resource unless stated. Errors use FastAPI `detail` string. Campaign detail includes its related state.

Brand: `{id,name,description,voice,approved_claims:string[],forbidden_phrases:string[],sources:Source[]}`.
Source: `{id,name,text,source_type}`.
Campaign: `{id,brand_id,name,brief,goal,audience,platforms:string[],duration_days,status,created_at,strategy:Strategy|null,selected_direction:string|null,timeline:TimelineItem[],assets:Asset[],trace:Trace[],experiments:Experiment[],learnings:Learning[]}`.
Strategy: `{positioning,core_message,audience_summary,content_pillars:string[],assumptions:string[],creative_directions:{id,name,description,rationale}[],source_refs:string[]}`.
TimelineItem: `{id,day,stage,platform,asset_type,objective}`.
Asset: `{id,campaign_id,platform,asset_type,status,current_version:number,versions:Version[],approvals:Approval[]}`.
Version: `{version:number,hook,body,cta,source_refs:string[],evaluation:{passed:boolean,issues:string[],checks:Record<string,boolean>},created_at}`.
Approval: `{version:number,decision,feedback,created_at}`.
Trace: `{id,event_type,message,status,timestamp}`.
Experiment: `{id,name,asset_id,variable,variants:{label,hook,impressions,clicks,conversions}[],is_demo:boolean}`.
Learning: `{id,statement,evidence,confidence,saved_to_brand:boolean}`.

Endpoints:

- `GET /health` → `{status,mode}`.
- `GET /brands` → Brand[]. Seed one useful demo brand automatically.
- `POST /brands` body `{name,description,voice,approved_claims,forbidden_phrases}` → Brand.
- `PATCH /brands/{id}` same editable fields → Brand.
- `POST /brands/{id}/sources` body `{name,text,source_type}` → Brand.
- `POST /brands/{id}/sources/upload` multipart `file` for PDF/text → Brand.
- `GET /campaigns` → Campaign[].
- `POST /campaigns` body `{brand_id,name,brief,goal,audience,platforms,duration_days}` → Campaign.
- `GET /campaigns/{id}` → Campaign.
- `POST /campaigns/{id}/strategy` → Campaign.
- `POST /campaigns/{id}/direction` body `{direction_id}` → Campaign.
- `POST /campaigns/{id}/timeline` → Campaign.
- `POST /campaigns/{id}/assets` body `{platform,asset_type,demonstrate_failure?:boolean}` → Campaign.
- `PATCH /assets/{id}` body `{hook,body,cta}` → Asset; creates and evaluates new version.
- `POST /assets/{id}/regenerate` body `{section?:"all"|"hook"|"cta"}` → Asset.
- `POST /assets/{id}/approve`, `/reject`, `/request-changes` body `{version:number,feedback?:string}` → Asset; reject stale version.
- `POST /assets/{id}/publish` body `{version:number}` → Asset; only explicitly approved current passing version.
- `POST /campaigns/{id}/experiments` body `{asset_id,variable:"hook"}` → Campaign.
- `GET /campaigns/{id}/analytics` → `{is_demo:true,impressions,clicks,conversions,ctr,platforms:{platform,impressions,clicks,conversions}[],observations:string[]}`.
- `POST /campaigns/{id}/learnings` → Campaign.
- `POST /campaigns/{id}/learnings/{learning_id}/save` → Campaign.
- `GET /campaigns/{id}/trace` → Trace[].
- `GET /campaigns/{id}/stream` → finite SSE replay of persisted trace events, documented as replay (live job streaming deferred).
- `GET /campaigns/{id}/export` → JSON campaign pack.

## Initial boundaries and next steps

Implement connected demo behavior first. Hosted auth, true vector retrieval, external model generation, distributed jobs, real publishing, live metrics, and public deployment require later work. Exact delivered behavior and verification will be recorded after integration. Globals remain unchanged.
