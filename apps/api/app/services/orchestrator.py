"""LangGraph orchestration. Mongo aggregates remain the authoritative approval state.

Version nodes stage immutable drafts; routes commit the complete graph result and
campaign trace atomically. Review is a terminal boundary, never auto-approval.
"""
from copy import deepcopy
from datetime import datetime, timezone
import os
from uuid import uuid4

from langgraph.graph import StateGraph, START, END

from ..agents.base import retrieved_context
from ..agents.runtime import AgentRuntime
from ..agents.strategist import StrategistAgent
from ..agents.marketing import MarketingAgent
from ..agents.creative import CreativeAgent
from ..agents.evaluator import EvaluatorAgent
from ..agents.analytics import AnalyticsAgent
from ..core.events import progress
from ..core.errors import AgentError
from ..core.providers import HybridProvider
from ..schemas.campaign_state import CampaignState

MAX_RETRIES = 2


class CampaignOrchestrator:
    mode = "gemini"

    def __init__(self, provider=None):
        self.provider = provider or HybridProvider()
        self.runtime = AgentRuntime(self.provider)
        self.strategist = StrategistAgent(self.runtime)
        self.marketing = MarketingAgent(self.runtime)
        self.creative = CreativeAgent(self.runtime)
        self.evaluator = EvaluatorAgent(self.runtime)
        self.analytics = AnalyticsAgent(self.runtime)
        self.graphs = {name: self._compile(name) for name in
                       ("strategy", "directions", "timeline", "content", "asset", "evaluate", "repair", "learning", "observations", "media")}

    def ingest(self, source):
        return self.runtime.retriever.ingest(source)

    def retrieve(self, brand, query):
        return self.runtime.retriever.retrieve(brand, query)

    def _node(self, name, action):
        def execute(state):
            progress(name, "running")
            token = retrieved_context.set(state.get("context"))
            try:
                update = action(state)
            finally:
                retrieved_context.reset(token)
            campaign = state.get("campaign")
            if campaign is not None:
                campaign.setdefault("trace", []).append({"id": str(uuid4()), "event_type": name,
                    "message": f"LangGraph node {name} completed.", "status": "completed",
                    "timestamp": datetime.now(timezone.utc).isoformat()})
            progress(name, "completed")
            return update
        return execute

    def _compile(self, operation):
        graph = StateGraph(CampaignState)
        graph.add_node("load_campaign_state", self._node("brief_loaded", lambda s: {
            "campaign_id": s["campaign"].get("id", ""), "goal": s["campaign"].get("goal", ""),
            "audience": s["campaign"].get("audience", ""), "strategy": s["campaign"].get("strategy"),
            "creative_direction": next((d for d in (s["campaign"].get("strategy") or {}).get("creative_directions", [])
                                        if d["id"] == s["campaign"].get("selected_direction")), None),
            "timeline": s["campaign"].get("timeline", []), "brand_id": s["campaign"].get("brand_id", ""),
            "approved_assets": s["campaign"].get("approved_assets", []),
            "campaign_context": {"brief": s["campaign"].get("brief", ""), "platforms": s["campaign"].get("platforms", [])}}))
        graph.add_edge(START, "load_campaign_state")
        parent = "load_campaign_state"
        if operation not in ("evaluate", "learning", "observations"):
            graph.add_node("retrieve_context", self._node("context_retrieved", lambda s: {
                "context": {**self.runtime.context(s["campaign"], s["brand"]),
                            "campaign_state": {k: s.get(k) for k in ("campaign_id", "goal", "audience", "strategy", "creative_direction", "timeline", "approved_assets", "brand_id", "campaign_context")}}}))
            graph.add_edge(parent, "retrieve_context")
            parent = "retrieve_context"
        actions = {
            "strategy": ("strategist", lambda s: self._strategy(s)),
            "directions": ("creative_directions", lambda s: {"result": self.strategist.directions(s["campaign"], s["brand"], s["campaign"]["strategy"])}),
            "timeline": ("marketing", lambda s: {"result": self.marketing.timeline(s["campaign"], s["brand"])}),
            "content": ("creative", lambda s: {"result": self.creative.content(s["campaign"], s["brand"], s["asset"], s.get("revision", 0))}),
            "repair": ("creative_repair", lambda s: {"result": self.creative.repair(s["campaign"], s["brand"], s["asset"], s["content"])}),
            "evaluate": ("evaluator", lambda s: {"result": self.evaluator.evaluate(s["content"], s["brand"], self._evaluation_asset(s))}),
            "learning": ("analytics_learning", lambda s: {"result": self.analytics.learning(s["campaign"], s["experiment"])}),
            "observations": ("analytics_observations", lambda s: {"result": self.analytics.observations(s["campaign"], s["metrics"])}),
            "media": ("creative_media", lambda s: {"result": self.creative.media(s["campaign"], s["brand"], s["asset"], s["media_kind"])})}
        if operation != "asset":
            name, action = actions[operation]
            graph.add_node(name, self._node(name, action))
            graph.add_edge(parent, name)
            if operation == "strategy":
                graph.add_node("creative_directions", self._node("creative_directions", lambda s: {
                    "result": {**s["strategy"], **self.strategist.directions(s["campaign"], s["brand"], s["strategy"])}}))
                graph.add_edge(name, "creative_directions")
                graph.add_edge("creative_directions", END)
            else:
                graph.add_edge(name, END)
        else:
            graph.add_node("creative_generation", self._node("generation_completed", self._generate))
            graph.add_node("save_version", self._node("asset_version_staged", lambda s: {
                "versions": [*s["versions"], {"content": deepcopy(s["content"])}]}))
            graph.add_node("evaluate", self._node("evaluation_completed", self._evaluate))
            graph.add_node("repair", self._node("regeneration_started", self._repair))
            graph.add_node("human_review", self._node("approval_requested", lambda s: {"status": "needs_review"}))
            graph.add_node("needs_human_review", self._node("repair_exhausted", lambda s: {"status": "needs_human_review"}))
            graph.add_edge(parent, "creative_generation")
            graph.add_edge("creative_generation", "save_version")
            graph.add_edge("save_version", "evaluate")
            graph.add_conditional_edges("evaluate", lambda s: "human_review" if s["evaluation"]["passed"] else
                                        "repair" if s["retries"] < MAX_RETRIES else "needs_human_review",
                                        {name: name for name in ("human_review", "repair", "needs_human_review")})
            graph.add_edge("repair", "save_version")
            graph.add_edge("human_review", END)
            graph.add_edge("needs_human_review", END)
        return graph.compile()

    def _strategy(self, state):
        strategy = self.strategist.positioning(state["campaign"], state["brand"])
        return {"strategy": strategy, "result": strategy}

    def _evaluation_asset(self, state):
        return {**state["asset"], "campaign_context": {k: state.get(k) for k in
            ("campaign_id", "goal", "audience", "strategy", "creative_direction", "timeline", "approved_assets", "brand_id", "campaign_context")}}

    def _generate(self, state):
        content = self.creative.content(state["campaign"], state["brand"], state["asset"], state.get("revision", 0))
        if state.get("section", "all") != "all":
            section = state["section"]
            prior = state["asset"]["versions"][-1]
            content = {k: content.get(k, "") if k == section else deepcopy(prior.get(k, "")) for k in ("hook", "body", "cta", "caption", "source_refs")}
        return {"content": content}

    def _evaluate(self, state):
        asset = self._evaluation_asset(state)
        evaluation = self.evaluator.evaluate(state["content"], state["brand"], asset)
        versions = deepcopy(state["versions"])
        versions[-1]["evaluation"] = evaluation
        return {"evaluation": evaluation, "versions": versions}

    def _repair(self, state):
        content = self.creative.repair(state["campaign"], state["brand"], state["asset"],
                                      {**state["content"], "evaluation": state["evaluation"]})
        if state.get("section", "all") != "all":
            content = {k: content.get(k, "") if k == state["section"] else state["content"].get(k, "") for k in ("hook", "body", "cta", "caption", "source_refs")}
        return {"content": content, "retries": state["retries"] + 1}

    def _input(self, campaign, brand=None, **kwargs):
        return {"campaign": deepcopy(campaign), "brand": deepcopy(brand or {}), "retries": 0, "versions": [], **deepcopy(kwargs)}

    def _finish(self, state, campaign):
        # Copy only successful trace/run mutations; provider failures never leak partial state.
        campaign["trace"] = state["campaign"].get("trace", [])
        campaign["agent_runs"] = state["campaign"].get("agent_runs", [])
        return state.get("result", state)

    def _invoke(self, operation, campaign, brand=None, **kwargs):
        state = self.graphs[operation].invoke(self._input(campaign, brand, **kwargs), {"recursion_limit": 32})
        return self._finish(state, campaign)

    async def _ainvoke(self, operation, campaign, brand=None, **kwargs):
        state = await self.graphs[operation].ainvoke(self._input(campaign, brand, **kwargs), {"recursion_limit": 32})
        return self._finish(state, campaign)

    def strategy(self, campaign, brand):
        return self._invoke("strategy", campaign, brand)

    def timeline(self, campaign, brand):
        return self._invoke("timeline", campaign, brand)

    def directions(self, campaign, brand):
        return self._invoke("directions", campaign, brand)

    def content(self, campaign, brand, asset, variant=0):
        return self._invoke("content", campaign, brand, asset=asset, revision=variant)

    def generate_asset_sync(self, campaign, brand, asset, revision=0, section="all"):
        return self._invoke("asset", campaign, brand, asset=asset, revision=revision, section=section)

    def evaluate(self, content, brand, asset):
        campaign = {**asset.get("campaign_context", {}), "id": asset.get("campaign_id", ""), "trace": []}
        return self._invoke("evaluate", campaign, brand, content=content, asset=asset)

    def repair(self, campaign, brand, asset, content):
        return self._invoke("repair", campaign, brand, asset=asset, content=content)

    def learning(self, campaign, experiment):
        return self._invoke("learning", campaign, experiment=experiment)

    def observations(self, campaign, metrics):
        return self._invoke("observations", campaign, metrics=metrics)

    def media(self, campaign, brand, asset, kind):
        # Check before graph retrieval, since embeddings are also model calls.
        if kind == "image" and os.getenv("IMAGE_PROVIDER", "gemini").lower() == "gemini" and os.getenv("GEMINI_IMAGE_ALLOW_PAID", "false").lower() != "true":
            raise AgentError("Gemini image generation is disabled in free-only mode: current Gemini image APIs have no free tier. No image provider was called. Paid usage requires explicitly setting GEMINI_IMAGE_ALLOW_PAID=true.")
        return self._invoke("media", campaign, brand, asset=asset, media_kind=kind)

    async def build_campaign_strategy(self, campaign, brand):
        return await self._ainvoke("strategy", campaign, brand)

    async def generate_timeline(self, campaign, brand):
        return await self._ainvoke("timeline", campaign, brand)

    async def generate_asset(self, campaign, brand, asset, revision=0, section="all"):
        return await self._ainvoke("asset", campaign, brand, asset=asset, revision=revision, section=section)

    async def evaluate_asset(self, campaign, brand, asset, content):
        return await self._ainvoke("evaluate", campaign, brand, asset={**asset, "campaign_context": campaign}, content=content)

    async def repair_asset(self, campaign, brand, asset, content):
        return await self._ainvoke("repair", campaign, brand, asset=asset, content=content)

    async def create_experiment(self, campaign, brand, asset, count=3):
        if not 2 <= count <= 5:
            raise ValueError("Experiment variant count must be between 2 and 5.")
        return [await self.generate_asset(campaign, brand, asset, revision=i + 1, section="hook") for i in range(count)]

    async def generate_learnings(self, campaign, experiment):
        return await self._ainvoke("learning", campaign, experiment=experiment)
