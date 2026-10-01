"""Connected campaign API with Gemini agents and MongoDB private workspaces."""
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import PurePath
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pypdf import PdfReader
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..models.database import Record
from ..services.store import Repository, CapacityError
from ..core.auth import Auth
from ..agents import AgentSuite, AgentError
from ..services.storage import BlobStore, StorageError
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[4] / ".env")
from ..services.generation import ASSET_TYPES, DEFAULT_TYPES, DeterministicRouter
from ..core.limits import BodyLimitMiddleware
from ..schemas import (ApprovalInput, AssetInput, BrandInput, BrandPatch, CampaignInput,
                      DirectionInput, EditInput, ExperimentInput, PublishInput,
                      RegenerateInput, SourceInput, MetricInput, StrategyEdit, TimelineEdit, MediaInput,
                      GenerationInput, SectionReviewInput, CampaignPatch)

MAX_UPLOAD = 5 * 1024 * 1024
SECTIONS = ("brief", "strategy", "direction", "timeline", "insights", "learnings")
COPY_FIELDS = ("hook", "body", "cta", "caption", "source_refs")


def section_state(data):
    revisions = data.setdefault("section_revisions", {})
    for section in SECTIONS:
        revisions.setdefault(section, 1)
    data.setdefault("reviews", [])
    data.setdefault("generation_prompts", {})
    return data


def revise(data, *sections):
    section_state(data)
    for section in sections:
        data["section_revisions"][section] += 1


def guidance(data, section, body):
    section_state(data)
    data["generation_prompts"][section] = body.prompt if body else ""


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid4())


def trace(campaign, event, message, status="completed"):
    campaign["trace"].append({"id": uid(), "event_type": event, "message": message, "status": status, "timestamp": now()})


def create_app(database_url=None, agent_suite=None):
    demo = database_url is not None or os.getenv("DEMO_MODE", "false").lower() == "true"
    repository = Repository(database_url)
    router = agent_suite or (DeterministicRouter() if demo else AgentSuite())
    mode = "deterministic" if isinstance(router, DeterministicRouter) else "gemini"
    auth = Auth(repository, demo)
    blobs = BlobStore(repository.database if repository.mongo else None)
    from ..services.social import SocialAccounts, SocialError
    from ..services.publishing import SocialPublisher
    accounts = SocialAccounts(repository)
    publisher = SocialPublisher(repository, accounts, router, blobs)

    @asynccontextmanager
    async def lifespan(app):
        repository.initialize()
        if demo:
            db = repository.open("demo")
            if not db.list("brand"):
                brand = {"id": uid(), "name": "Orbit", "description": "A campaign workspace for small marketing teams.", "voice": "Clear, practical, warm. Avoid hype.", "approved_claims": ["Orbit connects briefs, content review, and campaign learning in one workspace."], "forbidden_phrases": ["revolutionary", "guaranteed results"], "sources": [{"id": uid(), "name": "Orbit product brief", "text": "Orbit connects briefs, content review, and campaign learning in one workspace. Built for small marketing teams. Humans review every asset before publication.", "source_type": "product_document"}]}
                db.add(Record(id=brand["id"], kind="brand", data=brand))
                db.commit()
        yield
        accounts.close()
        repository.close()

    app = FastAPI(title="Campaign Launchpad", lifespan=lifespan)
    app.state.repository = repository
    app.state.social_accounts = accounts
    app.state.social_publisher = publisher
    app.include_router(auth.routes())
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000"), "http://127.0.0.1:3000"], allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"], allow_credentials=True)

    from pymongo.errors import PyMongoError

    @app.exception_handler(PyMongoError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": "MongoDB operation failed. Check connectivity and use Atlas or a replica set supporting transactions. Reload before retrying."})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        messages = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})

    @app.middleware("http")
    async def origin_guard(request: Request, call_next):
        if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
            origin = request.headers.get("origin")
            allowed = {os.getenv("FRONTEND_URL", "http://localhost:3000"), "http://127.0.0.1:3000"}
            if origin and origin not in allowed:
                return JSONResponse(status_code=403, content={"detail": "Request origin is not allowed."})
        return await call_next(request)

    @app.exception_handler(AgentError)
    async def agent_error(request, exc):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(StorageError)
    async def storage_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(CapacityError)
    async def capacity_error(request, exc):
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    @app.exception_handler(SocialError)
    async def social_error(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(StaleDataError)
    async def publication_conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": "Publication state changed in another request. Reload before retrying."})

    def session(request: Request):
        user = auth.user(request)
        if request.method in {"POST", "PATCH", "DELETE"}:
            auth.limit((user["id"], "operations"), 30)
        db = repository.open(user["id"])
        try:
            yield db
        finally:
            if hasattr(db, "session"):
                db.session.close()

    def get(db, item_id, kind):
        item = db.get(Record, item_id)
        if item is None or item.kind != kind:
            raise HTTPException(404, f"{kind.title()} not found.")
        return item

    def save(db, record, data):
        record.data = deepcopy(data)
        if record.kind == "campaign":
            record.data.pop("approved_assets", None)
        try:
            db.commit()
        except StaleDataError:
            db.rollback()
            raise HTTPException(409, "State changed in another request; reload and try again.")
        return data

    def campaign_view(db, record):
        data = section_state(deepcopy(record.data))
        data["assets"] = [deepcopy(a.data) for a in db.list("asset", record.id)]
        return data

    def campaign_state(db, record):
        data = section_state(deepcopy(record.data))
        data["approved_assets"] = []
        for item in db.list("asset", record.id):
            asset = item.data
            latest = asset.get("approvals", [])[-1:]
            if (asset["status"] in {"approved", "published"} and latest and
                    latest[0]["decision"] == "approved" and latest[0]["version"] == asset["current_version"]):
                data["approved_assets"].append({"id": asset["id"], "platform": asset["platform"],
                    "asset_type": asset["asset_type"], "version": asset["current_version"],
                    "hook": asset["versions"][-1]["hook"]})
        return data

    def change_asset(db, asset_record, data, campaign_record, campaign):
        prior = asset_record.data.get("publication", {})
        if prior.get("status") == "scheduled" and data["status"] != "scheduled":
            job = db.get(Record, prior["id"])
            if job and job.data["status"] == "scheduled":
                job.data = {**job.data, "status": "cancelled", "error": "Asset revised or approval changed."}
            if data.get("publication", {}).get("id") == prior["id"]:
                data["publication"] = {**data["publication"], "status": "cancelled"}
        asset_record.data = deepcopy(data)
        save(db, campaign_record, campaign)
        return data

    def append_version(asset, content, brand, campaign, created_by="ai", evaluation=None):
        if asset.get("publication"):
            asset.setdefault("publication_history", []).append(deepcopy(asset.pop("publication")))
        version = len(asset["versions"]) + 1
        evaluation = evaluation if evaluation is not None else router.evaluate(content, brand, {**asset, "campaign_context": {k: campaign.get(k) for k in ("goal", "audience", "strategy", "selected_direction")}})
        asset["versions"].append({**content, "caption": content.get("caption", ""), "generation_prompt": asset.get("generation_prompt", ""), "timeline_item_id": asset.get("timeline_item_id"), "timeline_snapshot": deepcopy(asset.get("timeline_snapshot")), "version": version, "evaluation": evaluation, "created_by": created_by if mode == "gemini" else "demo", "generation_mode": mode, "created_at": now(), "context": {"selected_direction": campaign["selected_direction"], "strategy": deepcopy(campaign["strategy"]), "brand_voice": brand["voice"], "approved_claims": deepcopy(brand["approved_claims"])}})
        if evaluation.get("agent_run"):
            campaign.setdefault("agent_runs", []).append(evaluation["agent_run"])
        asset["current_version"] = version
        asset["status"] = "needs_review" if evaluation["passed"] else "failed"
        campaign["status"] = "review"
        trace(campaign, "evaluation_passed" if evaluation["passed"] else "evaluation_failed", f"Asset {asset['id']} v{version}: " + ("quality checks passed; human review required." if evaluation["passed"] else " ".join(evaluation["issues"])), "completed" if evaluation["passed"] else "failed")

    def asset_context(db, asset_id):
        a = get(db, asset_id, "asset")
        c = get(db, a.parent_id, "campaign")
        b = get(db, c.data["brand_id"], "brand")
        asset = deepcopy(a.data)
        if asset["status"] in {"publishing", "publish_unknown"}:
            raise HTTPException(409, "Publication is processing or its outcome needs inspection. Editing is locked to protect the approved version.")
        campaign = campaign_state(db, c)
        asset["campaign_context"] = {k: campaign.get(k) for k in ("goal", "audience", "strategy", "selected_direction")}
        return a, asset, c, campaign, b.data

    def current_version(asset, requested):
        if requested != asset["current_version"]:
            raise HTTPException(409, "This is a stale asset version. Reload and review the current version.")
        return asset["versions"][-1]

    @app.get("/health")
    def health():
        return {"status": "ok" if demo or repository.mongo else "setup-required", "mode": mode, "database": "mongodb" if repository.mongo else "sqlite-demo" if demo else "unconfigured", "authentication": not demo, "configured": demo or (repository.mongo and bool(os.getenv("GEMINI_API_KEY")))}

    @app.get("/brands")
    def brands(db: Session = Depends(session)):
        return [b.data for b in db.list("brand")]

    @app.post("/brands", status_code=201)
    def create_brand(body: BrandInput, db: Session = Depends(session)):
        data = {"id": uid(), **body.model_dump(), "sources": [], "owner_id": db.owner}
        record = Record(id=data["id"], kind="brand", data=data)
        db.add(record)
        return save(db, record, data)

    @app.delete("/brands/{brand_id}")
    def delete_brand(brand_id: str, db: Session = Depends(session)):
        b = get(db, brand_id, "brand")
        campaigns = [c for c in db.list("campaign") if c.parent_id == brand_id or c.data.get("brand_id") == brand_id]
        for c in campaigns:
            for a in db.list("asset", c.id):
                db.delete(a)
            db.delete(c)
        db.delete(b)
        db.commit()
        return {"ok": True, "id": brand_id}

    @app.patch("/brands/{brand_id}")
    def edit_brand(brand_id: str, body: BrandPatch, db: Session = Depends(session)):
        record = get(db, brand_id, "brand")
        data = deepcopy(record.data)
        data.update(body.model_dump(exclude_none=True))
        return save(db, record, data)

    def add_source(db, brand_id, body):
        record = get(db, brand_id, "brand")
        data = deepcopy(record.data)
        if len(data["sources"]) >= 100:
            raise HTTPException(400, "This local demo supports at most 100 sources per brand.")
        if sum(len(s["text"]) for s in data["sources"]) + len(body["text"]) > 750000:
            raise HTTPException(413, "Brand context exceeds the 750,000 character limit. Remove unused sources first.")
        source = {"id": uid(), **body}
        if mode == "gemini":
            source = router.ingest(source)
        data["sources"].append(source)
        return save(db, record, data)

    @app.post("/brands/{brand_id}/sources")
    def create_source(brand_id: str, body: SourceInput, db: Session = Depends(session)):
        return add_source(db, brand_id, body.model_dump())

    @app.delete("/brands/{brand_id}/sources/{source_id}")
    def delete_source(brand_id: str, source_id: str, db: Session = Depends(session)):
        b = get(db, brand_id, "brand")
        data = deepcopy(b.data)
        if not any(s["id"] == source_id for s in data["sources"]):
            raise HTTPException(404, "Source not found.")
        data["sources"] = [s for s in data["sources"] if s["id"] != source_id]
        return save(db, b, data)

    @app.get("/brands/{brand_id}/sources/{source_id}/download")
    def download_source(brand_id: str, source_id: str, db: Session = Depends(session)):
        b = get(db, brand_id, "brand")
        source = next((s for s in b.data["sources"] if s["id"] == source_id), None)
        if not source or not source.get("blob"):
            raise HTTPException(404, "Original source file not found.")
        stream = blobs.read(source["blob"], db.owner)
        def chunks():
            try:
                yield from iter(lambda: stream.read(65536), b"")
            finally:
                stream.close()
        return StreamingResponse(chunks(), media_type=source["blob"]["mime_type"], headers={"Cache-Control": "private, no-store", "Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff"})

    @app.post("/brands/{brand_id}/sources/upload")
    async def upload_source(brand_id: str, file: UploadFile = File(...), db: Session = Depends(session)):
        get(db, brand_id, "brand")
        name = PurePath((file.filename or "upload").replace("\\", "/")).name[:200]
        suffix = name.lower().rsplit(".", 1)[-1]
        allowed = {"pdf": {"application/pdf", "application/octet-stream"}, "txt": {"text/plain", "application/octet-stream"}, "md": {"text/markdown", "text/plain", "application/octet-stream"}}
        if suffix not in allowed or file.content_type not in allowed[suffix]:
            raise HTTPException(415, "Upload a PDF or UTF-8 text (.txt/.md) file.")
        raw = await file.read(MAX_UPLOAD + 1)
        await file.close()
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, "File exceeds the 5 MiB upload limit.")
        try:
            if suffix == "pdf":
                if not raw.startswith(b"%PDF-"):
                    raise ValueError("Invalid PDF signature.")
                reader = PdfReader(io.BytesIO(raw), strict=True)
                if reader.is_encrypted or len(reader.pages) > 50:
                    raise ValueError("Use an unencrypted PDF with at most 50 pages.")
                pieces = []
                for page in reader.pages:
                    pieces.append(page.extract_text() or "")
                    if sum(map(len, pieces)) > 100000:
                        raise ValueError("Extracted text exceeds 100,000 characters.")
                text = "\n".join(pieces)
            else:
                text = raw.decode("utf-8-sig")
                if "\x00" in text:
                    raise ValueError("Binary text files are unsupported.")
        except Exception as exc:
            raise HTTPException(422, "Could not read this file. Use a valid, unencrypted text PDF (up to 50 pages) or UTF-8 text.") from exc
        if not text.strip() or len(text) > 100000:
            raise HTTPException(422, "Source must contain 1–100,000 text characters. Scanned PDFs require OCR, which is not available in this demo.")
        from starlette.concurrency import run_in_threadpool
        body = {"name": name, "text": text.strip(), "source_type": "pdf" if suffix == "pdf" else "text"}
        def persist_upload():
            blob = blobs.put(raw, db.owner, name, "application/pdf" if suffix == "pdf" else "text/plain") if repository.mongo else None
            try:
                return add_source(db, brand_id, {**body, **({"blob": blob} if blob else {})})
            except Exception:
                if blob:
                    blobs.delete(blob)
                raise
        return await run_in_threadpool(persist_upload)

    @app.get("/campaigns")
    def campaigns(db: Session = Depends(session)):
        return [campaign_view(db, c) for c in db.list("campaign")]

    @app.post("/campaigns", status_code=201)
    def create_campaign(body: CampaignInput, db: Session = Depends(session)):
        get(db, body.brand_id, "brand")
        data = {"id": uid(), **body.model_dump(), "owner_id": db.owner, "generation_mode": mode, "status": "draft", "created_at": now(), "strategy": None, "selected_direction": None, "timeline": [], "trace": [], "experiments": [], "learnings": []}
        trace(data, "brief_loaded", "Campaign brief persisted in your workspace.")
        record = Record(id=data["id"], kind="campaign", parent_id=body.brand_id, data=data)
        db.add(record)
        save(db, record, data)
        return campaign_view(db, record)

    @app.get("/campaigns/{campaign_id}")
    def campaign_detail(campaign_id: str, db: Session = Depends(session)):
        return campaign_view(db, get(db, campaign_id, "campaign"))

    @app.patch("/campaigns/{campaign_id}")
    def edit_campaign(campaign_id: str, body: CampaignPatch, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        changes = body.model_dump(exclude_none=True)
        if not changes:
            raise HTTPException(422, "Provide a campaign field to edit.")
        if any(data.get(k) != v for k, v in changes.items()):
            data.setdefault("brief_history", []).append({k: data[k] for k in ("brief", "goal", "audience", "name")})
            data.update(changes)
            if data.get("strategy"):
                data.setdefault("strategy_history", []).append(deepcopy(data["strategy"]))
            data["strategy"] = None
            data["selected_direction"] = None
            data["timeline"] = []
            revise(data, "brief", "strategy", "direction", "timeline")
            trace(data, "brief_revised", "Updated brief; rebuild strategy and timeline. Existing deliverables retain their historical context.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.delete("/campaigns/{campaign_id}")
    def delete_campaign(campaign_id: str, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        deletion_guard(db, c.id)
        assets = db.list("asset", c.id)
        for a in assets:
            if a.data["status"] in {"publishing", "publish_unknown"}:
                raise HTTPException(409, "A publication is processing or needs inspection; resolve it before deleting this campaign.")
        cleanup_id = queue_media_cleanup(db, assets)
        for a in assets:
            for job in db.list("publication", a.id):
                db.delete(job)
            db.delete(a)
        db.delete(c)
        db.commit()
        if cleanup_id:
            publisher.cleanup(db.owner, cleanup_id)
        return {"ok": True, "id": campaign_id}

    @app.post("/campaigns/{campaign_id}/reviews")
    def section_review(campaign_id: str, body: SectionReviewInput, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        present = data.get("selected_direction") if body.section == "direction" else data.get(body.section)
        if not present:
            raise HTTPException(409, "Create this campaign section before reviewing it.")
        if body.revision != data["section_revisions"][body.section]:
            raise HTTPException(409, "This section changed. Reload and review its current revision.")
        if body.decision == "changes_requested" and not body.feedback.strip():
            raise HTTPException(422, "Describe the requested changes.")
        data["reviews"].append({"id": uid(), **body.model_dump(), "created_at": now(), "user_id": db.owner})
        trace(data, "section_reviewed", f"Human {body.decision} for {body.section} revision {body.revision}.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/strategy")
    def strategy(campaign_id: str, body: GenerationInput | None = None, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        brand = get(db, data["brand_id"], "brand").data
        if not any(s["source_type"] != "previous_campaign" for s in brand["sources"]):
            raise HTTPException(409, "Add a factual brand source before generating a grounded strategy.")
        if data["strategy"] and body is None:
            return campaign_view(db, c)
        guidance(data, "strategy", body)
        if data["strategy"]:
            data.setdefault("strategy_history", []).append(deepcopy(data["strategy"]))
        data["strategy"] = router.strategy(data, brand)
        data["selected_direction"] = None
        data["timeline"] = []
        revise(data, "strategy", "direction", "timeline")
        data["status"] = "planning"
        trace(data, "context_retrieved", f"Selected {len(data['strategy']['source_refs'])} sources using " + ("semantic embeddings." if mode == "gemini" else "deterministic keyword overlap.") + "")
        trace(data, "strategy_generated", f"Generated strategy and three creative directions using {mode}.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/directions")
    def directions(campaign_id: str, body: GenerationInput | None = None, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        if not data["strategy"]:
            raise HTTPException(409, "Generate a strategy before refining directions.")
        guidance(data, "direction", body)
        data.setdefault("strategy_history", []).append(deepcopy(data["strategy"]))
        brand = get(db, data["brand_id"], "brand").data
        fresh = router.directions(data, brand) if mode == "gemini" else {"creative_directions": router.strategy(data, brand)["creative_directions"]}
        data["strategy"]["creative_directions"] = fresh["creative_directions"]
        data["selected_direction"] = None
        data["timeline"] = []
        revise(data, "direction", "timeline")
        trace(data, "directions_revised", "Refined creative directions; select one and rebuild the timeline.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/direction")
    def direction(campaign_id: str, body: DirectionInput, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        if not data["strategy"] or body.direction_id not in [d["id"] for d in data["strategy"]["creative_directions"]]:
            raise HTTPException(409, "Generate a strategy and select one of its creative directions.")
        if data["selected_direction"] != body.direction_id:
            data["selected_direction"] = body.direction_id
            data["timeline"] = []
            revise(data, "direction", "timeline")
            trace(data, "direction_selected", f"Selected {body.direction_id}; future generation inherits this direction. Existing versions remain unchanged.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.patch("/campaigns/{campaign_id}/strategy")
    def edit_strategy(campaign_id: str, body: StrategyEdit, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        if not data["strategy"]:
            raise HTTPException(409, "Generate a strategy first.")
        data.setdefault("strategy_history", []).append(deepcopy(data["strategy"]))
        data["strategy"].update(body.model_dump())
        data["timeline"] = []
        revise(data, "strategy", "direction", "timeline")
        trace(data, "strategy_revised", "Saved strategy revision. Rebuild timeline; existing assets retain their versions.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.patch("/campaigns/{campaign_id}/timeline/{item_id}")
    def edit_timeline(campaign_id: str, item_id: str, body: TimelineEdit, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        item = next((i for i in data["timeline"] if i["id"] == item_id), None)
        if not item:
            raise HTTPException(404, "Timeline item not found.")
        if body.day > data["duration_days"] or body.platform not in data["platforms"] or body.asset_type not in ASSET_TYPES[body.platform] or any(i["id"] != item_id and i["day"] == body.day for i in data["timeline"]):
            raise HTTPException(422, "Use a unique campaign day and compatible campaign platform/type.")
        item.update(body.model_dump())
        data["timeline"].sort(key=lambda i: i["day"])
        revise(data, "timeline")
        trace(data, "timeline_revised", "Updated campaign schedule.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/timeline")
    def timeline(campaign_id: str, body: GenerationInput | None = None, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        if not data["selected_direction"]:
            raise HTTPException(409, "Select a creative direction before building a timeline.")
        guidance(data, "timeline", body)
        if data["timeline"]:
            data.setdefault("timeline_history", []).append(deepcopy(data["timeline"]))
        if mode == "gemini":
            data["timeline"] = router.timeline(data, get(db, data["brand_id"], "brand").data)
        else:
            stages = ["Awareness", "Education", "Trust", "Reveal", "Proof", "Objection handling", "Conversion"]
            data["timeline"] = []
            for day in range(1, data["duration_days"] + 1):
                platform = data["platforms"][(day - 1) % len(data["platforms"])]
                stage = stages[min(6, (day - 1) * 7 // data["duration_days"])]
                data["timeline"].append({"id": uid(), "day": day, "stage": stage, "platform": platform, "asset_type": DEFAULT_TYPES[platform], "objective": f"{stage}: {data['strategy']['core_message'][:120]}"})
        trace(data, "timeline_generated", f"Created {len(data['timeline'])} connected timeline items.")
        revise(data, "timeline")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/assets")
    def generate_asset(campaign_id: str, body: AssetInput, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        brand = get(db, data["brand_id"], "brand").data
        if not data["timeline"]:
            raise HTTPException(409, "Build the campaign timeline before generating assets.")
        if body.platform not in data["platforms"] or body.asset_type not in ASSET_TYPES[body.platform]:
            raise HTTPException(422, "Choose a campaign platform and a compatible asset type.")
        item = next((i for i in data["timeline"] if i["id"] == body.timeline_item_id), None) if body.timeline_item_id else next((i for i in data["timeline"] if i["platform"] == body.platform and i["asset_type"] == body.asset_type), None)
        if body.timeline_item_id and not item:
            raise HTTPException(422, "Select a timeline item belonging to this campaign.")
        if item and (item["platform"] != body.platform or item["asset_type"] != body.asset_type):
            raise HTTPException(422, "The deliverable platform and type must match the timeline item.")
        asset = {"id": uid(), "campaign_id": c.id, "platform": body.platform, "asset_type": body.asset_type, "owner_id": db.owner, "status": "draft", "current_version": 0, "versions": [], "approvals": []}
        asset.update({"timeline_item_id": item["id"] if item else None, "timeline_snapshot": deepcopy(item), "generation_prompt": body.prompt})
        guidance(data, "canvas", body)
        trace(data, "generation_started", f"{mode} generation for {body.platform} {body.asset_type}.")
        if mode == "gemini":
            result = router.generate_asset_sync(data, brand, asset)
            for draft in result["versions"]:
                append_version(asset, draft["content"], brand, data, evaluation=draft["evaluation"])
            asset["status"] = result["status"]
        else:
            content = router.content(data, brand, asset)
            if body.demonstrate_failure:
                bad = {**content, "body": "Guaranteed 10x revenue in 7 days."}
                append_version(asset, bad, brand, data)
                trace(data, "regeneration_started", "Rejected unsupported demonstration claim; replacing with source-grounded copy.")
            append_version(asset, content, brand, data)
        db.add(Record(id=asset["id"], kind="asset", parent_id=c.id, data=asset))
        save(db, c, data)
        return campaign_view(db, c)

    @app.patch("/assets/{asset_id}")
    def edit_asset(asset_id: str, body: EditInput, db: Session = Depends(session)):
        a, asset, c, campaign, brand = asset_context(db, asset_id)
        content = {**body.model_dump(exclude_none=True), "caption": body.caption if body.caption is not None else asset["versions"][-1].get("caption", ""), "source_refs": asset["versions"][-1]["source_refs"]}
        append_version(asset, content, brand, campaign, created_by="human")
        trace(campaign, "asset_revised", "Created immutable edited version; prior approval no longer authorizes this asset.")
        return change_asset(db, a, asset, c, campaign)

    @app.post("/assets/{asset_id}/regenerate")
    def regenerate(asset_id: str, body: RegenerateInput, db: Session = Depends(session)):
        a, asset, c, campaign, brand = asset_context(db, asset_id)
        asset["generation_prompt"] = body.prompt
        guidance(campaign, "canvas", body)
        if mode == "gemini":
            result = router.generate_asset_sync(campaign, brand, asset, asset["current_version"], body.section)
            for draft in result["versions"]:
                append_version(asset, draft["content"], brand, campaign, evaluation=draft["evaluation"])
            asset["status"] = result["status"]
            return change_asset(db, a, asset, c, campaign)
        generated = router.content(campaign, brand, asset, asset["current_version"])
        if body.section == "all":
            content = generated
        else:
            content = {k: deepcopy(asset["versions"][-1].get(k, "")) for k in COPY_FIELDS}
            content[body.section] = generated[body.section]
        trace(campaign, "regeneration_started", f"Regenerating {body.section} using {mode}.")
        append_version(asset, content, brand, campaign)
        return change_asset(db, a, asset, c, campaign)

    @app.post("/assets/{asset_id}/media")
    def generate_media(asset_id: str, body: MediaInput, db: Session = Depends(session)):
        a, asset, c, campaign, brand = asset_context(db, asset_id)
        version = current_version(asset, body.version)
        if mode != "gemini" or not repository.mongo:
            raise HTTPException(409, "Media generation requires Gemini and MongoDB account mode.")
        if not version["evaluation"]["passed"]:
            raise HTTPException(409, "Repair the current copy before generating media.")
        if not asset.get("timeline_item_id") or not asset.get("timeline_snapshot"):
            raise HTTPException(409, "Create a timeline-linked deliverable before generating media.")
        if body.kind == "voiceover" and asset["platform"] != "instagram":
            raise HTTPException(422, "Voiceover is available for Instagram deliverables.")
        asset["media_prompt"] = body.prompt
        asset["media_voice"] = body.voice
        raw, metadata = router.media(campaign, brand, asset, body.kind)
        blob = blobs.put(raw, db.owner, f"{asset_id}-{body.kind}", metadata["mime_type"])
        try:
            content = {k: deepcopy(version.get(k, "")) for k in COPY_FIELDS}
            prior_media = version.get("media_items") or ([version["media"]] if version.get("media") else [])
            append_version(asset, content, brand, campaign)
            latest_media = {**metadata, **blob, "generation_prompt": body.prompt, "timeline_item_id": asset["timeline_item_id"], "timeline_snapshot": deepcopy(asset["timeline_snapshot"])}
            asset["versions"][-1]["media_items"] = [deepcopy(media) for media in prior_media if media["kind"] != body.kind] + [latest_media]
            asset["versions"][-1]["media"] = latest_media
            trace(campaign, "media_generated", "Created a new version with AI media. Review the media and explicitly approve this version before publication.")
            return change_asset(db, a, asset, c, campaign)
        except Exception:
            blobs.delete(blob)
            raise

    @app.get("/assets/{asset_id}/media/{media_id}")
    def get_media(asset_id: str, media_id: str, download: bool = False, db: Session = Depends(session)):
        a = get(db, asset_id, "asset")
        metadata = next((media for v in a.data["versions"] for media in (v.get("media_items") or ([v["media"]] if v.get("media") else [])) if media.get("id") == media_id), None)
        if not metadata or not repository.mongo:
            raise HTTPException(404, "Media not found.")
        stream = blobs.read(metadata, db.owner)
        def chunks():
            try:
                yield from iter(lambda: stream.read(65536), b"")
            finally:
                stream.close()
        headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
        if download:
            headers["Content-Disposition"] = "attachment"
        return StreamingResponse(chunks(), media_type=metadata["mime_type"], headers=headers)

    def decide(asset_id, body, decision, db):
        a, asset, c, campaign, brand = asset_context(db, asset_id)
        version = current_version(asset, body.version)
        if asset["status"] == "published":
            raise HTTPException(409, "Revise the published asset before requesting a new decision.")
        if decision == "approved" and (not version["evaluation"]["passed"] or not router.evaluate(version, brand, asset)["passed"]):
            raise HTTPException(409, "The current asset must pass evaluation under current brand guardrails before approval.")
        if decision == "approved" and (version.get("media_items") or version.get("media")) and not body.media_reviewed:
            raise HTTPException(409, "Review the generated media and explicitly confirm media_reviewed before approval.")
        asset["approvals"].append({"version": body.version, "decision": decision, "feedback": body.feedback, "media_reviewed": body.media_reviewed, "created_at": now(), "user_id": db.owner})
        asset["status"] = decision
        trace(campaign, decision, f"Human decision recorded for asset {asset_id} v{body.version}.")
        return change_asset(db, a, asset, c, campaign)

    @app.post("/assets/{asset_id}/approve")
    def approve(asset_id: str, body: ApprovalInput, db: Session = Depends(session)):
        return decide(asset_id, body, "approved", db)

    @app.post("/assets/{asset_id}/reject")
    def reject(asset_id: str, body: ApprovalInput, db: Session = Depends(session)):
        return decide(asset_id, body, "rejected", db)

    @app.post("/assets/{asset_id}/request-changes")
    def request_changes(asset_id: str, body: ApprovalInput, db: Session = Depends(session)):
        return decide(asset_id, body, "changes_requested", db)

    @app.post("/assets/{asset_id}/publish")
    def publish(asset_id: str, body: PublishInput, db: Session = Depends(session)):
        if not demo:
            raise HTTPException(409, "Use connected-account publishing for live content. Local publication recording is available only in demo mode.")
        a, asset, c, campaign, brand = asset_context(db, asset_id)
        version = current_version(asset, body.version)
        approval = asset["approvals"][-1] if asset["approvals"] else None
        if asset["status"] == "published":
            return asset
        if asset["status"] != "approved" or not approval or approval["version"] != body.version or approval["decision"] != "approved" or not version["evaluation"]["passed"] or not router.evaluate(version, brand, asset)["passed"]:
            raise HTTPException(409, "Publication requires a passing, explicitly approved current version.")
        asset["status"] = "published"
        campaign["status"] = "live"
        trace(campaign, "published", f"Marked asset {asset_id} v{body.version} published locally. No social platform API was called.")
        return change_asset(db, a, asset, c, campaign)

    @app.delete("/assets/{asset_id}")
    def delete_asset(asset_id: str, db: Session = Depends(session)):
        a = get(db, asset_id, "asset")
        c = get(db, a.parent_id, "campaign")
        deletion_guard(db, c.id)
        if a.data["status"] in {"publishing", "publish_unknown"}:
            raise HTTPException(409, "Publication is processing or needs inspection; resolve it before deleting this asset.")
        cleanup_id = queue_media_cleanup(db, [a])
        for job in db.list("publication", a.id):
            db.delete(job)
        db.delete(a)
        data = deepcopy(c.data)
        removed = {e["id"] for e in data["experiments"] if e["asset_id"] == asset_id}
        data["experiments"] = [e for e in data["experiments"] if e["asset_id"] != asset_id]
        data["learnings"] = [l for l in data["learnings"] if l.get("experiment_id") not in removed]
        data["insights"] = []
        data.pop("social_sync", None)
        revise(data, "insights", "learnings")
        trace(data, "asset_deleted", f"Deleted asset {asset_id} and its related experiments. Existing social posts remain unchanged.")
        save(db, c, data)
        if cleanup_id:
            publisher.cleanup(db.owner, cleanup_id)
        return {"ok": True, "id": asset_id}

    def deletion_guard(db, campaign_id):
        if repository.mongo and repository.database.jobs.find_one({"owner_id": db.owner, "campaign_id": campaign_id, "active": True}):
            raise HTTPException(409, "Wait for the campaign agent operation to finish before deleting.")

    def queue_media_cleanup(db, assets):
        media = {}
        for asset in assets:
            for version in asset.data["versions"]:
                for item in version.get("media_items") or ([version["media"]] if version.get("media") else []):
                    if item.get("key"):
                        media[item["key"]] = deepcopy(item)
        if not media:
            return None
        key = uid()
        db.add(Record(id=key, kind="blob_cleanup", data={"id": key, "owner_id": db.owner, "status": "pending", "blobs": list(media.values())}))
        return key

    @app.post("/campaigns/{campaign_id}/experiments")
    def experiment(campaign_id: str, body: ExperimentInput, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        a = get(db, body.asset_id, "asset")
        if a.parent_id != c.id:
            raise HTTPException(422, "The asset belongs to a different campaign.")
        asset = a.data
        if asset["status"] not in {"approved", "published"}:
            raise HTTPException(409, "Approve the current asset before creating an experiment.")
        brand = get(db, data["brand_id"], "brand").data
        if not router.evaluate(asset["versions"][-1], brand, {**asset, "campaign_context": {k: data.get(k) for k in ("goal", "audience", "strategy", "selected_direction")}})["passed"]:
            raise HTTPException(409, "Asset no longer passes current brand guardrails. Revise and approve it again.")
        variants = [
            {"label": "A · Original", "hook": asset["versions"][-1]["hook"], "impressions": 2400, "clicks": 96, "conversions": 12},
            {"label": "B · Question", "hook": "What would a clearer campaign workflow look like?", "impressions": 2400, "clicks": 132, "conversions": 15},
            {"label": "C · Product", "hook": "One campaign. A clearer next step.", "impressions": 2400, "clicks": 108, "conversions": 13},
        ]
        if mode == "gemini":
            variants = [{"label": "A · Original", "hook": asset["versions"][-1]["hook"], "impressions": 0, "clicks": 0, "conversions": 0}]
            for index in (1, 2):
                result = router.generate_asset_sync(data, brand, {**deepcopy(asset), "generation_prompt": body.prompt}, index, "hook")
                draft = result["versions"][-1]
                variants.append({"label": f"{chr(65 + index)} · AI hook", "hook": draft["content"]["hook"],
                    "evaluation": draft["evaluation"], "generation_history": result["versions"],
                    "status": result["status"], "impressions": 0, "clicks": 0, "conversions": 0})
        data["experiments"].append({"id": uid(), "name": f"Hook comparison {len(data['experiments']) + 1}", "asset_id": a.id, "asset_version": asset["current_version"], "variable": body.variable, "variants": variants, "is_demo": mode == "deterministic", "status": "draft", "metrics_source": "simulated" if mode == "deterministic" else "none"})
        revise(data, "insights", "learnings")
        data["experiments"][-1]["generation_prompt"] = body.prompt
        guidance(data, "experiments", body)
        trace(data, "experiment_created", "Created comparison drafts; each variant requires its own asset review before publication. " + ("Fixed simulated metrics." if mode == "deterministic" else "No performance metrics yet."))
        save(db, c, data)
        return campaign_view(db, c)

    def analytics_data(campaign):
        totals = {p: {"platform": p, "impressions": 0, "clicks": 0, "conversions": 0} for p in campaign["platforms"]}
        assets = {a["id"]: a for a in campaign["assets"]}
        for experiment in campaign["experiments"]:
            platform = assets[experiment["asset_id"]]["platform"]
            for v in experiment["variants"]:
                for key in ("impressions", "clicks", "conversions"):
                    totals[platform][key] += v[key]
        result = {key: sum(row[key] for row in totals.values()) for key in ("impressions", "clicks", "conversions")}
        result.update({"is_demo": any(e["is_demo"] for e in campaign["experiments"]), "ctr": result["clicks"] / result["impressions"] if result["impressions"] else 0, "platforms": list(totals.values()), "observations": ["All metrics are deterministic simulated data, not real campaign performance.", "Experiment comparisons describe the fixture only; no causal or statistical conclusion is supported."]})
        if mode == "gemini":
            result["observations"] = ["No audience results yet. Import actual metrics to analyze performance." if not result["impressions"] else "Metrics were manually imported by a workspace user; no social analytics API was called."]
        from ..services.social_analytics import with_social_metrics
        return with_social_metrics(result, campaign)

    @app.get("/campaigns/{campaign_id}/analytics")
    def analytics(campaign_id: str, db: Session = Depends(session)):
        return analytics_data(campaign_view(db, get(db, campaign_id, "campaign")))

    @app.post("/campaigns/{campaign_id}/experiments/{experiment_id}/metrics")
    def import_metrics(campaign_id: str, experiment_id: str, body: MetricInput, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        exp = next((e for e in data["experiments"] if e["id"] == experiment_id), None)
        variant = next((v for v in exp["variants"] if v["label"] == body.label), None) if exp else None
        if not variant:
            raise HTTPException(404, "Experiment variant not found.")
        if body.clicks > body.impressions or body.conversions > body.clicks:
            raise HTTPException(422, "Conversions must not exceed clicks; clicks must not exceed impressions.")
        if exp["is_demo"]:
            raise HTTPException(409, "Demo experiments cannot accept real metrics. Create an experiment in AI mode.")
        exp.setdefault("metric_history", []).append({"label": body.label, "previous": {k: variant[k] for k in ("impressions", "clicks", "conversions")}, **body.model_dump(), "captured_at": now(), "user_id": db.owner})
        variant.update({k: getattr(body, k) for k in ("impressions", "clicks", "conversions")})
        exp["metrics_source"] = "manual_import"
        exp["metric_revision"] = exp.get("metric_revision", 0) + 1
        revise(data, "insights", "learnings")
        trace(data, "metrics_imported", "User imported cumulative variant metrics; source and prior snapshot recorded.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/experiments/{experiment_id}/variants/{variant_index}/asset")
    def promote_variant(campaign_id: str, experiment_id: str, variant_index: int, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        exp = next((e for e in data["experiments"] if e["id"] == experiment_id), None)
        if not exp or not 0 <= variant_index < len(exp["variants"]):
            raise HTTPException(404, "Experiment variant not found.")
        variant = exp["variants"][variant_index]
        if variant.get("review_asset_id"):
            return campaign_view(db, c)
        original = get(db, exp["asset_id"], "asset").data
        version = next(v for v in original["versions"] if v["version"] == exp["asset_version"])
        content = {k: deepcopy(version.get(k, "")) for k in COPY_FIELDS}
        content["hook"] = variant["hook"]
        asset = {"id": uid(), "campaign_id": c.id, "platform": original["platform"], "asset_type": original["asset_type"], "owner_id": db.owner, "status": "draft", "current_version": 0, "versions": [], "approvals": [], "experiment_id": experiment_id}
        asset.update({k: deepcopy(original.get(k)) for k in ("timeline_item_id", "timeline_snapshot", "generation_prompt")})
        append_version(asset, content, get(db, data["brand_id"], "brand").data, data)
        db.add(Record(id=asset["id"], kind="asset", parent_id=c.id, data=asset))
        variant["review_asset_id"] = asset["id"]
        trace(data, "variant_ready_for_review", "Created a separate evaluated asset for a hook variant; human approval is still required.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/insights")
    def insights(campaign_id: str, body: GenerationInput | None = None, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_view(db, c)
        if mode != "gemini":
            raise HTTPException(409, "AI insights require Gemini mode.")
        guidance(data, "insights", body)
        data["insights"] = router.observations(data, analytics_data(data))
        revise(data, "insights")
        data.pop("assets", None)
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/learnings")
    def learnings(campaign_id: str, body: GenerationInput | None = None, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        if not data["experiments"]:
            raise HTTPException(409, "Create an experiment before generating evidence-linked learnings.")
        guidance(data, "learnings", body)
        if body is not None and data["learnings"]:
            data.setdefault("learning_history", []).append(deepcopy(data["learnings"]))
            data["learnings"] = []
        recorded = {(l.get("experiment_id"), l.get("metric_revision", 0)) for l in data["learnings"]}
        for exp in data["experiments"]:
            if (exp["id"], exp.get("metric_revision", 0)) in recorded:
                continue
            if mode == "gemini":
                learning = router.learning(data, exp)
                data["learnings"].append({"id": uid(), "experiment_id": exp["id"], "metric_revision": exp.get("metric_revision", 0), **learning, "saved_to_brand": False})
                continue
            winner = max(exp["variants"], key=lambda v: v["clicks"] / v["impressions"])
            data["learnings"].append({"id": uid(), "experiment_id": exp["id"], "statement": f"In simulated data, {winner['label']} had the highest observed click-through rate. Validate with a real experiment.", "evidence": f"DEMO ONLY: {winner['clicks']} clicks / {winner['impressions']} impressions = {winner['clicks'] / winner['impressions']:.1%}; experiment {exp['id']}. Confidence is a demo placeholder, not statistically calibrated.", "confidence": 0.2, "saved_to_brand": False})
        trace(data, "learning_generated", "Stored evidence-linked campaign observations.")
        revise(data, "learnings")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/learnings/{learning_id}/save")
    def save_learning(campaign_id: str, learning_id: str, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = campaign_state(db, c)
        learning = next((l for l in data["learnings"] if l["id"] == learning_id), None)
        if not learning:
            raise HTTPException(404, "Learning not found.")
        if not learning["saved_to_brand"]:
            b = get(db, data["brand_id"], "brand")
            brand = deepcopy(b.data)
            if len(brand["sources"]) >= 100:
                raise HTTPException(400, "Brand source limit reached.")
            brand["sources"].append({"id": uid(), "name": f"Campaign learning: {data['name']}"[:200], "text": learning["statement"] + "\n" + learning["evidence"], "source_type": "previous_campaign"})
            b.data = brand
            learning["saved_to_brand"] = True
            trace(data, "learning_saved", "Saved campaign learning to Brand Brain; excluded from factual product claims.")
            save(db, c, data)
        return campaign_view(db, c)

    @app.get("/campaigns/{campaign_id}/trace")
    def traces(campaign_id: str, db: Session = Depends(session)):
        return get(db, campaign_id, "campaign").data["trace"]

    @app.get("/campaigns/{campaign_id}/stream")
    def stream(campaign_id: str, db: Session = Depends(session)):
        events = deepcopy(get(db, campaign_id, "campaign").data["trace"])
        def replay():
            yield ': Persisted trace replay; this is not a live job stream.\n\n'
            for event in events:
                yield f"id: {event['id']}\nevent: trace\ndata: {json.dumps(event)}\n\n"
            yield 'event: complete\ndata: {"replay":true}\n\n'
        return StreamingResponse(replay(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    from typing import Literal

    @app.get("/campaigns/{campaign_id}/export")
    def export(campaign_id: str, format: Literal["pdf", "json"] = "pdf", auth_user=Depends(auth.user), db: Session = Depends(session)):
        campaign_record = get(db, campaign_id, "campaign")
        auth.require_owner(campaign_record, auth_user)
        data = campaign_view(db, campaign_record)
        payload = {"mode": "local-demo" if demo else "authenticated", "generation": mode, "analytics": analytics_data(data), "campaign": data, "brand": get(db, data["brand_id"], "brand").data}
        if format == "json":
            return JSONResponse(payload, headers={"Content-Disposition": f'attachment; filename="campaign-{data["id"]}.json"'})
        from ..services.exports import campaign_pdf
        pdf_file = campaign_pdf(payload, blobs, auth_user["id"])
        return StreamingResponse(pdf_file, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="campaign-{data["id"]}.pdf"'})

    @app.get("/campaigns/{campaign_id}/deliverables/download")
    def download_campaign_deliverables(campaign_id: str, auth_user=Depends(auth.user), db: Session = Depends(session)):
        from ..services.exports import deliverables_zip
        campaign = get(db, campaign_id, "campaign")
        auth.require_owner(campaign, auth_user)
        data = campaign_view(db, campaign)
        zip_file = deliverables_zip(data, blobs, auth_user["id"])
        return StreamingResponse(zip_file, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="campaign-{campaign_id}-deliverables.zip"'})

    @app.get("/assets/{asset_id}/deliverables/download")
    def download_asset_deliverables(asset_id: str, auth_user=Depends(auth.user), db: Session = Depends(session)):
        from ..services.exports import deliverables_zip
        asset = get(db, asset_id, "asset")
        auth.require_owner(asset, auth_user)
        campaign_record = get(db, asset.data["campaign_id"], "campaign")
        campaign = campaign_view(db, campaign_record)
        # Filter to only this asset
        campaign["assets"] = [a for a in campaign.get("assets", []) if a["id"] == asset_id]
        zip_file = deliverables_zip(campaign, blobs, auth_user["id"])
        return StreamingResponse(zip_file, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="asset-{asset_id}-deliverables.zip"'})

    from ..workers.jobs import job_routes
    from .social_routes import social_routes
    app.include_router(social_routes(repository, auth, accounts, publisher, session, get, campaign_view, demo))
    app.include_router(job_routes(repository, auth, {"strategy": strategy, "directions": directions, "timeline": timeline, "assets": generate_asset, "insights": insights, "learnings": learnings}))
    return app


app = create_app()
