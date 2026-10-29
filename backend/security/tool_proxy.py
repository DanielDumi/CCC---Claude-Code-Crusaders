"""Approval-bound tool proxy: the ONLY component that may invoke the MCP adapter (spec 03 §6, 07 §3).

Fail closed. Every check runs before invocation; a DENIED receipt is persisted and the MCP server
is never called. The model never holds credentials and cannot bypass this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.domain.models import (
    Approval, AuthorizationDecision, Case, Evidence, EvidenceStatus, InvestigationPlan, PlanDecision, Preflight,
    PreflightStatus, ToolCallStatus, ToolReceipt,
)
from backend.security.policy_engine import Policy, compute_plan_hash
from backend.security.result_filter import filter_result, find_instruction, instruction_target
from backend.security.source_rules import Records, RuleHit, evaluate_call
from backend.storage.repository import Repository
from backend.tools.catalog import CATALOG
from backend.tools.mcp_fixture_server import FakeMCPServer, ToolTimeout, ToolUnavailable
from backend.util import canonical_json, clock, ids, parse_iso, sha256_hex

APPROVER_ROLES = {"BANK_CASE_REVIEWER", "COMPLIANCE_REVIEWER"}


@dataclass
class ProxyResult:
    receipt: ToolReceipt
    evidence: Optional[Evidence] = None


class ToolProxy:
    def __init__(self, repo: Repository, policy: Policy, mcp: FakeMCPServer) -> None:
        self.repo = repo
        self.policy = policy
        self.mcp = mcp
        # Preflight and proxy read the same bank records, including simulated outages (fail_modes).
        policy.records_provider = lambda sid: Records(self.mcp.scenarios.get(sid), self.mcp.fail_modes)

    # ------------------------------------------------------------------ checks
    def _authorize(self, case: Case, plan: Optional[InvestigationPlan], step_id: Optional[str], tool_id: str,
                   arguments: dict[str, Any], caused_by: str) -> tuple[list[str], list[str], Optional[Approval]]:
        denials: list[str] = []
        rules: list[str] = []

        def deny(rule: str, why: str) -> None:
            rules.append(rule)
            denials.append(why)

        if case.stopped:
            deny("STOP-001", "Case stopped by a reviewer")
        if caused_by not in ("plan_step",):
            deny("INJ-001", f"Call not caused by an approved plan step (caused_by={caused_by})")
        deny_rule = self.policy.deny_rule(tool_id)
        if deny_rule:
            deny(deny_rule, f"{tool_id} is forbidden by policy (hard deny, cannot be approved)")
        spec = CATALOG.get(tool_id)
        if spec is None or not spec.enabled:
            deny("POL-TOOL-002", f"{tool_id} is not an enabled catalogue tool")
        if plan is None:
            deny("PLAN-002", "No plan referenced")
            return rules, denials, None
        if plan.case_id != case.case_id:
            deny("PLAN-004", "Plan belongs to another case")
        if compute_plan_hash(plan) != plan.plan_hash:
            deny("PLAN-005", "Stored plan does not match its hash (plan changed after approval)")
        if plan.status != "APPROVED":
            deny("PLAN-002", f"Plan status is {plan.status}, not APPROVED")

        approval = self._active_approval(plan)
        if approval is None:
            deny("APR-001", "No active APPROVE record bound to this exact plan hash")
        else:
            if approval.reviewer_role not in APPROVER_ROLES:
                deny("APR-002", f"Approver role {approval.reviewer_role} may not authorise execution")
            if approval.authorization_expires_at and clock.now() > parse_iso(approval.authorization_expires_at):
                deny("APR-003", "Approval expired")
            preflight = self.repo.get(Preflight, approval.preflight_id or "")
            if preflight is None or preflight.plan_hash != plan.plan_hash:
                deny("PRE-001", "Approval is not bound to a preflight of this plan hash")
            elif preflight.status not in (PreflightStatus.ALLOWED, PreflightStatus.ALLOWED_WITH_CONDITIONS):
                deny("PRE-002", f"Preflight status {preflight.status.value} does not permit execution")
            elif preflight.policy_version != self.policy.version:
                deny("PRE-003", "Policy version changed since preflight; re-evaluation required")

        step = next((s for s in plan.steps if s.step_id == step_id), None)
        if step is None:
            deny("PLAN-001", f"Step {step_id} is not in the approved plan")
        else:
            if step.tool_id != tool_id:
                deny("PLAN-001", f"Tool {tool_id} does not match approved step {step.step_id} ({step.tool_id})")
            if canonical_json(step.arguments) != canonical_json(arguments):
                deny("PLAN-001", "Arguments differ from the approved step")
            used = sum(1 for r in self.repo.list(ToolReceipt, case.case_id)
                       if r.plan_id == plan.plan_id and r.step_id == step.step_id
                       and r.tool_call_status in (ToolCallStatus.EXECUTED, ToolCallStatus.FAILED))
            if used >= step.max_calls:
                deny("LIM-002", f"Step {step.step_id} call budget ({step.max_calls}) exhausted")
            allowed = self.policy.allowed(tool_id)
            if allowed and spec:
                if step.allowed_source_ref not in (None, allowed["source"]) or spec.source_ref != allowed["source"]:
                    deny("POL-SRC-001", "Source does not match the catalogue entry")
                if any(c not in allowed["categories"] for c in step.data_categories):
                    deny("POL-SRC-001", "Data category not allowed for this tool")
            if tool_id in plan.forbidden_tools:
                deny("PLAN-003", f"{tool_id} was excluded by the reviewer")
        if case.tool_calls_used >= self.policy.max_total_tool_calls:
            deny("LIM-001", f"Case tool-call budget ({self.policy.max_total_tool_calls}) exhausted")
        if plan.purpose != case.purpose or case.purpose not in self.policy.data["allowed_case_purposes"]:
            deny("POL-PURPOSE-001", "Purpose mismatch")
        if clock.now() > parse_iso(plan.expires_at):
            deny("APR-003", "Plan authorisation window expired")
        return rules, denials, approval

    def _source_permission(self, case: Case, plan: Optional[InvestigationPlan], tool_id: str,
                           arguments: dict[str, Any]) -> tuple[list[RuleHit], list[RuleHit], str]:
        """SRC-* rules at call time: (denies, holds, at). Same facts and code as the preflight."""
        records = self.policy.records(case.scenario_id)
        at = records.case_time or clock.now()
        hits = evaluate_call(tool_id, arguments, plan.purpose if plan else case.purpose, self.policy.data, records, at)
        return [h for h in hits if h.outcome == "deny"], [h for h in hits if h.outcome == "hold"], at.isoformat()

    def _gate_evidence(self, case: Case, receipt: ToolReceipt, tool_id: str, arguments: dict[str, Any],
                       decision: AuthorizationDecision, hits: list[RuleHit], at: str) -> Evidence:
        """The gate's refusal as an evidence item (gate spec: kind rule_result, source_allowed false), so the
        verifier can give the dependent claim INSUFFICIENT_EVIDENCE with the rule ids attached."""
        spec = CATALOG.get(tool_id)
        facts: dict[str, Any] = {}
        for h in hits:
            facts.update(h.facts)
        return Evidence(
            evidence_id=ids.next("EVD"), case_id=case.case_id, source_type="GATE_DECISION",
            source_ref=spec.source_ref if spec else f"tool://{tool_id}", tool_receipt_id=receipt.tool_receipt_id,
            retrieved_at=clock.iso(), status=EvidenceStatus.UNAVAILABLE,
            data_categories=[spec.data_category] if spec else [],
            original_excerpt="; ".join(h.reason for h in hits),
            fields={"tool_id": tool_id, "arguments": arguments, "decision": decision.value,
                    "rule_ids": [h.rule_id for h in hits], "reasons": [h.reason for h in hits],
                    "next_steps": sorted({h.next_step for h in hits if h.next_step != "none"}), "facts": facts, "at": at,
                    "citations": [{"rule_id": h.rule_id, "title": self.policy.rule(h.rule_id).get("title"),
                                   "source_uri": self.policy.rule(h.rule_id).get("source_uri"),
                                   "legal_refs": self.policy.rule(h.rule_id).get("legal_refs", []),
                                   "label": self.policy.rule(h.rule_id).get("label")} for h in hits]},
            authenticity_verification="NOT_APPLICABLE", authorized_for_case=False,
        )

    def _active_approval(self, plan: InvestigationPlan) -> Optional[Approval]:
        approvals = [a for a in self.repo.list(Approval) if a.plan_id == plan.plan_id]
        for a in reversed(approvals):
            if a.plan_hash != plan.plan_hash:
                continue
            if a.decision != PlanDecision.APPROVE or a.revoked:
                return None  # a later MODIFY/REJECT or revocation supersedes
            return a
        return None

    # ------------------------------------------------------------------ invoke
    def invoke(self, case: Case, plan_id: Optional[str], step_id: Optional[str], tool_id: str,
               arguments: dict[str, Any], caused_by: str = "plan_step", actor_id: str = "agent:assure-v1") -> ProxyResult:
        plan = self.repo.get(InvestigationPlan, plan_id) if plan_id else None
        rules, denials, _ = self._authorize(case, plan, step_id, tool_id, arguments, caused_by)
        src_denies, src_holds, at = self._source_permission(case, plan, tool_id, arguments)
        if caused_by != "plan_step":
            src_denies, src_holds = [], []  # provenance already decides; no source-permission evidence for such attempts
        for hit in src_denies:
            rules.append(hit.rule_id)
            denials.append(hit.reason)
        # deny beats hold beats allow; a hold is recorded as a refusal (permission unverifiable), never retried silently
        if denials:
            decision = AuthorizationDecision.DENY
        elif src_holds:
            decision = AuthorizationDecision.HOLD
            rules.extend(h.rule_id for h in src_holds)
            denials = [f"permission_unverifiable: {h.reason}" for h in src_holds]
        else:
            decision = AuthorizationDecision.ALLOW
            rules.append((self.policy.allowed(tool_id) or {}).get("rule_id", "POL-TOOL-001"))
        receipt = ToolReceipt(
            tool_receipt_id=ids.next("CALL"), case_id=case.case_id, plan_id=plan_id, step_id=step_id,
            tool_id=tool_id, arguments_hash=sha256_hex(canonical_json(arguments)),
            authorization_decision=decision, authorization_rule_ids=rules, denial_reasons=denials,
            tool_call_status=ToolCallStatus.EXECUTED if decision == AuthorizationDecision.ALLOW else ToolCallStatus.DENIED,
        )
        if decision != AuthorizationDecision.ALLOW:
            refs = [receipt.tool_receipt_id]
            gate_evidence: Optional[Evidence] = None
            if src_denies or src_holds:
                gate_evidence = self._gate_evidence(case, receipt, tool_id, arguments, decision, src_denies + src_holds, at)
                receipt.response_evidence_ids = [gate_evidence.evidence_id]
                self.repo.put(gate_evidence)
                refs.append(gate_evidence.evidence_id)
            self.repo.put(receipt)
            word = "held" if decision == AuthorizationDecision.HOLD else "denied"
            origin = f" (caused_by={caused_by}, requested by {actor_id})" if caused_by != "plan_step" else ""
            self.repo.append_event(case.case_id, "TOOL_DENIED", "SYSTEM", "tool-proxy",
                                   f"{tool_id} {word}{origin}: {'; '.join(denials)}", refs)
            return ProxyResult(receipt, gate_evidence)

        receipt.invoked_at = clock.iso()
        case.tool_calls_used += 1
        self.repo.put(case)
        evidence: Optional[Evidence] = None
        try:
            result = self.mcp.call(case.scenario_id or "", tool_id, arguments)
            record = result["record"]
            receipt.response_digest = sha256_hex(canonical_json(record))
            evidence = self._to_evidence(case, receipt, result)
            receipt.response_evidence_ids = [evidence.evidence_id]
        except (ToolUnavailable, ToolTimeout) as exc:
            receipt.tool_call_status = ToolCallStatus.FAILED
            receipt.error = str(exc)
            evidence = Evidence(
                evidence_id=ids.next("EVD"), case_id=case.case_id, source_type="AUTHORIZED_MCP_FIXTURE",
                source_ref=(CATALOG[tool_id].source_ref), tool_receipt_id=receipt.tool_receipt_id,
                retrieved_at=clock.iso(), status=EvidenceStatus.UNAVAILABLE,
                data_categories=[CATALOG[tool_id].data_category],
                fields={"tool_id": tool_id, "arguments": arguments, "error": str(exc)},
            )
            receipt.response_evidence_ids = [evidence.evidence_id]
        receipt.completed_at = clock.iso()
        self.repo.put(evidence)
        self.repo.put(receipt)
        kind = "TOOL_INVOKED" if receipt.tool_call_status == ToolCallStatus.EXECUTED else "TOOL_FAILED"
        self.repo.append_event(case.case_id, kind, "SYSTEM", "tool-proxy",
                               f"{tool_id}({canonical_json(arguments)}) -> {receipt.tool_call_status.value}",
                               [receipt.tool_receipt_id, evidence.evidence_id])
        if evidence.untrusted_instruction_detected:
            span = evidence.fields.get("instruction_span", "")
            self.repo.append_event(case.case_id, "INJECTION_FLAGGED", "SYSTEM", "tool-proxy",
                                   f"Tool response contains instruction-like text; treated as data only: \"{span[:120]}\"",
                                   [evidence.evidence_id])
            target = instruction_target(span)
            if target and caused_by == "plan_step":
                # Put the refusal on the record: the call the text asks for is submitted with its true provenance
                # (document_span) and the gate denies it. Nothing ever runs on a document's say-so.
                self.invoke(case, plan_id, None, target, self._instruction_arguments(target, case, span),
                            caused_by="document_span", actor_id=f"document:{evidence.document_id or tool_id}")
        return ProxyResult(receipt, evidence)

    def _instruction_arguments(self, target: str, case: Case, span: str) -> dict[str, Any]:
        """Arguments the instruction implies; they are only ever hashed into a DENIED receipt."""
        client = self.policy.records(case.scenario_id).client_id or case.subject.reference_id
        if target == "unrestricted_web_search":
            return {"query": span[:80]}
        return {"client_id": client}

    def _to_evidence(self, case: Case, receipt: ToolReceipt, result: dict) -> Evidence:
        raw = dict(result["record"])
        span = find_instruction(raw)  # scanned on the raw text; the text stays data
        record, masking = filter_result(raw, self.policy.data)  # analyst view: identifiers masked, Art. 9 rows removed
        excerpt = record.get("excerpt") or record.get("note")
        case_time = self.policy.records(case.scenario_id).case_time  # the reference time of the case, if the fixture pins one
        stamp = {"as_of_case_time": case_time.isoformat()} if case_time else {}
        if masking["masked_fields"] or masking["rows_removed_art9"]:
            stamp["masking"] = masking
        if span:
            stamp["instruction_span"] = span[:200]
        return Evidence(
            evidence_id=ids.next("EVD"), case_id=case.case_id, source_type="AUTHORIZED_MCP_FIXTURE",
            source_ref=result["source_ref"], tool_receipt_id=receipt.tool_receipt_id,
            document_id=record.get("document_id"), entity_id=record.get("entity_id"),
            published_at=record.get("published_at"), retrieved_at=clock.iso(),
            content_sha256=sha256_hex(canonical_json(record)), data_categories=[result["data_category"]],
            status=EvidenceStatus.AVAILABLE, original_excerpt=excerpt,
            fields={"tool_id": result["tool_id"], **record, **stamp},
            authenticity_verification="NOT_VERIFIED", authorized_for_case=True,
            untrusted_instruction_detected=bool(span),
        )
