"""Deterministic, source-citing local provider. No external model calls are made.

Evaluation is intentionally conservative rule checking, not semantic fact checking.
Saved simulated learnings are excluded from factual grounding.
"""
import re
from typing import Protocol

ASSET_TYPES = {"linkedin": {"post"}, "instagram": {"reel", "carousel", "story", "post"}, "x": {"post", "thread"}}
DEFAULT_TYPES = {"linkedin": "post", "instagram": "reel", "x": "thread"}


class ModelRouter(Protocol):
    def strategy(self, campaign: dict, brand: dict) -> dict: ...
    def content(self, campaign: dict, brand: dict, asset: dict, variant: int = 0) -> dict: ...
    def evaluate(self, content: dict, brand: dict, asset: dict) -> dict: ...


def sources_for(brand, query):
    tokens = set(re.findall(r"\w+", query.lower()))
    sources = [s for s in brand["sources"] if s["source_type"] != "previous_campaign"]
    return sorted(sources, key=lambda s: -len(tokens & set(re.findall(r"\w+", s["text"].lower()))))[:4]


class DeterministicRouter:
    def strategy(self, campaign, brand):
        sources = sources_for(brand, campaign["brief"])
        fact = brand["approved_claims"][0] if brand["approved_claims"] else sources[0]["text"].split("\n")[0][:240]
        return {
            "positioning": f"{brand['name']} for {campaign['audience']}: {brand['description'][:400]}",
            "core_message": fact,
            "audience_summary": campaign["audience"],
            "content_pillars": ["The problem your audience recognizes", "How the product works", "A clear next step"],
            "assumptions": ["Generated with deterministic demo templates; no external AI model was called.", "Audience and goal are user-provided; demand is unvalidated.", f"Brand voice: {brand['voice']}", "Sources are selected by keyword overlap, not vector retrieval."],
            "creative_directions": [
                {"id": "problem-first", "name": "Problem-first", "description": f"Start with the daily friction faced by {campaign['audience']}.", "rationale": "Connect the audience's problem to a documented product capability."},
                {"id": "product-led", "name": "Product-led", "description": f"Show {brand['name']} in a practical workflow.", "rationale": "Explain the approved product facts through a concrete walkthrough."},
                {"id": "educational", "name": "Educational", "description": "Teach one useful idea before introducing the product.", "rationale": "Build understanding without promising unsupported outcomes."},
            ],
            "source_refs": [s["id"] for s in sources],
        }

    def content(self, campaign, brand, asset, variant=0):
        sources = sources_for(brand, campaign["brief"])
        fact = brand["approved_claims"][0] if brand["approved_claims"] else sources[0]["text"].split("\n")[0][:180]
        name = brand["name"][:45]
        direction = campaign["selected_direction"]
        hooks = {
            "problem-first": ["Too many tabs. Too little clarity.", "What if your next campaign started with clarity?"],
            "product-led": [f"Meet {name}. See the workflow.", f"A closer look at {name}."],
            "educational": ["A better campaign starts with one clear idea.", "Start with the message. Build from there."],
        }
        hook = hooks.get(direction, hooks["problem-first"])[variant % 2]
        cta = [f"Explore {name}.", "See the workflow for yourself."][variant % 2]
        platform, asset_type = asset["platform"], asset["asset_type"]
        if platform == "x":
            if asset_type == "thread":
                body = f"1/ {fact[:220]}\n\n2/ Start with a clear brief. Review the message before you launch."
            else:
                available = max(20, 275 - len(hook) - len(cta) - 2)
                body = fact[:available]
        elif platform == "instagram":
            body = f"[Opening: show the challenge]\n{fact}\n\n[Demo: show {name} in use]\nOne idea. One clear next step."
        else:
            body = f"For {campaign['audience']}:\n\n{fact}\n\nStart with a clear brief, shape the message, and review it before launch."
        return {"hook": hook, "body": body, "cta": cta, "source_refs": [s["id"] for s in sources]}

    def evaluate(self, content, brand, asset):
        combined = "\n".join(content.get(k, "") for k in ("hook", "body", "cta"))
        lower = combined.lower()
        available = {s["id"]: s for s in brand["sources"] if s["source_type"] != "previous_campaign"}
        refs = content.get("source_refs", [])
        evidence = " ".join(available[r]["text"] for r in refs if r in available)
        evidence += " " + " ".join(brand["approved_claims"])
        evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?(?:%|x)?", evidence.lower()))
        # Thread index markers are formatting, not factual numeric claims.
        claim_text = re.sub(r"(?m)^\d+/\s*", "", lower)
        numbers = set(re.findall(r"\b\d+(?:\.\d+)?(?:%|x)?", claim_text))
        unsafe = any(phrase in lower for phrase in ("guaranteed", "guarantee", "100% success", "cures", "risk-free", "10x revenue"))
        if asset["platform"] == "x" and asset["asset_type"] == "thread":
            chunks = [content["hook"], *content["body"].split("\n\n"), content["cta"]]
            platform_fit = all(len(chunk) <= 280 for chunk in chunks)
        else:
            maximum = {"x": 280, "linkedin": 3000, "instagram": 2200}[asset["platform"]]
            platform_fit = len(combined) <= maximum
        checks = {
            "source_grounding": bool(refs) and all(r in available for r in refs),
            "claim_safety": not unsafe and numbers <= evidence_numbers,
            "brand_fit": not any(p.lower() in lower for p in brand["forbidden_phrases"]),
            "platform_fit": platform_fit,
            "completeness": all(content.get(k, "").strip() for k in ("hook", "body", "cta")),
        }
        messages = {"source_grounding": "No valid factual source references were provided.", "claim_safety": "Unsupported numeric or absolute claim detected; remove it or provide approved evidence.", "brand_fit": "Content contains a forbidden brand phrase.", "platform_fit": "Content exceeds platform character limits.", "completeness": "Hook, body, and CTA are required."}
        return {"passed": all(checks.values()), "issues": [messages[k] for k, passed in checks.items() if not passed], "checks": checks}
