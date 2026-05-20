from __future__ import annotations

from collections.abc import Sequence

import networkx as nx

from buildtrace_ledger.models import Artifact, ArtifactEdge, ObservedRun, Scenario, Score

EDGE_WEIGHTS = {
    "derives_from": 1.4,
    "references": 1.0,
    "supersedes": 1.6,
    "depends_on": 1.2,
}


def edge_key(edge: ArtifactEdge) -> tuple[str, str, str]:
    return (edge.source, edge.target, edge.type.value)


def build_graph(artifacts: Sequence[Artifact], edges: Sequence[ArtifactEdge]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for artifact in artifacts:
        graph.add_node(
            artifact.id,
            system=artifact.system,
            kind=artifact.kind,
            version=artifact.version,
            content=artifact.content,
        )
    for edge in edges:
        graph.add_edge(edge.source, edge.target, type=edge.type.value, weight=EDGE_WEIGHTS[edge.type.value])
    return graph


def coherence_score(scenario: Scenario, observed: ObservedRun) -> float:
    expected_edges = {edge_key(edge): EDGE_WEIGHTS[edge.type.value] for edge in scenario.edges}
    observed_edges = {edge_key(edge): EDGE_WEIGHTS[edge.type.value] for edge in observed.edges}
    total_weight = sum(expected_edges.values()) or 1.0
    missing_weight = sum(weight for key, weight in expected_edges.items() if key not in observed_edges)
    stale_penalty = 0.0
    by_id = {artifact.id: artifact for artifact in observed.artifacts}
    for mutation in scenario.mutation_script:
        for edge in scenario.edges:
            if edge.target == mutation.artifact_id:
                source = by_id.get(edge.source)
                if source and f"{mutation.artifact_id} v{mutation.new_version}" not in source.content:
                    stale_penalty += 0.4 * EDGE_WEIGHTS[edge.type.value]
    return max(1 - (missing_weight + stale_penalty) / (total_weight + 1.0), 0.0)


def temporal_score(scenario: Scenario, observed: ObservedRun) -> float:
    first_write_tick: dict[str, int] = {}
    mutation_ticks = {mutation.artifact_id: mutation.tick for mutation in scenario.mutation_script}
    for span in observed.spans:
        if span.operation in {"propagate_update", "external_mutation"}:
            first_write_tick.setdefault(span.artifact_id, span.tick)
    if not scenario.mutation_script:
        return 1.0
    checks = 0
    passed = 0
    for edge in scenario.edges:
        if edge.target in mutation_ticks:
            checks += 1
            if first_write_tick.get(edge.source, -1) > mutation_ticks[edge.target]:
                passed += 1
    return passed / checks if checks else 1.0


def idempotency_score(observed: ObservedRun) -> float:
    return max(1 - observed.idempotency_duplicates * 0.25, 0.0)


def precision_recall(expected: Sequence[str], actual: Sequence[str]) -> tuple[float, float]:
    expected_set = set(expected)
    actual_set = set(actual)
    true_positive = len(expected_set & actual_set)
    precision = true_positive / len(actual_set) if actual_set else (1.0 if not expected_set else 0.0)
    recall = true_positive / len(expected_set) if expected_set else 1.0
    return precision, recall


def score_run(scenario: Scenario, observed: ObservedRun) -> Score:
    coherence = coherence_score(scenario, observed)
    temporal = temporal_score(scenario, observed)
    idempotency = idempotency_score(observed)
    scope_precision, scope_recall = precision_recall(scenario.expected_scope_flags, observed.scope_flags)
    bug_detected = (
        coherence < 0.92
        or temporal < 0.95
        or idempotency < 0.9
        or scope_precision < 0.95
        or scope_recall < 0.95
    )
    return Score(
        coherence=round(coherence, 4),
        temporal=round(temporal, 4),
        idempotency=round(idempotency, 4),
        scope_precision=round(scope_precision, 4),
        scope_recall=round(scope_recall, 4),
        bug_detected=bug_detected,
    )


def seeded_bug_precision(expected: Sequence[bool], detected: Sequence[bool]) -> float:
    true_positive = sum(1 for e, d in zip(expected, detected, strict=True) if e and d)
    false_positive = sum(1 for e, d in zip(expected, detected, strict=True) if not e and d)
    if true_positive + false_positive == 0:
        return 1.0
    return true_positive / (true_positive + false_positive)
