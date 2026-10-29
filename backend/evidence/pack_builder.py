"""InvestigationReport + GovernanceEvidencePack, assembled only from persisted objects and the ledger
(spec 02 'Output artifacts', 04 §7, 06 §10). Never fabricates history: absent traces are NOT_CAPTURED.
"""
from __future__ import annotations

from typing import Any

from backend.domain.models import (
    Approval, Evidence, EvidenceStatus, FinalReviewRecord, InvestigationPlan, Preflight, ToolReceipt,
)
from backend.storage.repository import verify_chain
from backend.util import canonical_json, clock, sha256_hex, to_plain

DISCLAIMER = ("Prepared as supporting governance evidence; not a certification or legal opinion. "
              "Synthetic demo data and demo policies only. The sign-off is not a banking or credit decision.")


def build_pack(orch, case_id: str) -> dict[str, Any]:
    repo = orch.repo
    case = orch.case(case_id)
    plans = orch.plans(case_id)
    plan_ids = {p.plan_id for p in plans}
    preflights = [p for p in repo.list(Preflight) if p.plan_id in plan_ids]
    approvals = [a for a in repo.list(Approval) if a.plan_id in plan_ids]
    receipts = repo.list(ToolReceipt, case_id)
    evidence = repo.list(Evidence, case_id)
    findings = orch.findings(case_id)
    claims = orch.claims(case_id)
    signoffs = repo.list(FinalReviewRecord, case_id)
    events = repo.events(case_id)
    chain = verify_chain(events)
    gaps = [f"{e.evidence_id}: {e.status.value}" for e in evidence if e.status != EvidenceStatus.AVAILABLE]
    if case.original_execution_trace_status != "CAPTURED":
        gaps.append(f"Original agent execution trace: {case.original_execution_trace_status}")

    pack: dict[str, Any] = {
        "schema_version": "1.0",
        "pack_id": f"PACK-{case_id}",
        "case_id": case_id,
        "closure_state": case.state.value,
        "subject": to_plain(case.subject),
        "purpose": case.purpose,
        "origin": case.origin.value,
        "origin_system": to_plain(case.origin_system),
        "raw_finding": case.raw_finding,
        "raw_finding_sha256": case.raw_finding_sha256,
        "original_artifact_refs": case.initial_evidence_ids,
        "claims": to_plain(claims),
        "findings": to_plain(findings),
        "plans": to_plain(plans),
        "preflights": to_plain(preflights),
        "approvals": to_plain(approvals),
        "tool_receipts": to_plain(receipts),
        "evidence": to_plain(evidence),
        "human_signoffs": to_plain(signoffs),
        "plan_ids": [p.plan_id for p in plans],
        "preflight_ids": [p.preflight_id for p in preflights],
        "approval_ids": [a.decision_id for a in approvals],
        "tool_receipt_ids": [r.tool_receipt_id for r in receipts],
        "denied_tool_receipt_ids": [r.tool_receipt_id for r in receipts if r.tool_call_status.value == "DENIED"],
        "finding_ids": [f.finding_id for f in findings],
        "human_signoff_id": signoffs[-1].signoff_id if signoffs else None,
        "effective_policy_version": orch.policy.version,
        "legal_reference_snapshot": orch.policy.legal_snapshot,
        "ai_act_relevance": {
            "system": case.origin_system.system_id, "version": case.origin_system.version,
            "risk_classification": case.origin_system.ai_act_risk_classification,
            "provider_deployer_role": case.origin_system.provider_deployer_role,
            "article_evidence_map": [
                {"article": "Art. 12 logging", "evidence": "event ledger (hash-chained)", "status": "NEEDS_LEGAL_CONFIRMATION"},
                {"article": "Art. 14 human oversight", "evidence": "plan approvals/modifications, stop, final sign-off",
                 "status": "NEEDS_LEGAL_CONFIRMATION"},
                {"article": "Art. 26 deployer duties", "evidence": "reviewer actions, input relevance (claim-level checks)",
                 "status": "NEEDS_LEGAL_CONFIRMATION"},
            ],
        },
        "known_trace_gaps": gaps,
        "open_issues": [
            {"claim_id": f.claim_id, "verdict": f.verdict.value, "reason": f.reason}
            for f in findings if f.verdict.value != "SUPPORTED"
        ],
        "llm": orch.llm.label,
        "events": to_plain(events),
        "ledger_verification": chain,
        "legal_assessment_disclaimer": DISCLAIMER,
        "generated_at": clock.iso(),
    }
    pack["pack_sha256"] = sha256_hex(canonical_json(pack))
    return pack


def verify_pack(pack: dict[str, Any]) -> dict[str, Any]:
    body = dict(pack)
    claimed = body.pop("pack_sha256", None)
    ok_hash = claimed == sha256_hex(canonical_json(body))
    chain = verify_chain(pack.get("events", []))
    event_refs = {r for e in pack.get("events", []) for r in e.get("payload_refs", [])}
    missing = [rid for rid in pack.get("tool_receipt_ids", []) + pack.get("approval_ids", []) if rid not in event_refs]
    return {"pack_hash_ok": ok_hash, "chain": chain, "ids_missing_from_ledger": missing,
            "ok": ok_hash and chain["ok"] and not missing}


def render_markdown(pack: dict[str, Any]) -> str:
    L: list[str] = []
    add = L.append
    add(f"# Investigation report — {pack['case_id']}")
    add("")
    add(f"> {pack['legal_assessment_disclaimer']}")
    add("")
    add(f"- **Subject:** {pack['subject']['display_name']} (`{pack['subject'].get('reference_id')}`) — synthetic")
    add(f"- **Purpose:** {pack['purpose']}  ·  **Origin:** {pack['origin']} ({pack['origin_system']['system_id']})")
    add(f"- **Closure state:** `{pack['closure_state']}`")
    add(f"- **Policy:** {pack['effective_policy_version']}  ·  **Legal snapshot:** {pack['legal_reference_snapshot']}")
    add(f"- **Model:** {pack['llm']}  ·  **Generated:** {pack['generated_at']}")
    add(f"- **Pack SHA-256:** `{pack['pack_sha256']}`  ·  **Ledger:** "
        f"{'verified' if pack['ledger_verification']['ok'] else 'BROKEN'} ({pack['ledger_verification']['entries']} events)")
    add("")
    add("## Original finding")
    add(f"> {pack['raw_finding']}")
    add("")
    add("## Claim verdicts")
    add("| Claim | Verdict | Reason | Supporting | Contradicting | Limits |")
    add("|---|---|---|---|---|---|")
    claims = {c['claim_id']: c for c in pack['claims']}
    for f in pack['findings']:
        c = claims.get(f['claim_id'], {})
        add(f"| {f['claim_id']}: {c.get('claim_text', '')} | **{f['verdict']}** | {f['reason']} | "
            f"{', '.join(f['supporting_evidence_ids']) or '—'} | {', '.join(f['contradicting_evidence_ids']) or '—'} | "
            f"{'; '.join(f['authenticity_limitations']) or '—'} |")
    add("")
    add("## Plans, preflights and human decisions")
    pf_by_plan: dict[str, list] = {}
    for p in pack['preflights']:
        pf_by_plan.setdefault(p['plan_id'], []).append(p)
    ap_by_plan: dict[str, list] = {}
    for a in pack['approvals']:
        ap_by_plan.setdefault(a['plan_id'], []).append(a)
    for p in pack['plans']:
        add(f"### {p['plan_id']} (v{p['version']}, `{p['plan_hash'][:16]}…`, {p['status']})")
        for s in p['steps']:
            add(f"- {s['step_id']}: `{s['tool_id']}` {s['arguments']} — {s['objective']}")
        if p['reviewer_restrictions']:
            add(f"- Reviewer restrictions: {'; '.join(p['reviewer_restrictions'])}")
        for pf in pf_by_plan.get(p['plan_id'], []):
            add(f"- **Preflight {pf['preflight_id']}: {pf['status']}**" + (f" — conditions: {'; '.join(pf['conditions'])}" if pf['conditions'] else ""))
            for ch in pf['checks']:
                if ch['result'] != 'PASS':
                    add(f"  - {ch['category']} {ch['result']} `{ch['rule_id']}`: {ch['explanation']}")
        for a in ap_by_plan.get(p['plan_id'], []):
            add(f"- Human: **{a['decision']}** by {a['reviewer_id']} ({a['reviewer_role']}) at {a['decided_at']}"
                + (f" — {a['reason']}" if a['reason'] else ""))
        add("")
    add("## Tool calls (through the approval-bound proxy)")
    add("| Receipt | Plan/step | Tool | Decision | Status | Rules | Note |")
    add("|---|---|---|---|---|---|---|")
    for r in pack['tool_receipts']:
        add(f"| {r['tool_receipt_id']} | {r['plan_id']}/{r['step_id']} | `{r['tool_id']}` | {r['authorization_decision']} | "
            f"{r['tool_call_status']} | {', '.join(r['authorization_rule_ids'])} | {'; '.join(r['denial_reasons']) or r.get('error') or ''} |")
    add("")
    add("## Evidence")
    for e in pack['evidence']:
        add(f"- `{e['evidence_id']}` {e['status']} — {e['source_ref']} ({e.get('published_at') or 'n/a'}); "
            f"sha256 `{(e.get('content_sha256') or '')[:12]}`; authenticity: {e['authenticity_verification']}"
            + ("; ⚠ instruction-like text ignored" if e.get('untrusted_instruction_detected') else "")
            + (f"\n  > {e['original_excerpt']}" if e.get('original_excerpt') else ""))
    add("")
    add("## AI Act relevance (supporting evidence only)")
    ai = pack['ai_act_relevance']
    add(f"- Verified system: {ai['system']} {ai['version']} — risk classification **{ai['risk_classification']}**, "
        f"role **{ai['provider_deployer_role']}**")
    for m in ai['article_evidence_map']:
        add(f"- {m['article']}: {m['evidence']} — {m['status']}")
    add("")
    add("## Open issues and trace gaps")
    for i in pack['open_issues']:
        add(f"- {i['claim_id']} {i['verdict']}: {i['reason']}")
    for g in pack['known_trace_gaps']:
        add(f"- Gap: {g}")
    if not pack['open_issues'] and not pack['known_trace_gaps']:
        add("- None")
    add("")
    add("## Event timeline")
    for e in pack['events']:
        add(f"- {e['timestamp']} `{e['event_type']}` ({e['actor_type']}:{e['actor_id']}) {e['summary']}")
    return "\n".join(L) + "\n"
