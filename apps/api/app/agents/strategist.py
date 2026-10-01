from ..core.errors import AgentError
from ..schemas.agent_outputs import Strategy, Directions
from .base import BaseAgent

class StrategistAgent(BaseAgent):
    def strategy(self, campaign, brand):
        strategy = self.positioning(campaign, brand)
        return {**strategy, **self.directions(campaign, brand, strategy)}

    def positioning(self, campaign, brand):
        context = self.context(campaign, brand)
        strategy = self.call(campaign, "strategist", "Build positioning, core message, content pillars and explicitly labeled assumptions. Cite only supplied source IDs. Historical learnings are hypotheses, not product facts.", context, Strategy)
        allowed = {s["id"] for s in context["sources"]}
        if not set(strategy["source_refs"]) <= allowed:
            raise AgentError("Strategy cited an unknown source. Retry generation.")
        return strategy

    def directions(self, campaign, brand, strategy):
        context = {**self.context(campaign, brand), **self.guidance(campaign, "strategy")}
        context = {**context, **self.guidance(campaign, "direction"), "strategy": strategy, "campaign_state": {**context.get("campaign_state", {}), "strategy": strategy}}
        creative = self.call(campaign, "strategist", "Propose three distinct creative directions with unique IDs and grounded rationales.", context, Directions)
        if len({d["id"] for d in creative["creative_directions"]}) != 3:
            raise AgentError("Strategist returned duplicate directions. Retry generation.")
        return creative

