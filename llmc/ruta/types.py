from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class TraceEvent(TypedDict):
    run_id: str
    timestamp: str  # ISO8601
    step: int
    agent: str
    event: Literal["tool_call", "tool_result", "thought", "system", "error"]
    tool_name: str | None
    args: dict[str, Any] | None
    result_summary: dict[str, Any] | None
    latency_ms: float | None
    success: bool | None
    metadata: dict[str, Any] | None


class RunContext(TypedDict):
    run_id: str
    scenario_id: str
    start_time: str
    status: Literal["running", "completed", "failed"]


# --- Scenario Schema ---


class Property(BaseModel):
    name: str
    type: Literal["metamorphic", "assertion", "heuristic"]
    relation: str | None = None
    constraint: str


class SeverityPolicy(BaseModel):
    property_failures: dict[str, Literal["P0", "P1", "P2", "P3"]] = Field(
        default_factory=dict
    )


class Expectations(BaseModel):
    must_use_tools: list[str] = Field(default_factory=list)
    must_not_use_tools: list[str] = Field(default_factory=list)
    properties: list[Property] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    version: int = 1
    suite: str
    description: str
    goal: str
    interfaces: list[str]
    preconditions: dict[str, Any] = Field(default_factory=dict)
    # Flexible input data for the scenario (e.g., search queries, enrichment targets)
    queries: dict[str, Any] = Field(default_factory=dict)
    expectations: Expectations
    severity_policy: SeverityPolicy = Field(default_factory=SeverityPolicy)
