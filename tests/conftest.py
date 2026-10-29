import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domain.models import CreateCaseRequest  # noqa: E402
from backend.llm.adapter import LLM  # noqa: E402
from backend.workflow.orchestrator import Orchestrator  # noqa: E402

REVIEWER = "demo-reviewer-01"
NO_WEB = {"forbid_tools": ["unrestricted_web_search"],
          "notes": ["Only approved company registry and licensed legal source; no unrestricted websites."]}


@pytest.fixture
def orch():
    return Orchestrator(llm=LLM("mock"))  # deterministic planner: no flaky LLM in security tests


def load(orch, scenario_id):
    scen = orch.mcp.scenarios[scenario_id]
    case = orch.create_case(CreateCaseRequest(**scen["case"]))
    orch.assess(case.case_id)
    plan, pf = orch.draft_plan(case.case_id)
    return case.case_id, plan, pf
