"""Fake, read-only MCP-compatible tool server over the synthetic scenario fixtures.

Only the tool proxy may call `call()`. The invocation counter lets tests prove that a DENIED
request never reached the server (spec 06 invariant 3).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from backend.tools.catalog import CATALOG

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


class ToolUnavailable(Exception):
    pass


class ToolTimeout(Exception):
    pass


def load_scenarios() -> dict[str, dict]:
    out = {}
    for path in sorted((FIXTURES / "scenarios").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[path.stem] = data
    return out


class FakeMCPServer:
    def __init__(self, scenarios: dict[str, dict] | None = None) -> None:
        self.scenarios = scenarios or load_scenarios()
        self.invocations: Counter[str] = Counter()
        self.fail_modes: dict[str, str] = {}  # tool_id -> "timeout"

    def _data_for(self, case_scenario: str) -> dict[str, Any]:
        return self.scenarios.get(case_scenario, {}).get("tool_data", {})

    def call(self, scenario_id: str, tool_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.invocations[tool_id] += 1
        spec = CATALOG.get(tool_id)
        if spec is None:
            raise ToolUnavailable(f"unknown tool {tool_id}")
        if self.fail_modes.get(tool_id) == "timeout":
            raise ToolTimeout(f"{tool_id} timed out (fixture fail_mode)")
        table = self._data_for(scenario_id).get(tool_id, {})
        key = "|".join(str(arguments.get(k)) for k in spec.key_args)
        record = table.get(key) or table.get("*")
        if record is None or record.get("__unavailable__"):
            raise ToolUnavailable(f"{tool_id}: no record for {key}")
        return {"tool_id": tool_id, "source_ref": spec.source_ref, "data_category": spec.data_category, "record": record}

    @property
    def total_invocations(self) -> int:
        return sum(self.invocations.values())
