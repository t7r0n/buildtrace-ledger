# Cross-System Coherence Harness

A local evaluation harness for implementation agents that generate and update artifacts across enterprise systems. It replays synthetic implementation scenarios, records OpenTelemetry-shaped tool traces, scores the final artifact graph, and produces a visual report.

The harness grades four axes:

- artifact coherence across systems
- temporal correctness of dependent writes
- idempotency under reruns
- scope-change detection precision and recall

Everything runs locally with synthetic fixtures. No external APIs, credentials, customer data, or hosted tracing backend are required.

## Quick Start

```bash
uv sync
uv run auctor-trace init-demo
uv run auctor-trace run --iterations 3
uv run auctor-trace verify
uv run auctor-trace dashboard
```

Generated artifacts are written under `runs/` and `outputs/`.

## Outputs

- `runs/latest/results.duckdb` stores scenario, model, trace, and score rows
- `outputs/summary.json` stores the leaderboard and regression report
- `outputs/traces.jsonl` stores OpenTelemetry-shaped spans
- `outputs/dashboard.html` gives a self-contained visual Gantt and finding summary
- `outputs/demo_pack/` is a portable evidence bundle
