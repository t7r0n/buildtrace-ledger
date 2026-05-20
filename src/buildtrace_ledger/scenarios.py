from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from buildtrace_ledger.models import Scenario, project_root


class ScenarioFile(BaseModel):
    scenarios: list[Scenario]


def scenario_path() -> Path:
    return project_root() / "scenarios" / "implementation_scenarios.json"


def load_scenarios(path: Path | None = None) -> list[Scenario]:
    target = path or scenario_path()
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return ScenarioFile.model_validate(payload).scenarios
