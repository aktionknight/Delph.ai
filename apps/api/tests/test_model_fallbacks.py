"""Routing regressions with mocked providers; no credentials or external calls."""
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from app.core.errors import AgentError, ProviderError
from app.core.gemini import GeminiProvider
from app.core.groq import GroqProvider, rate_limit_cooldown
from app.core.hybrid import HybridProvider
from app.core import routing


class Answer(BaseModel):
    summary: str


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    for role in ("strategist", "marketing", "creative", "evaluator", "analytics", "writer", "repair"):
        monkeypatch.delenv(f"{role.upper()}_PROVIDER", raising=False)
        for provider in ("GEMINI", "GROQ"):
            for suffix in ("MODEL", "FALLBACK_MODELS"):
                monkeypatch.delenv(f"{provider}_{role.upper()}_{suffix}", raising=False)
    for name in ("WRITER_PROVIDER", "REPAIR_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {
        "GEMINI_API_KEY": "fixture-gemini-key", "GROQ_API_KEY": "fixture-groq-key",
        "GEMINI_MODEL": "gemini-primary", "GEMINI_FALLBACK_MODELS": "gemini-secondary",
        "GROQ_CONTENT_MODEL": "groq-primary", "GROQ_EVALUATOR_MODEL": "groq-primary",
        "GROQ_FALLBACK_MODELS": "groq-secondary", "AI_FALLBACK_ENABLED": "true",
        "AI_PROVIDER_FALLBACK_ENABLED": "true", "AI_MAX_MODEL_ATTEMPTS": "7",
        "AI_MODEL_TIMEOUT_SECONDS": "45", "AI_REQUEST_TIMEOUT_SECONDS": "150",
    }.items():
        monkeypatch.setenv(name, value)


def gemini_ok(text='{"summary":"Grounded answer"}'):
    return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]})


def groq_ok(text='{"summary":"Grounded answer"}'):
    return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": text}}]})


def gemini_model(request):
    return request.url.path.rsplit("/", 1)[-1].split(":")[0]


def quota():
    return httpx.Response(429, json={"error": {"details": [{"violations": [
        {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})


@pytest.mark.parametrize("role", ["strategist", "marketing", "creative", "evaluator", "analytics"])
def test_each_role_exhausts_gemini_then_uses_groq_with_provenance(role):
    calls = []
    def gemini(request):
        calls.append(gemini_model(request))
        return quota()
    def groq(request):
        calls.append(json.loads(request.content)["model"])
        assert request.headers["authorization"] == "Bearer fixture-groq-key"
        return groq_ok()
    value, run = HybridProvider(httpx.MockTransport(gemini), httpx.MockTransport(groq)).generate(role, "Grounded reply", {}, Answer)
    assert value == {"summary": "Grounded answer"}
    assert calls == ["gemini-primary", "gemini-secondary", "groq-primary"]
    assert run["model"] == "groq-primary" and run["provider"] == "groq"
    assert [a["status"] for a in run["attempts"]] == ["failed", "failed", "completed"]
    assert "fixture-" not in json.dumps(run)


def test_daily_cooldown_skips_exhausted_model_across_roles():
    calls = []
    def handler(request):
        model = gemini_model(request)
        calls.append(model)
        return quota() if model == "gemini-primary" else gemini_ok()
    provider = GeminiProvider(httpx.MockTransport(handler))
    provider.generate("marketing", "Reply", {}, Answer)
    _, run = provider.generate("analytics", "Reply", {}, Answer)
    assert calls == ["gemini-primary", "gemini-secondary", "gemini-secondary"]
    assert run["attempts"][0]["reason"] == "cooldown"


@pytest.mark.parametrize("failure", ["rate_limit", "unavailable", "outage", "network", "invalid_response", "incomplete"])
def test_recoverable_gemini_failures_advance_immediately(monkeypatch, failure):
    monkeypatch.setattr("app.core.gemini.sleep", lambda seconds: pytest.fail("Text failover must not sleep"))
    calls = []
    def handler(request):
        calls.append(gemini_model(request))
        if len(calls) > 1:
            return gemini_ok()
        if failure == "network":
            raise httpx.ReadTimeout("Fixture timeout", request=request)
        if failure == "invalid_response":
            return gemini_ok('{"summary":null}')
        if failure == "incomplete":
            return httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS"}]})
        return httpx.Response({"rate_limit": 429, "unavailable": 404, "outage": 503}[failure], json={})
    _, run = GeminiProvider(httpx.MockTransport(handler)).generate("marketing", "Reply", {}, Answer)
    assert calls == ["gemini-primary", "gemini-secondary"]
    assert run["attempts"][0]["reason"] == ("invalid_response" if failure == "incomplete" else failure)


@pytest.mark.parametrize("failure", ["safety", "prompt_safety", "bad_request", "invalid_key"])
def test_nonrecoverable_failures_do_not_switch_model_or_vendor(failure):
    calls = []
    def handler(request):
        calls.append(request)
        if failure == "safety":
            return httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY"}]})
        if failure == "prompt_safety":
            return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
        return httpx.Response(400 if failure == "bad_request" else 401, json={})
    def no_groq(request):
        pytest.fail("Safety/configuration failures must not switch vendors")
    with pytest.raises(ProviderError) as error:
        HybridProvider(httpx.MockTransport(handler), httpx.MockTransport(no_groq)).generate("creative", "Reply", {}, Answer)
    assert not error.value.recoverable and len(calls) == 1


def test_groq_model_chain_and_reverse_provider_order(monkeypatch):
    monkeypatch.setenv("MARKETING_PROVIDER", "groq")
    calls = []
    def handler(request):
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(429) if len(calls) == 1 else groq_ok()
    _, run = HybridProvider(httpx.MockTransport(lambda request: pytest.fail("No Gemini needed")),
                          httpx.MockTransport(handler)).generate("marketing", "Reply", {}, Answer)
    assert calls == ["groq-primary", "groq-secondary"] and run["provider"] == "groq"


def test_groq_exhaustion_can_fall_back_to_gemini(monkeypatch):
    monkeypatch.setenv("CREATIVE_PROVIDER", "groq")
    _, run = HybridProvider(httpx.MockTransport(lambda request: gemini_ok()),
        httpx.MockTransport(lambda request: httpx.Response(503))).generate("creative", "Reply", {}, Answer)
    assert [a["provider"] for a in run["attempts"]] == ["groq", "groq", "gemini"]


def test_role_model_order_deduplicated_and_capped(monkeypatch):
    monkeypatch.setenv("GEMINI_MARKETING_FALLBACK_MODELS", "gemini-primary, role-next,role-next, role-last")
    assert routing.models("GEMINI", "marketing", "gemini-primary", "ignored") == ["gemini-primary", "role-next", "role-last"]
    assert routing.models("GEMINI", "analytics", "gemini-primary", "ignored") == ["gemini-primary", "gemini-secondary"]
    monkeypatch.setenv("GEMINI_MARKETING_FALLBACK_MODELS", ",".join(f"model-{i}" for i in range(20)))
    assert len(routing.models("GEMINI", "marketing", "gemini-primary", "ignored")) == 5


def test_global_attempt_cap_reserves_second_provider(monkeypatch):
    monkeypatch.setenv("AI_MAX_MODEL_ATTEMPTS", "2")
    _, run = HybridProvider(httpx.MockTransport(lambda request: quota()),
        httpx.MockTransport(lambda request: groq_ok())).generate("strategist", "Reply", {}, Answer)
    assert [(a["provider"], a["status"]) for a in run["attempts"]] == [("gemini", "failed"), ("groq", "completed")]


def test_time_budget_leaves_time_for_second_provider(monkeypatch):
    clock = [0.0]
    fake_time = SimpleNamespace(monotonic=lambda: clock[0])
    monkeypatch.setattr(routing, "time", fake_time)
    monkeypatch.setattr("app.core.hybrid.time", fake_time)
    def slow_gemini(request):
        clock[0] += request.extensions["timeout"]["read"]
        raise httpx.ReadTimeout("Fixture timeout", request=request)
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-secondary,gemini-third,gemini-fourth")
    _, run = HybridProvider(httpx.MockTransport(slow_gemini),
        httpx.MockTransport(lambda request: groq_ok())).generate("strategist", "Reply", {}, Answer)
    assert run["provider"] == "groq" and clock[0] == 105


def test_cooldown_expiry_restores_candidate(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(routing, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    pool = routing.ModelPool("gemini")
    calls = []
    def invoke(model, timeout):
        calls.append(model)
        if model == "primary" and clock[0] == 0:
            raise ProviderError("Rate limited", reason="rate_limit", cooldown=60)
        return {}, {}
    pool.run("marketing", ["primary", "secondary"], invoke)
    clock[0] = 61
    pool.run("marketing", ["primary", "secondary"], invoke)
    assert calls == ["primary", "secondary", "primary"]


def test_missing_secondary_key_is_skipped_without_fake_success(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(ProviderError) as error:
        HybridProvider(httpx.MockTransport(lambda request: quota())).generate("marketing", "Reply", {}, Answer)
    assert error.value.attempts[-1]["reason"] == "missing_key"


def test_no_keys_has_actionable_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(AgentError, match="Set GEMINI_API_KEY or GROQ_API_KEY"):
        HybridProvider().generate("marketing", "Reply", {}, Answer)


def test_fallback_can_be_disabled(monkeypatch):
    monkeypatch.setenv("AI_FALLBACK_ENABLED", "false")
    with pytest.raises(ProviderError) as error:
        HybridProvider(httpx.MockTransport(lambda request: quota())).generate("marketing", "Reply", {}, Answer)
    assert len(error.value.attempts) == 1


def test_valid_failed_evaluation_does_not_trigger_routing():
    class Assessment(BaseModel):
        passed: bool
    calls = []
    def handler(request):
        calls.append(request)
        return gemini_ok('{"passed":false}')
    value, _ = HybridProvider(httpx.MockTransport(handler)).generate("evaluator", "Evaluate", {}, Assessment)
    assert value["passed"] is False and len(calls) == 1


def test_groq_invalid_output_advances_but_content_filter_stops():
    calls = []
    def handler(request):
        calls.append(request)
        return groq_ok("invalid-json") if len(calls) == 1 else groq_ok()
    _, run = GroqProvider(httpx.MockTransport(handler)).generate("analytics", "Reply", {}, Answer)
    assert run["attempts"][0]["reason"] == "invalid_response" and len(calls) == 2
    with pytest.raises(ProviderError) as error:
        GroqProvider(httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [
            {"finish_reason": "content_filter"}]}))).generate("analytics", "Reply", {}, Answer)
    assert not error.value.recoverable


@pytest.mark.parametrize("code", ["json_validate_failed", "model_decommissioned"])
def test_groq_known_model_or_generated_json_errors_allow_fallback(code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(400, json={"error": {"code": code}}) if len(calls) == 1 else groq_ok()
    _, run = GroqProvider(httpx.MockTransport(handler)).generate("marketing", "Reply", {}, Answer)
    assert len(calls) == 2 and run["model"] == "groq-secondary"


@pytest.mark.parametrize("delay,expected", [("8.25", 8.25), ("invalid", 60), ("NaN", 60), ("0", 1), ("90000", 3600)])
def test_groq_backoff_honors_safe_retry_after(delay, expected):
    assert rate_limit_cooldown(httpx.Response(429, headers={"Retry-After": delay})) == expected
