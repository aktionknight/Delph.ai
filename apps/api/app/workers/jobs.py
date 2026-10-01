"""Durable job status with in-process execution and reconnectable live SSE progress."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Literal

from ..agents import AgentError, progress_sink
from ..schemas import Input, AssetInput, GenerationInput, Prompt
from ..models.database import Record


class JobInput(Input):
    operation: Literal["strategy", "directions", "timeline", "assets", "insights", "learnings"]
    asset: AssetInput | None = None
    prompt: Prompt = ""


def job_routes(repository, auth, handlers):
    routes = APIRouter()

    def execute(job_id, owner, campaign_id, body):
        jobs = repository.database.jobs
        def event(role, status):
            jobs.update_one({"_id": job_id, "owner_id": owner}, {"$push": {"events": {"role": role, "status": status, "timestamp": datetime.now(timezone.utc).isoformat()}}, "$set": {"updated_at": datetime.now(timezone.utc)}})
        token = progress_sink.set(event)
        db = repository.open(owner)
        try:
            jobs.update_one({"_id": job_id}, {"$set": {"status": "running"}})
            event(body.operation, "running")
            if body.operation == "assets":
                handlers[body.operation](campaign_id, body.asset, db)
            else:
                handlers[body.operation](campaign_id, GenerationInput(prompt=body.prompt), db)
            event(body.operation, "completed")
            jobs.update_one({"_id": job_id}, {"$set": {"status": "completed", "active": False}})
        except Exception as exc:
            db.rollback()
            message = str(exc) if isinstance(exc, AgentError) else str(exc.detail) if isinstance(exc, HTTPException) else "Operation failed. Check MongoDB connectivity and retry after reloading."
            jobs.update_one({"_id": job_id}, {"$set": {"status": "failed", "error": message, "active": False}})
        finally:
            progress_sink.reset(token)

    @routes.post("/campaigns/{campaign_id}/jobs", status_code=202)
    def start(campaign_id: str, body: JobInput, request: Request, background: BackgroundTasks):
        user = auth.user(request)
        if auth.demo or not repository.mongo:
            raise HTTPException(409, "Background agents require MongoDB account mode.")
        auth.limit((user["id"], "operations"), 30)
        db = repository.open(user["id"])
        campaign = db.get(Record, campaign_id)
        if not campaign or campaign.kind != "campaign":
            raise HTTPException(404, "Campaign not found.")
        if body.operation == "assets" and not body.asset:
            raise HTTPException(422, "Asset platform and type are required.")
        from pymongo.errors import DuplicateKeyError
        job_id = str(uuid4())
        repository.database.jobs.update_many({"owner_id": user["id"], "campaign_id": campaign_id, "active": True, "updated_at": {"$lt": datetime.now(timezone.utc) - timedelta(minutes=15)}}, {"$set": {"active": False, "status": "failed", "error": "Worker stopped or timed out. Reload and retry."}})
        try:
            repository.database.jobs.insert_one({"_id": job_id, "owner_id": user["id"], "campaign_id": campaign_id, "operation": body.operation, "status": "queued", "active": True, "events": [], "updated_at": datetime.now(timezone.utc)})
        except DuplicateKeyError:
            raise HTTPException(409, "Another agent operation is running for this campaign. Wait for it to finish.")
        background.add_task(execute, job_id, user["id"], campaign_id, body)
        return {"id": job_id, "status": "queued"}

    @routes.get("/jobs/{job_id}")
    def status(job_id: str, request: Request):
        user = auth.user(request)
        if not repository.mongo:
            raise HTTPException(404, "Job not found.")
        job = repository.database.jobs.find_one({"_id": job_id, "owner_id": user["id"]})
        if not job:
            raise HTTPException(404, "Job not found.")
        # A crashed process cannot resume a job: mark abandoned after the time limit.
        if job["active"] and job["updated_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc) - timedelta(minutes=15):
            repository.database.jobs.update_one({"_id": job_id}, {"$set": {"active": False, "status": "failed", "error": "Worker stopped or timed out. Reload and retry."}})
            job.update(active=False, status="failed", error="Worker stopped or timed out. Reload and retry.")
        return {"id": job["_id"], "status": job["status"], "events": job["events"], "error": job.get("error")}

    @routes.get("/jobs/{job_id}/stream")
    def stream(job_id: str, request: Request):
        status(job_id, request)
        async def events():
            position = 0
            while not await request.is_disconnected():
                from starlette.concurrency import run_in_threadpool
                job = await run_in_threadpool(status, job_id, request)
                for index, event in enumerate(job["events"][position:], position):
                    yield f"id: {index}\nevent: progress\ndata: {json.dumps(event)}\n\n"
                position = len(job["events"])
                if job["status"] in {"completed", "failed"}:
                    yield f"event: complete\ndata: {json.dumps(job)}\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return routes
