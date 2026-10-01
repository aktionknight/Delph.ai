from ..schemas.agent_outputs import Learning, Observations
from .base import BaseAgent

class AnalyticsAgent(BaseAgent):
    def learning(self, campaign, experiment):
        return self.call(campaign, "analytics", "Summarize a cautious, evidence-linked learning. Identify simulated data explicitly. Zero impressions means no results and no winning variant. Confidence is a heuristic, not statistical certainty.", {"experiment": experiment, **self.guidance(campaign, "learnings")}, Learning)


    def observations(self, campaign, metrics):
        return self.call(campaign, "analytics", "Describe only supplied metrics and their provenance: real social API snapshots, manual imports, or simulations. Respect availability flags and null values: unavailable clicks, impressions or conversions are unknown, not zero, and ratios requiring them cannot be inferred. Separate engagement from conversions. Avoid causal claims and statistical significance. Zero measured results mean no evidence yet. Never claim variant winners from unlinked cumulative post metrics.", {**metrics, **self.guidance(campaign, "insights")}, Observations)["observations"]

