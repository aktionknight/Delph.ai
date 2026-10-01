from datetime import datetime, timezone
from uuid import uuid4
from ..core.events import progress
from ..core.errors import AgentError
from ..core.prompts import load_prompt
from ..rag.retrieval import ContextRetriever

class AgentRuntime:
    def __init__(self, provider):
        self.provider = provider
        self.retriever = ContextRetriever(provider)

    def call(self, campaign, role, instructions, payload, schema):
        if campaign is not None and "campaign_state" not in payload:
            payload = {**payload, "campaign_state": {"campaign_id": campaign.get("id"),
                "goal": campaign.get("goal"), "audience": campaign.get("audience"),
                "strategy": campaign.get("strategy"), "creative_direction": campaign.get("selected_direction"),
                "timeline": campaign.get("timeline", []), "approved_assets": campaign.get("approved_assets", []),
                "brand_id": campaign.get("brand_id"), "campaign_context": {"brief": campaign.get("brief", "")}}}
        instructions = load_prompt(role, payload, schema) + "\nObjective: " + instructions
        progress(role, "running")
        try:
            output, run = self.provider.generate(role, instructions, payload, schema)
        except AgentError:
            raise
        if campaign is not None:
            campaign.setdefault("agent_runs", []).append(run)
            fallbacks = sum(attempt.get("status") != "completed" for attempt in run.get("attempts", []))
            suffix = f", {fallbacks} fallback steps" if fallbacks else ""
            campaign["trace"].append({"id": run["id"], "event_type": "agent_completed", "message": f"{role}: {run.get('provider', 'ai')}/{run['model']}, {run['duration_ms']} ms{suffix}", "status": "completed", "timestamp": run["created_at"]})
        progress(role, "completed")
        if campaign is None:
            output["_agent_run"] = run
        return output


    def context(self, campaign, brand):
        progress("retrieval", "running")
        sources = self.retriever.retrieve(brand, campaign["brief"])
        progress("retrieval", "completed")
        return {"brief": campaign["brief"], "goal": campaign["goal"], "audience": campaign["audience"], "platforms": campaign["platforms"], "brand": {k: brand[k] for k in ("name", "description", "voice", "approved_claims", "forbidden_phrases")}, "sources": sources, "strategy": campaign.get("strategy"), "selected_direction": campaign.get("selected_direction"), "memory": [{"name": s["name"], "text": s["text"][:2000]} for s in brand["sources"] if s["source_type"] == "previous_campaign"][-10:]}

