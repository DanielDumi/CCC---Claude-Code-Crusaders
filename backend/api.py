"""HTTP API (spec 05 §7) + the static review UI.

Run:  python -m uvicorn backend.api:app --port 8000      (or: python run.py)
Reviewer identity for the demo comes from the X-Reviewer-Id header (users in fixtures/users.json).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.domain.models import (
    Approval, Assessment, Case, CreateCaseRequest, Evidence, FinalReview, InvestigationPlan, PlanDecision, Preflight,
)
from backend.security.policy_engine import preflight
from backend.evidence.pack_builder import build_pack, render_markdown, verify_pack
from backend.storage.repository import Repository, verify_jsonl
from backend.util import to_plain
from backend.workflow.orchestrator import AuthError, Orchestrator, WorkflowError
from backend.workflow.state_machine import InvalidTransition

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"

app = FastAPI(title="Agent Assurance", version="0.1.0",
              description="Human-approved, policy-gated verification of banking AI agent findings (synthetic demo).")
ORCH = Orchestrator(Repository(os.environ.get("AA_DB", ":memory:")))


def _ok(data: Any) -> JSONResponse:
    return JSONResponse(to_plain(data))


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AuthError as exc:
        raise HTTPException(403, str(exc))
    except (WorkflowError, InvalidTransition) as exc:
        raise HTTPException(409, str(exc))


def _reviewer(x_reviewer_id: Optional[str]) -> str:
    if not x_reviewer_id:
        raise HTTPException(401, "X-Reviewer-Id header required")
    return x_reviewer_id


# ---------------------------------------------------------------- spec 05 §7
@app.post("/cases")
def create_case(req: CreateCaseRequest, x_reviewer_id: Optional[str] = Header(None)):
    _call(ORCH.user, _reviewer(x_reviewer_id), req.case_id)
    return _ok(_call(ORCH.create_case, req))


@app.get("/cases/{case_id}")
def get_case(case_id: str, x_reviewer_id: Optional[str] = Header(None)):
    _call(ORCH.user, _reviewer(x_reviewer_id), case_id)
    return _ok(view(case_id))


@app.post("/cases/{case_id}/assess")
def assess(case_id: str, x_reviewer_id: Optional[str] = Header(None)):
    _call(ORCH.user, _reviewer(x_reviewer_id), case_id)
    return _ok(_call(ORCH.assess, case_id))


class PlanRequest(BaseModel):
    restrictions: dict[str, Any] = {}


@app.post("/cases/{case_id}/plans")
def new_plan(case_id: str, body: PlanRequest = Body(PlanRequest()), x_reviewer_id: Optional[str] = Header(None)):
    _call(ORCH.user, _reviewer(x_reviewer_id), case_id)
    plan, pf = _call(ORCH.draft_plan, case_id, body.restrictions)
    return _ok({"plan": plan, "preflight": pf})


@app.post("/plans/{plan_id}/preflight")
def rerun_preflight(plan_id: str, x_reviewer_id: Optional[str] = Header(None)):
    plan = ORCH.repo.get(InvestigationPlan, plan_id)
    if not plan:
        raise HTTPException(404, "unknown plan")
    case = ORCH.case(plan.case_id)
    _call(ORCH.user, _reviewer(x_reviewer_id), case.case_id)
    pf = preflight(plan, case, ORCH.policy, calls_used=case.tool_calls_used)
    ORCH.repo.put(pf)
    ORCH.repo.append_event(case.case_id, "PREFLIGHT_COMPLETED", "SYSTEM", "policy-preflight",
                           f"{pf.status.value} (re-run)", [pf.preflight_id, plan_id])
    return _ok(pf)


class DecisionRequest(BaseModel):
    decision: PlanDecision
    plan_hash: Optional[str] = None
    restrictions: dict[str, Any] = {}
    reason: str = ""


@app.post("/plans/{plan_id}/decisions")
def decide(plan_id: str, body: DecisionRequest, x_reviewer_id: Optional[str] = Header(None)):
    out = _call(ORCH.decide_plan, plan_id, _reviewer(x_reviewer_id), body.decision,
                restrictions=body.restrictions, reason=body.reason, plan_hash=body.plan_hash)
    return _ok(out)


@app.post("/plans/{plan_id}/compliance")
def compliance(plan_id: str, note: str = Body("", embed=True), x_reviewer_id: Optional[str] = Header(None)):
    _call(ORCH.request_compliance, plan_id, _reviewer(x_reviewer_id), note)
    return _ok({"ok": True})


@app.post("/cases/{case_id}/execute")
def execute(case_id: str, x_reviewer_id: Optional[str] = Header(None)):
    _call(ORCH.user, _reviewer(x_reviewer_id), case_id)
    return _ok(_call(ORCH.execute, case_id))


@app.get("/cases/{case_id}/events")
def events(case_id: str, x_reviewer_id: Optional[str] = Header(None)):
    _call(ORCH.user, _reviewer(x_reviewer_id), case_id)
    return _ok(ORCH.repo.events(case_id))


class FinalRequest(BaseModel):
    decision: FinalReview
    note: str = ""
    acknowledge_unresolved: bool = False


@app.post("/cases/{case_id}/final-review")
def final_review(case_id: str, body: FinalRequest, x_reviewer_id: Optional[str] = Header(None)):
    return _ok(_call(ORCH.final_review, case_id, _reviewer(x_reviewer_id), body.decision, body.note,
                     body.acknowledge_unresolved))


@app.get("/cases/{case_id}/pack")
def pack(case_id: str, x_reviewer_id: Optional[str] = Header(None)):
    _call(ORCH.user, _reviewer(x_reviewer_id), case_id)
    return _ok(build_pack(ORCH, case_id))


@app.get("/cases/{case_id}/pack.md", response_class=PlainTextResponse)
def pack_md(case_id: str, reviewer: str = "demo-reviewer-01"):
    _call(ORCH.user, reviewer, case_id)
    return render_markdown(build_pack(ORCH, case_id))


@app.post("/packs/verify")
def pack_verify(pack_body: dict = Body(...)):
    return _ok(verify_pack(pack_body))


@app.get("/cases/{case_id}/ledger.jsonl", response_class=PlainTextResponse)
def ledger(case_id: str, reviewer: str = "demo-reviewer-01"):
    _call(ORCH.user, reviewer, case_id)
    return ORCH.repo.export_jsonl(case_id)


@app.post("/ledger/verify")
def ledger_verify(text: str = Body(..., media_type="text/plain")):
    return _ok(verify_jsonl(text))


# ---------------------------------------------------------------- case controls
@app.post("/cases/{case_id}/stop")
def stop(case_id: str, reason: str = Body("", embed=True), x_reviewer_id: Optional[str] = Header(None)):
    return _ok(_call(ORCH.stop, case_id, _reviewer(x_reviewer_id), reason))


@app.post("/cases/{case_id}/close-blocked")
def close_blocked(case_id: str, note: str = Body("", embed=True), x_reviewer_id: Optional[str] = Header(None)):
    return _ok(_call(ORCH.close_blocked, case_id, _reviewer(x_reviewer_id), note))


@app.post("/cases/{case_id}/close-unresolved")
def close_unresolved(case_id: str, note: str = Body("", embed=True), x_reviewer_id: Optional[str] = Header(None)):
    return _ok(_call(ORCH.close_unresolved_legal, case_id, _reviewer(x_reviewer_id), note))


# ---------------------------------------------------------------- demo helpers (synthetic only)
@app.get("/demo/scenarios")
def scenarios():
    return _ok([{"scenario_id": k, "title": v["title"], "case_id": v["case"]["case_id"],
                 "raw_finding": v["case"]["raw_finding"]} for k, v in ORCH.mcp.scenarios.items()])


@app.post("/demo/scenarios/{scenario_id}/load")
def load_scenario(scenario_id: str, x_reviewer_id: Optional[str] = Header(None)):
    scen = ORCH.mcp.scenarios.get(scenario_id)
    if not scen:
        raise HTTPException(404, "unknown scenario")
    req = CreateCaseRequest(**{**scen["case"], "reviewer_id": _reviewer(x_reviewer_id)})
    if ORCH.repo.get(Case, req.case_id):
        return _ok(view(req.case_id))
    _call(ORCH.create_case, req)
    _call(ORCH.assess, req.case_id)
    _call(ORCH.draft_plan, req.case_id)
    return _ok(view(req.case_id))


class RedTeam(BaseModel):
    tool_id: str
    arguments: dict[str, Any] = {}
    plan_id: Optional[str] = None
    step_id: Optional[str] = None
    caused_by: str = "plan_step"


@app.post("/cases/{case_id}/redteam/attempt-tool")
def redteam(case_id: str, body: RedTeam, x_reviewer_id: Optional[str] = Header(None)):
    """Deny-path demo: sends a tool request straight to the proxy (as a compromised agent would).
    It can only ever execute if it matches an approved step exactly; otherwise a DENIED receipt is logged."""
    _call(ORCH.user, _reviewer(x_reviewer_id), case_id)
    case = ORCH.case(case_id)
    res = ORCH.proxy.invoke(case, body.plan_id or case.current_plan_id, body.step_id, body.tool_id, body.arguments,
                            caused_by=body.caused_by, actor_id="redteam")
    return _ok({"receipt": res.receipt, "mcp_invocations": dict(ORCH.mcp.invocations)})


class FailMode(BaseModel):
    tool_id: str
    mode: Optional[str] = "timeout"


@app.post("/demo/fail-mode")
def fail_mode(body: FailMode):
    if body.mode:
        ORCH.mcp.fail_modes[body.tool_id] = body.mode
    else:
        ORCH.mcp.fail_modes.pop(body.tool_id, None)
    return _ok(ORCH.mcp.fail_modes)


@app.post("/demo/reset")
def reset():
    """Start the demo over: fresh in-memory store, fixtures reloaded, fail modes cleared."""
    global ORCH
    ORCH = Orchestrator(Repository(os.environ.get("AA_DB", ":memory:")))
    return _ok({"ok": True})


@app.get("/demo/info")
def info():
    return _ok({"llm": ORCH.llm.label, "policy_version": ORCH.policy.version,
                "users": list(ORCH.users.values()), "mcp_invocations": dict(ORCH.mcp.invocations)})


def view(case_id: str) -> dict:
    case = ORCH.case(case_id)
    plans = ORCH.plans(case_id)
    plan_ids = {p.plan_id for p in plans}
    assessment = ORCH.repo.get(Assessment, case_id)
    return {
        "case": case,
        "claims": ORCH.claims(case_id),
        "gaps": assessment.gaps if assessment else [],
        "findings": ORCH.findings(case_id),
        "plans": plans,
        "preflights": [p for p in ORCH.repo.list(Preflight) if p.plan_id in plan_ids],
        "approvals": [a for a in ORCH.repo.list(Approval) if a.plan_id in plan_ids],
        "receipts": ORCH.receipts(case_id),
        "evidence": ORCH.repo.list(Evidence, case_id),
        "events": ORCH.repo.events(case_id),
        "llm": ORCH.llm.label,
        "policy_version": ORCH.policy.version,
        "limits": {"max_approved_plans": ORCH.policy.max_approved_plans,
                   "max_total_tool_calls": ORCH.policy.max_total_tool_calls},
    }


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
