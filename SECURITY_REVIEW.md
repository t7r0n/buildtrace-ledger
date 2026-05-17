# Security Review

## Scope

Local CLI, synthetic scenario fixtures, graph scorer, DuckDB result store, JSONL trace export, and generated static dashboard.

## Current Assessment

The application is offline by design. It has no network clients, no server runtime, no subprocess execution, no credential handling, and no external integration calls. Integration systems are modeled as deterministic in-memory mocks.

## Controls

- Scenario JSON is parsed into Pydantic models before execution.
- Results are written with parameterized DuckDB inserts.
- The dashboard uses Jinja autoescaping and local summary data only.
- Runtime state, generated outputs, virtual environments, and caches are ignored by git.

## Focused Scan

Reviewed command execution, network access, unsafe deserialization, generated dashboard rendering, trace export, and public-repository hygiene. Package code contains no subprocess calls, shell execution, sockets, HTTP clients, pickle, dynamic evaluation, credential loading, or global configuration edits. Local file reads and writes are limited to validated scenario JSON, `runs/`, and `outputs/`.

## Attack-Path Analysis

The realistic attacker-controlled surface is a local scenario file. Scenario fields can affect JSONL traces and dashboard text, but they are validated with Pydantic and rendered through Jinja autoescaping. Scenario text cannot reach a shell, a network client, a privileged file path, or credential material. Generated runtime files are excluded from the public repo.

## Review Status

Passed focused local security review on 2026-05-17. No high-impact attacker-reachable path identified.
