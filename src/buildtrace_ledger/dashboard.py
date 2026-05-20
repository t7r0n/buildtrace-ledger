from __future__ import annotations

from pathlib import Path

import duckdb
from jinja2 import Environment, select_autoescape

from buildtrace_ledger.models import RunSummary, project_root
from buildtrace_ledger.runner import verify_outputs

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cross-System Coherence Dashboard</title>
  <style>
    :root { color-scheme: light dark; --bg:#f7f8fb; --panel:#fff; --ink:#172033; --muted:#64748b; --line:#d9e2ef; --blue:#2663eb; --green:#0e9f6e; --amber:#d97706; --red:#c2410c; }
    @media (prefers-color-scheme: dark) { :root { --bg:#0f141d; --panel:#171e2b; --ink:#eef4ff; --muted:#9aa8bc; --line:#2b374b; --blue:#7aa2ff; --green:#38c989; --amber:#f6b955; --red:#ff9363; } }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width:1200px; margin:0 auto; padding:32px 20px 52px; }
    header { display:flex; justify-content:space-between; align-items:flex-end; gap:20px; margin-bottom:24px; }
    h1 { font-size:28px; margin:0 0 8px; letter-spacing:0; }
    h2 { font-size:18px; margin:0 0 14px; }
    p { color:var(--muted); margin:0; }
    .grid { display:grid; gap:16px; }
    .metrics { grid-template-columns:repeat(4, minmax(0, 1fr)); }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px; box-shadow:0 14px 28px rgba(15,23,42,.06); }
    .metric strong { display:block; font-size:26px; line-height:1.1; }
    .metric span { color:var(--muted); font-size:13px; }
    .charts { grid-template-columns:1fr 1fr; margin-top:16px; }
    .bar-row { display:grid; grid-template-columns:190px 1fr 52px; gap:12px; align-items:center; margin:12px 0; }
    .track { height:18px; border-radius:999px; background:color-mix(in srgb, var(--line) 75%, transparent); overflow:hidden; border:1px solid var(--line); }
    .fill { height:100%; border-radius:999px; background:linear-gradient(90deg, var(--blue), var(--green)); min-width:2px; }
    .gantt { display:grid; gap:8px; }
    .lane { display:grid; grid-template-columns:120px 1fr; gap:10px; align-items:center; }
    .timeline { height:18px; border-radius:999px; background:var(--line); position:relative; overflow:hidden; }
    .segment { position:absolute; height:100%; border-radius:999px; background:var(--blue); left:var(--left); width:var(--width); }
    .segment.bad { background:var(--red); }
    table { width:100%; border-collapse:collapse; font-size:14px; margin-top:8px; }
    th, td { text-align:left; padding:10px 8px; border-bottom:1px solid var(--line); }
    th { color:var(--muted); font-weight:600; }
    .pass { color:var(--green); font-weight:700; }
    .fail { color:var(--red); font-weight:700; }
    @media (max-width: 780px) { header { display:block; } .metrics, .charts { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Cross-System Coherence Dashboard</h1>
      <p>Run {{ summary.run_id }} · graph-state scoring, temporal replay, idempotency, and scope-change detection.</p>
    </div>
    <p class="{{ 'pass' if verification.passed else 'fail' }}">{{ 'Verification passed' if verification.passed else 'Verification failed' }}</p>
  </header>
  <section class="grid metrics">
    <div class="panel metric"><strong>{{ summary.result_count }}</strong><span>scenario-model results</span></div>
    <div class="panel metric"><strong>{{ summary.scenario_count }}</strong><span>implementation scenarios</span></div>
    <div class="panel metric"><strong>{{ '%.0f'|format(summary.seeded_bug_precision * 100) }}%</strong><span>seeded bug precision</span></div>
    <div class="panel metric"><strong>{{ summary.baseline_false_positives }}</strong><span>baseline false positives</span></div>
  </section>
  <section class="grid charts">
    <div class="panel">
      <h2>Quality Floor</h2>
      {% for row in summary.leaderboard %}
        <div class="bar-row"><strong>{{ row.model }}</strong><div class="track"><div class="fill" style="width: {{ row.quality_floor * 100 }}%"></div></div><span>{{ '%.2f'|format(row.quality_floor) }}</span></div>
      {% endfor %}
    </div>
    <div class="panel">
      <h2>Trace Gantt Sample</h2>
      <div class="gantt">
        {% for row in gantt %}
          <div class="lane"><span>{{ row.system }}</span><div class="timeline"><div class="segment {{ 'bad' if row.bad else '' }}" style="--left: {{ row.left }}%; --width: {{ row.width }}%"></div></div></div>
        {% endfor %}
      </div>
    </div>
  </section>
  <section class="panel" style="margin-top:16px">
    <h2>Leaderboard</h2>
    <table>
      <thead><tr><th>Model</th><th>Coherence</th><th>Temporal</th><th>Idempotency</th><th>Scope P</th><th>Scope R</th><th>Bugs</th></tr></thead>
      <tbody>
      {% for row in summary.leaderboard %}
        <tr><td>{{ row.model }}</td><td>{{ row.coherence }}</td><td>{{ row.temporal }}</td><td>{{ row.idempotency }}</td><td>{{ row.scope_precision }}</td><td>{{ row.scope_recall }}</td><td>{{ row.bugs }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </section>
  <section class="panel" style="margin-top:16px">
    <h2>Verification Gates</h2>
    <table><tbody>
      {% for key, value in verification.checks.items() %}
        <tr><td>{{ key }}</td><td class="{{ 'pass' if value else 'fail' }}">{{ value }}</td></tr>
      {% endfor %}
    </tbody></table>
  </section>
</main>
</body>
</html>
"""


def gantt_rows() -> list[dict[str, object]]:
    root = project_root()
    trace_path = root / "outputs" / "traces.jsonl"
    if not trace_path.exists():
        return []
    rows: list[dict[str, object]] = []
    systems: dict[str, list[int]] = {}
    for line in trace_path.read_text(encoding="utf-8").splitlines()[:200]:
        if not line:
            continue
        import json

        span = json.loads(line)
        systems.setdefault(span["system"], []).append(int(span["tick"]))
    max_tick = max((max(ticks) for ticks in systems.values()), default=1)
    for system, ticks in sorted(systems.items()):
        left = min(ticks) / max_tick * 100
        width = max((max(ticks) - min(ticks)) / max_tick * 100, 4)
        rows.append({"system": system, "left": round(left, 2), "width": round(width, 2), "bad": system == "agent"})
    return rows[:9]


def build_dashboard() -> Path:
    root = project_root()
    summary_path = root / "outputs" / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError("Run `uv run buildtrace-ledger run` before dashboard generation.")
    summary = RunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    html = env.from_string(TEMPLATE).render(summary=summary, verification=verify_outputs(), gantt=gantt_rows())
    target = root / "outputs" / "dashboard.html"
    target.write_text(html, encoding="utf-8")
    return target


def benchmark_summary() -> dict[str, float]:
    root = project_root()
    db_path = root / "runs" / "latest" / "results.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Run `uv run buildtrace-ledger run` first.")
    conn = duckdb.connect(str(db_path), read_only=True)
    row = conn.execute("select avg(span_count), avg(artifact_count), count(*) from results").fetchone()
    conn.close()
    return {"avg_spans": float(row[0]), "avg_artifacts": float(row[1]), "rows": float(row[2])}
