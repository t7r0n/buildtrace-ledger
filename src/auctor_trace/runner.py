from __future__ import annotations

import shutil
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import duckdb

from auctor_trace.mocks import run_mock_agent
from auctor_trace.models import RunSummary, ScenarioResult, project_root
from auctor_trace.scenarios import load_scenarios
from auctor_trace.scorer import score_run, seeded_bug_precision

MODELS = ("reference-agent", "fast-but-loose-agent", "coherence-regression-agent")


def init_demo(force: bool = False) -> dict[str, str]:
    root = project_root()
    for name in ("data", "runs", "outputs"):
        path = root / name
        if force and path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    return {"scenarios": str(root / "scenarios" / "implementation_scenarios.json"), "outputs": str(root / "outputs")}


def connect_store(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    conn.execute(
        """
        create table if not exists results (
          run_id varchar,
          scenario_id varchar,
          model varchar,
          coherence double,
          temporal double,
          idempotency double,
          scope_precision double,
          scope_recall double,
          bug_detected boolean,
          expected_bug boolean,
          span_count integer,
          artifact_count integer
        )
        """
    )
    return conn


def persist(conn: duckdb.DuckDBPyConnection, result: ScenarioResult) -> None:
    conn.execute(
        "insert into results values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            result.run_id,
            result.scenario.id,
            result.observed.model,
            result.score.coherence,
            result.score.temporal,
            result.score.idempotency,
            result.score.scope_precision,
            result.score.scope_recall,
            result.score.bug_detected,
            result.observed.model in result.scenario.regression_expected_for,
            len(result.observed.spans),
            len(result.observed.artifacts),
        ],
    )


def summarize(run_id: str, results: list[ScenarioResult], runtime_seconds: float) -> RunSummary:
    by_model: dict[str, list[ScenarioResult]] = defaultdict(list)
    expected: list[bool] = []
    detected: list[bool] = []
    for result in results:
        by_model[result.observed.model].append(result)
        expected.append(result.observed.model in result.scenario.regression_expected_for)
        detected.append(result.score.bug_detected)
    leaderboard: list[dict[str, Any]] = []
    for model, items in by_model.items():
        coherence = sum(item.score.coherence for item in items) / len(items)
        temporal = sum(item.score.temporal for item in items) / len(items)
        idempotency = sum(item.score.idempotency for item in items) / len(items)
        scope_precision = sum(item.score.scope_precision for item in items) / len(items)
        scope_recall = sum(item.score.scope_recall for item in items) / len(items)
        quality = min(coherence, temporal, idempotency, scope_precision, scope_recall)
        leaderboard.append(
            {
                "model": model,
                "coherence": round(coherence, 4),
                "temporal": round(temporal, 4),
                "idempotency": round(idempotency, 4),
                "scope_precision": round(scope_precision, 4),
                "scope_recall": round(scope_recall, 4),
                "quality_floor": round(quality, 4),
                "bugs": sum(1 for item in items if item.score.bug_detected),
                "scenarios": len(items),
            }
        )
    leaderboard.sort(key=lambda item: item["quality_floor"], reverse=True)
    return RunSummary(
        run_id=run_id,
        result_count=len(results),
        scenario_count=len({result.scenario.id for result in results}),
        models=sorted(by_model),
        leaderboard=leaderboard,
        seeded_bug_precision=round(seeded_bug_precision(expected, detected), 4),
        seeded_bugs_detected=sum(1 for item in detected if item),
        seeded_bugs_expected=sum(1 for item in expected if item),
        baseline_false_positives=sum(1 for e, d in zip(expected, detected, strict=True) if not e and d),
        runtime_seconds=round(runtime_seconds, 4),
    )


def run_suite(iterations: int = 3, models: tuple[str, ...] = MODELS) -> RunSummary:
    init_demo()
    root = project_root()
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    run_dir = root / "runs" / "latest"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    conn = connect_store(run_dir / "results.duckdb")
    trace_path = root / "outputs" / "traces.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    if trace_path.exists():
        trace_path.unlink()
    started = time.perf_counter()
    scenarios = load_scenarios()
    results: list[ScenarioResult] = []
    with trace_path.open("w", encoding="utf-8") as trace_file:
        for iteration in range(iterations):
            for scenario in scenarios:
                for model in models:
                    observed = run_mock_agent(scenario, model, iteration)
                    score = score_run(scenario, observed)
                    result = ScenarioResult(run_id=run_id, scenario=scenario, observed=observed, score=score)
                    persist(conn, result)
                    for span in observed.spans:
                        trace_file.write(span.model_dump_json() + "\n")
                    results.append(result)
    conn.close()
    summary = summarize(run_id, results, time.perf_counter() - started)
    (root / "outputs" / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return summary


def verify_outputs() -> dict[str, Any]:
    root = project_root()
    summary_path = root / "outputs" / "summary.json"
    trace_path = root / "outputs" / "traces.jsonl"
    db_path = root / "runs" / "latest" / "results.duckdb"
    if not summary_path.exists() or not trace_path.exists() or not db_path.exists():
        raise FileNotFoundError("Run `uv run auctor-trace run` before verification.")
    summary = RunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
    conn = duckdb.connect(str(db_path), read_only=True)
    result_count = conn.execute("select count(*) from results").fetchone()[0]
    baseline_false_positives = conn.execute(
        "select count(*) from results where bug_detected = true and expected_bug = false"
    ).fetchone()[0]
    conn.close()
    trace_count = sum(1 for _ in trace_path.open("r", encoding="utf-8"))
    checks = {
        "required_outputs_present": summary_path.exists() and trace_path.exists() and db_path.exists(),
        "at_least_forty_five_results": result_count >= 45,
        "otel_shaped_traces_present": trace_count >= result_count,
        "seeded_bug_precision_at_least_0_95": summary.seeded_bug_precision >= 0.95,
        "zero_baseline_false_positives": baseline_false_positives == 0,
        "runtime_under_90_seconds_per_scenario": summary.runtime_seconds / max(result_count, 1) < 90,
    }
    return {
        "run_id": summary.run_id,
        "result_count": result_count,
        "trace_count": trace_count,
        "leaderboard": summary.leaderboard,
        "checks": checks,
        "passed": all(checks.values()),
    }


def export_demo_pack() -> Path:
    root = project_root()
    pack = root / "outputs" / "demo_pack"
    if pack.exists():
        shutil.rmtree(pack)
    pack.mkdir(parents=True, exist_ok=True)
    for name in ("summary.json", "traces.jsonl", "dashboard.html"):
        source = root / "outputs" / name
        if source.exists():
            shutil.copy2(source, pack / name)
    shutil.copy2(root / "scenarios" / "implementation_scenarios.json", pack / "implementation_scenarios.json")
    return pack
