"""Durable version-bound publication jobs and real metric snapshots."""
from copy import deepcopy
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm.exc import StaleDataError

from ..models.database import Record
from .social import SocialError, iso, utcnow


def add_trace(campaign, event, message, status="completed"):
    campaign.setdefault("trace", []).append({"id": str(uuid4()), "event_type": event, "message": message, "status": status, "timestamp": iso()})


def approved(asset, version):
    latest = asset.get("approvals", [])[-1:]
    current = asset["versions"][-1]
    media = current.get("media_items") or ([current["media"]] if current.get("media") else [])
    return (asset["current_version"] == version and latest and latest[0]["version"] == version
            and latest[0]["decision"] == "approved" and current["evaluation"]["passed"]
            and (not media or latest[0].get("media_reviewed", False)))


def publication_parts(asset):
    version = asset["versions"][-1]
    if asset["platform"] not in {"x", "linkedin"}:
        raise SocialError("Automated publishing currently supports X and LinkedIn only.")
    if asset["platform"] == "linkedin" and asset["asset_type"] != "post":
        raise SocialError("LinkedIn automation supports posts and a single static image.")
    if asset["platform"] == "x" and asset["asset_type"] not in {"post", "thread"}:
        raise SocialError("X automation supports posts and threads.")
    text = "\n".join(version[key].strip() for key in ("hook", "body", "cta") if version[key].strip())
    if asset["platform"] == "x" and asset["asset_type"] == "thread":
        parts = [version["hook"].strip(), *[p.strip() for p in version["body"].split("\n\n") if p.strip()], version["cta"].strip()]
        parts = [p for p in parts if p]
    else:
        parts = [text]
    if not parts or len(parts) > 30 or any(len(p) > (280 if asset["platform"] == "x" else 3000) for p in parts):
        raise SocialError("Content exceeds the supported post/thread length. Revise and approve it before posting.")
    media = version.get("media_items") or ([version["media"]] if version.get("media") else [])
    if any(m["kind"] != "image" for m in media) or len(media) > 1:
        raise SocialError("Automated publishing supports at most one reviewed static image; audio/video publishing is not supported.")
    return parts, media


class SocialPublisher:
    def __init__(self, repository, accounts, router, blobs):
        self.repository, self.accounts, self.router, self.blobs = repository, accounts, router, blobs

    def require_account_mode(self):
        if not self.repository.mongo:
            raise SocialError("Automated publishing requires MongoDB and signed-in account mode.")

    def schedule(self, db, asset_record, campaign_record, brand, version, connection_id, scheduled_at):
        self.require_account_mode()
        asset = deepcopy(asset_record.data)
        if asset.get("publication", {}).get("post_ids"):
            raise SocialError("This version already has remote post receipts. Inspect its existing publication instead of posting it again.")
        if asset["status"] not in {"approved", "publish_failed"} or not approved(asset, version):
            raise SocialError("Publication requires a passing, explicitly approved current version.")
        if not self.router.evaluate(asset["versions"][-1], brand, {**asset, "campaign_context": campaign_record.data})["passed"]:
            raise SocialError("Current brand evaluation failed. Revise and approve the content again.")
        publication_parts(asset)
        connection = self.accounts.connection(db.owner, connection_id)
        if connection["brand_id"] != campaign_record.data["brand_id"] or connection["platform"] != asset["platform"]:
            raise SocialError("Choose a connected account for this brand and platform.")
        if scheduled_at.tzinfo is None:
            raise SocialError("Scheduling requires a timezone-aware date and time.")
        scheduled_at = scheduled_at.astimezone(timezone.utc)
        if scheduled_at > utcnow() + timedelta(days=366):
            raise SocialError("Schedule posts within the next year.")
        job_id = str(uuid4())
        publication = {"id": job_id, "version": version, "platform": asset["platform"], "connection_id": connection_id,
            "provider_account_id": connection["provider_account_id"], "account_name": connection["display_name"],
            "connection_generation": connection.get("generation"),
            "status": "scheduled", "scheduled_at": scheduled_at.isoformat(), "post_ids": [], "created_at": iso()}
        if asset.get("publication"):
            asset.setdefault("publication_history", []).append(deepcopy(asset["publication"]))
        asset.update(status="scheduled", publication=publication)
        job = {**deepcopy(publication), "asset_id": asset["id"], "campaign_id": campaign_record.id,
               "owner_id": db.owner, "run_at": publication["scheduled_at"], "attempts": 0}
        db.add(Record(id=job_id, kind="publication", parent_id=asset["id"], data=job))
        asset_record.data = asset
        campaign = deepcopy(campaign_record.data)
        add_trace(campaign, "publication_scheduled", f"Scheduled {asset['platform']} asset {asset['id']} v{version} for {publication['scheduled_at']}.")
        campaign_record.data = campaign
        db.commit()
        return asset

    def cancel(self, db, asset_record):
        asset = deepcopy(asset_record.data)
        publication = asset.get("publication", {})
        if asset["status"] != "scheduled":
            raise SocialError("Only a scheduled post can be cancelled; a publishing request may already be live.")
        job = db.get(Record, publication.get("id"))
        if not job or job.data["status"] != "scheduled":
            raise SocialError("Publication is already processing. Reload its status.")
        job.data = {**job.data, "status": "cancelled", "cancelled_at": iso()}
        asset["publication"] = {**publication, "status": "cancelled"}
        asset["status"] = "approved" if approved(asset, asset["current_version"]) else "needs_review"
        asset_record.data = asset
        campaign = db.get(Record, asset_record.parent_id)
        add_trace(campaign.data, "publication_cancelled", f"Cancelled scheduled asset {asset['id']}.")
        db.commit()
        return asset

    def run_job(self, owner, job_id):
        self.require_account_mode()
        db = self.repository.open(owner)
        job_record = db.get(Record, job_id)
        if not job_record or job_record.kind != "publication" or job_record.data["status"] != "scheduled" or job_record.data["run_at"] > iso():
            return
        job = deepcopy(job_record.data)
        asset_record = db.get(Record, job["asset_id"])
        campaign_record = db.get(Record, job["campaign_id"])
        if not asset_record or not campaign_record:
            return
        brand_record = db.get(Record, campaign_record.data["brand_id"])
        asset = asset_record.data
        try:
            if asset["status"] != "scheduled" or asset.get("publication", {}).get("id") != job_id or not approved(asset, job["version"]):
                job_record.data = {**job, "status": "cancelled", "error": "Asset version or approval changed."}
                db.commit()
                return
            if not self.router.evaluate(asset["versions"][-1], brand_record.data, {**asset, "campaign_context": campaign_record.data})["passed"]:
                raise SocialError("Scheduled content no longer passes current brand evaluation. Revise and approve again.")
            parts, media = publication_parts(asset)
            job.update(status="publishing", attempts=job["attempts"] + 1, started_at=iso())
            job_record.data = job
            asset_record.data = {**asset, "status": "publishing", "publication": {**asset["publication"], "status": "publishing"}}
            # Optimistic transaction claims the job and asset together before any remote write.
            db.commit()
        except StaleDataError:
            db.rollback()
            return
        except SocialError as exc:
            self.finish(owner, job_id, "publish_failed", error=str(exc))
            return
        try:
            connection, token = self.accounts.access(owner, job["connection_id"])
            if connection["provider_account_id"] != job["provider_account_id"] or connection.get("generation") != job.get("connection_generation"):
                raise SocialError("Connected account identity changed. Reconnect and reschedule.")
            image_id = job.get("image_id")
            if media and not image_id:
                stream, mime = self.blobs.read(media[0], owner), media[0]["mime_type"]
                try:
                    raw = stream.read(5 * 1024 * 1024 + 1)
                finally:
                    stream.close()
                image_id = self.accounts.upload_image(connection, token, raw, mime)
                self.progress(owner, job_id, image_id=image_id)
            post_ids = list(job.get("post_ids", []))
            for index in range(len(post_ids), len(parts)):
                post_id = self.accounts.post(connection, token, parts[index], image_id=image_id if index == 0 else None,
                    reply_id=post_ids[-1] if post_ids else None, alt_text=media[0].get("alt_text", "") if media else "")
                post_ids.append(post_id)
                # Persist each known thread result before issuing another irreversible request.
                self.progress(owner, job_id, post_ids=post_ids)
            self.finish(owner, job_id, "published", post_ids=post_ids, published_at=iso())
        except SocialError as exc:
            if exc.retry_after and job["attempts"] < 5 and not exc.uncertain:
                delay = max(exc.retry_after, min(900, 30 * 2 ** (job["attempts"] - 1)))
                self.finish(owner, job_id, "scheduled", error=str(exc), run_at=(utcnow() + timedelta(seconds=delay)).isoformat())
            else:
                saved = self.repository.open(owner).get(Record, job_id)
                partial = bool(saved and saved.data.get("post_ids"))
                self.finish(owner, job_id, "publish_unknown" if exc.uncertain or partial else "publish_failed", error=str(exc))
        except Exception:
            # A crash or persistence failure after remote acceptance must not replay writes.
            self.finish(owner, job_id, "publish_unknown", error="Publication outcome needs inspection. Check the social account before any further publication.")

    def progress(self, owner, job_id, **fields):
        db = self.repository.open(owner)
        record = db.get(Record, job_id)
        record.data = {**record.data, **fields}
        db.commit()

    def finish(self, owner, job_id, status, **fields):
        for _ in range(3):
            db = self.repository.open(owner)
            record = db.get(Record, job_id)
            if not record:
                return
            job = {**record.data, **fields, "status": status, "updated_at": iso()}
            record.data = job
            asset = db.get(Record, job["asset_id"])
            campaign = db.get(Record, job["campaign_id"])
            if asset and asset.data.get("publication", {}).get("id") == job_id and asset.data["current_version"] == job["version"]:
                asset.data = {**asset.data, "status": status, "publication": {**asset.data["publication"],
                    **{k: v for k, v in job.items() if k in {"status", "post_ids", "published_at", "error", "run_at"}}}}
                if status == "published":
                    asset.data["publication"]["url"] = ("https://x.com/i/status/" + job["post_ids"][0] if job["platform"] == "x"
                        else "https://www.linkedin.com/feed/update/" + job["post_ids"][0])
            if campaign:
                if status == "published":
                    campaign.data["status"] = "live"
                    campaign.data["social_next_sync_at"] = iso()
                add_trace(campaign.data, "social_" + status, f"{job['platform']} asset {job['asset_id']} v{job['version']}: {status}. " + fields.get("error", ""), "failed" if status.startswith("publish_") else "completed")
            try:
                db.commit()
                return
            except StaleDataError:
                db.rollback()
        raise SocialError("Publication receipt could not be saved; inspect the social account before retrying.", uncertain=True)

    def tick(self):
        self.require_account_mode()
        collection = self.repository.database.records
        # Recover abandoned claims conservatively: never replay an unknown remote write.
        cutoff = (utcnow() - timedelta(minutes=30)).isoformat()
        for doc in collection.find({"kind": "publication", "data.status": "publishing", "data.started_at": {"$lt": cutoff}}).limit(20):
            self.finish(doc["owner_id"], doc["_id"], "publish_unknown", error="Worker stopped during publication. Inspect the remote account; automatic replay is disabled.")
        for doc in collection.find({"kind": "publication", "data.status": "scheduled", "data.run_at": {"$lte": iso()}}).sort("data.run_at", 1).limit(20):
            self.run_job(doc["owner_id"], doc["_id"])
        for doc in collection.find({"kind": "blob_cleanup", "data.status": "pending"}).limit(20):
            self.cleanup(doc["owner_id"], doc["_id"])
        for doc in collection.find({"kind": "campaign", "data.social_next_sync_at": {"$lte": iso()}}).limit(10):
            db = self.repository.open(doc["owner_id"])
            campaign = db.get(Record, doc["_id"])
            try:
                self.sync_metrics(db, campaign)
            except StaleDataError:
                db.rollback()

    def cleanup(self, owner, job_id):
        db = self.repository.open(owner)
        job = db.get(Record, job_id)
        if not job or job.kind != "blob_cleanup":
            return
        pending = []
        for blob in job.data["blobs"]:
            if not blob["key"].startswith(owner + "/"):
                continue
            try:
                self.blobs.delete(blob)
            except Exception:
                pending.append(blob)
        if pending:
            job.data = {**job.data, "blobs": pending, "status": "pending"}
        else:
            db.delete(job)
        try:
            db.commit()
        except StaleDataError:
            db.rollback()

    def sync_metrics(self, db, campaign_record):
        self.require_account_mode()
        results = []
        for asset_record in db.list("asset", campaign_record.id):
            asset = deepcopy(asset_record.data)
            receipts = [*asset.get("publication_history", []), *([asset["publication"]] if asset.get("publication") else [])]
            for receipt in receipts:
                if receipt.get("status") != "published" or not receipt.get("post_ids"):
                    continue
                try:
                    connection, token = self.accounts.access(db.owner, receipt["connection_id"])
                    metrics = self.accounts.metrics(connection, token, receipt["post_ids"])
                    snapshot = {"publication_id": receipt["id"], "asset_version": receipt["version"], "platform": asset["platform"],
                        "source": "social_api", "captured_at": iso(), "post_ids": receipt["post_ids"], **metrics}
                    history = asset.setdefault("metric_history", [])
                    history.append(snapshot)
                    asset["metric_history"] = history[-200:]
                    asset.setdefault("social_metrics", {})[receipt["id"]] = snapshot
                    results.append({"asset_id": asset["id"], "publication_id": receipt["id"], "status": "synced"})
                except SocialError as exc:
                    results.append({"asset_id": asset["id"], "publication_id": receipt["id"], "status": "unavailable", "error": str(exc)})
            asset_record.data = asset
        campaign = deepcopy(campaign_record.data)
        campaign["social_sync"] = {"captured_at": iso(), "results": results}
        campaign["social_next_sync_at"] = (utcnow() + timedelta(hours=1)).isoformat()
        revisions = campaign.setdefault("section_revisions", {})
        revisions["insights"] = revisions.get("insights", 1) + 1
        campaign["insights"] = []
        if any(r["status"] == "synced" for r in results) and os.getenv("SOCIAL_AUTO_INSIGHTS", "true").lower() == "true":
            from .social_analytics import with_social_metrics
            from ..core.errors import AgentError
            view = {**campaign, "assets": [a.data for a in db.list("asset", campaign_record.id)]}
            metrics = with_social_metrics({"is_demo": False}, view)
            try:
                campaign["insights"] = self.router.observations(campaign, metrics)
                campaign.pop("social_insights_error", None)
            except AgentError:
                campaign["social_insights_error"] = "Real metrics were saved, but AI insights are unavailable. Retry Analyze with AI."
        add_trace(campaign, "social_metrics_synced", f"Fetched {sum(r['status'] == 'synced' for r in results)} real publication metric snapshots; unavailable metrics remain unknown.")
        campaign_record.data = campaign
        db.commit()
        return results
