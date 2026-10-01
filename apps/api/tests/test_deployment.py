import pytest
from fastapi.testclient import TestClient

from app.core.deployment import allowed_origins
from app.main import create_app


def test_deployment_origins_accept_configured_aliases_and_normalize(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example/")
    monkeypatch.setenv("FRONTEND_URL_PRODUCTION", "https://production.example")
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://preview.example/,https://frontend.example, ")
    origins = allowed_origins()
    assert origins.count("https://frontend.example") == 1
    assert "https://production.example" in origins
    assert "https://preview.example" in origins


@pytest.mark.parametrize("origin", ["*", "https://example.com/path", "https://user:password@example.com", "https://example.com?token=1", "javascript:bad"])
def test_deployment_origins_reject_invalid_configuration(monkeypatch, origin):
    monkeypatch.setenv("ALLOWED_ORIGINS", origin)
    with pytest.raises(ValueError):
        allowed_origins()


def test_render_probes_and_vercel_origin_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setenv("FRONTEND_URL_PRODUCTION", "")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://delph-ai-beta.vercel.app")
    with TestClient(create_app(f"sqlite:///{(tmp_path / 'deployment.db').as_posix()}")) as client:
        assert client.get("/").status_code == 200
        assert client.head("/").status_code == 200
        assert client.head("/").content == b""
        assert client.get("/health").json()["status"] == "ok"
        assert client.head("/health").status_code == 200
        origin = {"Origin": "https://delph-ai-beta.vercel.app"}
        preflight = client.options("/auth/login", headers={**origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin["Origin"]
        # Invalid login inputs still reach validation rather than the origin guard.
        assert client.post("/auth/login", headers=origin, json={}).status_code == 422
        assert client.post("/auth/login", headers={"Origin": "https://untrusted.example"}, json={}).status_code == 403
