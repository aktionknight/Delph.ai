import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    with TestClient(app) as client:
        yield client


def post(client, url, data=None):
    response = client.post(url, json=data)
    assert response.status_code in (200, 201), response.text
    return response.json()


def campaign(client):
    brand = client.get("/brands").json()[0]
    c = post(client, "/campaigns", {"brand_id": brand["id"], "name": "Launch Orbit", "brief": "Introduce Orbit to small marketing teams.", "goal": "Early signups", "audience": "Small marketing teams", "platforms": ["linkedin", "instagram", "x"], "duration_days": 14})
    return c


def planned(client):
    c = campaign(client)
    prefix = f"/campaigns/{c['id']}"
    c = post(client, prefix + "/strategy")
    post(client, prefix + "/direction", {"direction_id": c["strategy"]["creative_directions"][0]["id"]})
    return post(client, prefix + "/timeline")


def generated(client, failure=False):
    c = planned(client)
    c = post(client, f"/campaigns/{c['id']}/assets", {"platform": "linkedin", "asset_type": "post", "demonstrate_failure": failure})
    return c, c["assets"][-1]


def test_golden_path_with_repair_and_memory(client):
    c, a = generated(client, failure=True)
    assert len(a["versions"]) == 2
    assert not a["versions"][0]["evaluation"]["passed"]
    assert a["versions"][1]["evaluation"]["passed"]
    prefix = f"/assets/{a['id']}"
    assert client.post(prefix + "/publish", json={"version": 2}).status_code == 409
    post(client, prefix + "/approve", {"version": 2})
    assert post(client, prefix + "/publish", {"version": 2})["status"] == "published"
    c = post(client, f"/campaigns/{c['id']}/experiments", {"asset_id": a["id"], "variable": "hook"})
    metrics = client.get(f"/campaigns/{c['id']}/analytics").json()
    assert metrics["is_demo"] is True
    assert metrics["impressions"] == 7200
    assert metrics["clicks"] == 336
    assert metrics["ctr"] == 336 / 7200
    c = post(client, f"/campaigns/{c['id']}/learnings")
    learning = c["learnings"][0]
    assert "simulated" in learning["statement"]
    c = post(client, f"/campaigns/{c['id']}/learnings/{learning['id']}/save")
    assert c["learnings"][0]["saved_to_brand"]
    post(client, f"/campaigns/{c['id']}/learnings/{learning['id']}/save")
    brand = client.get("/brands").json()[0]
    assert len([s for s in brand["sources"] if s["source_type"] == "previous_campaign"]) == 1
    replay = client.get(f"/campaigns/{c['id']}/stream")
    assert "event: complete" in replay.text
    assert "evaluation_failed" in replay.text
    exported = client.get(f"/campaigns/{c['id']}/export").json()
    assert exported["campaign"]["assets"][0]["approvals"][0]["version"] == 2
    assert exported["generation"] == "deterministic"


def test_revision_preserves_history_and_invalidates_approval(client):
    c, a = generated(client)
    prefix = f"/assets/{a['id']}"
    original = a["versions"][0]
    post(client, prefix + "/approve", {"version": 1})
    a = post(client, prefix + "/regenerate", {"section": "cta"})
    assert a["versions"][0] == original
    assert a["versions"][1]["hook"] == original["hook"]
    assert a["versions"][1]["body"] == original["body"]
    assert a["versions"][1]["cta"] != original["cta"]
    assert a["approvals"][0]["version"] == 1
    assert a["status"] == "needs_review"
    assert client.post(prefix + "/approve", json={"version": 1}).status_code == 409
    assert client.post(prefix + "/publish", json={"version": 2}).status_code == 409
    post(client, prefix + "/approve", {"version": 2})
    post(client, prefix + "/request-changes", {"version": 2, "feedback": "Please revise CTA"})
    assert client.post(prefix + "/publish", json={"version": 2}).status_code == 409


def test_failed_edit_cannot_be_approved_and_latest_brand_rules_apply(client):
    c, a = generated(client)
    prefix = f"/assets/{a['id']}"
    response = client.patch(prefix, json={"hook": "A claim", "body": "Guaranteed 10x revenue in 7 days.", "cta": "Explore Orbit."})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert client.post(prefix + "/approve", json={"version": 2}).status_code == 409
    a = post(client, prefix + "/regenerate", {"section": "all"})
    post(client, prefix + "/approve", {"version": 3})
    response = client.patch(f"/brands/{c['brand_id']}", json={"forbidden_phrases": [a["versions"][-1]["hook"]]})
    assert response.status_code == 200
    assert client.post(prefix + "/publish", json={"version": 3}).status_code == 409
    assert client.post(f"/campaigns/{c['id']}/experiments", json={"asset_id": a["id"]}).status_code == 409


def test_prerequisites_and_cross_campaign_experiments(client):
    c = campaign(client)
    assert client.post(f"/campaigns/{c['id']}/timeline").status_code == 409
    assert client.post(f"/campaigns/{c['id']}/assets", json={"platform": "linkedin", "asset_type": "post"}).status_code == 409
    assert client.post(f"/campaigns/{c['id']}/learnings").status_code == 409
    other, asset = generated(client)
    post(client, f"/assets/{asset['id']}/approve", {"version": 1})
    assert client.post(f"/campaigns/{c['id']}/experiments", json={"asset_id": asset["id"]}).status_code == 422
    assert client.get("/campaigns/missing").status_code == 404
    assert client.post("/campaigns", json={"name": "invalid"}).status_code == 422
    assert isinstance(client.post("/campaigns", json={}).json()["detail"], str)


@pytest.mark.parametrize("platform,asset_type", [("linkedin", "post"), ("instagram", "reel"), ("x", "thread"), ("x", "post")])
def test_platform_generation_is_evaluated(client, platform, asset_type):
    c = planned(client)
    c = post(client, f"/campaigns/{c['id']}/assets", {"platform": platform, "asset_type": asset_type})
    assert c["assets"][-1]["versions"][-1]["evaluation"]["passed"]


def text_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 250 Td (Orbit keeps human review in the workflow.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_source_uploads_and_bounds(client):
    brand = client.get("/brands").json()[0]
    url = f"/brands/{brand['id']}/sources/upload"
    response = client.post(url, files={"file": ("../../guide.txt", b"Orbit helps review campaign content.", "text/plain")})
    assert response.status_code == 200
    assert response.json()["sources"][-1]["name"] == "guide.txt"
    response = client.post(url, files={"file": ("guide.pdf", text_pdf(), "application/pdf")})
    assert response.status_code == 200, response.text
    assert "human review" in response.json()["sources"][-1]["text"]
    assert client.post(url, files={"file": ("bad.pdf", b"not a pdf", "application/pdf")}).status_code == 422
    assert client.post(url, files={"file": ("bad.exe", b"test", "application/octet-stream")}).status_code == 415
    assert client.post(url, files={"file": ("big.txt", b"a" * (5 * 1024 * 1024 + 1), "text/plain")}).status_code == 413
    assert client.post(url, files={"file": ("empty.txt", b" ", "text/plain")}).status_code == 422


def test_persistence_across_app_restart(tmp_path):
    url = f"sqlite:///{(tmp_path / 'persistent.db').as_posix()}"
    with TestClient(create_app(url)) as first:
        c, asset = generated(first, True)
        post(first, f"/assets/{asset['id']}/approve", {"version": 2})
    with TestClient(create_app(url)) as second:
        restored = second.get(f"/campaigns/{c['id']}").json()
        assert restored["assets"][0]["status"] == "approved"
        assert len(restored["assets"][0]["versions"]) == 2
        assert restored["strategy"]["source_refs"]
        assert len(second.get("/brands").json()) == 1


def test_no_grounded_strategy_without_factual_source(client):
    brand = post(client, "/brands", {"name": "Empty", "description": "New brand", "voice": "Simple"})
    c = post(client, "/campaigns", {"brand_id": brand["id"], "name": "Launch", "brief": "New product launch", "goal": "Awareness", "audience": "Founders", "platforms": ["linkedin"], "duration_days": 1})
    assert client.post(f"/campaigns/{c['id']}/strategy").status_code == 409
