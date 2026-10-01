"""Connected deliverable/review contracts with offline provider and Mongo fixtures."""
from copy import deepcopy
import io

import pytest
from fastapi.testclient import TestClient

from app import main
from app.agents import AgentSuite
from app.core.errors import AgentError
from test_agents_accounts import FakeRepository, FixtureProvider
from test_workflow import client, planned, post


def test_timeline_mapping_rejects_foreign_and_mismatched_items(client):
    campaign = planned(client)
    item = campaign["timeline"][0]
    url = f"/campaigns/{campaign['id']}/assets"
    assert client.post(url, json={"platform": "linkedin", "asset_type": "post", "timeline_item_id": "foreign"}).status_code == 422
    assert client.post(url, json={"platform": "instagram", "asset_type": "reel", "timeline_item_id": item["id"]}).status_code == 422
    created = post(client, url, {"platform": item["platform"], "asset_type": item["asset_type"], "timeline_item_id": item["id"], "prompt": "Use a warm opening"})
    asset = created["assets"][-1]
    assert asset["timeline_snapshot"] == item
    assert asset["versions"][-1]["timeline_item_id"] == item["id"]
    assert asset["versions"][-1]["generation_prompt"] == "Use a warm opening"
    changed = client.patch(f"/campaigns/{campaign['id']}/timeline/{item['id']}", json={**{k: v for k, v in item.items() if k != "id"}, "objective": "A new objective"}).json()
    assert changed["assets"][-1]["timeline_snapshot"] == item
    assert changed["timeline"][0]["objective"] == "A new objective"


def test_section_reviews_become_stale_and_brief_history_survives(client):
    campaign = planned(client)
    base = f"/campaigns/{campaign['id']}"
    revision = campaign["section_revisions"]["strategy"]
    review = {"section": "strategy", "revision": revision, "decision": "approved", "feedback": "Clear positioning"}
    assert post(client, base + "/reviews", review)["reviews"][-1]["revision"] == revision
    strategy = campaign["strategy"]
    edited = client.patch(base + "/strategy", json={k: strategy[k] for k in ("positioning", "core_message", "audience_summary", "content_pillars")}).json()
    assert edited["section_revisions"]["strategy"] > revision
    assert edited["reviews"][-1]["revision"] == revision
    assert client.post(base + "/reviews", json=review).status_code == 409
    response = client.patch(base, json={"brief": "Focus on the human review workflow."})
    assert response.status_code == 200, response.text
    revised = response.json()
    assert revised["strategy"] is None and revised["selected_direction"] is None and not revised["timeline"]
    assert revised["brief_history"][0]["brief"] == campaign["brief"]
    assert client.post(base + "/reviews", json={"section": "brief", "revision": revised["section_revisions"]["brief"], "decision": "changes_requested", "feedback": " "}).status_code == 422


def test_caption_is_evaluated_and_prompt_limits_are_enforced(client):
    campaign = planned(client)
    campaign = post(client, f"/campaigns/{campaign['id']}/assets", {"platform": "linkedin", "asset_type": "post"})
    asset = campaign["assets"][0]
    version = asset["versions"][-1]
    changed = client.patch(f"/assets/{asset['id']}", json={k: version[k] for k in ("hook", "body", "cta")} | {"caption": "Guaranteed 10x revenue in 7 days."})
    assert changed.status_code == 200 and changed.json()["status"] == "failed"
    assert client.post(f"/assets/{asset['id']}/approve", json={"version": 2}).status_code == 409
    assert client.post(f"/assets/{asset['id']}/regenerate", json={"prompt": "a" * 2001}).status_code == 422


class DeliverableProvider(FixtureProvider):
    def __init__(self):
        self.calls = []

    def generate(self, role, instructions, payload, schema):
        self.calls.append((role, deepcopy(payload), instructions))
        if schema.__name__ == "Narration":
            source = payload["sources"][0]["id"]
            output = {"script": "Orbit connects campaign work. Explore Orbit.", "source_refs": [source]}
            return schema.model_validate(output).model_dump(), {"id": "narration", "agent_type": role, "model": self.model, "duration_ms": 1, "created_at": "2026-10-01T00:00:00Z"}
        output, run = super().generate(role, instructions, payload, schema)
        if role == "marketing":
            output["items"] = [{**item, "platform": "instagram", "asset_type": "reel"} for item in output["items"]]
        if role == "creative":
            output["body"] = "Orbit connects campaign work."
            output["caption"] = "A clearer campaign workflow."
        return output, run


class FakeBlobs:
    def __init__(self, database):
        self.data = {}

    def put(self, raw, owner, name, mime):
        key = str(len(self.data) + 1)
        self.data[key] = raw
        return {"id": key, "key": key, "storage": "mongo", "mime_type": mime, "owner_id": owner}

    def read(self, metadata, owner):
        assert metadata["owner_id"] == owner
        return io.BytesIO(self.data[metadata["id"]])

    def delete(self, metadata):
        self.data.pop(metadata["id"], None)


@pytest.fixture
def account(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setattr(main, "Repository", FakeRepository)
    monkeypatch.setattr(main, "BlobStore", FakeBlobs)
    provider = DeliverableProvider()
    suite = AgentSuite(provider)
    with TestClient(main.create_app(agent_suite=suite)) as client:
        post(client, "/auth/register", {"email": "review@example.com", "password": "long password 123"})
        brand = post(client, "/brands", {"name": "Orbit", "description": "Campaign work", "voice": "Clear", "approved_claims": ["Orbit connects campaign work."]})
        post(client, f"/brands/{brand['id']}/sources", {"name": "Product", "text": "Orbit connects campaign work."})
        campaign = post(client, "/campaigns", {"brand_id": brand["id"], "name": "Launch", "brief": "Launch Orbit", "goal": "Awareness", "audience": "Teams", "platforms": ["instagram"], "duration_days": 2})
        base = f"/campaigns/{campaign['id']}"
        campaign = post(client, base + "/strategy", {"prompt": "Make the message practical"})
        post(client, base + "/direction", {"direction_id": campaign["strategy"]["creative_directions"][0]["id"]})
        campaign = post(client, base + "/timeline", {"prompt": "Use awareness first"})
        yield client, campaign, provider, suite


def test_agent_payloads_receive_scoped_prompts_and_timeline_context(account):
    client, campaign, provider, _ = account
    item = campaign["timeline"][0]
    campaign = post(client, f"/campaigns/{campaign['id']}/assets", {"platform": "instagram", "asset_type": "reel", "timeline_item_id": item["id"], "prompt": "Open with a question"})
    assert provider.calls[0][1]["custom_instructions"] == "Make the message practical"
    marketing = next(payload for role, payload, _ in provider.calls if role == "marketing")
    assert marketing["custom_instructions"] == "Use awareness first"
    creative = next(payload for role, payload, _ in provider.calls if role == "creative")
    assert creative["timeline_deliverable"] == item
    assert creative["custom_instructions"] == "Open with a question"
    evaluation = next(payload for role, payload, _ in provider.calls if role == "evaluator")
    assert evaluation["content"]["caption"] == "A clearer campaign workflow."
    before = campaign["strategy"]["positioning"]
    refined = post(client, f"/campaigns/{campaign['id']}/directions", {"prompt": "Show the workflow"})
    assert refined["strategy"]["positioning"] == before
    assert refined["selected_direction"] is None and not refined["timeline"]
    assert provider.calls[-1][1]["custom_instructions"] == "Show the workflow"


def test_media_coexists_and_new_copy_invalidates_both_media_and_approval(account, monkeypatch):
    client, campaign, _, suite = account
    item = campaign["timeline"][0]
    campaign = post(client, f"/campaigns/{campaign['id']}/assets", {"platform": "instagram", "asset_type": "reel", "timeline_item_id": item["id"]})
    asset = campaign["assets"][0]
    base = f"/assets/{asset['id']}"
    monkeypatch.setattr(suite, "media", lambda c, b, a, kind: (b"fixture media", {"kind": kind, "mime_type": "image/png" if kind == "image" else "audio/mpeg", "requires_human_review": True, "model": "fixture"}))
    first = post(client, base + "/media", {"version": 1, "kind": "image", "prompt": "Use warm colors"})
    second = post(client, base + "/media", {"version": 2, "kind": "voiceover", "voice": "en-US-AriaNeural"})
    latest = second["versions"][-1]
    assert {media["kind"] for media in latest["media_items"]} == {"image", "voiceover"}
    assert second["versions"][1] == first["versions"][1]
    assert client.post(base + "/approve", json={"version": 3}).status_code == 409
    approved = post(client, base + "/approve", {"version": 3, "media_reviewed": True})
    assert approved["status"] == "approved"
    for media in latest["media_items"]:
        assert client.get(base + f"/media/{media['id']}").content == b"fixture media"
    edited = client.patch(base, json={k: latest[k] for k in ("hook", "body", "cta", "caption")}).json()
    assert not edited["versions"][-1].get("media_items") and not edited["versions"][-1].get("media")
    assert edited["status"] == "needs_review"
    assert client.post(base + "/publish", json={"version": 4}).status_code == 409
    assert client.post(base + "/media", json={"version": 4, "kind": "voiceover", "voice": "arbitrary-voice"}).status_code == 422


def test_instagram_narration_is_grounded_and_uses_selected_voice(account, monkeypatch):
    client, campaign, provider, _ = account
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    recorded = []
    from app.core import providers
    monkeypatch.setattr(providers, "edge_voiceover", lambda text, voice=None: recorded.append((text, voice)) or b"fixture mp3")
    item = campaign["timeline"][0]
    campaign = post(client, f"/campaigns/{campaign['id']}/assets", {"platform": "instagram", "asset_type": "reel", "timeline_item_id": item["id"]})
    asset = campaign["assets"][0]
    created = post(client, f"/assets/{asset['id']}/media", {"version": 1, "kind": "voiceover", "voice": "en-GB-SoniaNeural", "prompt": "Warm conversational pacing"})
    assert recorded == [("Orbit connects campaign work. Explore Orbit.", "en-GB-SoniaNeural")]
    assert created["versions"][-1]["media"]["script"] == recorded[0][0]
    narration = next(payload for _, payload, instructions in provider.calls if "natural spoken narration" in instructions)
    assert narration["timeline_deliverable"]["objective"] == item["objective"]
    assert narration["custom_instructions"] == "Warm conversational pacing"


def test_edge_voice_adapter_rejects_unrecognized_service_names():
    from app.core.providers import edge_voiceover
    with pytest.raises(AgentError, match="supported Edge"):
        edge_voiceover("Campaign copy", "arbitrary-service")


def test_ungrounded_narration_does_not_call_tts_or_create_version(account, monkeypatch):
    client, campaign, provider, _ = account
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    from app.core import providers
    monkeypatch.setattr(providers, "edge_voiceover", lambda *args: pytest.fail("Failed narration must not reach TTS"))
    item = campaign["timeline"][0]
    campaign = post(client, f"/campaigns/{campaign['id']}/assets", {"platform": "instagram", "asset_type": "reel", "timeline_item_id": item["id"]})
    asset = campaign["assets"][0]
    real_generate = provider.generate
    def ungrounded(role, instructions, payload, schema):
        output, run = real_generate(role, instructions, payload, schema)
        if schema.__name__ == "Narration":
            output["script"] = "Guaranteed 10x revenue in 7 days."
        return output, run
    monkeypatch.setattr(provider, "generate", ungrounded)
    response = client.post(f"/assets/{asset['id']}/media", json={"version": 1, "kind": "voiceover"})
    assert response.status_code == 502 and "quality checks" in response.json()["detail"]
    restored = client.get(f"/campaigns/{campaign['id']}").json()["assets"][0]
    assert restored == asset


def test_experiment_prompt_scopes_to_variants_and_preserves_original(account):
    client, campaign, provider, _ = account
    item = campaign["timeline"][0]
    campaign = post(client, f"/campaigns/{campaign['id']}/assets", {"platform": "instagram", "asset_type": "reel", "timeline_item_id": item["id"], "prompt": "Original instructions"})
    asset = campaign["assets"][0]
    post(client, f"/assets/{asset['id']}/approve", {"version": 1})
    revised = post(client, f"/campaigns/{campaign['id']}/experiments", {"asset_id": asset["id"], "prompt": "Compare two concise questions"})
    assert revised["experiments"][-1]["generation_prompt"] == "Compare two concise questions"
    assert revised["assets"][0]["generation_prompt"] == "Original instructions"
    assert revised["assets"][0]["versions"] == asset["versions"]
    variants = [payload for role, payload, _ in provider.calls if role == "creative" and payload.get("revision") in (1, 2)]
    assert len(variants) == 2
    assert all(payload["custom_instructions"] == "Compare two concise questions" for payload in variants)


def test_narration_repairs_once_then_synthesizes_only_the_passing_audio(account, monkeypatch):
    client, campaign, provider, _ = account
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    from app.core import providers
    synthesized = []
    monkeypatch.setattr(providers, "edge_voiceover", lambda text, voice=None: synthesized.append(text) or b"fixture audio")
    item = campaign["timeline"][0]
    campaign = post(client, f"/campaigns/{campaign['id']}/assets", {"platform": "instagram", "asset_type": "reel", "timeline_item_id": item["id"]})
    asset = campaign["assets"][0]
    generate = provider.generate
    drafts = []
    def first_draft_bad(role, instructions, payload, schema):
        output, run = generate(role, instructions, payload, schema)
        if schema.__name__ == "Narration":
            drafts.append(deepcopy(payload))
            if len(drafts) == 1:
                output["script"] = "Guaranteed 10x revenue in 7 days."
        return output, run
    monkeypatch.setattr(provider, "generate", first_draft_bad)
    completed = post(client, f"/assets/{asset['id']}/media", {"version": 1, "kind": "voiceover"})
    history = completed["versions"][-1]["media"]["narration_history"]
    assert len(history) == 2 and not history[0]["evaluation"]["passed"] and history[1]["evaluation"]["passed"]
    assert drafts[1]["failed_narration"]["evaluation"]["issues"]
    assert synthesized == [history[1]["script"]]
    evaluations = [payload for role, payload, _ in provider.calls if role == "evaluator" and payload.get("narration_only")]
    assert len(evaluations) == 2
    assert all(payload["deliverable_kind"] == "voiceover" and payload["content"]["caption"] == "" for payload in evaluations)


def test_single_x_post_validates_full_publishable_text_and_empty_caption():
    from pydantic import ValidationError
    from app.schemas.agent_outputs import XPostContent
    content = {"hook": "H", "body": "B" * 276, "cta": "C", "source_refs": ["source"]}
    assert XPostContent.model_validate(content).caption == ""
    with pytest.raises(ValidationError, match="280"):
        XPostContent.model_validate({**content, "body": "B" * 277})
    with pytest.raises(ValidationError, match="caption must be empty"):
        XPostContent.model_validate({**content, "body": "Short", "caption": "Duplicate post"})


def test_spoken_audio_completeness_does_not_require_caption_or_storyboard():
    from app.services.generation import DeterministicRouter
    brand = {"sources": [{"id": "source", "source_type": "product_document", "text": "Orbit connects campaign work."}], "approved_claims": ["Orbit connects campaign work."], "forbidden_phrases": []}
    content = {"hook": "", "body": "Orbit connects campaign work.", "cta": "", "caption": "", "source_refs": ["source"]}
    asset = {"platform": "instagram", "asset_type": "reel", "narration_only": True}
    assert DeterministicRouter().evaluate(content, brand, asset)["passed"]
    assert not DeterministicRouter().evaluate({**content, "body": "Guaranteed 10x revenue."}, brand, asset)["passed"]


@pytest.mark.parametrize("operation", ["directions", "timeline", "assets"])
def test_background_job_preserves_prompt_and_deliverable_contract(account, operation):
    client, campaign, provider, _ = account
    instruction = "Keep this generation focused on the scheduled objective."
    body = {"operation": operation, "prompt": instruction}
    if operation == "assets":
        item = campaign["timeline"][0]
        body["asset"] = {"platform": item["platform"], "asset_type": item["asset_type"],
                         "timeline_item_id": item["id"], "prompt": instruction}
    previous = len(provider.calls)
    response = client.post(f"/campaigns/{campaign['id']}/jobs", json=body)
    assert response.status_code == 202, response.text
    job = client.get(f"/jobs/{response.json()['id']}").json()
    assert job["status"] == "completed", job
    assert any(payload.get("custom_instructions") == instruction for _, payload, _ in provider.calls[previous:])
    if operation == "assets":
        saved = client.get(f"/campaigns/{campaign['id']}").json()["assets"][-1]
        assert saved["timeline_item_id"] == item["id"] and saved["timeline_snapshot"] == item
