"""Native image wire format, credential reuse and safe ordered failover."""
import base64
import json

import httpx
import pytest

from app.core.errors import ProviderError
from app.core.gemini import GeminiProvider
from app.core.gemini_images import generate_image, DEFAULT_IMAGE_MODEL
from app.core.routing import ModelPool

PNG = b"\x89PNG\r\n\x1a\nfixture image"


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    monkeypatch.setenv("AI_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("GEMINI_IMAGE_FALLBACK_MODELS", "gemini-3.1-flash-lite-image")


def image_response(parts=None):
    return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": parts or [
        {"text": "Generated static"}, {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(PNG).decode()}}]}}]})


def test_image_request_reuses_gemini_key_and_selected_model():
    def handler(request):
        assert request.headers["x-goog-api-key"] == "fixture-key"
        assert request.url.path.endswith("/gemini-2.5-flash-image:generateContent")
        body = json.loads(request.content)
        assert body["generationConfig"] == {"responseModalities": ["TEXT", "IMAGE"]}
        assert body["contents"][0]["parts"][0]["text"] == "Grounded campaign static"
        return image_response()
    raw, metadata = generate_image(GeminiProvider(httpx.MockTransport(handler)), ModelPool("gemini"),
                                  DEFAULT_IMAGE_MODEL, "Grounded campaign static", "Campaign illustration")
    assert raw == PNG and metadata["model"] == DEFAULT_IMAGE_MODEL
    assert metadata["requires_human_review"] and "fixture-key" not in json.dumps(metadata)


@pytest.mark.parametrize("failure", ["shutdown", "quota", "invalid_image"])
def test_native_image_fallback_records_actual_model(failure):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if len(calls) == 1:
            if failure == "invalid_image":
                return image_response([{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"not png").decode()}}])
            return httpx.Response(404 if failure == "shutdown" else 429, json={})
        return image_response()
    _, metadata = generate_image(GeminiProvider(httpx.MockTransport(handler)), ModelPool("gemini"),
                                 DEFAULT_IMAGE_MODEL, "Grounded static", "Static")
    assert len(calls) == 2 and "gemini-3.1-flash-lite-image" in calls[1]
    assert metadata["model"] == "gemini-3.1-flash-lite-image"
    assert [a["status"] for a in metadata["attempts"]] == ["failed", "completed"]


def test_image_safety_block_stops_without_model_switch():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"candidates": [{"finishReason": "IMAGE_SAFETY"}]})
    with pytest.raises(ProviderError) as error:
        generate_image(GeminiProvider(httpx.MockTransport(handler)), ModelPool("gemini"), DEFAULT_IMAGE_MODEL, "Static", "Static")
    assert not error.value.recoverable and len(calls) == 1


def test_image_chain_never_uses_configured_text_fallbacks(monkeypatch):
    monkeypatch.delenv("GEMINI_IMAGE_FALLBACK_MODELS")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-text-model")
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(404, json={}) if len(calls) == 1 else image_response()
    generate_image(GeminiProvider(httpx.MockTransport(handler)), ModelPool("gemini"), DEFAULT_IMAGE_MODEL, "Static", "Static")
    assert len(calls) == 2 and "gemini-text-model" not in " ".join(calls)
