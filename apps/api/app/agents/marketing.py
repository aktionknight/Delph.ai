from uuid import uuid4
from ..core.errors import AgentError
from ..schemas.agent_outputs import Timeline
from ..services.generation import ASSET_TYPES, DEFAULT_TYPES
from .base import BaseAgent

class MarketingAgent(BaseAgent):
    def timeline(self, campaign, brand):
        output = self.call(campaign, "marketing", "Plan exactly one item per day, covering all days. Use only campaign platforms and compatible asset types. Sequence awareness through conversion around the selected direction. Follow custom instructions and reviewer feedback without inventing claims.", {**self.context(campaign, brand), **self.guidance(campaign, "timeline"), "duration_days": campaign["duration_days"], "allowed_asset_types": {k: sorted(v) for k, v in ASSET_TYPES.items()}}, Timeline)["items"]
        
        duration = campaign["duration_days"]
        platforms = campaign.get("platforms", ["linkedin"])
        if not platforms: platforms = ["linkedin"]
        
        if len(output) > duration:
            output = output[:duration]
        while len(output) < duration:
            output.append(output[-1].copy() if output else {"stage": "Launch", "objective": "Drive engagement", "platform": platforms[0], "asset_type": DEFAULT_TYPES.get(platforms[0], "post")})
            
        for idx, item in enumerate(output):
            item["day"] = idx + 1
            if item.get("platform") not in platforms:
                item["platform"] = platforms[0]
            if item.get("asset_type") not in ASSET_TYPES.get(item["platform"], set()):
                item["asset_type"] = DEFAULT_TYPES.get(item["platform"], "post")
                
        return [{"id": str(uuid4()), **i} for i in output]
