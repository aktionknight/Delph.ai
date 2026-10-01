"""Load reviewed prompt files; schemas are supplied by the provider at runtime."""
from pathlib import Path
from .errors import AgentError

PROMPTS = Path(__file__).resolve().parents[4] / "prompts"


def load_prompt(role, payload, schema):
    tasks = {"strategist": "strategy", "marketing": "timeline", "creative": "content",
             "evaluator": "grounding", "analytics": "observations"}
    task = tasks[role]
    if role == "creative":
        task = "repair" if payload.get("operation") == "repair" else {
            ("instagram", "reel"): "instagram_reel", ("linkedin", "post"): "linkedin_post",
            ("x", "thread"): "x_thread"}.get((payload.get("platform"), payload.get("asset_type")), "content")
    if schema.__name__ == "Directions":
        task = "directions"
    elif schema.__name__ == "Learning":
        task = "learning"
    elif schema.__name__ == "VisualPlan":
        task = "visual"
    elif schema.__name__ == "Narration":
        task = "narration"
    names = ["system", task] + (["brand_fit", "audience_fit"] if role == "evaluator" else [])
    try:
        parts = [(PROMPTS / role / f"{name}.txt").read_text(encoding="utf-8") for name in names]
        platform = payload.get("platform")
        if role in {"creative", "evaluator"} and platform in {"linkedin", "instagram", "x"}:
            parts.append((PROMPTS / "creative" / f"platform_{platform}.txt").read_text(encoding="utf-8"))
            if role == "evaluator":
                parts.append("Assess platform_fit against this channel guidance, including tone, structure and CTA. "
                             "Flag copy that reads like another platform and give actionable repair feedback. "
                             "Respect brand voice and reviewer preferences; emojis and hashtags are optional. "
                             "For narration_only, assess natural spoken delivery rather than written layout or visual directions.")
        return "\n\n".join(parts)
    except OSError as exc:
        raise AgentError(f"Required {role} prompt file is unavailable.") from exc
