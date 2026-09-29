"""Campaign Launchpad local demo API. Bind to loopback; this is not authentication."""
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import PurePath
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from .database import Record, make_engine, make_sessions
from .generation import ASSET_TYPES, DEFAULT_TYPES, DeterministicRouter
from .schemas import (ApprovalInput, AssetInput, BrandInput, BrandPatch, CampaignInput,
                      DirectionInput, EditInput, ExperimentInput, PublishInput,
                      RegenerateInput, SourceInput)

MAX_UPLOAD = 5 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid4())


def trace(campaign, event, message, status="completed"):
    campaign["trace"].append({"id": uid(), "event_type": event, "message": message, "status": status, "timestamp": now()})


def create_app(database_url=None):
    engine = make_engine(database_url)
    sessions = make_sessions(engine)
    router = DeterministicRouter()

    @asynccontextmanager
    async def lifespan(app):
        with sessions() as db:
            if not db.scalar(select(Record).where(Record.kind == "brand")):
                brand = {"id": uid(), "name": "Orbit", "description": "A campaign workspace for small marketing teams.", "voice": "Clear, practical, warm. Avoid hype.", "approved_claims": ["Orbit connects briefs, content review, and campaign learning in one workspace."], "forbidden_phrases": ["revolutionary", "guaranteed results"], "sources": [{"id": uid(), "name": "Orbit product brief", "text": "Orbit connects briefs, content review, and campaign learning in one workspace. Built for small marketing teams. Humans review every asset before publication.", "source_type": "product_document"}]}
                db.add(Record(id=brand["id"], kind="brand", data=brand))
                db.commit()
        yield
        engine.dispose()

    app = FastAPI(title="Campaign Launchpad — local demo", lifespan=lifespan)
    app.state.sessions = sessions
    app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000"), "http://127.0.0.1:3000"], allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        messages = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})

    def session():
        with sessions() as db:
            yield db

    def get(db, item_id, kind):
        item = db.get(Record, item_id)
        if item is None or item.kind != kind:
            raise HTTPException(404, f"{kind.title()} not found.")
        return item

    def save(db, record, data):
        record.data = deepcopy(data)
        try:
            db.commit()
        except StaleDataError:
            db.rollback()
            raise HTTPException(409, "State changed in another request; reload and try again.")
        return data

    def campaign_view(db, record):
        data = deepcopy(record.data)
        data["assets"] = [deepcopy(a.data) for a in db.scalars(select(Record).where(Record.kind == "asset", Record.parent_id == record.id))]
        return data

    def change_asset(db, asset_record, data, campaign_record, campaign):
        asset_record.data = deepcopy(data)
        save(db, campaign_record, campaign)
        return data

    def append_version(asset, content, brand, campaign):
        version = len(asset["versions"]) + 1
        evaluation = router.evaluate(content, brand, asset)
        asset["versions"].append({**content, "version": version, "evaluation": evaluation, "created_at": now()})
        asset["current_version"] = version
        asset["status"] = "needs_review" if evaluation["passed"] else "failed"
        campaign["status"] = "review"
        trace(campaign, "evaluation_passed" if evaluation["passed"] else "evaluation_failed", f"Asset {asset['id']} v{version}: " + ("rule checks passed; human review required." if evaluation["passed"] else " ".join(evaluation["issues"])), "completed" if evaluation["passed"] else "failed")

    def asset_context(db, asset_id):
        a = get(db, asset_id, "asset")
        c = get(db, a.parent_id, "campaign")
        b = get(db, c.data["brand_id"], "brand")
        return a, deepcopy(a.data), c, deepcopy(c.data), b.data

    def current_version(asset, requested):
        if requested != asset["current_version"]:
            raise HTTPException(409, "This is a stale asset version. Reload and review the current version.")
        return asset["versions"][-1]

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "local-demo; deterministic generation; simulated analytics; no authentication"}

    @app.get("/brands")
    def brands(db: Session = Depends(session)):
        return [b.data for b in db.scalars(select(Record).where(Record.kind == "brand"))]

    @app.post("/brands", status_code=201)
    def create_brand(body: BrandInput, db: Session = Depends(session)):
        data = {"id": uid(), **body.model_dump(), "sources": []}
        record = Record(id=data["id"], kind="brand", data=data)
        db.add(record)
        return save(db, record, data)

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
        data["sources"].append({"id": uid(), **body})
        return save(db, record, data)

    @app.post("/brands/{brand_id}/sources")
    def create_source(brand_id: str, body: SourceInput, db: Session = Depends(session)):
        return add_source(db, brand_id, body.model_dump())

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
        return add_source(db, brand_id, {"name": name, "text": text.strip(), "source_type": "pdf" if suffix == "pdf" else "text"})

    @app.get("/campaigns")
    def campaigns(db: Session = Depends(session)):
        return [campaign_view(db, c) for c in db.scalars(select(Record).where(Record.kind == "campaign"))]

    @app.post("/campaigns", status_code=201)
    def create_campaign(body: CampaignInput, db: Session = Depends(session)):
        get(db, body.brand_id, "brand")
        data = {"id": uid(), **body.model_dump(), "status": "draft", "created_at": now(), "strategy": None, "selected_direction": None, "timeline": [], "trace": [], "experiments": [], "learnings": []}
        trace(data, "brief_loaded", "Campaign brief persisted in the local demo workspace.")
        record = Record(id=data["id"], kind="campaign", parent_id=body.brand_id, data=data)
        db.add(record)
        save(db, record, data)
        return campaign_view(db, record)

    @app.get("/campaigns/{campaign_id}")
    def campaign_detail(campaign_id: str, db: Session = Depends(session)):
        return campaign_view(db, get(db, campaign_id, "campaign"))

    @app.post("/campaigns/{campaign_id}/strategy")
    def strategy(campaign_id: str, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = deepcopy(c.data)
        brand = get(db, data["brand_id"], "brand").data
        if not any(s["source_type"] != "previous_campaign" for s in brand["sources"]):
            raise HTTPException(409, "Add a factual brand source before generating a grounded strategy.")
        if data["strategy"]:
            return campaign_view(db, c)
        data["strategy"] = router.strategy(data, brand)
        data["status"] = "planning"
        trace(data, "context_retrieved", f"Selected {len(data['strategy']['source_refs'])} sources using deterministic keyword overlap.")
        trace(data, "strategy_generated", "Generated strategy and three creative directions using deterministic demo templates.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/direction")
    def direction(campaign_id: str, body: DirectionInput, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = deepcopy(c.data)
        if not data["strategy"] or body.direction_id not in [d["id"] for d in data["strategy"]["creative_directions"]]:
            raise HTTPException(409, "Generate a strategy and select one of its creative directions.")
        if data["selected_direction"] != body.direction_id:
            data["selected_direction"] = body.direction_id
            data["timeline"] = []
            trace(data, "direction_selected", f"Selected {body.direction_id}; future generation inherits this direction. Existing versions remain unchanged.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/timeline")
    def timeline(campaign_id: str, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = deepcopy(c.data)
        if not data["selected_direction"]:
            raise HTTPException(409, "Select a creative direction before building a timeline.")
        stages = ["Awareness", "Education", "Trust", "Reveal", "Proof", "Objection handling", "Conversion"]
        data["timeline"] = []
        for day in range(1, data["duration_days"] + 1):
            platform = data["platforms"][(day - 1) % len(data["platforms"])]
            stage = stages[min(6, (day - 1) * 7 // data["duration_days"])]
            data["timeline"].append({"id": uid(), "day": day, "stage": stage, "platform": platform, "asset_type": DEFAULT_TYPES[platform], "objective": f"{stage}: {data['strategy']['core_message'][:120]}"})
        trace(data, "timeline_generated", f"Created {len(data['timeline'])} connected timeline items.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/assets")
    def generate_asset(campaign_id: str, body: AssetInput, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = deepcopy(c.data)
        brand = get(db, data["brand_id"], "brand").data
        if not data["timeline"]:
            raise HTTPException(409, "Build the campaign timeline before generating assets.")
        if body.platform not in data["platforms"] or body.asset_type not in ASSET_TYPES[body.platform]:
            raise HTTPException(422, "Choose a campaign platform and a compatible asset type.")
        asset = {"id": uid(), "campaign_id": c.id, "platform": body.platform, "asset_type": body.asset_type, "status": "draft", "current_version": 0, "versions": [], "approvals": []}
        content = router.content(data, brand, asset)
        trace(data, "generation_started", f"Deterministic demo generation for {body.platform} {body.asset_type}.")
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
        content = {**body.model_dump(), "source_refs": asset["versions"][-1]["source_refs"]}
        append_version(asset, content, brand, campaign)
        trace(campaign, "asset_revised", "Created immutable edited version; prior approval no longer authorizes this asset.")
        return change_asset(db, a, asset, c, campaign)

    @app.post("/assets/{asset_id}/regenerate")
    def regenerate(asset_id: str, body: RegenerateInput, db: Session = Depends(session)):
        a, asset, c, campaign, brand = asset_context(db, asset_id)
        generated = router.content(campaign, brand, asset, asset["current_version"])
        if body.section == "all":
            content = generated
        else:
            content = {k: deepcopy(asset["versions"][-1][k]) for k in ("hook", "body", "cta", "source_refs")}
            content[body.section] = generated[body.section]
        trace(campaign, "regeneration_started", f"Regenerating {body.section} using deterministic demo templates.")
        append_version(asset, content, brand, campaign)
        return change_asset(db, a, asset, c, campaign)

    def decide(asset_id, body, decision, db):
        a, asset, c, campaign, brand = asset_context(db, asset_id)
        version = current_version(asset, body.version)
        if asset["status"] == "published":
            raise HTTPException(409, "Revise the published asset before requesting a new decision.")
        if decision == "approved" and (not version["evaluation"]["passed"] or not router.evaluate(version, brand, asset)["passed"]):
            raise HTTPException(409, "The current asset must pass evaluation under current brand guardrails before approval.")
        asset["approvals"].append({"version": body.version, "decision": decision, "feedback": body.feedback, "created_at": now()})
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

    @app.post("/campaigns/{campaign_id}/experiments")
    def experiment(campaign_id: str, body: ExperimentInput, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = deepcopy(c.data)
        a = get(db, body.asset_id, "asset")
        if a.parent_id != c.id:
            raise HTTPException(422, "The asset belongs to a different campaign.")
        asset = a.data
        if asset["status"] not in {"approved", "published"}:
            raise HTTPException(409, "Approve the current asset before generating a simulated experiment.")
        brand = get(db, data["brand_id"], "brand").data
        if not router.evaluate(asset["versions"][-1], brand, asset)["passed"]:
            raise HTTPException(409, "Asset no longer passes current brand guardrails. Revise and approve it again.")
        variants = [
            {"label": "A · Original", "hook": asset["versions"][-1]["hook"], "impressions": 2400, "clicks": 96, "conversions": 12},
            {"label": "B · Question", "hook": "What would a clearer campaign workflow look like?", "impressions": 2400, "clicks": 132, "conversions": 15},
            {"label": "C · Product", "hook": "One campaign. A clearer next step.", "impressions": 2400, "clicks": 108, "conversions": 13},
        ]
        data["experiments"].append({"id": uid(), "name": f"Hook comparison {len(data['experiments']) + 1}", "asset_id": a.id, "asset_version": asset["current_version"], "variable": body.variable, "variants": variants, "is_demo": True})
        trace(data, "experiment_created", "Created three unreviewed simulated hook variants with fixed demonstration metrics. These comparison drafts are not approved or published.")
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
        result.update({"is_demo": True, "ctr": result["clicks"] / result["impressions"] if result["impressions"] else 0, "platforms": list(totals.values()), "observations": ["All metrics are deterministic simulated data, not real campaign performance.", "Experiment comparisons describe the fixture only; no causal or statistical conclusion is supported."]})
        return result

    @app.get("/campaigns/{campaign_id}/analytics")
    def analytics(campaign_id: str, db: Session = Depends(session)):
        return analytics_data(campaign_view(db, get(db, campaign_id, "campaign")))

    @app.post("/campaigns/{campaign_id}/learnings")
    def learnings(campaign_id: str, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = deepcopy(c.data)
        if not data["experiments"]:
            raise HTTPException(409, "Create a simulated experiment before generating evidence-based demo learnings.")
        recorded = {l.get("experiment_id") for l in data["learnings"]}
        for exp in data["experiments"]:
            if exp["id"] in recorded:
                continue
            winner = max(exp["variants"], key=lambda v: v["clicks"] / v["impressions"])
            data["learnings"].append({"id": uid(), "experiment_id": exp["id"], "statement": f"In simulated data, {winner['label']} had the highest observed click-through rate. Validate with a real experiment.", "evidence": f"DEMO ONLY: {winner['clicks']} clicks / {winner['impressions']} impressions = {winner['clicks'] / winner['impressions']:.1%}; experiment {exp['id']}. Confidence is a demo placeholder, not statistically calibrated.", "confidence": 0.2, "saved_to_brand": False})
        trace(data, "learning_generated", "Stored evidence-bounded simulated observations; no production performance inference.")
        save(db, c, data)
        return campaign_view(db, c)

    @app.post("/campaigns/{campaign_id}/learnings/{learning_id}/save")
    def save_learning(campaign_id: str, learning_id: str, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        data = deepcopy(c.data)
        learning = next((l for l in data["learnings"] if l["id"] == learning_id), None)
        if not learning:
            raise HTTPException(404, "Learning not found.")
        if not learning["saved_to_brand"]:
            b = get(db, data["brand_id"], "brand")
            brand = deepcopy(b.data)
            if len(brand["sources"]) >= 100:
                raise HTTPException(400, "Brand source limit reached.")
            brand["sources"].append({"id": uid(), "name": f"Demo learning: {data['name']}"[:200], "text": learning["statement"] + "\n" + learning["evidence"], "source_type": "previous_campaign"})
            b.data = brand
            learning["saved_to_brand"] = True
            trace(data, "learning_saved", "Saved simulated learning to Brand Brain; excluded from factual grounding.")
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

    @app.get("/campaigns/{campaign_id}/export")
    def export(campaign_id: str, db: Session = Depends(session)):
        data = campaign_view(db, get(db, campaign_id, "campaign"))
        return JSONResponse({"mode": "local-demo", "generation": "deterministic", "analytics": analytics_data(data), "campaign": data, "brand": get(db, data["brand_id"], "brand").data}, headers={"Content-Disposition": f'attachment; filename="campaign-{data["id"]}.json"'})

    return app


app = create_app()
