# Cross-System Coherence Harness

A local evaluation harness for implementation agents that generate and update artifacts across enterprise systems. It replays synthetic implementation scenarios, records OpenTelemetry-shaped tool traces, scores the final artifact graph, and produces a visual report.

The harness grades four axes:

## Problem shape

Local cross-system coherence harness for implementation agents.

## What the harness exercises

- Replays the main `auctor-trace` scenario from source-controlled fixtures.
- Pushes degraded `Cross-System Coherence Harness` cases through the same path as clean cases, then compares the evidence.
- Frames `Cross-System Coherence Harness` as a working evaluator rather than a static concept mock.
- Leaves `auctor-trace` generated state outside git while keeping the rebuild path short.

## Local workflow

```bash
uv sync
uv run auctor-trace init-demo
uv run auctor-trace run --iterations 3
uv run auctor-trace verify
uv run auctor-trace dashboard
```

## Review surfaces

- `runs/latest/results.duckdb` stores scenario, model, trace, and score rows
- `outputs/summary.json` stores the leaderboard and regression report
- `outputs/traces.jsonl` stores OpenTelemetry-shaped spans
- `outputs/dashboard.html` gives a self-contained visual Gantt and finding summary
- `outputs/demo_pack/` is a portable evidence bundle

## Quality checks

```bash
uv run ruff check .
uv run pytest -q
uv run auctor-trace verify
```

## Repository hygiene

`Cross-System Coherence Harness` is built for local reproduction: deterministic inputs enter the run, deterministic evidence comes out, and private data stays outside the repo.
