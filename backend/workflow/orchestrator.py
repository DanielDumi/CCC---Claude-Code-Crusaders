"""Investigation orchestrator: a programmatic state machine with model calls embedded (spec 03, 05 §3).

State transitions, access grants and approval records are never delegated to an LLM.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

from backend.agents.planner import Planner
from backend.domain.models import (
    Approval, Assessment, Case, CaseState, ClaimVerdict, CreateCaseRequest, Evidence, EvidenceStatus, FinalReview,
    FinalReviewRecord, Finding, InvestigationPlan, PlanDecision, Preflight, PreflightStatus, ToolCallStatus,
    ToolReceipt,
)
from backend.evidence.claim_verification import verify_all
from backend.llm.adapter import LLM
from backend.security.policy_engine import Policy, compute_plan_hash, preflight
from backend.security.tool_proxy import APPROVER_ROLES, ToolProxy
from backend.storage.repository import Repository
from backend.tools.mcp_fixture_server import FakeMCPServer
from backend.util import clock, ids, sha256_hex
from backend.workflow.state_machine import TERMINAL, InvalidTransition, check_transition

USERS_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "users.json"
S = CaseState


class AuthError(Exception):
    pass


class WorkflowError(Exception):
    pass


class Orchestrator:
    def __init__(self, repo: Optional[Repository] = None, llm: Optional[LLM] = None,
                 policy: Optional[Policy] = None, mcp: Optional[FakeMCPServer] = None) -> None:
        self.repo = repo or Repository()
        self.policy = policy or Policy.load()
        self.mcp = mcp or FakeMCPServer()
        self.llm = llm or LLM()
        self.planner = Planner(self.llm, self.policy)
        self.proxy = ToolProxy(self.repo, self.policy, self.mcp)
        self.users = {u["reviewer_id"]: u for u in json.loads(USERS_PATH.read_text())["users"]}
        self._restrictions: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ helpers
    def case(self, case_id: str) -> Case:
        c = self.repo.get(Case, case_id)
        if c is None:
            raise WorkflowError(f"unknown case {case_id}")
        return c

    def _move(self, case: Case, new: CaseState, actor_type="SYSTEM", actor_id="orchestrator", summary="", refs=()):
        check_transition(case.state, new)
        old = case.state
        case.state = new
        self.repo.put(case)
        self.repo.append_event(case.case_id, "STATE_CHANGED", actor_type, actor_id,
                               f"{old.value} -> {new.value}" + (f": {summary}" if summary else ""), refs)

    def user(self, reviewer_id: str, case_id: Optional[str] = None) -> dict:
        u = self.users.get(reviewer_id)
        if not u:
            raise AuthError(f"unknown reviewer {reviewer_id}")
        if case_id and "*" not in u["cases"] and case_id not in u["cases"]:
            raise AuthError(f"{reviewer_id} is not authorised for {case_id}")
        return u

    def scenario(self, case: Case) -> Optional[dict]:
        return self.mcp.scenarios.get(case.scenario_id or "")

    def claims(self, case_id: str):
        a = self.repo.get(Assessment, case_id)
        return a.claims if a else []

    def findings(self, case_id: str) -> list[Finding]:
        return self._findings(case_id)

    def plans(self, case_id: str) -> list[InvestigationPlan]:
        return self.repo.list(InvestigationPlan, case_id)

    def current_plan(self, case: Case) -> Optional[InvestigationPlan]:
        return self.repo.get(InvestigationPlan, case.current_plan_id) if case.current_plan_id else None

    def evidence(self, case_id: str) -> list[Evidence]:
        return self.repo.list(Evidence, case_id)

    # ------------------------------------------------------------------ 1. intake
    def create_case(self, req: CreateCaseRequest) -> Case:
        self.user(req.reviewer_id, req.case_id)
        if self.repo.get(Case, req.case_id):
            raise WorkflowError(f"case {req.case_id} already exists")
        case = Case(**req.model_dump(exclude={"origin_system", "subject"}), subject=req.subject,
                    origin_system=req.origin_system, raw_finding_sha256=sha256_hex(req.raw_finding),
                    created_at=clock.iso())
        self.repo.put(case)
        refs = []
        scen = self.scenario(case) or {}
        attached = {e["evidence_id"]: e for e in scen.get("initial_evidence", [])}
        for eid in req.initial_evidence_ids:
            raw = attached.get(eid)
            if raw:
                ev = Evidence(case_id=case.case_id, status=EvidenceStatus.AVAILABLE,
                              content_sha256=sha256_hex(json.dumps(raw, sort_keys=True)),
                              retrieved_at=clock.iso(), authenticity_verification="NOT_VERIFIED", **raw)
            else:
                ev = Evidence(evidence_id=eid, case_id=case.case_id, source_type="ORIGINAL_CASE_ARTIFACT",
                              source_ref="unknown", status=EvidenceStatus.NOT_CAPTURED)
            self.repo.put(ev)
            refs.append(ev.evidence_id)
        self.repo.append_event(case.case_id, "CASE_RECEIVED", "HUMAN" if case.origin.value == "HUMAN" else "AI_AGENT",
                               case.origin_system.system_id,
                               f"Case received; finding sha256 {case.raw_finding_sha256[:12]}…; "
                               f"trace {case.original_execution_trace_status}", refs)
        return case

    # ------------------------------------------------------------------ 2. assessment (no external calls)
    def assess(self, case_id: str) -> Assessment:
        case = self.case(case_id)
        assessment = self.planner.assess(case, self.evidence(case_id), self.scenario(case))
        self.repo.put(assessment)
        for c in assessment.claims:
            self.repo.put(c)
        self.repo.append_event(case_id, "CLAIMS_ASSESSED", "AI_AGENT", f"planner ({assessment.produced_by})",
                               f"{len(assessment.claims)} claims, {len(assessment.gaps)} gaps",
                               [c.claim_id for c in assessment.claims])
        self._move(case, S.ASSESSED)
        return assessment

    # ------------------------------------------------------------------ 3+4. plan + mandatory preflight
    def _done_calls(self, case_id: str) -> set[str]:
        from backend.agents.planner import call_key
        plans = {p.plan_id: p for p in self.plans(case_id)}
        out = set()
        for r in self.repo.list(ToolReceipt, case_id):
            if r.tool_call_status in (ToolCallStatus.EXECUTED, ToolCallStatus.FAILED) and r.plan_id in plans:
                step = next((s for s in plans[r.plan_id].steps if s.step_id == r.step_id), None)
                if step:
                    out.add(call_key(step.tool_id, step.arguments))
        return out

    def draft_plan(self, case_id: str, restrictions: Optional[dict[str, Any]] = None,
                   prebuilt: Optional[InvestigationPlan] = None) -> tuple[InvestigationPlan, Preflight]:
        case = self.case(case_id)
        if case.state not in (S.ASSESSED, S.PREFLIGHT_BLOCKED, S.LEGAL_REVIEW_REQUIRED, S.AWAITING_PLAN_APPROVAL,
                              S.REPLAN_REQUIRED):
            raise WorkflowError(f"cannot draft a plan in state {case.state.value}")
        prev = self.current_plan(case)
        if prev and prev.status not in ("APPROVED", "REJECTED", "SUPERSEDED"):
            prev.status = "SUPERSEDED"
            self.repo.put(prev)
        # reviewer restrictions carry forward across versions (a later plan cannot silently drop them)
        restrictions = _merge_restrictions(self._restrictions.get(case_id, {}), restrictions or {})
        self._restrictions[case_id] = restrictions
        version = case.plan_count + 1
        plan = prebuilt or self.planner.propose_plan(case, self.claims(case_id), self._findings(case_id),
                                                     self.evidence(case_id), restrictions, version,
                                                     prev.plan_id if prev else None, self._done_calls(case_id))
        if case.state != S.PLAN_DRAFTED:
            self._move(case, S.PLAN_DRAFTED, summary=plan.plan_id)
        case = self.case(case_id)
        case.plan_count = version
        case.current_plan_id = plan.plan_id
        self.repo.put(case)
        self.repo.put(plan)
        self.repo.append_event(case_id, "PLAN_PROPOSED", "AI_AGENT", plan.created_by,
                               f"v{version} hash {plan.plan_hash[:12]}…: " + ", ".join(s.tool_id for s in plan.steps),
                               [plan.plan_id])
        pf = preflight(plan, case, self.policy, calls_used=case.tool_calls_used)
        self.repo.put(pf)
        self.repo.append_event(case_id, "PREFLIGHT_COMPLETED", "SYSTEM", "policy-preflight",
                               f"{pf.status.value} ({self.policy.version})", [pf.preflight_id, plan.plan_id])
        nxt = {PreflightStatus.BLOCKED: S.PREFLIGHT_BLOCKED,
               PreflightStatus.LEGAL_REVIEW_REQUIRED: S.LEGAL_REVIEW_REQUIRED}.get(pf.status, S.AWAITING_PLAN_APPROVAL)
        self._move(case, nxt, summary=pf.status.value, refs=[pf.preflight_id])
        if not plan.steps:
            self.repo.append_event(case_id, "NO_SAFE_ALTERNATIVE", "AI_AGENT", plan.created_by,
                                   "No permitted check can address the open claims", [plan.plan_id])
        return plan, pf

    def latest_preflight(self, plan_id: str) -> Optional[Preflight]:
        pfs = [p for p in self.repo.list(Preflight) if p.plan_id == plan_id]
        return pfs[-1] if pfs else None

    # ------------------------------------------------------------------ 5. human decision on the exact plan
    def decide_plan(self, plan_id: str, reviewer_id: str, decision: PlanDecision, *,
                    restrictions: Optional[dict[str, Any]] = None, reason: str = "",
                    plan_hash: Optional[str] = None) -> dict:
        plan = self.repo.get(InvestigationPlan, plan_id)
        if plan is None:
            raise WorkflowError("unknown plan")
        case = self.case(plan.case_id)
        u = self.user(reviewer_id, case.case_id)
        if u["role"] not in APPROVER_ROLES:
            raise AuthError(f"role {u['role']} may not decide plans")
        if case.current_plan_id != plan_id:
            raise WorkflowError("only the latest plan revision can be decided")
        if plan_hash and plan_hash != plan.plan_hash:
            raise WorkflowError("plan hash mismatch: the plan you reviewed is not the stored plan")
        pf = self.latest_preflight(plan_id)
        restrictions = restrictions or {}
        texts = list(restrictions.get("notes", [])) + [f"Exclude {t}" for t in restrictions.get("forbid_tools", [])]
        rec = Approval(decision_id=ids.next("APR"), plan_id=plan_id, plan_hash=plan.plan_hash,
                       preflight_id=pf.preflight_id if pf else None, decision=decision, reviewer_id=reviewer_id,
                       reviewer_role=u["role"], restrictions=texts, structured_restrictions=restrictions,
                       reason=reason, decided_at=clock.iso())
        if decision == PlanDecision.APPROVE:
            if case.state != S.AWAITING_PLAN_APPROVAL or not pf or pf.status not in (
                    PreflightStatus.ALLOWED, PreflightStatus.ALLOWED_WITH_CONDITIONS):
                self.repo.append_event(case.case_id, "APPROVAL_REFUSED", "HUMAN", reviewer_id,
                                       f"Approve refused: preflight {pf.status.value if pf else 'missing'}; "
                                       "a click cannot turn a policy deny into an allow", [plan_id])
                raise WorkflowError(f"plan cannot be approved (preflight {pf.status.value if pf else 'missing'})")
            approved = sum(1 for p in self.plans(case.case_id) if p.status in ("APPROVED", "SUPERSEDED_APPROVED"))
            if approved >= self.policy.max_approved_plans:
                raise WorkflowError("maximum number of approved plans reached")
            rec.authorization_expires_at = min(
                plan.expires_at,
                (clock.now() + timedelta(minutes=self.policy.approval_ttl_minutes)).replace(microsecond=0)
                .isoformat().replace("+00:00", "Z"))
            self.repo.put(rec)
            plan.status = "APPROVED"
            self.repo.put(plan)
            self.repo.append_event(case.case_id, "PLAN_APPROVED", "HUMAN", reviewer_id,
                                   f"{plan_id} hash {plan.plan_hash[:12]}… approved", [rec.decision_id, plan_id])
            self._move(case, S.APPROVED, "HUMAN", reviewer_id)
            return {"approval": rec}
        # MODIFY / REJECT: never an execution authorisation; always a new version + new preflight
        self.repo.put(rec)
        plan.status = "REJECTED" if decision == PlanDecision.REJECT else "SUPERSEDED"
        self.repo.put(plan)
        self.repo.append_event(case.case_id, f"PLAN_{decision.value}", "HUMAN", reviewer_id,
                               f"{plan_id}: {reason or ', '.join(texts) or 'no reason'}", [rec.decision_id, plan_id])
        new_plan, new_pf = self.draft_plan(case.case_id, restrictions)
        return {"decision": rec, "plan": new_plan, "preflight": new_pf}

    def request_compliance(self, plan_id: str, reviewer_id: str, note: str) -> None:
        plan = self.repo.get(InvestigationPlan, plan_id)
        case = self.case(plan.case_id)
        self.user(reviewer_id, case.case_id)
        self.repo.append_event(case.case_id, "COMPLIANCE_REQUESTED", "HUMAN", reviewer_id, note, [plan_id])

    # ------------------------------------------------------------------ 6–8. execute approved steps via the proxy
    def execute(self, case_id: str) -> dict:
        case = self.case(case_id)
        if case.state != S.APPROVED:
            raise WorkflowError(f"nothing approved to execute (state {case.state.value})")
        plan = self.current_plan(case)
        self._move(case, S.EXECUTING)
        done: set[str] = set()
        receipts = []
        for step in _topological(plan.steps):
            case = self.case(case_id)
            if case.stopped:
                break
            if any(d not in done for d in step.depends_on):
                self.repo.append_event(case_id, "STEP_SKIPPED", "AI_AGENT", "agent:assure-v1",
                                       f"{step.step_id}: dependency not satisfied", [plan.plan_id])
                continue
            # adaptive: skip a step whose claims are already settled by earlier evidence
            current = self._verify(case)
            if step.claim_ids and all(_settled(current, cid) for cid in step.claim_ids) and step.tool_id != "document_signature_check":
                self.repo.append_event(case_id, "STEP_SKIPPED", "AI_AGENT", "agent:assure-v1",
                                       f"{step.step_id} {step.tool_id}: claims already settled", [plan.plan_id])
                continue
            res = self.proxy.invoke(case, plan.plan_id, step.step_id, step.tool_id, step.arguments)
            receipts.append(res.receipt)
            if res.receipt.tool_call_status == ToolCallStatus.EXECUTED:
                done.add(step.step_id)
            elif res.receipt.tool_call_status == ToolCallStatus.DENIED:
                break
        case = self.case(case_id)
        findings = self._verify(case, persist=True)
        notes = self.planner.explain(findings, self.evidence(case_id))
        for f in findings:
            if f.claim_id in notes:
                f.explanation = notes[f.claim_id]
                self.repo.put(f, key=f"{case_id}:{f.finding_id}")
        if notes:
            self.repo.append_event(case_id, "EXPLANATIONS_WRITTEN", "AI_AGENT", self.llm.label,
                                   f"{len(notes)} plain-language explanations (verdicts unchanged)")
        self._move(case, S.FINDINGS_READY, summary=_verdict_summary(findings))
        return {"receipts": receipts, "findings": findings, **self._after_findings(case_id)}

    def _after_findings(self, case_id: str) -> dict:
        case = self.case(case_id)
        findings = self._findings(case_id)
        approved_plans = sum(1 for p in self.plans(case_id) if p.status == "APPROVED")
        needs = [f.next_action_proposal for f in findings if f.next_action_proposal]
        needs += [f"check {f.claim_id}" for f in findings if f.verdict == ClaimVerdict.NOT_CHECKED]
        budget_left = case.tool_calls_used < self.policy.max_total_tool_calls
        if needs and approved_plans < self.policy.max_approved_plans and budget_left and not case.stopped:
            restrictions = self._restrictions.get(case_id, {})
            candidate = self.planner.propose_plan(case, self.claims(case_id), findings, self.evidence(case_id),
                                                  restrictions, case.plan_count + 1, case.current_plan_id,
                                                  self._done_calls(case_id))
            if candidate.steps:  # only ask the human again if there is something new to approve
                self._move(case, S.REPLAN_REQUIRED, "AI_AGENT", "agent:assure-v1", "new scope needed: " + ", ".join(needs))
                plan, pf = self.draft_plan(case_id, prebuilt=candidate)
                return {"replan": {"plan": plan, "preflight": pf}}
        self._move(case, S.AWAITING_FINAL_REVIEW)
        return {}

    def _verify(self, case: Case, persist: bool = False) -> list[Finding]:
        attempted = {r.tool_id for r in self.repo.list(ToolReceipt, case.case_id)
                     if r.tool_call_status in (ToolCallStatus.EXECUTED, ToolCallStatus.FAILED)}
        findings = verify_all(case, self.claims(case.case_id), self.evidence(case.case_id), attempted)
        if persist:
            for f in findings:
                prev = self._findings_map(case.case_id).get(f.claim_id)
                self.repo.put(f, key=f"{case.case_id}:{f.finding_id}")
                if not prev or prev.verdict != f.verdict:
                    self.repo.append_event(case.case_id, "FINDING_UPDATED", "AI_AGENT", "verification-engine",
                                           f"{f.claim_id}: {f.verdict.value}" + (f" (was {prev.verdict.value})" if prev else ""),
                                           [f.finding_id] + f.supporting_evidence_ids + f.contradicting_evidence_ids)
        return findings

    def _findings_map(self, case_id: str) -> dict[str, Finding]:
        out = {}
        for c in self.claims(case_id):
            f = self.repo.get(Finding, f"{case_id}:FND-{c.claim_id}")
            if f:
                out[c.claim_id] = f
        return out

    def _findings(self, case_id: str) -> list[Finding]:
        return list(self._findings_map(case_id).values())

    # ------------------------------------------------------------------ blocked path / stop
    def close_blocked(self, case_id: str, reviewer_id: str, note: str = "") -> Case:
        case = self.case(case_id)
        self.user(reviewer_id, case_id)
        if case.state != S.PREFLIGHT_BLOCKED:
            raise WorkflowError("only a preflight-blocked case can be closed as blocked")
        self._verify(case, persist=True)
        self.repo.append_event(case_id, "CLOSED_BLOCKED_BY_REVIEWER", "HUMAN", reviewer_id, note or "No lawful investigation path")
        self._move(case, S.CLOSED_BLOCKED, "HUMAN", reviewer_id)
        return self.case(case_id)

    def close_unresolved_legal(self, case_id: str, reviewer_id: str, note: str = "") -> Case:
        case = self.case(case_id)
        self.user(reviewer_id, case_id)
        self._verify(case, persist=True)
        self._move(case, S.CLOSED_UNRESOLVED, "HUMAN", reviewer_id, note or "legal basis not established")
        return self.case(case_id)

    def stop(self, case_id: str, reviewer_id: str, reason: str) -> Case:
        case = self.case(case_id)
        self.user(reviewer_id, case_id)
        case.stopped = True
        self.repo.put(case)
        for a in self.repo.list(Approval):
            plan = self.repo.get(InvestigationPlan, a.plan_id)
            if plan and plan.case_id == case_id and a.decision == PlanDecision.APPROVE and not a.revoked:
                a.revoked = True
                self.repo.put(a)
        self.repo.append_event(case_id, "STOP", "HUMAN", reviewer_id, reason or "stopped")
        return case

    # ------------------------------------------------------------------ 9. final human review
    def final_review(self, case_id: str, reviewer_id: str, decision: FinalReview, note: str = "",
                     acknowledge_unresolved: bool = False) -> dict:
        case = self.case(case_id)
        u = self.user(reviewer_id, case_id)
        if u["role"] not in APPROVER_ROLES:
            raise AuthError("role may not sign off")
        if case.state != S.AWAITING_FINAL_REVIEW:
            raise WorkflowError(f"not awaiting final review (state {case.state.value})")
        findings = self._findings(case_id)
        rec = FinalReviewRecord(signoff_id=ids.next("SIGNOFF"), case_id=case_id, decision=decision,
                                reviewer_id=reviewer_id, reviewer_role=u["role"],
                                acknowledged_unresolved=acknowledge_unresolved, note=note, decided_at=clock.iso())
        self.repo.put(rec)
        self.repo.append_event(case_id, f"FINAL_{decision.value}", "HUMAN", reviewer_id,
                               note or "final review", [rec.signoff_id])
        if decision == FinalReview.SIGN_OFF:
            verdicts = {f.verdict for f in findings}
            if ClaimVerdict.CONTRADICTED in verdicts:
                target = S.CLOSED_WITH_ISSUES
            elif verdicts & {ClaimVerdict.INSUFFICIENT_EVIDENCE, ClaimVerdict.NOT_CHECKED}:
                if not acknowledge_unresolved:
                    raise WorkflowError("unresolved claims: acknowledge them to sign off")
                target = S.CLOSED_UNRESOLVED
            else:
                target = S.CLOSED_VERIFIED
            self._move(case, target, "HUMAN", reviewer_id, "sign-off (not a banking or credit decision)", [rec.signoff_id])
            return {"signoff": rec, "state": target}
        self._move(case, S.REPLAN_REQUIRED, "HUMAN", reviewer_id, decision.value)
        plan, pf = self.draft_plan(case_id, {"notes": [note]} if note else {})
        return {"signoff": rec, "plan": plan, "preflight": pf}

    # ------------------------------------------------------------------ convenience
    def receipts(self, case_id: str) -> list[ToolReceipt]:
        return self.repo.list(ToolReceipt, case_id)


def _merge_restrictions(old: dict, new: dict) -> dict:
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in old.items()}
    for k, v in new.items():
        if isinstance(v, list):
            out[k] = sorted(set(out.get(k, [])) | set(v)) if k != "notes" else list(dict.fromkeys(out.get(k, []) + v))
        else:
            out[k] = v
    return out


def _settled(findings: list[Finding], claim_id: str) -> bool:
    f = next((x for x in findings if x.claim_id == claim_id), None)
    return bool(f and f.verdict.value in ("SUPPORTED", "CONTRADICTED") and not f.next_action_proposal)


def _verdict_summary(findings: list[Finding]) -> str:
    return ", ".join(f"{f.claim_id}={f.verdict.value}" for f in findings)


def _topological(steps):
    order, seen = [], set()
    pending = list(steps)
    while pending:
        progressed = False
        for s in list(pending):
            if all(d in seen or d not in {x.step_id for x in steps} for d in s.depends_on):
                order.append(s)
                seen.add(s.step_id)
                pending.remove(s)
                progressed = True
        if not progressed:
            order.extend(pending)
            break
    return order
