"""One-command evaluation over the labelled synthetic scenarios (spec 08 'Quality measurement').

    python eval/run_eval.py            # deterministic mock planner
    python eval/run_eval.py --llm      # use LLM_MODE from .env (Bedrock)

A scripted reviewer plays the human: removes the open web search when preflight blocks, approves
allowed plans, signs off (acknowledging unresolved). Misses (wrong claims marked SUPPORTED) are
reported first. Results are our measurement on synthetic data, not a bank ROI.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domain.models import CreateCaseRequest, FinalReview, PlanDecision, PreflightStatus  # noqa: E402
from backend.evidence.pack_builder import build_pack, verify_pack  # noqa: E402
from backend.llm.adapter import LLM  # noqa: E402
from backend.workflow.orchestrator import Orchestrator  # noqa: E402

REVIEWER = "demo-reviewer-01"
RESTRICT = {"forbid_tools": ["unrestricted_web_search"], "notes": ["No unrestricted websites."]}


def run_case(orch: Orchestrator, sid: str) -> dict:
    scen = orch.mcp.scenarios[sid]
    t0 = time.perf_counter()
    case = orch.create_case(CreateCaseRequest(**scen["case"]))
    cid = case.case_id
    orch.assess(cid)
    plan, pf = orch.draft_plan(cid)
    v1_status = pf.status.value
    # red-team probe: a forbidden call must be denied with zero invocations
    before = orch.mcp.invocations["unrestricted_web_search"]
    probe = orch.proxy.invoke(orch.case(cid), plan.plan_id, "S1", "unrestricted_web_search", {"query": "probe"})
    probe_ok = probe.receipt.tool_call_status.value == "DENIED" and orch.mcp.invocations["unrestricted_web_search"] == before
    rounds = 0
    while True:
        state = orch.case(cid).state.value
        if state == "PREFLIGHT_BLOCKED":
            if pf.plan_id and any(s.tool_id == "unrestricted_web_search" for s in plan.steps) and plan.version == 1:
                r = orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.MODIFY, restrictions=RESTRICT, reason="eval")
                plan, pf = r["plan"], r["preflight"]
                if not plan.steps:
                    orch.close_blocked(cid, REVIEWER, "no permitted check")
                    break
                continue
            orch.close_blocked(cid, REVIEWER, "no permitted check")
            break
        if state == "AWAITING_PLAN_APPROVAL":
            orch.decide_plan(plan.plan_id, REVIEWER, PlanDecision.APPROVE, plan_hash=plan.plan_hash)
            out = orch.execute(cid)
            rounds += 1
            if "replan" in out:
                plan, pf = out["replan"]["plan"], out["replan"]["preflight"]
            continue
        if state == "AWAITING_FINAL_REVIEW":
            orch.final_review(cid, REVIEWER, FinalReview.SIGN_OFF, "eval sign-off", acknowledge_unresolved=True)
            break
        if state == "LEGAL_REVIEW_REQUIRED":
            orch.close_unresolved_legal(cid, REVIEWER)
            break
        break
    findings = {f.claim_id: f.verdict.value for f in orch.findings(cid)}
    claims = orch.claims(cid)
    expected = scen["ground_truth"]["verdicts"]
    got = [findings.get(c.claim_id, "NOT_CHECKED") for c in claims]
    pack = build_pack(orch, cid)
    return {
        "scenario": sid, "title": scen["title"], "expected": expected, "got": got,
        "closure_expected": scen["ground_truth"]["closure"], "closure": orch.case(cid).state.value,
        "v1_preflight": v1_status, "v1_expected": scen["ground_truth"].get("v1_preflight"),
        "probe_denied": probe_ok, "rounds": rounds, "tool_calls": orch.case(cid).tool_calls_used,
        "denied": len(pack["denied_tool_receipt_ids"]), "pack_ok": verify_pack(pack)["ok"],
        "evidence_complete": all((f["supporting_evidence_ids"] or f["contradicting_evidence_ids"] or f["verdict"] in ("INSUFFICIENT_EVIDENCE", "NOT_CHECKED"))
                                 for f in pack["findings"]),
        "seconds": round(time.perf_counter() - t0, 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="use LLM_MODE from .env instead of the mock planner")
    ap.add_argument("--out", default=None, help="report path (default eval/report.md, or eval/report-<provider>.md with --llm)")
    args = ap.parse_args()
    orch = Orchestrator(llm=LLM() if args.llm else LLM("mock"))
    rows = [run_case(orch, sid) for sid in sorted(orch.mcp.scenarios)]
    pairs = [(e, g) for r in rows for e, g in zip(r["expected"], r["got"])]
    false_accept = [r["scenario"] for r in rows for e, g in zip(r["expected"], r["got"]) if g == "SUPPORTED" and e != "SUPPORTED"]
    false_reject = [r["scenario"] for r in rows for e, g in zip(r["expected"], r["got"]) if e == "SUPPORTED" and g != "SUPPORTED"]
    correct = sum(1 for e, g in pairs if e == g)
    lines = [
        "# Evaluation report (synthetic scenarios)", "",
        f"Planner: **{orch.llm.label}** · policy {orch.policy.version} · {len(rows)} cases, {len(pairs)} claims"
        + (f" · model calls {orch.llm.summary()['calls']}, cost est. USD {orch.llm.summary()['cost_estimate_usd']} ({orch.llm.summary()['cost_basis']})"
           if orch.llm.calls_log else ""), "",
        "## Headline (misses first)",
        f"1. **Wrong claims marked SUPPORTED (false accept): {len(false_accept)}** {false_accept or ''}",
        f"2. Valid claims not SUPPORTED (false reject): {len(false_reject)} {false_reject or ''}",
        f"3. Claim verdicts matching ground truth: {correct}/{len(pairs)}",
        f"4. Forbidden-tool probes denied with zero invocations: {sum(r['probe_denied'] for r in rows)}/{len(rows)}",
        f"5. Closure state as expected: {sum(r['closure'] == r['closure_expected'] for r in rows)}/{len(rows)}",
        f"6. Evidence packs verifying (hash + chain + ids): {sum(r['pack_ok'] for r in rows)}/{len(rows)}",
        f"7. Findings with evidence or an explicit abstention: {sum(r['evidence_complete'] for r in rows)}/{len(rows)}", "",
        "## Per case", "",
        "| Case | Expected | Got | v1 preflight | Closure | Rounds | Tool calls | Denied | Probe | Pack | s |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        mark = "✅" if r["expected"] == r["got"] and r["closure"] == r["closure_expected"] else "❌"
        lines.append(f"| {mark} {r['scenario']} {r['title']} | {', '.join(r['expected'])} | {', '.join(r['got'])} | "
                     f"{r['v1_preflight']} | {r['closure']} | {r['rounds']} | {r['tool_calls']} | {r['denied']} | "
                     f"{'✅' if r['probe_denied'] else '❌'} | {'✅' if r['pack_ok'] else '❌'} | {r['seconds']} |")
    lines += ["", "_Synthetic fixtures; our own measurement. Not a bank time-saving or ROI figure._", ""]
    report = "\n".join(lines)
    default_name = f"report-{orch.llm.mode}.md" if args.llm else "report.md"
    out = Path(args.out) if args.out else Path(__file__).resolve().parent / default_name
    out.write_text(report, encoding="utf-8")
    print(report)
    sys.exit(0 if not false_accept and correct == len(pairs) else 1)


if __name__ == "__main__":
    main()
