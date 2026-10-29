"""A model-extracted claim with odd parameters must never crash the verifier or become SUPPORTED."""
from backend.domain.models import CheckType, Claim, CreateCaseRequest, PlanDecision
from backend.evidence.claim_verification import verify_all
from conftest import REVIEWER, load


def test_calculation_with_near_miss_field_name_and_bad_params(orch):
    cid, plan, pf = load(orch, "S05")
    orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)
    orch.execute(cid)
    case = orch.case(cid)
    evidence = orch.evidence(cid)
    good = orch.claims(cid)[0]
    near_miss = Claim(claim_id="CL-X1", case_id=cid, claim_text="revenue fell 20%", check_type=CheckType.CALCULATION,
                      params={"field": "revenue", "from_year": "2024", "to_year": 2025.0, "asserted_change_pct": "-20"})
    garbage = Claim(claim_id="CL-X2", case_id=cid, claim_text="?", check_type=CheckType.CALCULATION,
                    params={"field": None, "from_year": "last year", "to_year": None, "asserted_change_pct": "a fifth"})
    unknown_field = Claim(claim_id="CL-X3", case_id=cid, claim_text="?", check_type=CheckType.CALCULATION,
                          params={"field": "headcount", "from_year": 2024, "to_year": 2025, "asserted_change_pct": -20})
    weird = Claim(claim_id="CL-X4", case_id=cid, claim_text="?", check_type=CheckType.VERSIONED_FIGURE,
                  params={"field": "x", "asserted_value": 1, "document_ids": "not-a-list"})
    f = {x.claim_id: x for x in verify_all(case, [good, near_miss, garbage, unknown_field, weird], evidence, {"financial_report_lookup"})}
    assert f[good.claim_id].verdict.value == "SUPPORTED"
    assert f["CL-X1"].verdict.value == "SUPPORTED" and "revenue_eur" in f["CL-X1"].reason
    assert f["CL-X2"].verdict.value == "NOT_CHECKED" and "unusable_claim_params" in f["CL-X2"].reason_codes
    assert f["CL-X3"].verdict.value == "INSUFFICIENT_EVIDENCE" and "field_not_found" in f["CL-X3"].reason_codes
    assert f["CL-X4"].verdict.value != "SUPPORTED"
