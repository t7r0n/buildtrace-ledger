from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class EdgeType(StrEnum):
    DERIVES_FROM = "derives_from"
    REFERENCES = "references"
    SUPERSEDES = "supersedes"
    DEPENDS_ON = "depends_on"


class Artifact(BaseModel):
    id: str
    system: str
    kind: str
    version: int = 1
    title: str
    content: str
    scope_tags: list[str] = Field(default_factory=list)


class ArtifactEdge(BaseModel):
    source: str
    target: str
    type: EdgeType


class Mutation(BaseModel):
    tick: int
    artifact_id: str
    new_version: int
    new_content: str
    scope_change: bool = False
    expected_flag: str | None = None


class Scenario(BaseModel):
    id: str
    title: str
    description: str
    artifacts: list[Artifact]
    edges: list[ArtifactEdge]
    mutation_script: list[Mutation]
    expected_order: list[str]
    expected_scope_flags: list[str]
    regression_expected_for: list[str] = Field(default_factory=list)


class ToolSpan(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    scenario_id: str
    model: str
    tick: int
    system: str
    operation: str
    artifact_id: str
    expected_artifact_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ObservedRun(BaseModel):
    scenario_id: str
    model: str
    artifacts: list[Artifact]
    edges: list[ArtifactEdge]
    spans: list[ToolSpan]
    scope_flags: list[str]
    idempotency_duplicates: int


class Score(BaseModel):
    coherence: float
    temporal: float
    idempotency: float
    scope_precision: float
    scope_recall: float
    bug_detected: bool


class ScenarioResult(BaseModel):
    run_id: str
    scenario: Scenario
    observed: ObservedRun
    score: Score


class RunSummary(BaseModel):
    run_id: str
    result_count: int
    scenario_count: int
    models: list[str]
    leaderboard: list[dict[str, Any]]
    seeded_bug_precision: float
    seeded_bugs_detected: int
    seeded_bugs_expected: int
    baseline_false_positives: int
    runtime_seconds: float


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
