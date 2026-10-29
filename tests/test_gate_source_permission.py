"""C1 · The gate enforces Romanian source-permission rules end to end: the preflight names the step that will
be refused, the proxy refuses it at run time with zero MCP invocations and records the refusal as evidence,
a withdrawn application blocks the whole plan, and an unreadable register holds (never allows).
The Maria data is built in-test; the S07 fixtures and verdicts follow in the next change."""
from datetime import timedelta

import pytest

from backend.domain.models import CreateCaseRequest, InvestigationPlan, PlanDecision, PlanStep, PreflightStatus
from backend.llm.adapter import LLM
from backend.security.policy_engine import compute_plan_hash
from backend.tools.catalog import CATALOG
from backend.tools.mcp_fixture_server import FakeMCPServer, load_scenarios
from backend.util import clock
from backend.workflow.orchestrator import Orchestrator, WorkflowError

REVIEWER = "demo-reviewer-01"
CONSENT = {"consent_id": "cons_0192", "client_id": "cl_0412", "source": "ANAF", "purpose": "credit_application",
           "application_id": "app_0931", "signed_at": "2026-11-02", "channel": "branch", "scope": ["income"],
           "status": "Given"}
APP = {"application_id": "app_0931", "client_id": "cl_0412", "product": "personal_loan", "status": "withdrawn",
       "status_history": [{"status": "active", "at": "2026-11-02T10:15:00+02:00"},
                          {"status": "withdrawn", "at": "2026-11-12T15:00:00+02:00"}]}
ANAF_ARGS = {"client_id": "cl_0412", "consent_id": "cons_0192"}
CONSENT_ARGS = {"client_id": "cl_0412", "source": "ANAF"}


def maria(case_time="2026-11-12T09:00:00+02:00", consent=CONSENT, app=APP):
    return {
        "title": "Maria (test)", "synthetic": True, "case_time": case_time,
        "records": {"client_id": "cl_0412", "application_id": "app_0931"},
        "case": {"origin": "AI_AGENT", "case_id": "CASE-T-MARIA", "purpose": "credit_file_review_demo",
                 "subject": {"type": "NATURAL_PERSON", "display_name": "Maria P. (synthetic client cl_0412)",
                             "reference_id": "cl_0412", "jurisdiction": "RO"},
                 "raw_finding": "Net monthly income 5,200 RON per ANAF; consent cons_0192 valid; application app_0931 active.",
                 "initial_evidence_ids": [], "original_execution_trace_status": "NOT_CAPTURED",
                 "reviewer_id": REVIEWER, "scenario_id": "S07T"},
        "initial_evidence": [],
        "mock_claims": [{"claim_text": "Net monthly income is 5,200 RON per ANAF.", "temporal_scope": "CURRENT",
                         "check_type": "FACT_PRESENCE",
                         "params": {"field": "net_monthly_income_ron", "tool": "anaf_income_query"}}],
        "tool_data": {"consent_lookup": {"cl_0412|ANAF": consent},
                      "application_status_lookup": {"app_0931": app},
                      "anaf_income_query": {"cl_0412|cons_0192": {"client_id": "cl_0412", "consent_id": "cons_0192",
                                                                   "net_monthly_income_ron": 4900}}},
        "ground_truth": {"verdicts": ["INSUFFICIENT_EVIDENCE"], "closure": "CLOSED_WITH_ISSUES"},
    }


def make_orch(scen):
    return Orchestrator(llm=LLM("mock"), mcp=FakeMCPServer({**load_scenarios(), "S07T": scen}))


def step(i, tool, args):
    spec = CATALOG[tool]
    return PlanStep(step_id=f"S{i}", claim_ids=["CL-001"], objective=tool, tool_id=tool, arguments=args,
                    allowed_source_ref=spec.source_ref, data_categories=[spec.data_category])


def plan_for(case, version=1):
    steps = [step(1, "consent_lookup", CONSENT_ARGS), step(2, "application_status_lookup", {"application_id": "app_0931"}),
             step(3, "anaf_income_query", ANAF_ARGS)]
    plan = InvestigationPlan(
        plan_id=f"PLAN-{case.case_id}-v{version}", case_id=case.case_id, version=version, objective="verify the loan file",
        purpose=case.purpose, data_categories=sorted({c for s in steps for c in s.data_categories}),
        source_allowlist=sorted({s.allowed_source_ref for s in steps}), global_max_tool_calls=8,
        expires_at=(clock.now() + timedelta(minutes=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        steps=steps)
    plan.plan_hash = compute_plan_hash(plan)
    return plan


def start(scen, orch=None):
    orch = orch or make_orch(scen)
    case = orch.create_case(CreateCaseRequest(**scen["case"]))
    orch.assess(case.case_id)
    plan, pf = orch.draft_plan(case.case_id, prebuilt=plan_for(case))
    return orch, case.case_id, plan, pf


def test_preflight_names_the_step_that_will_be_refused():
    orch, cid, plan, pf = start(maria())
    assert pf.status == PreflightStatus.ALLOWED_WITH_CONDITIONS
    src = [c for c in pf.checks if c.rule_id == "SRC-ANAF-002"]
    assert src and src[0].step_id == "S3" and src[0].result.value == "NEEDS_REVIEW"
    assert any("S3" in c and "lapsed on 2026-11-09" in c for c in pf.conditions)
    assert orch.mcp.total_invocations == 0


def test_proxy_refuses_lapsed_consent_at_run_time_with_zero_invocations_and_records_it():
    orch, cid, plan, pf = start(maria())
    orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)
    ok = orch.proxy.invoke(orch.case(cid), plan.plan_id, "S1", "consent_lookup", CONSENT_ARGS)
    assert ok.receipt.tool_call_status.value == "EXECUTED"
    res = orch.proxy.invoke(orch.case(cid), plan.plan_id, "S3", "anaf_income_query", ANAF_ARGS)
    r = res.receipt
    assert r.tool_call_status.value == "DENIED" and r.authorization_decision.value == "DENY"
    assert r.authorization_rule_ids == ["SRC-ANAF-002"]
    assert orch.mcp.invocations["anaf_income_query"] == 0
    ev = res.evidence
    assert ev is not None and ev.source_type == "GATE_DECISION" and not ev.authorized_for_case
    assert ev.fields["facts"]["consent.valid_until"] == "2026-11-09" and ev.fields["facts"]["working_days_elapsed"] == 8
    assert ev.fields["citations"][0]["label"] == "draft"
    assert r.response_evidence_ids == [ev.evidence_id]
    assert any(e.event_type == "TOOL_DENIED" and ev.evidence_id in e.payload_refs for e in orch.repo.events(cid))


def test_day_5_consent_passes_preflight_and_proxy():
    orch, cid, plan, pf = start(maria(case_time="2026-11-09T11:00:00+02:00"))
    assert pf.status == PreflightStatus.ALLOWED_WITH_CONDITIONS  # the ANAF tool carries a standing YAML condition
    assert not [c for c in pf.checks if c.rule_id.startswith("SRC-")]
    orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)
    res = orch.proxy.invoke(orch.case(cid), plan.plan_id, "S3", "anaf_income_query", ANAF_ARGS)
    assert res.receipt.tool_call_status.value == "EXECUTED" and orch.mcp.invocations["anaf_income_query"] == 1
    assert res.receipt.authorization_rule_ids == ["POL-TOOL-001"]


def test_withdrawn_application_blocks_the_plan_and_the_proxy_even_with_forged_approval():
    orch, cid, plan, pf = start(maria(case_time="2026-11-13T09:00:00+02:00"))
    assert pf.status == PreflightStatus.BLOCKED
    assert {c.rule_id for c in pf.checks if c.result.value == "FAIL"} == {"SRC-STATUS-001"}
    with pytest.raises(WorkflowError):
        orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE)
    plan.status = "APPROVED"
    orch.repo.put(plan)
    res = orch.proxy.invoke(orch.case(cid), plan.plan_id, "S1", "consent_lookup", CONSENT_ARGS)
    assert res.receipt.tool_call_status.value == "DENIED" and "SRC-STATUS-001" in res.receipt.authorization_rule_ids
    assert orch.mcp.total_invocations == 0


def test_unreadable_consent_register_holds_and_never_allows():
    scen = maria(case_time="2026-11-03T09:00:00+02:00")
    orch, cid, plan, pf = start(scen)
    orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)
    orch.mcp.fail_modes["consent_lookup"] = "timeout"  # the register goes down between approval and execution
    res = orch.proxy.invoke(orch.case(cid), plan.plan_id, "S3", "anaf_income_query", ANAF_ARGS)
    assert res.receipt.authorization_decision.value == "HOLD" and res.receipt.tool_call_status.value == "DENIED"
    assert res.receipt.authorization_rule_ids == ["SRC-HOLD-001"] and orch.mcp.invocations["anaf_income_query"] == 0
    assert res.receipt.denial_reasons[0].startswith("permission_unverifiable")
    # the same outage at preflight time sends the plan to compliance instead of approving it
    orch2 = make_orch(scen)
    orch2.mcp.fail_modes["consent_lookup"] = "timeout"
    _, _, _, pf2 = start(scen, orch2)
    assert pf2.status == PreflightStatus.LEGAL_REVIEW_REQUIRED
    assert [c.rule_id for c in pf2.checks if c.result.value == "NEEDS_REVIEW"] == ["SRC-HOLD-001"]


def test_existing_scenarios_see_no_source_rules():
    orch = Orchestrator(llm=LLM("mock"))
    scen = orch.mcp.scenarios["S01"]
    case = orch.create_case(CreateCaseRequest(**scen["case"]))
    orch.assess(case.case_id)
    plan, pf = orch.draft_plan(case.case_id)
    assert not [c for c in pf.checks if c.rule_id.startswith("SRC-")]
