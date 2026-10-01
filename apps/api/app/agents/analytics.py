from ..schemas.agent_outputs import Learning, Observations
from .base import BaseAgent

class AnalyticsAgent(BaseAgent):
    def learning(self, campaign, experiment):
        return self.call(campaign, "analytics", "Summarize a cautious, evidence-linked learning. Identify simulated data explicitly. Zero impressions means no results and no winning variant. Confidence is a heuristic, not statistical certainty.", {"experiment": experiment, **self.guidance(campaign, "learnings")}, Learning)


    def observations(self, campaign, metrics):
        return self.call(campaign, "analytics", "Describe only the supplied metrics. Distinguish manually imported data from simulated results. Avoid causal claims and statistical significance. Zero results mean no evidence yet.", {**metrics, **self.guidance(campaign, "insights")}, Observations)["observations"]

