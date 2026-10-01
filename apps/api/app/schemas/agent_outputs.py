from pydantic import BaseModel, ConfigDict, Field
from . import Short, Text

class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Direction(Output):
    id: Short
    name: Short
    description: Text
    rationale: Text

class Strategy(Output):
    positioning: Text
    core_message: Text
    audience_summary: Text
    content_pillars: list[Short] = Field(min_length=1, max_length=8)
    assumptions: list[Short] = Field(max_length=15)
    source_refs: list[Short] = Field(min_length=1, max_length=8)

class Directions(Output):
    creative_directions: list[Direction] = Field(min_length=3, max_length=3)

class Content(Output):
    hook: Text
    body: Text
    cta: Text
    caption: str = Field(default="", max_length=10000)
    source_refs: list[Short] = Field(min_length=1, max_length=8)

class Evaluation(Output):
    passed: bool
    issues: list[Short] = Field(max_length=20)
    checks: dict[str, bool]

class TimelineItem(Output):
    day: int = Field(ge=1, le=90)
    stage: Short
    platform: Short
    asset_type: Short
    objective: Text

class Timeline(Output):
    items: list[TimelineItem] = Field(min_length=1, max_length=90)

class Learning(Output):
    statement: Text
    evidence: Text
    confidence: float = Field(ge=0, le=1)

class Observations(Output):
    observations: list[Text] = Field(min_length=1, max_length=8)

class VisualPlan(Output):
    prompt: Text
    alt_text: Short

class Narration(Output):
    script: str = Field(min_length=1, max_length=6000)
    source_refs: list[Short] = Field(min_length=1, max_length=8)

