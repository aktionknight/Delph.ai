"""Offline contract tests; fake provider outputs are fixtures, not live AI evidence."""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest
from pymongo.errors import DuplicateKeyError
from sqlalchemy.orm.exc import StaleDataError

from app.agents import AgentError, AgentSuite, Content, GeminiProvider
from app.auth import Auth
from app.database import Record
from app.generation import DeterministicRouter
from app.store import MongoStore
from app import main


def matches(doc, query):
    return all((doc.get(key) > value["$gt"] if isinstance(value, dict) and "$gt" in value else doc.get(key) < value["$lt"] if isinstance(value, dict) and "$lt" in value else doc.get(key) == value) for key, value in query.items())


class Collection:
    def __init__(self):
        self.docs = {}

    def find_one(self, query):
        return next((deepcopy(d) for d in self.docs.values() if matches(d, query)), None)

    def find(self, query, projection=None):
        return [deepcopy(d) for d in self.docs.values() if matches(d, query)]

    def insert_one(self, doc, **kwargs):
        if doc["_id"] in self.docs or any(d.get("email") == doc.get("email") for d in self.docs.values() if "email" in doc):
            raise DuplicateKeyError("duplicate")
        self.docs[doc["_id"]] = deepcopy(doc)

    def replace_one(self, query, doc, **kwargs):
        previous = self.find_one(query)
        if previous:
            self.docs[previous["_id"]] = deepcopy(doc)
        return SimpleNamespace(matched_count=int(previous is not None))

    def update_one(self, query, update):
        doc = self.find_one(query)
        if doc:
            doc.update(update.get("$set", {}))
            for key, value in update.get("$push", {}).items():
                doc.setdefault(key, []).append(value)
            self.docs[doc["_id"]] = doc

    def update_many(self, query, update):
        for doc in self.find(query):
            self.update_one({"_id": doc["_id"]}, update)

    def delete_one(self, query):
        doc = self.find_one(query)
        if doc:
            del self.docs[doc["_id"]]


class FakeDatabase:
    def __init__(self):
        self.records, self.users, self.sessions = Collection(), Collection(), Collection()
        self.jobs = Collection()
        self.client = self

    @contextmanager
    def start_session(self):
        yield self

    @contextmanager
    def start_transaction(self):
        original = deepcopy(self.records.docs)
        try:
            yield self
        except Exception:
            self.records.docs = original
            raise


class FakeRepository:
    mongo = True

    def __init__(self, url=None):
        self.database = FakeDatabase()

    def initialize(self):
        pass

    def open(self, owner):
        return MongoStore(self.database, owner)

    def close(self):
        pass


def test_mongo_isolation_conflict_and_atomic_rollback():
    db = FakeDatabase()
    store = MongoStore(db, "alice")
    store.add(Record(id="brand", kind="brand", data={"name": "A"}))
    store.add(Record(id="campaign", kind="campaign", data={"name": "C"}))
    store.commit()
    assert MongoStore(db, "bob").get(Record, "brand") is None
    assert MongoStore(db, "bob").list("brand") == []
    first, stale = MongoStore(db, "alice"), MongoStore(db, "alice")
    stale.get(Record, "campaign")
    stale.get(Record, "brand").data = {"name": "stale"}
    first.get(Record, "campaign").data = {"name": "new"}
    first.commit()
    with pytest.raises(StaleDataError):
        stale.commit()
    assert db.records.docs["brand"]["data"]["name"] == "A"
    assert db.records.docs["campaign"]["data"]["name"] == "new"


def test_accounts_profile_logout_and_expiry(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    repository = FakeRepository()
    auth = Auth(repository, False)
    app = FastAPI()
    app.include_router(auth.routes())
    with TestClient(app) as client:
        assert client.get("/me").status_code == 401
        body = {"email": "person@example.com", "password": "long password 123", "name": "Person"}
        response = client.post("/auth/register", json=body)
        assert response.status_code == 201
        assert "httponly" in response.headers["set-cookie"].lower()
        user = client.get("/me").json()
        assert "password_hash" not in user and "salt" not in user
        assert repository.database.users.docs[user["id"]]["password_hash"] != body["password"]
        assert client.patch("/me", json={"name": "Updated", "company": "Example"}).status_code == 200
        assert client.get("/me").json()["name"] == "Updated"
        client.post("/auth/logout")
        assert client.get("/me").status_code == 401
        assert client.post("/auth/login", json={**body, "password": "wrong password 123"}).status_code == 401
        assert client.post("/auth/login", json=body).status_code == 200
        from datetime import datetime, timedelta, timezone
        for session in repository.database.sessions.docs.values():
            session["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert client.get("/me").status_code == 401


def test_provider_headers_structured_validation_and_no_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    def handler(request):
        assert request.headers["x-goog-api-key"] == "fixture-key"
        assert "fixture-key" not in str(request.url)
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"hook":"Good","body":"Body","cta":"Go","source_refs":["source"]}'}]}}]})
    provider = GeminiProvider(httpx.MockTransport(handler))
    output, run = provider.generate("writer", "Write", {}, Content)
    assert output["hook"] == "Good" and run["agent_type"] == "writer"
    invalid = GeminiProvider(httpx.MockTransport(lambda request: httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS"}]})))
    with pytest.raises(AgentError):
        invalid.generate("writer", "Write", {}, Content)
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(AgentError, match="GEMINI_API_KEY"):
        provider.generate("writer", "Write", {}, Content)


class FixtureProvider:
    model = "fixture-model"
    embedding_model = "fixture-embedding"

    def embed(self, text, task):
        return [1.0] + [0.0] * 767

    def generate(self, role, instructions, payload, schema):
        source = payload.get("sources", [{"id": "source"}])[0]["id"]
        if role == "strategist" and schema.__name__ == "Strategy":
            output = {"positioning": "A workspace", "core_message": "Orbit connects campaign work.", "audience_summary": "Teams", "content_pillars": ["Workflow"], "assumptions": ["Audience demand is unvalidated."], "source_refs": [source]}
        elif role == "strategist" and schema.__name__ == "Directions":
            output = {"creative_directions": [{"id": f"direction-{i}", "name": f"Direction {i}", "description": "Show workflow", "rationale": "Documented facts"} for i in range(3)]}
        elif role == "marketing":
            output = {"items": [{"day": i, "stage": "Awareness", "platform": "linkedin", "asset_type": "post", "objective": "Introduce Orbit"} for i in range(1, payload["duration_days"] + 1)]}
        elif role == "evaluator":
            passed = "unsupported" not in payload["content"]["body"].lower()
            output = {"passed": passed, "issues": [] if passed else ["Unsupported semantic claim"], "checks": {k: passed for k in ("grounding", "brand_fit", "platform_fit", "audience_fit", "claim_safety", "completeness")}}
        elif role == "creative":
            output = {"hook": "A clearer campaign", "body": "Orbit connects campaign work." if payload.get("operation") == "repair" else "Unsupported market leadership claim.", "cta": "Explore Orbit.", "source_refs": [source]}
        elif role == "analytics" and schema.__name__ == "Learning":
            output = {"statement": "No audience results yet.", "evidence": "Zero impressions recorded.", "confidence": 0.1}
        else:
            output = {"observations": ["No results yet."]}
        return schema.model_validate(output).model_dump(), {"id": role, "agent_type": role, "model": self.model, "status": "completed", "duration_ms": 1, "created_at": "2026-10-01T00:00:00Z"}


def test_authenticated_ai_workflow_repair_metrics_and_isolation(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setattr(main, "Repository", FakeRepository)
    app = main.create_app(agent_suite=AgentSuite(FixtureProvider()))
    with TestClient(app) as client:
        assert client.get("/brands").status_code == 401
        client.post("/auth/register", json={"email": "alice@example.com", "password": "long password 123"})
        brand = client.post("/brands", json={"name": "Orbit", "description": "Campaign workspace", "voice": "Clear", "approved_claims": ["Orbit connects campaign work."]}).json()
        assert client.post(f"/brands/{brand['id']}/sources", json={"name": "Product", "text": "Orbit connects campaign work."}).status_code == 200
        c = client.post("/campaigns", json={"brand_id": brand["id"], "name": "Launch", "brief": "Launch Orbit", "goal": "Awareness", "audience": "Teams", "platforms": ["linkedin"], "duration_days": 3}).json()
        prefix = f"/campaigns/{c['id']}"
        job = client.post(prefix + "/jobs", json={"operation": "strategy"})
        assert job.status_code == 202, job.text
        job_id = job.json()["id"]
        assert client.get(f"/jobs/{job_id}").json()["status"] == "completed"
        assert "event: progress" in client.get(f"/jobs/{job_id}/stream").text
        c = client.get(prefix).json()
        client.post(prefix + "/direction", json={"direction_id": c["strategy"]["creative_directions"][0]["id"]})
        client.post(prefix + "/timeline")
        c = client.post(prefix + "/assets", json={"platform": "linkedin", "asset_type": "post"}).json()
        asset = c["assets"][0]
        assert len(asset["versions"]) == 2
        assert not asset["versions"][0]["evaluation"]["passed"]
        assert asset["versions"][1]["evaluation"]["passed"]
        assert client.post(f"/assets/{asset['id']}/approve", json={"version": 2}).status_code == 200
        c = client.post(prefix + "/experiments", json={"asset_id": asset["id"]}).json()
        exp = c["experiments"][0]
        assert not exp["is_demo"] and all(v["impressions"] == 0 for v in exp["variants"])
        url = prefix + f"/experiments/{exp['id']}/metrics"
        assert client.post(url, json={"label": exp["variants"][0]["label"], "impressions": 100, "clicks": 10, "conversions": 2, "source": "Platform report"}).status_code == 200
        assert client.get(prefix + "/analytics").json()["clicks"] == 10
        assert client.post(prefix + "/insights").status_code == 200
        assert client.post(prefix + "/learnings").status_code == 200
        promoted = client.post(prefix + f"/experiments/{exp['id']}/variants/0/asset").json()
        promoted_asset = next(a for a in promoted["assets"] if a.get("experiment_id") == exp["id"])
        assert promoted_asset["approvals"] == []
        assert client.post(f"/assets/{promoted_asset['id']}/publish", json={"version": 1}).status_code == 409
        assert client.post(prefix + f"/experiments/{exp['id']}/variants/0/asset").json()["assets"] == promoted["assets"]
        assert client.post(prefix + "/assets", json={"platform": "linkedin", "asset_type": "post"}, headers={"Origin": "https://evil.example"}).status_code == 403
        client.post("/auth/logout")
        client.post("/auth/register", json={"email": "bob@example.com", "password": "long password 123"})
        assert client.get(prefix).status_code == 404
        assert client.get("/brands").json() == []
        assert client.post(f"/assets/{asset['id']}/approve", json={"version": 2}).status_code == 404
        assert client.get(f"/jobs/{job_id}").status_code == 404


def test_groq_routing_and_validation(monkeypatch):
    from app.providers import GroqProvider, HybridProvider
    monkeypatch.setenv("GROQ_API_KEY", "fixture-groq")
    def handler(request):
        assert request.headers["authorization"] == "Bearer fixture-groq"
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"hook":"Good","body":"Copy","cta":"Go","source_refs":["s"]}'}}], "usage": {"total_tokens": 10}})
    output, run = GroqProvider(httpx.MockTransport(handler)).generate("writer", "Write", {}, Content)
    assert output["hook"] == "Good" and run["provider"] == "groq"
    monkeypatch.setenv("WRITER_PROVIDER", "groq")
    hybrid = HybridProvider()
    hybrid.groq = GroqProvider(httpx.MockTransport(handler))
    assert hybrid.generate("writer", "Write", {}, Content)[1]["provider"] == "groq"
    invalid = GroqProvider(httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{}'}}]})))
    with pytest.raises(AgentError, match="invalid structured"):
        invalid.generate("writer", "Write", {}, Content)


def test_media_revision_requires_explicit_review(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setattr(main, "Repository", FakeRepository)
    class FakeBlobs:
        def __init__(self, db):
            pass
        def put(self, raw, owner, name, mime):
            return {"id": "media", "key": owner + "/media", "storage": "mongo", "mime_type": mime}
        def delete(self, blob):
            pass
    monkeypatch.setattr(main, "BlobStore", FakeBlobs)
    suite = AgentSuite(FixtureProvider())
    suite.media = lambda *args: (b"fixture", {"kind": "image", "mime_type": "image/png", "alt_text": "Campaign", "model": "fixture"})
    with TestClient(main.create_app(agent_suite=suite)) as client:
        client.post("/auth/register", json={"email": "media@example.com", "password": "long password 123"})
        b = client.post("/brands", json={"name": "Orbit", "description": "Workspace", "voice": "Clear", "approved_claims": ["Orbit connects campaign work."]}).json()
        client.post(f"/brands/{b['id']}/sources", json={"name": "Source", "text": "Orbit connects campaign work."})
        c = client.post("/campaigns", json={"brand_id": b["id"], "name": "Launch", "brief": "Launch Orbit", "goal": "Awareness", "audience": "Teams", "platforms": ["linkedin"], "duration_days": 1}).json()
        prefix = f"/campaigns/{c['id']}"
        c = client.post(prefix + "/strategy").json()
        client.post(prefix + "/direction", json={"direction_id": c["strategy"]["creative_directions"][0]["id"]})
        client.post(prefix + "/timeline")
        c = client.post(prefix + "/assets", json={"platform": "linkedin", "asset_type": "post"}).json()
        asset = c["assets"][0]
        url = f"/assets/{asset['id']}"
        client.post(url + "/approve", json={"version": 2})
        revised = client.post(url + "/media", json={"version": 2, "kind": "image"}).json()
        assert revised["current_version"] == 3 and revised["status"] == "needs_review"
        assert revised["approvals"][0]["version"] == 2
        assert client.post(url + "/approve", json={"version": 3}).status_code == 409
        assert client.post(url + "/approve", json={"version": 3, "media_reviewed": True}).status_code == 200
