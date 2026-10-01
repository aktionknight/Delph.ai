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
    names = ["system", task] + (["brand_fit", "audience_fit"] if role == "evaluator" else [])
    try:
        return "\n\n".join((PROMPTS / role / f"{name}.txt").read_text(encoding="utf-8") for name in names)
    except OSError as exc:
        raise AgentError(f"Required {role} prompt file is unavailable.") from exc
