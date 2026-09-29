"""Exercise the real HTTP workflow, including the Next.js proxy when selected.

Usage: python scripts/smoke.py http://127.0.0.1:3000/api
Creates a clearly named smoke-test brand/campaign in the target local database.
"""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")

    def request(path, method="GET", data=None, expected=200):
        payload = None if data is None else json.dumps(data).encode()
        req = Request(base + path, data=payload, method=method, headers={"Content-Type": "application/json"})
        try:
            response = urlopen(req, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read().decode()
            assert response.status == expected, f"{method} {path}: expected {expected}, got {response.status}: {raw}"
            return json.loads(raw)

    assert request("/health")["status"] == "ok"
    brand = request("/brands", "POST", {
        "name": "HTTP smoke test brand", "description": "A planning workspace for small marketing teams.",
        "voice": "Clear and conversational", "approved_claims": ["Plan campaigns in one workspace."], "forbidden_phrases": ["guaranteed success"],
    }, expected=201)
    brand = request(f"/brands/{brand['id']}/sources", "POST", {
        "name": "Smoke product note", "text": "Plan campaigns in one workspace. Teams can review content before publishing.", "source_type": "product_document",
    })
    campaign = request("/campaigns", "POST", {
        "brand_id": brand["id"], "name": "HTTP smoke test campaign", "brief": "Introduce our campaign planning workspace to small marketing teams.",
        "goal": "Build awareness", "audience": "Small marketing teams", "platforms": ["linkedin", "instagram", "x"], "duration_days": 14,
    }, expected=201)
    path = f"/campaigns/{campaign['id']}"
    campaign = request(path + "/strategy", "POST")
    assert campaign["strategy"]["source_refs"], "Strategy must expose sources"
    campaign = request(path + "/direction", "POST", {"direction_id": campaign["strategy"]["creative_directions"][0]["id"]})
    campaign = request(path + "/timeline", "POST")
    assert campaign["timeline"]
    for platform, asset_type in (("linkedin", "post"), ("instagram", "reel"), ("x", "thread")):
        campaign = request(path + "/assets", "POST", {"platform": platform, "asset_type": asset_type, "demonstrate_failure": platform == "linkedin"})
    asset = campaign["assets"][0]
    assert len(asset["versions"]) >= 2, "Failure demonstration must preserve failed and repaired versions"
    assert any(not version["evaluation"]["passed"] for version in asset["versions"])
    assert asset["versions"][-1]["evaluation"]["passed"]
    asset_path = f"/assets/{asset['id']}"
    request(asset_path + "/publish", "POST", {"version": asset["current_version"]}, expected=409)
    asset = request(asset_path + "/approve", "POST", {"version": asset["current_version"]})
    previous = asset["current_version"]
    asset = request(asset_path + "/regenerate", "POST", {"section": "cta"})
    assert asset["current_version"] > previous
    request(asset_path + "/approve", "POST", {"version": previous}, expected=409)
    request(asset_path + "/publish", "POST", {"version": asset["current_version"]}, expected=409)
    asset = request(asset_path + "/approve", "POST", {"version": asset["current_version"]})
    asset = request(asset_path + "/publish", "POST", {"version": asset["current_version"]})
    assert asset["status"] == "published"
    campaign = request(path + "/experiments", "POST", {"asset_id": asset["id"], "variable": "hook"})
    assert campaign["experiments"][-1]["is_demo"]
    analytics = request(path + "/analytics")
    assert analytics["is_demo"] and analytics == request(path + "/analytics")
    campaign = request(path + "/learnings", "POST")
    assert campaign["learnings"]
    campaign = request(path + f"/learnings/{campaign['learnings'][0]['id']}/save", "POST")
    assert campaign["learnings"][0]["saved_to_brand"]
    exported = request(path + "/export")
    assert exported["campaign"]["id"] == campaign["id"]
    print(json.dumps({"result": "passed", "base": base, "campaign_id": campaign["id"], "assets": len(campaign["assets"]), "trace_events": len(request(path + "/trace"))}, indent=2))


if __name__ == "__main__":
    main()
