from typing import Any, TypedDict


class CampaignState(TypedDict, total=False):
    """Blueprint campaign channels plus private operation state; never streamed raw."""
    campaign_id: str
    goal: str
    audience: str
    strategy: dict | None
    creative_direction: dict | None
    timeline: list[dict]
    approved_assets: list[dict]
    brand_id: str
    campaign_context: dict
    campaign: dict
    brand: dict
    asset: dict
    operation: str
    context: dict
    content: dict
    evaluation: dict
    versions: list[dict]
    retries: int
    revision: int
    section: str
    status: str
    experiment: dict
    metrics: dict
    media_kind: str
    result: Any
