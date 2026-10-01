"""Wire-format regressions for every structured agent query, without live keys."""
import json

import httpx
import pytest

from app.core.errors import AgentError
from app.core.gemini import GeminiProvider, retry_delay
from app.core.gemini_schema import response_schema
from app.schemas.agent_outputs import (Content, Directions, Evaluation, Learning, Observations, Strategy, Timeline, VisualPlan)
from test_agents_accounts import FixtureProvider


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


@pytest.mark.parametrize("schema", [Strategy, Directions, Timeline, Content, Evaluation, Learning, Observations, VisualPlan])
def test_all_wire_schemas_remove_complex_constraints_without_mutating_validation(schema):
    original = schema.model_json_schema()
    wire = response_schema(schema)
    unsupported = {"$defs", "$ref", "minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum"}
    assert all(not unsupported.intersection(node) for node in walk(wire))
    assert wire["type"] == "object" and wire["required"]
    assert original == schema.model_json_schema()


@pytest.mark.parametrize("role,schema,payload", [
    ("strategist", Strategy, {"sources": [{"id": "source"}]}),
    ("strategist", Directions, {"sources": [{"id": "source"}]}),
    ("marketing", Timeline, {"duration_days": 3}),
    ("creative", Content, {"operation": "generate"}),
    ("creative", Content, {"operation": "repair"}),
    ("evaluator", Evaluation, {"content": {"body": "Orbit connects campaign work."}}),
    ("analytics", Learning, {}),
    ("analytics", Observations, {}),
    ("creative", VisualPlan, {}),
])
def test_each_query_sends_supported_schema_and_validates_response(monkeypatch, role, schema, payload):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    if schema is VisualPlan:
        output = {"prompt": "A campaign illustration", "alt_text": "A connected workflow"}
    else:
        output, _ = FixtureProvider().generate(role, "Fixture", payload, schema)
    def handler(request):
        body = json.loads(request.content)
        wire = body["generationConfig"]["responseJsonSchema"]
        assert all(not {"$ref", "maxItems", "maxLength"}.intersection(node) for node in walk(wire))
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert request.headers["x-goog-api-key"] == "fixture-key"
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(output)}]}}]})
    result, run = GeminiProvider(httpx.MockTransport(handler)).generate(role, "Fixture", payload, schema)
    assert result == output and run["agent_type"] == role


def test_full_timeline_bounds_still_reject_invalid_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    output = {"items": [{"day": 91, "stage": "awareness", "platform": "linkedin", "asset_type": "post", "objective": "Introduce Orbit"}]}
    provider = GeminiProvider(httpx.MockTransport(lambda request: httpx.Response(200, json={"candidates": [
        {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(output)}]}}]})))
    with pytest.raises(AgentError, match="invalid output"):
        provider.generate("marketing", "Plan a timeline", {}, Timeline)


def test_blank_role_model_uses_configured_default(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    monkeypatch.setenv("GEMINI_MODEL", "configured-model")
    monkeypatch.setenv("GEMINI_MARKETING_MODEL", "")
    output, _ = FixtureProvider().generate("marketing", "Fixture", {"duration_days": 1}, Timeline)
    def handler(request):
        assert "/models/configured-model:" in str(request.url)
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(output)}]}}]})
    GeminiProvider(httpx.MockTransport(handler)).generate("marketing", "Fixture", {}, Timeline)


def test_rate_limit_retry_honors_google_delay(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    waits = []
    monkeypatch.setattr("app.core.gemini.sleep", waits.append)
    attempts = []
    output, _ = FixtureProvider().generate("analytics", "Fixture", {}, Observations)
    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(429, json={"error": {"message": "Rate limited", "details": [
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "20.25s"}]}})
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(output)}]}}]})
    data = GeminiProvider(httpx.MockTransport(handler)).request("fixture-model", "generateContent", {})
    value = Observations.model_validate_json(data["candidates"][0]["content"]["parts"][0]["text"]).model_dump()
    assert value == output and waits == [20.25] and len(attempts) == 2


def test_daily_or_long_quota_delays_do_not_retry_early(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    monkeypatch.setattr("app.core.gemini.sleep", lambda seconds: pytest.fail("Daily quota must fail without sleep"))
    attempts = []
    def handler(request):
        attempts.append(request)
        return httpx.Response(429, json={"error": {"message": "Daily quota exhausted", "details": [
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
                {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})
    with pytest.raises(AgentError, match="daily request quota.*429"):
        GeminiProvider(httpx.MockTransport(handler)).request("fixture-model", "generateContent", {})
    assert len(attempts) == 1
    assert retry_delay(httpx.Response(429, headers={"Retry-After": "120"}, json={}), 0) is None
    assert retry_delay(httpx.Response(429, headers={"Retry-After": "4"}, json={}), 0) == 4
