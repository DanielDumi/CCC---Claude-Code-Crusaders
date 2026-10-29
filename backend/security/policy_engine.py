"""Deterministic legal/policy preflight (spec 04 §6) and the plan-hash helper.

No LLM is involved here. The preflight status is computed only from the versioned YAML policy,
the tool catalogue and the exact plan revision.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from backend.domain.models import (
    Case, InvestigationPlan, PolicyCheck, Preflight, PreflightCheckResult, PreflightStatus,
)
from backend.security.source_rules import Records, evaluate_call, records_for
from backend.tools.catalog import CATALOG
from backend.util import clock, hash_without, ids

POLICY_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "policies" / "demo-policy.yaml"


class Policy:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        # The tool proxy binds this to its fixture server so preflight and proxy read the same records
        # (and the same simulated outages). Without it, the fixtures are read from disk.
        self.records_provider: Optional[Callable[[str], Records]] = None

    def records(self, scenario_id: Optional[str]) -> Records:
        """The bank's own records (consents, application status) the gate reads for a case."""
        return records_for(scenario_id, self.records_provider)

    @classmethod
    def load(cls, path: Path = POLICY_PATH) -> "Policy":
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")))

    @property
    def version(self) -> str:
        return self.data["policy_version"]

    @property
    def legal_snapshot(self) -> str:
        return self.data["legal_reference_snapshot"]

    def allowed(self, tool_id: str) -> dict | None:
        return self.data["allowed_tools"].get(tool_id)

    def deny_rule(self, tool_id: str) -> str | None:
        return self.data.get("deny_tools", {}).get(tool_id)

    def forbidden_category_rule(self, category: str) -> str | None:
        return self.data.get("forbidden_data_categories", {}).get(category)

    @property
    def max_total_tool_calls(self) -> int:
        return int(self.data["max_total_tool_calls"])

    @property
    def max_approved_plans(self) -> int:
        return int(self.data["max_approved_plans"])

    @property
    def approval_ttl_minutes(self) -> int:
        return int(self.data.get("approval_ttl_minutes", 30))

    def rule(self, rule_id: str) -> dict:
        return self.data.get("rules", {}).get(rule_id, {"title": rule_id})


def compute_plan_hash(plan: InvestigationPlan) -> str:
    """SHA-256 over the canonical plan without plan_hash and lifecycle status."""
    return hash_without(plan, "plan_hash", "status")


def preflight(plan: InvestigationPlan, case: Case, policy: Policy, *, calls_used: int = 0,
              records: Optional[Records] = None) -> Preflight:
    checks: list[PreflightCheckResult] = []
    conditions: list[str] = []
    blocked = review = False
    records = records or policy.records(case.scenario_id)
    at = records.case_time or clock.now()

    def add(category: str, result: PolicyCheck, rule_id: str, explanation: str, step_id: str | None = None):
        checks.append(PreflightCheckResult(check_id=f"PC-{len(checks) + 1:03d}", step_id=step_id,
                                           category=category, result=result, rule_id=rule_id,
                                           explanation=explanation))

    # Purpose
    if case.purpose not in policy.data["allowed_case_purposes"] or plan.purpose != case.purpose:
        review = True
        add("CASE_PURPOSE", PolicyCheck.NEEDS_REVIEW, "POL-PURPOSE-001",
            f"Purpose '{plan.purpose}' is not an approved business purpose for this case.")
    else:
        add("CASE_PURPOSE", PolicyCheck.PASS, "POL-PURPOSE-001", f"Purpose '{plan.purpose}' approved.")

    # Budget
    planned_calls = sum(s.max_calls for s in plan.steps)
    if planned_calls > plan.global_max_tool_calls or calls_used + planned_calls > policy.max_total_tool_calls:
        blocked = True
        add("BUDGET", PolicyCheck.FAIL, "POL-BUDGET-001",
            f"Plan needs {planned_calls} calls; {calls_used} already used of {policy.max_total_tool_calls}.")
    else:
        add("BUDGET", PolicyCheck.PASS, "POL-BUDGET-001",
            f"{planned_calls} planned calls within budget ({calls_used}/{policy.max_total_tool_calls} used).")

    if not plan.steps:
        blocked = True
        add("PLAN_SCOPE", PolicyCheck.FAIL, "POL-SCOPE-001",
            "No permitted investigation step remains; nothing can be approved. Close as blocked or change the case.")

    # Steps
    for step in plan.steps:
        spec = CATALOG.get(step.tool_id)
        deny = policy.deny_rule(step.tool_id)
        if deny:
            blocked = True
            add("TOOL_ALLOWLIST", PolicyCheck.FAIL, deny,
                f"{step.tool_id}: {policy.rule(deny).get('title', 'denied by policy')}.", step.step_id)
            continue
        if spec is None or not spec.enabled:
            blocked = True
            add("TOOL_ALLOWLIST", PolicyCheck.FAIL, "POL-TOOL-002", f"{step.tool_id}: not in the tool catalogue.",
                step.step_id)
            continue
        allowed = policy.allowed(step.tool_id)
        if not allowed:
            blocked = True
            add("TOOL_ALLOWLIST", PolicyCheck.FAIL, "POL-TOOL-002", f"{step.tool_id}: not allowed by policy.",
                step.step_id)
            continue
        if step.action not in allowed["actions"] or not spec.read_only:
            blocked = True
            add("ACTION", PolicyCheck.FAIL, "POL-ACT-001", f"{step.tool_id}: action {step.action} not permitted.",
                step.step_id)
            continue
        bad_cats = [c for c in step.data_categories if c not in allowed["categories"]]
        forb = [c for c in step.data_categories if policy.forbidden_category_rule(c)]
        if forb:
            blocked = True
            rid = policy.forbidden_category_rule(forb[0])
            add("GDPR_PERSONAL_DATA", PolicyCheck.FAIL, rid, f"{step.tool_id}: data category {forb[0]} is blocked.",
                step.step_id)
            continue
        if bad_cats or (step.allowed_source_ref and step.allowed_source_ref != allowed["source"]):
            blocked = True
            add("SOURCE_SCOPE", PolicyCheck.FAIL, "POL-SRC-001",
                f"{step.tool_id}: source/categories do not match the catalogue entry.", step.step_id)
            continue
        add("TOOL_ALLOWLIST", PolicyCheck.PASS, allowed.get("rule_id", "POL-TOOL-001"),
            f"{step.tool_id}: read-only, {', '.join(allowed['categories'])}.", step.step_id)
        for cond in allowed.get("conditions", []):
            if cond not in conditions:
                conditions.append(cond)
        # Source permission (SRC-*): consent per source, application status. Predicted here from the
        # bank's records; the proxy enforces the same rules at call time (state can change in between).
        for hit in evaluate_call(step.tool_id, step.arguments, plan.purpose, policy.data, records, at):
            mode = policy.rule(hit.rule_id).get("preflight") or ("REVIEW" if hit.outcome == "hold" else "CONDITION")
            if mode == "BLOCK":
                blocked = True
                add("SOURCE_PERMISSION", PolicyCheck.FAIL, hit.rule_id, f"{step.tool_id}: {hit.reason}", step.step_id)
            elif mode == "REVIEW":
                review = True
                add("SOURCE_PERMISSION", PolicyCheck.NEEDS_REVIEW, hit.rule_id, f"{step.tool_id}: {hit.reason}",
                    step.step_id)
            else:
                add("SOURCE_PERMISSION", PolicyCheck.NEEDS_REVIEW, hit.rule_id,
                    f"{step.tool_id}: will be refused at run time. {hit.reason}", step.step_id)
                conditions.append(f"{step.step_id} ({step.tool_id}) will be refused at run time: {hit.reason}")

    if not blocked and policy.data.get("forbid_real_personal_data"):
        add("GDPR_PERSONAL_DATA", PolicyCheck.NOT_APPLICABLE, "POL-DEMO-SYNTHETIC-ONLY",
            "Synthetic legal-entity fixtures only; no real personal data. Would need a lawful-basis reference in production.")

    if blocked:
        status = PreflightStatus.BLOCKED
        conditions = []
    elif review:
        status = PreflightStatus.LEGAL_REVIEW_REQUIRED
    elif conditions or plan.reviewer_restrictions:
        status = PreflightStatus.ALLOWED_WITH_CONDITIONS
        conditions += [r for r in plan.reviewer_restrictions if r not in conditions]
    else:
        status = PreflightStatus.ALLOWED

    return Preflight(
        preflight_id=ids.next("PREF"), plan_id=plan.plan_id, plan_hash=plan.plan_hash,
        policy_version=policy.version, legal_reference_snapshot=policy.legal_snapshot, status=status,
        checks=checks, conditions=conditions, legal_review_required=status == PreflightStatus.LEGAL_REVIEW_REQUIRED,
        ai_act_notes=list(policy.data.get("ai_act_notes", [])), checked_at=clock.iso(),
    )
