"""Bounded offline adapter tests, no provider credentials or external requests."""
import io
from types import SimpleNamespace

import httpx
import pytest

from app.agents import AgentError
from app import providers
from app.storage import BlobStore, StorageError


def test_reranking_validates_provider_indices(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "fixture-key")
    real_client = httpx.Client
    def handler(request):
        assert request.headers["authorization"] == "Bearer fixture-key"
        return httpx.Response(200, json={"results": [{"index": 1}, {"index": 0}]})
    monkeypatch.setattr(providers.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    candidates = [{"text": "First"}, {"text": "Second"}]
    assert providers.rerank("Query", candidates)[0]["text"] == "Second"
    monkeypatch.setattr(providers.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"results": [{"index": 999}]})), **kw))
    with pytest.raises(AgentError):
        providers.rerank("Query", candidates)


def test_r2_private_storage_and_owner_check(monkeypatch):
    monkeypatch.setenv("OBJECT_STORAGE", "r2")
    monkeypatch.setenv("R2_BUCKET", "fixture-bucket")
    objects = {}
    class S3:
        def put_object(self, **kwargs):
            objects[kwargs["Key"]] = kwargs["Body"]
        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(objects[kwargs["Key"]])}
        def delete_object(self, **kwargs):
            del objects[kwargs["Key"]]
    blobs = BlobStore(None)
    monkeypatch.setattr(blobs, "client", lambda: S3())
    blob = blobs.put(b"private document", "alice", "guide.pdf", "application/pdf")
    assert blob["key"].startswith("alice/") and blob["storage"] == "r2"
    assert blobs.read(blob, "alice").read() == b"private document"
    with pytest.raises(StorageError):
        blobs.read(blob, "bob")
    blobs.delete(blob)
    assert not objects


def test_pollinations_needs_current_api_key(monkeypatch):
    monkeypatch.delenv("POLLINATIONS_API_KEY", raising=False)
    with pytest.raises(AgentError, match="requires a key"):
        providers.pollinations_image("Campaign illustration")


def test_gemini_free_only_guard_prevents_all_image_calls(monkeypatch):
    from app.agents import AgentSuite
    monkeypatch.setenv("IMAGE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_IMAGE_ALLOW_PAID", "false")
    class NoCalls:
        def generate(self, *args):
            pytest.fail("Free-only image generation must not call any model")
        def request(self, *args):
            pytest.fail("Free-only image generation must not make any image API call")
    suite = AgentSuite(NoCalls())
    with pytest.raises(AgentError, match="no free tier"):
        suite.media({}, {}, {}, "image")
