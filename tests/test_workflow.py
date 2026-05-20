from __future__ import annotations

from pathlib import Path

from buildtrace_ledger.dashboard import build_dashboard
from buildtrace_ledger.mocks import run_mock_agent
from buildtrace_ledger.runner import init_demo, run_suite, verify_outputs
from buildtrace_ledger.scenarios import load_scenarios
from buildtrace_ledger.scorer import build_graph, score_run


def test_end_to_end_run_and_verify() -> None:
    init_demo(force=True)
    summary = run_suite(iterations=3)
    report = verify_outputs()
    assert summary.result_count >= 45
    assert summary.seeded_bug_precision >= 0.95
    assert report["passed"] is True


def test_reference_agent_scores_cleanly() -> None:
    scenario = load_scenarios()[0]
    observed = run_mock_agent(scenario, "reference-agent", 0)
    score = score_run(scenario, observed)
    assert score.coherence >= 0.92
    assert score.temporal == 1.0
    assert score.bug_detected is False


def test_regression_agent_breaks_coherence() -> None:
    scenario = load_scenarios()[0]
    observed = run_mock_agent(scenario, "coherence-regression-agent", 0)
    score = score_run(scenario, observed)
    assert score.coherence < 0.92
    assert score.bug_detected is True


def test_graph_builder_preserves_typed_edges() -> None:
    scenario = load_scenarios()[0]
    graph = build_graph(scenario.artifacts, scenario.edges)
    assert graph.has_edge("jira-100", "sow-100")
    assert graph["jira-100"]["sow-100"]["type"] == "references"


def test_dashboard_contains_visual_gantt_and_gates() -> None:
    init_demo(force=True)
    run_suite(iterations=3)
    path = build_dashboard()
    html = Path(path).read_text(encoding="utf-8")
    assert "Trace Gantt Sample" in html
    assert "Quality Floor" in html
    assert "Verification passed" in html
