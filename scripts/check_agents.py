"""Live agent smoke checks with synthetic inputs, no database writes or publication.

Run: .venv/Scripts/python scripts/check_agents.py --live
Uses root .env provider settings. Calls consume configured text/embedding quota;
paid images are never requested. Output contains statuses, never credentials.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))


def fixtures():
    brand = {"id": "smoke-brand", "name": "Orbit", "description": "Campaign workspace",
        "voice": "Clear, practical and warm", "approved_claims": ["Orbit connects campaign work."],
        "forbidden_phrases": ["guaranteed results"], "sources": [{"id": "smoke-source",
        "name": "Synthetic smoke-test product guide", "text": "Orbit connects campaign work. Humans review every asset before publication.",
        "source_type": "product_document"}]}
    campaign = {"id": "smoke-campaign", "brand_id": brand["id"], "brief": "Introduce Orbit to small marketing teams using documented facts.",
        "goal": "Awareness", "audience": "Small marketing teams", "platforms": ["linkedin", "instagram", "x"],
        "duration_days": 3, "strategy": {"positioning": "Connected campaign work", "core_message": "Orbit connects campaign work.",
        "audience_summary": "Small marketing teams", "content_pillars": ["Campaign workflow"], "assumptions": [],
        "source_refs": ["smoke-source"], "creative_directions": [{"id": "workflow", "name": "Workflow",
        "description": "Show connected campaign work", "rationale": "Grounded in the supplied guide"}]},
        "selected_direction": "workflow", "timeline": [{"id": "smoke-item", "day": 1, "stage": "awareness",
        "platform": "linkedin", "asset_type": "post", "objective": "Introduce the documented workflow"}],
        "approved_assets": [], "agent_runs": [], "trace": []}
    content = {"hook": "Connect your campaign work", "body": "Orbit connects campaign work.",
               "cta": "Explore the workflow.", "source_refs": ["smoke-source"]}
    asset = {"id": "smoke-asset", "campaign_id": campaign["id"], "platform": "linkedin", "asset_type": "post",
             "timeline_item_id": "smoke-item", "timeline_snapshot": dict(campaign["timeline"][0]),
             "current_version": 1, "versions": [{**content, "version": 1}], "approvals": [], "campaign_context": campaign}
    return campaign, brand, asset, content


def safe_error(error):
    message = str(error)
    for name, value in os.environ.items():
        if value and any(part in name.upper() for part in ("KEY", "TOKEN", "SECRET", "PASSWORD", "MONGODB_URI")):
            message = message.replace(value, "[redacted]")
    return message[:800]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Run configured provider calls using synthetic data.")
    parser.add_argument("--only", nargs="+", choices=["strategy_and_directions", "timeline", "linkedin_content",
        "instagram_reel", "x_post", "x_thread", "evaluation", "repair", "variant_graph", "analytics", "learning", "visual_plan", "narration_plan", "voiceover"],
        help="Run only the named checks.")
    parser.add_argument("--duration", type=int, default=3, help="Timeline length (1–90 days).")
    parser.add_argument("--model", help="Override Gemini text model for this smoke process only; never edits .env.")
    parser.add_argument("--probe-groq-fallback", action="store_true",
        help="Simulate exhausted Gemini text quota, then test real Groq queries. Embeddings still use Gemini.")
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live to run provider queries; offline checks are in apps/api/tests.")
    if not 1 <= args.duration <= 90:
        parser.error("--duration must be between 1 and 90.")
    load_dotenv(ROOT / ".env")
    if args.model:
        os.environ["GEMINI_MODEL"] = args.model
        for role in ("strategist", "marketing", "creative", "evaluator", "analytics"):
            os.environ[f"GEMINI_{role.upper()}_MODEL"] = args.model
    from app.services.orchestrator import CampaignOrchestrator
    from app.schemas.agent_outputs import Narration, VisualPlan
    provider = None
    if args.probe_groq_fallback:
        if not os.getenv("GROQ_API_KEY"):
            parser.error("--probe-groq-fallback requires GROQ_API_KEY.")
        from app.core.hybrid import HybridProvider
        from app.core.errors import ProviderError
        class QuotaProbe(HybridProvider):
            def request(self, model, action, body, **kwargs):
                if action == "generateContent":
                    raise ProviderError("Simulated Gemini text quota exhaustion for routing probe.",
                                        reason="daily_quota", cooldown=3600)
                return super().request(model, action, body, **kwargs)
        for role in ("strategist", "marketing", "creative", "evaluator", "analytics"):
            os.environ[f"{role.upper()}_PROVIDER"] = "gemini"
        os.environ["AI_FALLBACK_ENABLED"] = "true"
        os.environ["AI_PROVIDER_FALLBACK_ENABLED"] = "true"
        provider = QuotaProbe()
    suite = CampaignOrchestrator(provider)
    campaign, brand, asset, content = fixtures()
    campaign["duration_days"] = args.duration
    experiment = {"is_demo": True, "metrics_source": "synthetic smoke fixture", "variants": [
        {"label": "A", "impressions": 0, "clicks": 0, "conversions": 0},
        {"label": "B", "impressions": 0, "clicks": 0, "conversions": 0}]}
    instagram_asset = {**asset, "platform": "instagram", "asset_type": "reel",
        "timeline_snapshot": {**asset["timeline_snapshot"], "platform": "instagram", "asset_type": "reel"},
        "media_voice": "en-US-AriaNeural", "media_prompt": "Use a warm, conversational introduction grounded in the supplied guide."}
    checks = {
        "strategy_and_directions": lambda: suite.strategy(campaign, brand),
        "timeline": lambda: suite.timeline(campaign, brand),
        "linkedin_content": lambda: suite.content(campaign, brand, asset),
        "instagram_reel": lambda: suite.content(campaign, brand, instagram_asset),
        "x_post": lambda: suite.content(campaign, brand, {**asset, "platform": "x", "asset_type": "post", "timeline_snapshot": {**asset["timeline_snapshot"], "platform": "x", "asset_type": "post"}}),
        "x_thread": lambda: suite.content(campaign, brand, {**asset, "platform": "x", "asset_type": "thread", "timeline_snapshot": {**asset["timeline_snapshot"], "platform": "x", "asset_type": "thread"}}),
        "evaluation": lambda: suite.evaluate(content, brand, asset),
        "repair": lambda: suite.repair(campaign, brand, asset, {**content, "evaluation": {"passed": False, "issues": ["CTA should be clearer."]}}),
        "variant_graph": lambda: suite.generate_asset_sync(campaign, brand, asset, revision=1, section="hook"),
        "analytics": lambda: suite.observations(campaign, {"is_demo": True, "impressions": 0, "clicks": 0, "conversions": 0}),
        "learning": lambda: suite.learning(campaign, experiment),
        "visual_plan": lambda: suite.runtime.call(campaign, "creative", "Plan an illustration from supported copy without adding claims.",
                         {**suite.runtime.context(campaign, brand), "copy": content}, VisualPlan),
        "narration_plan": lambda: suite.runtime.call(campaign, "creative", "Write short natural spoken narration from the evaluated copy and selected timeline objective. Do not add claims. Cite supplied sources.",
            {**suite.runtime.context(campaign, brand), "copy": content, "timeline_deliverable": instagram_asset["timeline_snapshot"]}, Narration),
    }
    if args.only:
        # Real speech is opt-in; never request paid Gemini audio in this smoke command.
        if "voiceover" in args.only:
            if os.getenv("TTS_PROVIDER", "edge").lower() != "edge":
                parser.error("The voiceover smoke check requires TTS_PROVIDER=edge to avoid paid speech calls.")
            checks["voiceover"] = lambda: suite.media(campaign, brand, instagram_asset, "voiceover")
        checks = {name: checks[name] for name in args.only}
    failed = 0
    for name, check in checks.items():
        print(json.dumps({"check": name, "status": "running"}), flush=True)
        previous_runs = len(campaign["agent_runs"])
        try:
            result = check()
            if name == "strategy_and_directions":
                campaign["strategy"] = result
                campaign["selected_direction"] = result["creative_directions"][0]["id"]
            elif name == "timeline":
                campaign["timeline"] = result
            if name == "evaluation" and not result["passed"]:
                raise RuntimeError("Known grounded fixture failed: " + "; ".join(result["issues"]))
            if name == "variant_graph" and result["status"] != "needs_review":
                raise RuntimeError("Variant remained blocked after repair: " + "; ".join(result["evaluation"]["issues"]))
            if name.startswith("x_"):
                evaluation = suite.creative.rules.evaluate(result, brand, {**asset, "platform": "x", "asset_type": "thread" if name == "x_thread" else "post"})
                if not evaluation["passed"]:
                    raise RuntimeError("Generated platform copy failed fixed validation: " + "; ".join(evaluation["issues"]))
            if name == "instagram_reel" and not result.get("caption", "").strip():
                raise RuntimeError("Instagram generation omitted a separate caption.")
            if name in {"linkedin_content", "instagram_reel", "x_post", "x_thread"}:
                platform, asset_type = {"linkedin_content": ("linkedin", "post"), "instagram_reel": ("instagram", "reel"),
                                       "x_post": ("x", "post"), "x_thread": ("x", "thread")}[name]
                assessment = suite.evaluate(result, brand, {**asset, "platform": platform, "asset_type": asset_type,
                    "timeline_snapshot": {**asset["timeline_snapshot"], "platform": platform, "asset_type": asset_type}})
                if not assessment["passed"]:
                    raise RuntimeError("Generated copy failed channel/grounding evaluation: " + "; ".join(assessment["issues"]))
            if name == "narration_plan":
                assessment = suite.evaluate({**content, "body": result["script"], "source_refs": result["source_refs"]}, brand,
                    {**instagram_asset, "deliverable_kind": "voiceover", "narration_only": True})
                if not assessment["passed"]:
                    raise RuntimeError("Narration failed grounding evaluation: " + "; ".join(assessment["issues"]))
            if name == "voiceover" and (not result[0] or result[1]["mime_type"] != "audio/mpeg"):
                raise RuntimeError("Edge TTS returned no supported narration audio.")
            runs = campaign["agent_runs"][previous_runs:]
            if isinstance(result, dict):
                for field in ("_agent_run", "agent_run"):
                    if result.get(field):
                        runs = [*runs, result[field]]
                if isinstance(result.get("evaluation"), dict) and result["evaluation"].get("agent_run"):
                    runs = [*runs, result["evaluation"]["agent_run"]]
            print(json.dumps({"check": name, "status": "passed", "models": sorted({r["model"] for r in runs}),
                "routing": [r.get("attempts", []) for r in runs], "simulated_gemini_quota": args.probe_groq_fallback}), flush=True)
        except Exception as exc:
            failed += 1
            print(json.dumps({"check": name, "status": "failed", "error": safe_error(exc)}), flush=True)
    print(json.dumps({"total": len(checks), "failed": failed,
        "media": "Paid images are intentionally excluded; free-only image guard is covered offline."}), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
