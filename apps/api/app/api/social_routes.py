"""Private OAuth connections, approved publication and metric synchronization."""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import Field, AwareDatetime
from ..core.auth import COOKIE, digest
from ..models.database import Record
from ..schemas import Input, Short
from ..services.social import PLATFORMS, config, public_connection, SocialError, utcnow

class ConnectInput(Input):
    brand_id: Short

class ScheduleInput(Input):
    version: int = Field(ge=1)
    connection_id: Short
    scheduled_at: AwareDatetime

class SocialPublishInput(Input):
    version: int = Field(ge=1)
    connection_id: Short

def social_routes(repository, auth, accounts, publisher, session, get, campaign_view, demo):
    routes = APIRouter()
    def account(request):
        user = auth.user(request)
        if demo or user.get("demo") or not repository.mongo:
            raise HTTPException(409, "Social connections require a signed-in MongoDB workspace; demo mode cannot publish.")
        return user

    @routes.get("/connections")
    def connections(request: Request, brand_id: str | None = None):
        user = account(request)
        query = {"owner_id": user["id"]}
        if brand_id:
            get(repository.open(user["id"]), brand_id, "brand")
            query["brand_id"] = brand_id
        setup = []
        for platform in sorted(PLATFORMS):
            try:
                config(platform)
                setup.append({"platform": platform, "configured": True})
            except SocialError as exc:
                setup.append({"platform": platform, "configured": False, "reason": str(exc)})
        return {"connections": [public_connection(doc) for doc in accounts.db.connections.find(query)], "providers": setup}

    @routes.post("/connect/{platform}")
    def connect(platform: str, body: ConnectInput, request: Request, response: Response, db=Depends(session)):
        user = account(request)
        auth.limit((user["id"], "social_connect"), 10)
        get(db, body.brand_id, "brand")
        url, binding = accounts.begin(user["id"], body.brand_id, platform, digest(request.cookies.get(COOKIE, "")))
        response.set_cookie(f"social_oauth_{platform}", binding, httponly=True,
            secure=os.getenv("COOKIE_SECURE", "true").lower() == "true", samesite="lax", max_age=600, path="/")
        response.headers["Cache-Control"] = "no-store"
        return {"authorization_url": url}

    @routes.get("/connect/{platform}/callback")
    def callback(platform: str, request: Request, state: str = "", code: str = "", error: str = ""):
        if platform not in PLATFORMS or demo or not repository.mongo:
            raise HTTPException(409, "OAuth callbacks require configured account mode.")
        result = "failed"
        if state and code and not error and len(state) <= 500 and len(code) <= 4096:
            try:
                accounts.complete(platform, state, code, request.cookies.get(f"social_oauth_{platform}", ""))
                result = "connected"
            except SocialError:
                pass
        frontend_url = os.getenv("FRONTEND_URL_PRODUCTION") or os.getenv("FRONTEND_URL", "http://localhost:3000")
        response = RedirectResponse(frontend_url.rstrip("/") + f"/settings/integrations?oauth={result}&platform={platform}", status_code=303)
        response.delete_cookie(f"social_oauth_{platform}", path="/")
        response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        return response

    @routes.delete("/connections/{connection_id}")
    def disconnect(connection_id: str, request: Request):
        user = account(request)
        if not accounts.db.connections.find_one({"_id": connection_id, "owner_id": user["id"]}):
            raise HTTPException(404, "Connection not found.")
        accounts.db.connections.update_one({"_id": connection_id, "owner_id": user["id"]},
            {"$set": {"status": "disconnected"}, "$unset": {"access_token": "", "refresh_token": ""}})
        return {"disconnected": True}

    def schedule_asset(asset_id, body, request, db, scheduled_at):
        account(request)
        asset = get(db, asset_id, "asset")
        campaign = get(db, asset.parent_id, "campaign")
        brand = get(db, campaign.data["brand_id"], "brand")
        return publisher.schedule(db, asset, campaign, brand.data, body.version, body.connection_id, scheduled_at)

    @routes.post("/assets/{asset_id}/schedule")
    def schedule(asset_id: str, body: ScheduleInput, request: Request, db=Depends(session)):
        return schedule_asset(asset_id, body, request, db, body.scheduled_at)

    @routes.post("/assets/{asset_id}/social-publish")
    def publish(asset_id: str, body: SocialPublishInput, request: Request, db=Depends(session)):
        scheduled = schedule_asset(asset_id, body, request, db, utcnow())
        publisher.run_job(db.owner, scheduled["publication"]["id"])
        return repository.open(db.owner).get(Record, asset_id).data

    @routes.post("/assets/{asset_id}/cancel-publication")
    def cancel(asset_id: str, request: Request, db=Depends(session)):
        account(request)
        return publisher.cancel(db, get(db, asset_id, "asset"))

    @routes.post("/campaigns/{campaign_id}/sync-social-metrics")
    def sync(campaign_id: str, request: Request, db=Depends(session)):
        user = account(request)
        auth.limit((user["id"], "social_metrics"), 5)
        campaign = get(db, campaign_id, "campaign")
        publisher.sync_metrics(db, campaign)
        return campaign_view(db, campaign)
    return routes
