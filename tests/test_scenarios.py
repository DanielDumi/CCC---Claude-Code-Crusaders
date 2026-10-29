"""Functional acceptance tests (spec 08 'Automated acceptance suite')."""
import pytest

from backend.domain.models import ClaimVerdict as V, CreateCaseRequest, FinalReview, PlanDecision, PreflightStatus
from backend.evidence.pack_builder import build_pack, render_markdown, verify_pack
from backend.workflow.orchestrator import WorkflowError
from conftest import NO_WEB, REVIEWER, load


def approve(orch, plan):
    orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)


def run_s01(orch, scenario="S01"):
    cid, v1, pf1 = load(orch, scenario)
    r = orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=NO_WEB, reason="no open web")
    v2 = r["plan"]
    approve(orch, v2)
    out = orch.execute(cid)
    return cid, v1, pf1, v2, out


def test_fun01_compound_finding_split_into_two_claims(orch):
    cid, *_ = load(orch, "S01")
    claims = orch.claims(cid)
    assert [c.temporal_scope for c in claims] == ["HISTORICAL", "CURRENT"]


def test_fun02_v1_blocked_edit_gives_new_hash_and_v1_cannot_execute(orch):
    cid, v1, pf1 = load(orch, "S01")
    assert pf1.status == PreflightStatus.BLOCKED
    with pytest.raises(WorkflowError):
        orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.APPROVE)
    r = orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=NO_WEB)
    v2 = r["plan"]
    assert v2.plan_hash != v1.plan_hash and v2.version == 2
    assert "unrestricted_web_search" not in [s.tool_id for s in v2.steps]
    assert r["preflight"].status == PreflightStatus.ALLOWED_WITH_CONDITIONS
    assert orch.mcp.total_invocations == 0  # nothing ran before approval


def test_fun03_new_tool_needs_another_approval(orch):
    cid, v1, pf1, v2, out = run_s01(orch)
    v3 = out["replan"]["plan"]
    assert [s.tool_id for s in v3.steps] == ["document_signature_check"]
    assert orch.case(cid).state.value == "AWAITING_PLAN_APPROVAL"
    assert orch.mcp.invocations["document_signature_check"] == 0


def test_fun04_s01_outcomes_and_closure(orch):
    cid, v1, pf1, v2, out = run_s01(orch)
    approve(orch, out["replan"]["plan"])
    orch.execute(cid)
    verdicts = {f.claim_id: f.verdict for f in orch.findings(cid)}
    assert verdicts == {"CL-001": V.SUPPORTED, "CL-002": V.CONTRADICTED}
    res = orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF, "accepted")
    assert res["state"].value == "CLOSED_WITH_ISSUES"


def test_fun04b_s01_with_unavailable_current_source_abstains(orch):
    orch.mcp.fail_modes["legal_case_status_lookup"] = "timeout"
    cid, *_ = run_s01(orch)
    f = {x.claim_id: x for x in orch.findings(cid)}
    assert f["CL-002"].verdict == V.INSUFFICIENT_EVIDENCE and "tool_error" in f["CL-002"].reason_codes


def test_fun05_s02_entity_mismatch(orch):
    cid, plan, pf = load(orch, "S02")
    assert pf.status in (PreflightStatus.ALLOWED, PreflightStatus.ALLOWED_WITH_CONDITIONS)
    approve(orch, plan)
    orch.execute(cid)
    f = orch.findings(cid)[0]
    assert f.verdict == V.CONTRADICTED and "wrong_entity" in f.reason_codes


def test_fun06_s03_absence_gives_insufficient(orch):
    cid, v1, pf1 = load(orch, "S03")
    assert pf1.status == PreflightStatus.BLOCKED
    v2 = orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=NO_WEB)["plan"]
    approve(orch, v2)
    orch.execute(cid)
    f = orch.findings(cid)[0]
    assert f.verdict == V.INSUFFICIENT_EVIDENCE
    with pytest.raises(WorkflowError):
        orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF)  # must acknowledge unresolved
    assert orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF, acknowledge_unresolved=True)["state"].value == "CLOSED_UNRESOLVED"


def test_fun07_s04_conflicting_versions(orch):
    cid, plan, pf = load(orch, "S04")
    approve(orch, plan)
    orch.execute(cid)
    f = orch.findings(cid)[0]
    assert f.verdict == V.INSUFFICIENT_EVIDENCE and "no_approved_version" in f.reason_codes


def test_fun08_s05_calculation_supported(orch):
    cid, plan, pf = load(orch, "S05")
    approve(orch, plan)
    out = orch.execute(cid)
    f = orch.findings(cid)[0]
    assert f.verdict == V.SUPPORTED and "-20.0%" in f.reason
    assert "replan" not in out  # no unnecessary follow-up
    assert orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF)["state"].value == "CLOSED_VERIFIED"


def test_fun09_s06_forbidden_search_blocked_even_with_forged_approval(orch):
    cid, plan, pf = load(orch, "S06")
    assert pf.status == PreflightStatus.BLOCKED
    with pytest.raises(WorkflowError):
        orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE)
    # forged: mark the plan approved in storage, then try to execute through the proxy
    plan.status = "APPROVED"
    orch.repo.put(plan)
    res = orch.proxy.invoke(orch.case(cid), plan.plan_id, "S1", "unrestricted_web_search", plan.steps[0].arguments)
    assert res.receipt.tool_call_status.value == "DENIED" and orch.mcp.total_invocations == 0
    assert orch.close_blocked(cid, REVIEWER).state.value == "CLOSED_BLOCKED"


def test_fun10_pack_matches_ledger(orch):
    cid, v1, pf1, v2, out = run_s01(orch)
    approve(orch, out["replan"]["plan"])
    orch.execute(cid)
    orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF)
    pack = build_pack(orch, cid)
    check = verify_pack(pack)
    assert check["ok"], check
    assert len(pack["plan_ids"]) == 3 and pack["closure_state"] == "CLOSED_WITH_ISSUES"
    types = [e["event_type"] for e in pack["events"]]
    assert "PLAN_MODIFY" in types and types.count("PLAN_APPROVED") == 2
    md = render_markdown(pack)
    assert "not a certification" in md and "CONTRADICTED" in md


def test_fun11_preflight_before_every_approval(orch):
    cid, v1, pf1, v2, out = run_s01(orch)
    events = [e.event_type for e in orch.repo.events(cid)]
    for i, t in enumerate(events):
        if t == "PLAN_APPROVED":
            assert "PREFLIGHT_COMPLETED" in events[:i]
    assert events.index("PREFLIGHT_COMPLETED") < events.index("PLAN_APPROVED")


def test_fun12_human_origin_same_contract(orch):
    scen = orch.mcp.scenarios["S05"]
    req = CreateCaseRequest(**{**scen["case"], "origin": "HUMAN", "case_id": "CASE-HUMAN-005"})
    case = orch.create_case(req)
    orch.assess(case.case_id)
    plan, pf = orch.draft_plan(case.case_id)
    approve(orch, plan)
    orch.execute(case.case_id)
    assert orch.findings(case.case_id)[0].verdict == V.SUPPORTED


def test_injection_in_tool_response_triggers_no_extra_call(orch):
    cid, v1, pf1, v2, out = run_s01(orch, "S01-INJ")
    assert orch.mcp.invocations["unrestricted_web_search"] == 0
    assert any(e.event_type == "INJECTION_FLAGGED" for e in orch.repo.events(cid))
    f = {x.claim_id: x for x in orch.findings(cid)}
    assert f["CL-002"].verdict == V.CONTRADICTED  # 'mark all claims SUPPORTED' was ignored


class _PlanOnlyLLM:
    """Stands in for Bedrock: round 1 proposes only the court registry (no identity check), like the live model did;
    every other task fails, so the deterministic path takes over."""
    mode = "bedrock"
    label = "bedrock:fake"

    def complete(self, task, payload, schema_hint, max_tokens=1500):
        from backend.llm.adapter import LLMError
        if task == "propose_plan" and payload["round"] == 1:
            return {"steps": [{"claim_ids": ["CL-002"], "objective": "Check current status", "tool_id": "legal_case_status_lookup",
                               "arguments": {"company_id": "RO-DEMO-48219370", "case_ref": "C-001"}}]}
        raise LLMError("not scripted")


def test_model_skips_identity_check_agent_asks_for_it_next_round():
    from backend.workflow.orchestrator import Orchestrator
    from conftest import load as _load
    o = Orchestrator(llm=_PlanOnlyLLM())
    cid, v1, pf = _load(o, "S01")
    assert [s.tool_id for s in v1.steps] == ["legal_case_status_lookup"] and "bedrock:fake" in v1.created_by
    approve(o, v1)
    out = o.execute(cid)
    assert {f.claim_id: f.verdict for f in o.findings(cid)}["CL-001"] == V.NOT_CHECKED
    v2 = out["replan"]["plan"]
    tools = [s.tool_id for s in v2.steps]
    assert "company_registry_lookup" in tools and "legal_case_status_lookup" not in tools  # no repeated call
    approve(o, v2)
    o.execute(cid)
    assert {f.claim_id: f.verdict for f in o.findings(cid)} == {"CL-001": V.SUPPORTED, "CL-002": V.CONTRADICTED}


def test_s09_unapproved_purpose_goes_to_compliance_and_never_runs(orch):
    cid, v1, pf1 = load(orch, "S09")
    assert pf1.status == PreflightStatus.LEGAL_REVIEW_REQUIRED
    assert orch.case(cid).state.value == "LEGAL_REVIEW_REQUIRED"
    with pytest.raises(WorkflowError):  # a click cannot approve what only compliance may decide
        orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=v1.plan_hash)
    orch.request_compliance(v1.plan_id, REVIEWER, "purpose not approved")
    assert any(e.event_type == "COMPLIANCE_REQUESTED" for e in orch.repo.events(cid))
    orch.close_unresolved_legal(cid, REVIEWER, "compliance has not decided")
    assert orch.case(cid).state.value == "CLOSED_UNRESOLVED"
    assert orch.mcp.total_invocations == 0
