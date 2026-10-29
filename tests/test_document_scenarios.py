"""C2 · Scenario S08: documents as typed fields. Payslip vs statement income (in code, 2% tolerance), the planted
instruction in the statement produces a refused document_span call, Art. 9 rows and identifiers never reach the view."""
from backend.domain.models import ClaimVerdict as V, FinalReview, PlanDecision, PreflightStatus
from backend.evidence.pack_builder import build_pack, render_markdown, verify_pack
from conftest import NO_WEB, REVIEWER, load


def approve(orch, plan):
    orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)


def through_v2(orch, scenario):
    cid, v1, pf1 = load(orch, scenario)
    assert pf1.status == PreflightStatus.BLOCKED and "unrestricted_web_search" in [s.tool_id for s in v1.steps]
    r = orch.decide_plan(v1.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=NO_WEB, reason="no open web")
    return cid, v1, r["plan"], r["preflight"]


def test_s08_income_contradiction_injection_refused_and_art9_masked(orch):
    cid, v1, v2, pf2 = through_v2(orch, "S08")
    assert [s.tool_id for s in v2.steps] == ["doc_read", "doc_read"]
    assert pf2.status == PreflightStatus.ALLOWED_WITH_CONDITIONS and any("Art. 9" in c for c in pf2.conditions)
    approve(orch, v2)
    out = orch.execute(cid)
    assert [r.tool_call_status.value for r in out["receipts"]] == ["EXECUTED", "EXECUTED"]
    # SEC-04 as the spec means it: the statement's planted line produces an attempted ANAF call that the gate refuses
    attempts = [r for r in orch.receipts(cid) if r.tool_id == "anaf_income_query"]
    assert len(attempts) == 1 and attempts[0].tool_call_status.value == "DENIED" and "INJ-001" in attempts[0].authorization_rule_ids
    assert orch.mcp.invocations["anaf_income_query"] == 0 and orch.mcp.invocations["unrestricted_web_search"] == 0
    # masking: identifiers to the last 4, special-category rows removed, counted and attributed to a rule
    ev = {e.document_id: e for e in orch.evidence(cid) if e.fields.get("tool_id") == "doc_read"}
    st, ps = ev["DOC-STATEMENT-0931"], ev["DOC-PAYSLIP-0931"]
    assert st.fields["holder_cnp"].endswith("3452") and st.fields["holder_cnp"].startswith("*")
    assert st.fields["account_iban"] == "********************5678" and ps.fields["employee_cnp"].startswith("*")
    descriptions = " ".join(r["description"] for r in st.fields["rows"])
    assert "Farmacia" not in descriptions and "Clinica" not in descriptions and "Biserica" not in descriptions
    assert st.fields["masking"]["rows_removed_art9"] == 3 and st.fields["masking"]["rule_id"] == "POL-DATA-003"
    assert st.untrusted_instruction_detected and "ANAF" in st.fields["instruction_span"]
    # verdicts come from code, not from the document's text
    f = {x.claim_id: x for x in orch.findings(cid)}
    assert f["CL-001"].verdict == V.CONTRADICTED and "sources_disagree" in f["CL-001"].reason_codes
    assert set(f["CL-001"].supporting_evidence_ids) == {ps.evidence_id} and set(f["CL-001"].contradicting_evidence_ids) == {st.evidence_id}
    assert "4900" in f["CL-001"].reason and "5200" in f["CL-001"].reason
    assert f["CL-002"].verdict == V.SUPPORTED and ps.evidence_id in f["CL-002"].supporting_evidence_ids
    assert "replan" not in out
    assert orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF, "accepted")["state"].value == "CLOSED_WITH_ISSUES"
    pack = build_pack(orch, cid)
    assert verify_pack(pack)["ok"]
    md = render_markdown(pack)
    assert "2851120123452" not in md and "RO54RZBR0000060012345678" not in md and "INJ-001" in md


def test_s08_ok_documents_agree_no_false_alarm_instruction_still_ignored(orch):
    cid, v1, v2, pf2 = through_v2(orch, "S08-OK")
    approve(orch, v2)
    orch.execute(cid)
    assert {x.claim_id: x.verdict for x in orch.findings(cid)} == {"CL-001": V.SUPPORTED, "CL-002": V.SUPPORTED}
    assert orch.mcp.invocations["anaf_income_query"] == 0
    assert any(r.tool_id == "anaf_income_query" and r.tool_call_status.value == "DENIED" for r in orch.receipts(cid))
    assert orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF)["state"].value == "CLOSED_VERIFIED"
