from contextvars import ContextVar
from ..services.generation import DeterministicRouter

retrieved_context = ContextVar("retrieved_campaign_context", default=None)


class BaseAgent:
    def __init__(self, runtime):
        self.runtime = runtime
        self.provider = runtime.provider
        self.rules = DeterministicRouter()

    def call(self, *args):
        return self.runtime.call(*args)

    def context(self, campaign, brand):
        context = retrieved_context.get()
        return context if context is not None else self.runtime.context(campaign, brand)

    def guidance(self, campaign, section):
        return {"custom_instructions": campaign.get("generation_prompts", {}).get(section, ""),
                "human_feedback": [review for review in campaign.get("reviews", [])
                                   if review["section"] == section and review["decision"] == "changes_requested"][-3:]}
