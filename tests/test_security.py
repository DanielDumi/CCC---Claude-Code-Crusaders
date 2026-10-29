"""Security tests SEC-01..10 (spec 07 §10). All must pass; they run without any LLM."""
import pytest

from backend.domain.models import EvidenceStatus, InvestigationPlan, PlanDecision
from backend.evidence.pack_builder import build_pack
from backend.storage.repository import verify_chain
from backend.util import clock
from backend.workflow.orchestrator import AuthError, WorkflowError
from conftest import NO_WEB, REVIEWER, load


def v2_approved(orch, scenario="S01"):
    cid, v1, _ = load(orch, scenario)
    v2 = orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=NO_WEB)["plan"]
    orch.decide_plan(v2.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=v2.plan_hash)
    return cid, v1, v2


def test_sec01_no_approve_record_means_denied(orch):
    cid, v1, _ = load(orch, "S01")
    v2 = orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=NO_WEB)["plan"]
    s = v2.steps[0]
    res = orch.proxy.invoke(orch.case(cid), v2.plan_id, s.step_id, s.tool_id, s.arguments)
    assert res.receipt.tool_call_status.value == "DENIED" and "APR-001" in res.receipt.authorization_rule_ids
    assert orch.mcp.total_invocations == 0


def test_sec02_changed_plan_invalidates_old_approval(orch):
    cid, v1, v2 = v2_approved(orch)
    tampered = orch.repo.get(InvestigationPlan, v2.plan_id)
    tampered.steps[0].arguments = {"company_id": "RO-DEMO-00000000"}
    orch.repo.put(tampered)  # plan_hash no longer matches content
    s = tampered.steps[0]
    res = orch.proxy.invoke(orch.case(cid), v2.plan_id, s.step_id, s.tool_id, s.arguments)
    assert res.receipt.tool_call_status.value == "DENIED" and "PLAN-005" in res.receipt.authorization_rule_ids
    assert orch.mcp.total_invocations == 0


def test_sec03_reviewer_excluded_search_cannot_run(orch):
    cid, v1, v2 = v2_approved(orch)
    res = orch.proxy.invoke(orch.case(cid), v2.plan_id, "S1", "unrestricted_web_search", {"query": "x"})
    assert res.receipt.tool_call_status.value == "DENIED"
    orch.execute(cid)
    assert orch.mcp.invocations["unrestricted_web_search"] == 0


def test_sec04_injected_call_caused_by_document_denied(orch):
    cid, v1, v2 = v2_approved(orch, "S01-INJ")
    s = v2.steps[0]
    res = orch.proxy.invoke(orch.case(cid), v2.plan_id, s.step_id, s.tool_id, s.arguments, caused_by="document_span")
    assert res.receipt.tool_call_status.value == "DENIED" and "INJ-001" in res.receipt.authorization_rule_ids
    assert orch.mcp.total_invocations == 0


def test_sec05_legal_review_required_blocks_queries(orch):
    cid, v1, _ = load(orch, "S01")
    case = orch.case(cid)
    case.purpose = "marketing_profiling"  # not an approved purpose
    orch.repo.put(case)
    r = orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=NO_WEB)
    assert r["preflight"].status.value == "LEGAL_REVIEW_REQUIRED"
    with pytest.raises(WorkflowError):
        orch.decide_plan(r["plan"].plan_id, REVIEWER, PlanDecision.APPROVE)
    assert orch.mcp.total_invocations == 0


def test_sec06_reviewer_from_another_case_denied(orch):
    cid, v1, _ = load(orch, "S01")
    with pytest.raises(AuthError):
        orch.decide_plan(v1.plan_id, "demo-reviewer-02", PlanDecision.MODIFY, restrictions=NO_WEB)
    with pytest.raises(AuthError):
        orch.decide_plan(v1.plan_id, "demo-viewer-01", PlanDecision.APPROVE)


def test_sec07_budget_exhausted(orch):
    cid, v1, v2 = v2_approved(orch)
    case = orch.case(cid)
    case.tool_calls_used = orch.policy.max_total_tool_calls
    orch.repo.put(case)
    s = v2.steps[0]
    res = orch.proxy.invoke(orch.case(cid), v2.plan_id, s.step_id, s.tool_id, s.arguments)
    assert res.receipt.tool_call_status.value == "DENIED" and "LIM-001" in res.receipt.authorization_rule_ids


def test_sec07b_step_budget(orch):
    cid, v1, v2 = v2_approved(orch)
    s = v2.steps[0]
    first = orch.proxy.invoke(orch.case(cid), v2.plan_id, s.step_id, s.tool_id, s.arguments)
    second = orch.proxy.invoke(orch.case(cid), v2.plan_id, s.step_id, s.tool_id, s.arguments)
    assert first.receipt.tool_call_status.value == "EXECUTED"
    assert second.receipt.tool_call_status.value == "DENIED" and "LIM-002" in second.receipt.authorization_rule_ids


def test_sec08_missing_original_receipt_marked_not_captured(orch):
    from backend.domain.models import CreateCaseRequest
    scen = orch.mcp.scenarios["S01"]
    req = CreateCaseRequest(**{**scen["case"], "case_id": "CASE-MISSING", "initial_evidence_ids": ["EVD-GONE"]})
    orch.create_case(req)
    ev = orch.evidence("CASE-MISSING")[0]
    assert ev.status == EvidenceStatus.NOT_CAPTURED
    orch.assess("CASE-MISSING")
    pack = build_pack(orch, "CASE-MISSING")
    assert any("NOT_CAPTURED" in g for g in pack["known_trace_gaps"])


def test_sec09_expired_approval_denied(orch):
    cid, v1, v2 = v2_approved(orch)
    clock.advance(minutes=31)
    try:
        s = v2.steps[0]
        res = orch.proxy.invoke(orch.case(cid), v2.plan_id, s.step_id, s.tool_id, s.arguments)
        assert res.receipt.tool_call_status.value == "DENIED" and "APR-003" in res.receipt.authorization_rule_ids
    finally:
        clock.pin(None)


def test_sec10_unverified_authority_claim_stays_unverified(orch):
    cid, v1, v2 = v2_approved(orch)
    orch.execute(cid)
    rec = [e for e in orch.evidence(cid) if e.fields.get("tool_id") == "legal_case_status_lookup"][0]
    assert rec.authenticity_verification == "NOT_VERIFIED"
    f = {x.claim_id: x for x in orch.findings(cid)}
    assert any("not verified" in lim for lim in f["CL-002"].authenticity_limitations)


def test_stop_revokes_and_denies(orch):
    cid, v1, v2 = v2_approved(orch)
    orch.stop(cid, REVIEWER, "test")
    s = v2.steps[0]
    res = orch.proxy.invoke(orch.case(cid), v2.plan_id, s.step_id, s.tool_id, s.arguments)
    assert res.receipt.tool_call_status.value == "DENIED" and "STOP-001" in res.receipt.authorization_rule_ids


def test_ledger_tamper_detected_and_append_only(orch):
    cid, *_ = v2_approved(orch)
    events = [e.model_dump(mode="json") for e in orch.repo.events(cid)]
    assert verify_chain(events)["ok"]
    events[3]["summary"] += " edited"
    assert verify_chain(events)["first_bad_index"] == 3
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        orch.repo._db.execute("DELETE FROM events")


def test_cross_case_isolation(orch):
    """Same fixture evidence/claim ids in two cases never leak into each other."""
    a, *_ = v2_approved(orch, "S01")
    b, *_ = v2_approved(orch, "S01-INJ")
    orch.execute(a)
    assert all(e.case_id == b for e in orch.evidence(b))
    assert {e.evidence_id for e in orch.evidence(b)} == {"EVD-OLD-ARTICLE"}
    assert orch.findings(b) == []


def test_llm_output_cannot_change_verdict(orch):
    """Even in LLM mode a model failure falls back to the deterministic path; verdicts come from code."""
    from backend.llm.adapter import LLM
    from backend.workflow.orchestrator import Orchestrator
    from conftest import load as _load
    o = Orchestrator(llm=LLM("bedrock"))  # no key in tests -> LLMError -> deterministic fallback
    import os
    os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
    cid, plan, pf = _load(o, "S05")
    o.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)
    o.execute(cid)
    assert o.findings(cid)[0].verdict.value == "SUPPORTED"
