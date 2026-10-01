"""Five blueprint agents; legacy AgentSuite resolves to the LangGraph orchestrator."""
from ..core.errors import AgentError
from ..core.events import progress_sink, progress
from ..core.gemini import GeminiProvider
from ..schemas.agent_outputs import Content, Directions, Evaluation, Strategy


def __getattr__(name):
    if name == "AgentSuite":
        from ..services.orchestrator import CampaignOrchestrator
        return CampaignOrchestrator
    raise AttributeError(name)
