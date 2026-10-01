from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
Claim = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Prompt = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BrandInput(Input):
    name: Short
    description: Text
    voice: Short
    approved_claims: list[Claim] = Field(default_factory=list, max_length=50)
    forbidden_phrases: list[Claim] = Field(default_factory=list, max_length=50)


class BrandPatch(Input):
    name: Short | None = None
    description: Text | None = None
    voice: Short | None = None
    approved_claims: list[Claim] | None = Field(default=None, max_length=50)
    forbidden_phrases: list[Claim] | None = Field(default=None, max_length=50)


class SourceInput(Input):
    name: Short
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100000)]
    source_type: Literal["manual_note", "brand_guideline", "product_document", "audience_research", "previous_campaign", "website", "pdf", "text"] = "manual_note"


class CampaignInput(Input):
    brand_id: Short
    name: Short
    brief: Text
    goal: Short
    audience: Short
    platforms: list[Literal["linkedin", "instagram", "x"]] = Field(min_length=1, max_length=3)
    duration_days: int = Field(ge=1, le=90)

    @field_validator("platforms", mode="before")
    @classmethod
    def platforms_lower(cls, value):
        return list(dict.fromkeys(str(p).lower() for p in value)) if isinstance(value, list) else value


class DirectionInput(Input):
    direction_id: Short

class CampaignPatch(Input):
    name: Short | None = None
    brief: Text | None = None
    goal: Short | None = None
    audience: Short | None = None


class GenerationInput(Input):
    prompt: Prompt = ""


class SectionReviewInput(Input):
    section: Literal["brief", "strategy", "direction", "timeline", "insights", "learnings"]
    revision: int = Field(ge=1)
    decision: Literal["approved", "changes_requested"]
    feedback: Prompt = ""


class AssetInput(GenerationInput):
    platform: Literal["linkedin", "instagram", "x"]
    asset_type: Literal["post", "reel", "thread", "carousel", "story"]
    demonstrate_failure: bool = False
    timeline_item_id: Short | None = None

    @field_validator("platform", mode="before")
    @classmethod
    def platform_lower(cls, value):
        return value.lower() if isinstance(value, str) else value


class EditInput(Input):
    hook: Text
    body: Text
    cta: Text
    caption: Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)] | None = None


class RegenerateInput(GenerationInput):
    section: Literal["all", "hook", "cta"] = "all"


class ApprovalInput(Input):
    version: int = Field(ge=1)
    feedback: str = Field(default="", max_length=2000)
    media_reviewed: bool = False


class PublishInput(Input):
    version: int = Field(ge=1)


class ExperimentInput(Input):
    asset_id: Short
    variable: Literal["hook"] = "hook"


class MetricInput(Input):
    label: Short
    impressions: int = Field(ge=0, le=1000000000)
    clicks: int = Field(ge=0, le=1000000000)
    conversions: int = Field(ge=0, le=1000000000)
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class StrategyEdit(Input):
    positioning: Text
    core_message: Text
    audience_summary: Text
    content_pillars: list[Short] = Field(min_length=1, max_length=8)


class TimelineEdit(Input):
    day: int = Field(ge=1, le=90)
    stage: Short
    platform: Literal["linkedin", "instagram", "x"]
    asset_type: Literal["post", "reel", "thread", "carousel", "story"]
    objective: Text


class MediaInput(GenerationInput):
    version: int = Field(ge=1)
    kind: Literal["image", "voiceover"]
    voice: Literal["en-US-JennyNeural", "en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-IN-NeerjaNeural", "en-IN-PrabhatNeural"] | None = None
