"""Channel guidance reaches real agent dispatch, repair, evaluation and media plans."""
from copy import deepcopy

import pytest

from app.agents.creative import CreativeAgent
from app.agents.evaluator import EvaluatorAgent
from app.agents.runtime import AgentRuntime
from app.core.prompts import load_prompt
from app.schemas.agent_outputs import Content, Evaluation, Narration, VisualPlan
from test_agents_accounts import FixtureProvider


class RecordingProvider(FixtureProvider):
    def __init__(self):
        self.calls = []

    def generate(self, role, instructions, payload, schema):
        self.calls.append((role, instructions, deepcopy(payload)))
        return super().generate(role, instructions, payload, schema)


@pytest.mark.parametrize("platform,asset_type", [
    ("linkedin", "post"), ("instagram", "post"), ("instagram", "reel"),
    ("instagram", "carousel"), ("instagram", "story"), ("x", "post"), ("x", "thread"),
])
def test_channel_survives_draft_repair_and_evaluation(platform, asset_type, monkeypatch):
    provider = RecordingProvider()
    runtime = AgentRuntime(provider)
    source = {"id": "source", "text": "Orbit connects campaign work.", "source_type": "product_document"}
    brand = {"voice": "Clear and warm", "approved_claims": [source["text"]], "forbidden_phrases": [], "sources": [source]}
    campaign = {"id": "campaign", "trace": [], "timeline": []}
    snapshot = {"day": 2, "objective": "Introduce the workflow", "platform": platform, "asset_type": asset_type}
    asset = {"platform": platform, "asset_type": asset_type, "timeline_snapshot": snapshot,
             "generation_prompt": "Keep our warm brand voice", "versions": [], "approvals": []}
    monkeypatch.setattr(runtime, "context", lambda *_: {"sources": [source], "brand": brand})
    creative = CreativeAgent(runtime)
    draft = creative.content(campaign, brand, asset)
    repaired = creative.repair(campaign, brand, asset, draft)
    assessment = EvaluatorAgent(runtime).evaluate(repaired, brand, asset)
    assert assessment["passed"]
    marker = f"Channel guidance: {'LinkedIn' if platform == 'linkedin' else 'Instagram' if platform == 'instagram' else 'X'}."
    assert len(provider.calls) == 3
    for role, instructions, payload in provider.calls:
        assert marker in instructions
        assert payload["platform"] == platform and payload["timeline_deliverable"] == snapshot
        if role == "creative":
            assert payload["custom_instructions"] == asset["generation_prompt"]
        else:
            assert "Flag copy that reads like another platform" in instructions
    assert provider.calls[1][2]["failed_version"] == draft
    if platform == "linkedin":
        assert "Instagram reels" not in provider.calls[0][1]
    if platform == "x" and asset_type == "thread":
        assert "Only single X posts" in provider.calls[-1][1]


@pytest.mark.parametrize("schema,operation", [(Content, "repair"), (VisualPlan, "generate"), (Narration, "narration")])
def test_media_and_repair_prompts_share_channel_policy(schema, operation):
    linkedin = load_prompt("creative", {"platform": "linkedin", "asset_type": "post", "operation": operation}, schema)
    instagram = load_prompt("creative", {"platform": "instagram", "asset_type": "reel", "operation": operation}, schema)
    assert "Channel guidance: LinkedIn." in linkedin and "Channel guidance: Instagram." not in linkedin
    assert "Channel guidance: Instagram." in instagram and "Channel guidance: LinkedIn." not in instagram
    assert linkedin != instagram


def test_narration_evaluation_retains_audio_scope():
    instructions = load_prompt("evaluator", {"platform": "instagram", "narration_only": True}, Evaluation)
    assert "assess natural spoken delivery rather than written layout" in instructions
