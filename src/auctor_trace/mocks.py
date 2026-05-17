from __future__ import annotations

import uuid

from auctor_trace.models import Artifact, ArtifactEdge, Mutation, ObservedRun, Scenario, ToolSpan


SYSTEMS = ("salesforce", "gong", "jira", "confluence", "sharepoint", "slack", "outlook", "teams", "meet")


def clone_artifacts(artifacts: list[Artifact]) -> dict[str, Artifact]:
    return {artifact.id: Artifact.model_validate(artifact.model_dump()) for artifact in artifacts}


def clone_edges(edges: list[ArtifactEdge]) -> list[ArtifactEdge]:
    return [ArtifactEdge.model_validate(edge.model_dump()) for edge in edges]


def span(
    trace_id: str,
    scenario_id: str,
    model: str,
    tick: int,
    system: str,
    operation: str,
    artifact_id: str,
    parent_span_id: str | None = None,
) -> ToolSpan:
    return ToolSpan(
        trace_id=trace_id,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=parent_span_id,
        scenario_id=scenario_id,
        model=model,
        tick=tick,
        system=system,
        operation=operation,
        artifact_id=artifact_id,
        expected_artifact_id=artifact_id,
        attributes={
            "otel.kind": "client",
            "component": f"mock.{system}",
            "agent.tool": operation,
        },
    )


def apply_mutation(artifacts: dict[str, Artifact], mutation: Mutation) -> None:
    current = artifacts[mutation.artifact_id]
    artifacts[mutation.artifact_id] = current.model_copy(
        update={"version": mutation.new_version, "content": mutation.new_content}
    )


def dependent_targets(scenario: Scenario, artifact_id: str) -> list[str]:
    return [
        edge.source
        for edge in scenario.edges
        if edge.target == artifact_id and edge.type.value in {"derives_from", "references", "depends_on", "supersedes"}
    ]


def run_mock_agent(scenario: Scenario, model: str, iteration: int) -> ObservedRun:
    artifacts = clone_artifacts(scenario.artifacts)
    edges = clone_edges(scenario.edges)
    spans: list[ToolSpan] = []
    scope_flags: list[str] = []
    trace_id = uuid.uuid4().hex
    duplicates = 0

    root_span = span(trace_id, scenario.id, model, 0, "agent", "plan", scenario.id)
    spans.append(root_span)

    for artifact_id in scenario.expected_order:
        artifact = artifacts[artifact_id]
        spans.append(
            span(trace_id, scenario.id, model, len(spans), artifact.system, "read", artifact.id, root_span.span_id)
        )

    for mutation in scenario.mutation_script:
        apply_mutation(artifacts, mutation)
        mutated = artifacts[mutation.artifact_id]
        spans.append(
            span(trace_id, scenario.id, model, mutation.tick, mutated.system, "external_mutation", mutated.id, root_span.span_id)
        )
        if mutation.scope_change and mutation.expected_flag:
            scope_flags.append(mutation.expected_flag)
        for target in dependent_targets(scenario, mutation.artifact_id):
            artifact = artifacts[target]
            next_content = f"{artifact.content} Refreshed from {mutation.artifact_id} v{mutation.new_version}."
            artifacts[target] = artifact.model_copy(update={"version": artifact.version + 1, "content": next_content})
            spans.append(
                span(trace_id, scenario.id, model, mutation.tick + 1, artifact.system, "propagate_update", artifact.id, root_span.span_id)
            )

    if model == "fast-but-loose-agent":
        duplicates = 1 if iteration % 2 == 0 else 0
        scope_flags = scope_flags[: max(0, len(scope_flags) - 1)]

    if model == "coherence-regression-agent":
        if scenario.mutation_script:
            changed = scenario.mutation_script[0].artifact_id
            stale_targets = dependent_targets(scenario, changed)
            if stale_targets:
                stale = artifacts[stale_targets[0]]
                artifacts[stale_targets[0]] = stale.model_copy(
                    update={"content": stale.content.replace("Refreshed", "Stale")}
                )
                edges = [edge for edge in edges if not (edge.source == stale.id and edge.target == changed)]
        scope_flags = []
        duplicates = 2

    return ObservedRun(
        scenario_id=scenario.id,
        model=model,
        artifacts=list(artifacts.values()),
        edges=edges,
        spans=spans,
        scope_flags=scope_flags,
        idempotency_duplicates=duplicates,
    )
