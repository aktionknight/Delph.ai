"""Graph routing and blueprint contracts, using offline model fixtures."""
import asyncio
from copy import deepcopy

import pytest

from app.core.errors import AgentError
from app.core.events import progress_sink
from app.services.orchestrator import CampaignOrchestrator
from test_agents_accounts import FixtureProvider


def inputs():
    brand = {"id": "brand", "name": "Orbit", "description": "Workspace", "voice": "Clear",
             "approved_claims": ["Orbit connects campaign work."], "forbidden_phrases": [],
             "sources": [{"id": "source", "name": "Guide", "text": "Orbit connects campaign work.", "source_type": "product_document"}]}
    campaign = {"id": "campaign", "brand_id": "brand", "brief": "Launch Orbit", "goal": "Awareness",
                "audience": "Marketing teams", "platforms": ["linkedin"], "duration_days": 3,
                "strategy": None, "selected_direction": None, "timeline": [], "trace": [], "agent_runs": [],
                "approved_assets": [{"id": "approved", "version": 2, "hook": "Keep this copy"}]}
    asset = {"id": "asset", "campaign_id": "campaign", "platform": "linkedin", "asset_type": "post", "versions": [], "approvals": []}
    return campaign, brand, asset


class RecordingProvider(FixtureProvider):
    def __init__(self, always_fail=False, broken=False):
        self.calls = []
        self.always_fail = always_fail
        self.broken = broken

    def generate(self, role, instructions, payload, schema):
        self.calls.append((role, deepcopy(payload), instructions))
        if self.broken and payload.get("operation") == "repair":
            raise AgentError("Fixture unavailable")
        output, run = super().generate(role, instructions, payload, schema)
        if self.always_fail and role == "evaluator":
            output.update(passed=False, issues=["Needs human review"], checks={k: False for k in output["checks"]})
        return output, run


def test_strategy_ownership_external_prompts_and_shared_state():
    provider = RecordingProvider()
    suite = CampaignOrchestrator(provider)
    campaign, brand, _ = inputs()
    output = asyncio.run(suite.build_campaign_strategy(campaign, brand))
    assert len(output["creative_directions"]) == 3
    assert [role for role, _, _ in provider.calls] == ["strategist", "strategist"]
    state = provider.calls[0][1]["campaign_state"]
    assert set(state) == {"campaign_id", "goal", "audience", "strategy", "creative_direction", "timeline", "approved_assets", "brand_id", "campaign_context"}
    assert state["audience"] == campaign["audience"]
    assert state["approved_assets"][0]["version"] == 2
    assert "Failure conditions:" in provider.calls[0][2]
    assert "three distinct" in provider.calls[1][2]
    assert provider.calls[1][1]["campaign_state"]["strategy"]["core_message"] == output["core_message"]
    assert "creative_directions" in suite.graphs["strategy"].get_graph().nodes


def test_asset_graph_order_repairs_and_review_boundary():
    provider = RecordingProvider()
    suite = CampaignOrchestrator(provider)
    campaign, brand, asset = inputs()
    events = []
    token = progress_sink.set(lambda name, status: events.append((name, status)))
    try:
        result = suite.generate_asset_sync(campaign, brand, asset)
    finally:
        progress_sink.reset(token)
    assert [role for role, _, _ in provider.calls] == ["creative", "evaluator", "creative", "evaluator"]
    assert result["status"] == "needs_review" and result["retries"] == 1
    assert len(result["versions"]) == 2
    assert not result["versions"][0]["evaluation"]["passed"]
    assert result["versions"][1]["evaluation"]["passed"]
    completed = [name for name, status in events if status == "completed"]
    assert completed.index("asset_version_staged") < completed.index("evaluation_completed")
    assert completed[-1] == "approval_requested"
    assert asset["versions"] == [] and asset["approvals"] == []
    assert provider.calls[1][1]["campaign_state"]["audience"] == campaign["audience"]
    assert "human_review" in suite.graphs["asset"].get_graph().nodes


def test_retry_exhaustion_stops_at_two_and_cannot_approve():
    provider = RecordingProvider(always_fail=True)
    suite = CampaignOrchestrator(provider)
    campaign, brand, asset = inputs()
    result = asyncio.run(suite.generate_asset(campaign, brand, asset))
    assert result["status"] == "needs_human_review"
    assert result["retries"] == 2 and len(result["versions"]) == 3
    assert sum(payload.get("operation") == "repair" for _, payload, _ in provider.calls) == 2
    assert all(not item["evaluation"]["passed"] for item in result["versions"])
    assert asset["approvals"] == []


def test_provider_failure_preserves_caller_state():
    suite = CampaignOrchestrator(RecordingProvider(broken=True))
    campaign, brand, asset = inputs()
    before = deepcopy((campaign, brand, asset))
    with pytest.raises(AgentError, match="Fixture unavailable"):
        suite.generate_asset_sync(campaign, brand, asset)
    assert (campaign, brand, asset) == before


def test_partial_revision_preserves_other_copy_and_approval_history():
    suite = CampaignOrchestrator(RecordingProvider())
    campaign, brand, asset = inputs()
    asset["versions"] = [{"hook": "Keep this hook", "body": "Orbit connects campaign work.", "cta": "Old CTA",
                          "source_refs": ["source"], "version": 2}]
    asset["approvals"] = [{"version": 2, "decision": "approved"}]
    before = deepcopy(asset)
    result = suite.generate_asset_sync(campaign, brand, asset, revision=3, section="cta")
    assert result["status"] == "needs_review"
    for item in result["versions"]:
        assert item["content"]["hook"] == before["versions"][-1]["hook"]
        assert item["content"]["body"] == before["versions"][-1]["body"]
        assert item["content"]["source_refs"] == ["source"]
    assert asset == before


def test_analytics_owns_learnings_and_observations():
    provider = RecordingProvider()
    suite = CampaignOrchestrator(provider)
    campaign, _, _ = inputs()
    suite.learning(campaign, {"impressions": 0})
    suite.observations(campaign, {"impressions": 0})
    assert [role for role, _, _ in provider.calls] == ["analytics", "analytics"]
    assert all(payload["campaign_state"]["goal"] == "Awareness" for _, payload, _ in provider.calls)


def test_missing_quality_dimensions_fail_closed():
    class Incomplete(RecordingProvider):
        def generate(self, role, instructions, payload, schema):
            output, run = super().generate(role, instructions, payload, schema)
            if role == "evaluator":
                output["checks"].pop("audience_fit")
            return output, run
    suite = CampaignOrchestrator(Incomplete())
    campaign, brand, asset = inputs()
    content = {"hook": "Workflow", "body": "Orbit connects campaign work.", "cta": "Explore", "source_refs": ["source"]}
    result = asyncio.run(suite.evaluate_asset(campaign, brand, asset, content))
    assert not result["passed"]
    assert "Evaluator omitted required quality checks." in result["issues"]


def test_exhausted_graph_persists_versions_but_approval_and_publication_fail(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_agents_accounts import FakeRepository
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setattr(main, "Repository", FakeRepository)
    with TestClient(main.create_app(agent_suite=CampaignOrchestrator(RecordingProvider(always_fail=True)))) as client:
        client.post("/auth/register", json={"email": "review@example.com", "password": "long fixture password 123"})
        brand = client.post("/brands", json={"name": "Orbit", "description": "Workspace", "voice": "Clear",
                                            "approved_claims": ["Orbit connects campaign work."]}).json()
        client.post(f"/brands/{brand['id']}/sources", json={"name": "Guide", "text": "Orbit connects campaign work."})
        campaign = client.post("/campaigns", json={"brand_id": brand["id"], "name": "Launch", "brief": "Launch Orbit",
            "goal": "Awareness", "audience": "Teams", "platforms": ["linkedin"], "duration_days": 3}).json()
        prefix = f"/campaigns/{campaign['id']}"
        strategy = client.post(prefix + "/strategy").json()["strategy"]
        client.post(prefix + "/direction", json={"direction_id": strategy["creative_directions"][0]["id"]})
        client.post(prefix + "/timeline")
        response = client.post(prefix + "/assets", json={"platform": "linkedin", "asset_type": "post"})
        assert response.status_code == 200, response.text
        asset = response.json()["assets"][0]
        assert asset["status"] == "needs_human_review" and asset["current_version"] == 3
        persisted = client.get(prefix).json()["assets"][0]
        assert persisted["versions"] == asset["versions"]
        assert client.post(f"/assets/{asset['id']}/approve", json={"version": 3}).status_code == 409
        assert client.post(f"/assets/{asset['id']}/publish", json={"version": 3}).status_code == 409
        assert client.get(prefix).json()["assets"][0]["approvals"] == []
