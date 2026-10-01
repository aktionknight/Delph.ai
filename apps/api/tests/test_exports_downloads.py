"""Download contracts with deterministic content and offline account/media fixtures."""
from copy import deepcopy
import io
import json
from pathlib import PurePosixPath
from zipfile import ZipFile

from pypdf import PdfReader

from app.services.storage import StorageError
from test_deliverables_reviews import account, FakeBlobs
from test_workflow import client, generated, planned, post


def pdf_text(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")
    assert "attachment" in response.headers["content-disposition"]
    assert ".pdf" in response.headers["content-disposition"]
    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


def archive(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    assert "attachment" in response.headers["content-disposition"]
    assert ".zip" in response.headers["content-disposition"]
    zipped = ZipFile(io.BytesIO(response.content))
    assert zipped.testzip() is None
    names = zipped.namelist()
    assert len(names) == len(set(names)), "No files may overwrite another deliverable"
    for name in names:
        assert not PurePosixPath(name).is_absolute()
        assert ".." not in PurePosixPath(name).parts
        assert "\\" not in name and ":" not in name
    manifest = json.loads(zipped.read("manifest.json"))
    assert manifest["schema_version"] == 1
    assert manifest["scope"] == "current_versions"
    for group in manifest["groups"]:
        for asset in group["assets"]:
            for file in asset["files"]:
                assert file["path"] in names
                assert file["path"].startswith(asset["folder"] + "/")
    return zipped, manifest


def entries(manifest):
    return [asset for group in manifest["groups"] for asset in group["assets"]]


def create_account_asset(client, campaign):
    item = campaign["timeline"][0]
    campaign = post(client, f"/campaigns/{campaign['id']}/assets", {
        "platform": item["platform"], "asset_type": item["asset_type"],
        "timeline_item_id": item["id"],
    })
    return campaign["assets"][-1]


def add_media(client, suite, monkeypatch, asset, *, kind, raw, script=None):
    metadata = {"kind": kind, "mime_type": "image/png" if kind == "image" else "audio/mpeg",
                "requires_human_review": True, "model": "fixture"}
    if script:
        metadata["script"] = script
    monkeypatch.setattr(suite, "media", lambda *args: (raw, metadata))
    return post(client, f"/assets/{asset['id']}/media", {"version": asset["current_version"], "kind": kind})


def test_pdf_is_default_complete_and_read_only_with_legacy_json(client):
    campaign, asset = generated(client, failure=True)
    base = f"/campaigns/{campaign['id']}"
    post(client, f"/assets/{asset['id']}/approve", {"version": 2, "feedback": "Approved launch wording"})
    post(client, f"/assets/{asset['id']}/publish", {"version": 2})
    post(client, base + "/experiments", {"asset_id": asset["id"], "variable": "hook"})
    campaign = post(client, base + "/learnings")
    before = deepcopy(client.get(base).json())
    brand_before = deepcopy(client.get("/brands").json())
    text = pdf_text(client.get(base + "/export"))
    normalized = " ".join(text.split())
    for value in (campaign["name"], campaign["brief"], campaign["goal"], campaign["audience"],
                  campaign["strategy"]["positioning"], "Approved launch wording",
                  "Guaranteed 10x revenue in 7 days.", asset["versions"][-1]["hook"]):
        assert " ".join(value.split()) in normalized
    for section in ("brand", "strategy", "direction", "timeline", "asset", "approval", "experiment", "analytics", "learning", "trace"):
        assert section in text.lower()
    assert "deterministic" in text.lower() and "simulated" in text.lower()
    legacy = client.get(base + "/export?format=json")
    assert legacy.status_code == 200
    assert legacy.headers["content-type"].startswith("application/json")
    assert legacy.json()["campaign"] == before
    assert legacy.json()["generation"] == "deterministic"
    assert client.get(base).json() == before
    assert client.get("/brands").json() == brand_before
    assert client.get(base + "/export?format=exe").status_code == 422


def test_pdf_keeps_unicode_and_long_copy_without_truncating(client):
    campaign, asset = generated(client)
    unicode_copy = 'Café naïve — “launch” Ω <campaign> & review'
    long_copy = ("Readable campaign details and concrete review notes. " * 110) + "FINAL-CAMPAIGN-DETAIL-987654"
    response = client.patch(f"/assets/{asset['id']}", json={"hook": unicode_copy, "body": long_copy, "cta": "Explore Orbit."})
    assert response.status_code == 200, response.text
    response = client.get(f"/campaigns/{campaign['id']}/export")
    text = pdf_text(response)
    assert unicode_copy in text
    assert "FINAL-CAMPAIGN-DETAIL-987654" in text
    assert len(PdfReader(io.BytesIO(response.content)).pages) > 1


def test_zip_preserves_active_historical_and_unmapped_assets(client):
    campaign = planned(client)
    base = f"/campaigns/{campaign['id']}"
    original_item = deepcopy(campaign["timeline"][0])
    campaign = post(client, base + "/assets", {"platform": "linkedin", "asset_type": "post", "timeline_item_id": original_item["id"]})
    historical_id = campaign["assets"][-1]["id"]
    campaign = post(client, base + "/timeline")
    current_item = campaign["timeline"][0]
    campaign = post(client, base + "/assets", {"platform": "linkedin", "asset_type": "post", "timeline_item_id": current_item["id"]})
    active_id = campaign["assets"][-1]["id"]
    # The generated X timeline slots use threads; an X post has no matching slot.
    campaign = post(client, base + "/assets", {"platform": "x", "asset_type": "post"})
    unmapped_id = campaign["assets"][-1]["id"]
    before = deepcopy(client.get(base).json())
    zipped, manifest = archive(client.get(base + "/deliverables/download"))
    assert manifest["campaign_id"] == campaign["id"]
    assert {entry["id"] for entry in entries(manifest)} == {historical_id, active_id, unmapped_id}
    groups = {group["mapping"]: group for group in manifest["groups"] if group["assets"]}
    assert {entry["id"] for entry in groups["active"]["assets"]} == {active_id}
    assert groups["historical"]["timeline_item"] == original_item
    assert groups["historical"]["assets"][0]["id"] == historical_id
    assert groups["unmapped"]["assets"][0]["id"] == unmapped_id
    for entry in entries(manifest):
        content_file = next(file for file in entry["files"] if file["name"] == "content.json")
        copy_file = next(file for file in entry["files"] if file["name"] == "copy.md")
        assert json.loads(zipped.read(content_file["path"]))
        assert zipped.read(copy_file["path"])
    _, single = archive(client.get(f"/assets/{historical_id}/deliverables/download"))
    assert [entry["id"] for entry in entries(single)] == [historical_id]
    assert client.get(base).json() == before


def test_zip_contains_current_media_bytes_copy_caption_and_narration(account, monkeypatch):
    client, campaign, _, suite = account
    asset = create_account_asset(client, campaign)
    asset = add_media(client, suite, monkeypatch, asset, kind="image", raw=b"first image bytes")
    narration = "Orbit connects campaign work. A distinct spoken script."
    asset = add_media(client, suite, monkeypatch, asset, kind="voiceover", raw=b"actual voiceover bytes", script=narration)
    asset = add_media(client, suite, monkeypatch, asset, kind="image", raw=b"replacement image bytes")
    before = deepcopy(client.get(f"/campaigns/{campaign['id']}").json())
    zipped, manifest = archive(client.get(f"/assets/{asset['id']}/deliverables/download"))
    entry = entries(manifest)[0]
    assert entry["current_version"] == 4
    files = {file["name"]: zipped.read(file["path"]) for file in entry["files"]}
    assert b"replacement image bytes" in files.values()
    assert b"actual voiceover bytes" in files.values()
    assert b"first image bytes" not in files.values()
    for media in asset["versions"][-1]["media_items"]:
        response = client.get(f"/assets/{asset['id']}/media/{media['id']}?download=true")
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert response.content in (b"replacement image bytes", b"actual voiceover bytes")
    assert narration in "\n".join(raw.decode("utf-8", errors="replace") for raw in files.values())
    assert any("narration" in name or "script" in name for name in files)
    assert any("caption" in name for name in files)
    copy = files["copy.md"].decode("utf-8")
    for field in ("hook", "body", "cta"):
        assert asset["versions"][-1][field] in copy
    assert client.get(f"/campaigns/{campaign['id']}").json() == before


def test_copy_revision_excludes_old_media_from_download_but_keeps_pdf_history(account, monkeypatch):
    client, campaign, _, suite = account
    asset = create_account_asset(client, campaign)
    asset = add_media(client, suite, monkeypatch, asset, kind="voiceover", raw=b"obsolete audio", script="HISTORICAL-NARRATION-ONLY")
    response = client.patch(f"/assets/{asset['id']}", json={"hook": "NEW-CURRENT-HOOK", "body": "Orbit connects campaign work.", "cta": "Explore Orbit.", "caption": "Current caption"})
    assert response.status_code == 200, response.text
    zipped, manifest = archive(client.get(f"/assets/{asset['id']}/deliverables/download"))
    entry = entries(manifest)[0]
    assert entry["current_version"] == 3
    current_bytes = [zipped.read(file["path"]) for file in entry["files"]]
    assert b"obsolete audio" not in current_bytes
    assert not any(b"HISTORICAL-NARRATION-ONLY" in raw for raw in current_bytes)
    text = pdf_text(client.get(f"/campaigns/{campaign['id']}/export"))
    assert "HISTORICAL-NARRATION-ONLY" in text and "NEW-CURRENT-HOOK" in text


def test_downloads_are_owner_scoped_and_require_authentication(account):
    client, campaign, _, _ = account
    asset = create_account_asset(client, campaign)
    paths = [f"/campaigns/{campaign['id']}/export", f"/campaigns/{campaign['id']}/export?format=json", f"/campaigns/{campaign['id']}/deliverables",
             f"/campaigns/{campaign['id']}/deliverables/download", f"/assets/{asset['id']}/deliverables/download"]
    assert client.post("/auth/logout").status_code == 200
    for path in paths:
        assert client.get(path).status_code == 401
    post(client, "/auth/register", {"email": "other-downloads@example.com", "password": "long password 123"})
    for path in paths:
        assert client.get(path).status_code == 404


def test_missing_binary_fails_clearly_instead_of_silently_omitting_it(account, monkeypatch):
    client, campaign, _, suite = account
    asset = create_account_asset(client, campaign)
    asset = add_media(client, suite, monkeypatch, asset, kind="image", raw=b"unavailable image")
    before = deepcopy(client.get(f"/campaigns/{campaign['id']}").json())
    def unavailable(*args):
        raise StorageError("Private object download failed. Check storage connectivity.")
    monkeypatch.setattr(FakeBlobs, "read", unavailable)
    for path in (f"/campaigns/{campaign['id']}/deliverables/download", f"/assets/{asset['id']}/deliverables/download"):
        response = client.get(path)
        assert response.status_code in (502, 503), response.text
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["detail"]
    assert client.get(f"/campaigns/{campaign['id']}").json() == before


def test_empty_campaign_downloads_and_unknown_records(client):
    campaign = planned(client)
    zipped, manifest = archive(client.get(f"/campaigns/{campaign['id']}/deliverables/download"))
    assert entries(manifest) == []
    assert "manifest.json" in zipped.namelist()
    assert campaign["name"] in pdf_text(client.get(f"/campaigns/{campaign['id']}/export"))
    for path in ("/campaigns/missing/export", "/campaigns/missing/deliverables/download", "/assets/missing/deliverables/download"):
        assert client.get(path).status_code == 404


def test_user_supplied_names_cannot_escape_archive_or_inject_headers(account):
    client, campaign, _, _ = account
    repository = client.app.state.repository
    # Persisted legacy names can predate validation; exports must still be safe.
    repository.database.records.docs[campaign["id"]]["data"]["name"] = '../../unsafe\\campaign\r\nX-Injected: yes'
    repository.database.records.docs[campaign["id"]]["data"]["timeline"][0]["stage"] = '../../outside\\folder'
    asset = create_account_asset(client, campaign)
    for path in (f"/campaigns/{campaign['id']}/deliverables/download", f"/assets/{asset['id']}/deliverables/download"):
        response = client.get(path)
        archive(response)
        assert "x-injected" not in response.headers
        assert "\r" not in response.headers["content-disposition"]
        assert "\n" not in response.headers["content-disposition"]
    pdf = client.get(f"/campaigns/{campaign['id']}/export")
    pdf_text(pdf)
    assert "x-injected" not in pdf.headers
