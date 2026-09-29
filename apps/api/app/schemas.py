from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
Claim = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


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


class AssetInput(Input):
    platform: Literal["linkedin", "instagram", "x"]
    asset_type: Literal["post", "reel", "thread", "carousel", "story"]
    demonstrate_failure: bool = False

    @field_validator("platform", mode="before")
    @classmethod
    def platform_lower(cls, value):
        return value.lower() if isinstance(value, str) else value


class EditInput(Input):
    hook: Text
    body: Text
    cta: Text


class RegenerateInput(Input):
    section: Literal["all", "hook", "cta"] = "all"


class ApprovalInput(Input):
    version: int = Field(ge=1)
    feedback: str = Field(default="", max_length=2000)


class PublishInput(Input):
    version: int = Field(ge=1)


class ExperimentInput(Input):
    asset_id: Short
    variable: Literal["hook"] = "hook"
