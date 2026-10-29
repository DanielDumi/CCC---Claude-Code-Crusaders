"""C1 · Scenario S07 and its variants end to end through the orchestrator (mock planner, no LLM):
Romanian consent rules decide which source may be used; verdicts stay separate from permission."""
from backend.domain.models import ClaimVerdict as V, FinalReview, PlanDecision, PreflightStatus
from backend.evidence.pack_builder import build_pack, render_markdown, verify_pack
from conftest import NO_WEB, REVIEWER, load


def approve(orch, plan):
    orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)


def through_v2(orch, scenario):
    cid, v1, pf1 = load(orch, scenario)
    assert pf1.status == PreflightStatus.BLOCKED  # the planner's first draft wants to search the web about a person
    assert "unrestricted_web_search" in [s.tool_id for s in v1.steps]
    r = orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=NO_WEB, reason="no open web")
    return cid, v1, r["plan"], r["preflight"]


def test_s07_lapsed_consent_end_to_end(orch):
    cid, v1, v2, pf2 = through_v2(orch, "S07")
    assert [s.tool_id for s in v2.steps] == ["consent_lookup", "application_status_lookup", "anaf_income_query"]
    assert pf2.status == PreflightStatus.ALLOWED_WITH_CONDITIONS
    assert any("anaf_income_query" in c and "lapsed on 2026-11-09" in c for c in pf2.conditions)
    assert orch.mcp.total_invocations == 0
    approve(orch, v2)
    out = orch.execute(cid)
    receipts = {r.tool_id: r for r in out["receipts"]}
    assert receipts["consent_lookup"].tool_call_status == receipts["application_status_lookup"].tool_call_status
    assert receipts["consent_lookup"].tool_call_status.value == "EXECUTED"
    anaf = receipts["anaf_income_query"]
    assert anaf.tool_call_status.value == "DENIED" and anaf.authorization_rule_ids == ["SRC-ANAF-002"]
    assert orch.mcp.invocations["anaf_income_query"] == 0 and orch.mcp.invocations["unrestricted_web_search"] == 0
    f = {x.claim_id: x for x in orch.findings(cid)}
    assert f["CL-001"].verdict == V.CONTRADICTED and "consent_lapsed" in f["CL-001"].reason_codes
    assert "2026-11-09" in f["CL-001"].reason
    assert f["CL-002"].verdict == V.SUPPORTED and "active" in f["CL-002"].reason.lower()
    assert f["CL-003"].verdict == V.INSUFFICIENT_EVIDENCE
    assert {"source_not_allowed", "gate:SRC-ANAF-002"} <= set(f["CL-003"].reason_codes)
    assert f["CL-003"].supporting_evidence_ids == anaf.response_evidence_ids
    assert "replan" not in out and orch.case(cid).state.value == "AWAITING_FINAL_REVIEW"
    assert orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF, "accepted", acknowledge_unresolved=True)["state"].value == "CLOSED_WITH_ISSUES"
    pack = build_pack(orch, cid)
    assert verify_pack(pack)["ok"]
    md = render_markdown(pack)
    assert "SRC-ANAF-002" in md and "lapsed on 2026-11-09" in md


def test_s07_ok_day_5_is_allowed_and_no_false_alarm(orch):
    cid, v1, v2, pf2 = through_v2(orch, "S07-OK")
    assert pf2.status == PreflightStatus.ALLOWED_WITH_CONDITIONS
    assert not [c for c in pf2.checks if c.rule_id.startswith("SRC-")]
    approve(orch, v2)
    out = orch.execute(cid)
    assert all(r.tool_call_status.value == "EXECUTED" for r in out["receipts"]) and len(out["receipts"]) == 3
    assert {x.claim_id: x.verdict for x in orch.findings(cid)} == {"CL-001": V.SUPPORTED, "CL-002": V.SUPPORTED, "CL-003": V.SUPPORTED}
    assert orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF)["state"].value == "CLOSED_VERIFIED"


def test_s07_hol_consent_across_public_holidays_still_valid(orch):
    cid, v1, v2, pf2 = through_v2(orch, "S07-HOL")
    assert not [c for c in pf2.checks if c.rule_id.startswith("SRC-")]
    approve(orch, v2)
    orch.execute(cid)
    f = {x.claim_id: x for x in orch.findings(cid)}
    assert {k: v.verdict for k, v in f.items()} == {"CL-001": V.SUPPORTED, "CL-002": V.SUPPORTED, "CL-003": V.SUPPORTED}
    assert "2026-12-08" in f["CL-001"].reason


def test_s07_wd_withdrawn_application_blocks_everything(orch):
    cid, v1, v2, pf2 = through_v2(orch, "S07-WD")
    assert pf2.status == PreflightStatus.BLOCKED
    assert {c.rule_id for c in pf2.checks if c.result.value == "FAIL"} == {"SRC-STATUS-001"}
    assert orch.close_blocked(cid, REVIEWER, "withdrawn application").state.value == "CLOSED_BLOCKED"
    assert {x.verdict for x in orch.findings(cid)} == {V.NOT_CHECKED}
    assert orch.mcp.total_invocations == 0
