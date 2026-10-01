from ..schemas.agent_outputs import Evaluation
from .base import BaseAgent

class EvaluatorAgent(BaseAgent):
    def evaluate(self, content, brand, asset):
        rules = self.rules.evaluate(content, brand, asset)
        allowed = set(content.get("source_refs", []))
        narration_only = bool(asset.get("narration_only"))
        scope = ("This is ONLY spoken audio: body is the complete narration script. Hook, CTA and caption fields may be empty. Do not require captions, hashtags, shot lists, visual storyboards, stage directions or on-screen text. Completeness means a nonempty coherent spoken script; platform_fit means plain speakable text at most 6000 characters. This flag changes audio format checks only: every factual claim still needs cited evidence. Conversational invitations add no product claims. " if narration_only else "Evaluate all written fields, including caption, against the selected platform and asset type. Instagram captions must be publishable without stage cues. LinkedIn should use an approachable professional register with clear work relevance; an empty caption is valid. Only single X posts require hook, body and CTA joined by newlines to fit 280 characters; X threads instead require each paragraph to fit 280 characters. X captions may be empty. ")
        output = self.call(None, "evaluator", scope + "Check every factual claim against cited sources and approved claims, brand voice, safety, and the specified deliverable format. Fail unsupported semantic claims, even without numbers. Return checks for grounding, brand_fit, platform_fit, audience_fit, claim_safety, completeness; passed must agree with all checks and empty issues.", {"content": {k: content.get(k) for k in ("hook", "body", "cta", "caption", "source_refs")}, "brand": {k: brand[k] for k in ("voice", "approved_claims", "forbidden_phrases")}, "sources": [{"id": s["id"], "text": s["text"][:20000]} for s in brand["sources"] if s["id"] in allowed and s["source_type"] != "previous_campaign"], "platform": asset["platform"], "asset_type": asset["asset_type"], "deliverable_kind": "voiceover" if narration_only else "social_copy", "narration_only": narration_only, "campaign_state": asset.get("campaign_context", {}), "timeline_deliverable": asset.get("timeline_snapshot")}, Evaluation)
        required = {"grounding", "brand_fit", "platform_fit", "audience_fit", "claim_safety", "completeness"}
        checks = {**rules["checks"], **{f"ai_{k}": v for k, v in output["checks"].items()}}
        valid = required <= output["checks"].keys()
        return {"passed": rules["passed"] and output["passed"] and valid and all(output["checks"].values()) and not output["issues"], "issues": rules["issues"] + output["issues"] + ([] if valid else ["Evaluator omitted required quality checks."]), "checks": checks, "model": output["_agent_run"]["model"], "agent_run": output["_agent_run"]}

