from ..schemas.agent_outputs import Evaluation
from .base import BaseAgent

class EvaluatorAgent(BaseAgent):
    def evaluate(self, content, brand, asset):
        rules = self.rules.evaluate(content, brand, asset)
        allowed = set(content.get("source_refs", []))
        output = self.call(None, "evaluator", "Check every factual claim in hook, body, CTA and caption against cited sources and approved claims, brand voice, safety, and platform format. Instagram captions must be publishable without stage cues; narration must be grounded too. Fail unsupported semantic claims, even without numbers. Return checks for grounding, brand_fit, platform_fit, audience_fit, claim_safety, completeness; passed must agree with all checks and empty issues.", {"content": {k: content.get(k) for k in ("hook", "body", "cta", "caption", "source_refs")}, "brand": {k: brand[k] for k in ("voice", "approved_claims", "forbidden_phrases")}, "sources": [{"id": s["id"], "text": s["text"][:20000]} for s in brand["sources"] if s["id"] in allowed and s["source_type"] != "previous_campaign"], "platform": asset["platform"], "asset_type": asset["asset_type"], "campaign_state": asset.get("campaign_context", {}), "timeline_deliverable": asset.get("timeline_snapshot")}, Evaluation)
        required = {"grounding", "brand_fit", "platform_fit", "audience_fit", "claim_safety", "completeness"}
        checks = {**rules["checks"], **{f"ai_{k}": v for k, v in output["checks"].items()}}
        valid = required <= output["checks"].keys()
        return {"passed": rules["passed"] and output["passed"] and valid and all(output["checks"].values()) and not output["issues"], "issues": rules["issues"] + output["issues"] + ([] if valid else ["Evaluator omitted required quality checks."]), "checks": checks, "model": output["_agent_run"]["model"], "agent_run": output["_agent_run"]}

