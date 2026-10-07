from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AskRequest(StrictModel):
    question: str = Field(min_length=3, max_length=1000)


class Citation(StrictModel):
    policy_id: str
    title: str
    section: str
    version: str
    excerpt: str
    source: str


class AskResponse(StrictModel):
    trace_id: str
    intent: str
    risk: str
    status: Literal["answered", "needs_clarification", "blocked", "degraded"]
    answer: str
    data: dict = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    suggested_action: dict | None = None
    warnings: list[str] = Field(default_factory=list)


class ProposalRequest(StrictModel):
    action: Literal["support_case", "escalation", "replacement_recommendation"]
    vehicle_id: str = Field(pattern=r"^V-\d{3}$")
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[\w-]+$")


class DecisionRequest(StrictModel):
    decision: Literal["approve", "reject"]


class FeedbackRequest(StrictModel):
    trace_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    score: int = Field(ge=1, le=5)
