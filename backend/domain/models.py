"""Canonical domain models (spec/build-spec/06_DATA_MODELS_AND_CONTRACTS.md).

Enum values are copied verbatim from the spec; do not rename them without the tech lead.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class CaseOrigin(StrEnum):
    AI_AGENT = "AI_AGENT"
    HUMAN = "HUMAN"


class CaseState(StrEnum):
    RECEIVED = "RECEIVED"
    ASSESSED = "ASSESSED"
    PLAN_DRAFTED = "PLAN_DRAFTED"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
    LEGAL_REVIEW_REQUIRED = "LEGAL_REVIEW_REQUIRED"
    AWAITING_PLAN_APPROVAL = "AWAITING_PLAN_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    FINDINGS_READY = "FINDINGS_READY"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    AWAITING_FINAL_REVIEW = "AWAITING_FINAL_REVIEW"
    CLOSED_VERIFIED = "CLOSED_VERIFIED"
    CLOSED_WITH_ISSUES = "CLOSED_WITH_ISSUES"
    CLOSED_UNRESOLVED = "CLOSED_UNRESOLVED"
    CLOSED_BLOCKED = "CLOSED_BLOCKED"


class PlanDecision(StrEnum):
    APPROVE = "APPROVE"
    MODIFY = "MODIFY"
    REJECT = "REJECT"


class PreflightStatus(StrEnum):
    ALLOWED = "ALLOWED"
    ALLOWED_WITH_CONDITIONS = "ALLOWED_WITH_CONDITIONS"
    BLOCKED = "BLOCKED"
    LEGAL_REVIEW_REQUIRED = "LEGAL_REVIEW_REQUIRED"


class ClaimVerdict(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_CHECKED = "NOT_CHECKED"


class EvidenceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CAPTURED = "NOT_CAPTURED"
    REDACTED = "REDACTED"


class PolicyCheck(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ToolCallStatus(StrEnum):
    EXECUTED = "EXECUTED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class FinalReview(StrEnum):
    SIGN_OFF = "SIGN_OFF"
    REQUEST_MORE_WORK = "REQUEST_MORE_WORK"
    REJECT_FINDINGS = "REJECT_FINDINGS"


class AuthorizationDecision(StrEnum):
    """Gate outcome per call. HOLD added per DISCREPANCIES A4 (a needed fact was unavailable)."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    HOLD = "HOLD"


class CheckType(StrEnum):
    """How a claim is verified. Chosen by the assessor, executed by deterministic code."""
    HISTORICAL_EVENT = "HISTORICAL_EVENT"
    CURRENT_STATUS = "CURRENT_STATUS"
    ENTITY_ATTRIBUTION = "ENTITY_ATTRIBUTION"
    FACT_PRESENCE = "FACT_PRESENCE"
    VERSIONED_FIGURE = "VERSIONED_FIGURE"
    CALCULATION = "CALCULATION"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


# ---------------------------------------------------------------- intake
class Subject(_Model):
    type: str = "LEGAL_ENTITY"
    display_name: str
    reference_id: Optional[str] = None
    jurisdiction: Optional[str] = None


class OriginSystem(_Model):
    system_id: str = "SIMULATED-BANK-AGENT"
    version: str = "demo-1.0"
    ai_act_risk_classification: str = "UNCONFIRMED"
    provider_deployer_role: str = "UNCONFIRMED"


class CreateCaseRequest(_Model):
    origin: CaseOrigin
    case_id: str
    purpose: str
    subject: Subject
    origin_system: OriginSystem = Field(default_factory=OriginSystem)
    raw_finding: str
    initial_evidence_ids: list[str] = Field(default_factory=list)
    original_execution_trace_status: str = "NOT_CAPTURED"
    reviewer_id: str
    scenario_id: Optional[str] = None


class Case(_Model):
    case_id: str
    origin: CaseOrigin
    purpose: str
    subject: Subject
    origin_system: OriginSystem
    raw_finding: str
    raw_finding_sha256: str
    initial_evidence_ids: list[str]
    original_execution_trace_status: str
    reviewer_id: str
    scenario_id: Optional[str] = None
    state: CaseState = CaseState.RECEIVED
    created_at: str
    plan_count: int = 0
    tool_calls_used: int = 0
    current_plan_id: Optional[str] = None
    stopped: bool = False


# ---------------------------------------------------------------- claims & evidence
class Claim(_Model):
    claim_id: str
    case_id: str
    claim_text: str
    temporal_scope: str = "UNSPECIFIED"  # HISTORICAL | CURRENT | UNSPECIFIED
    source_claim_origin: str = "ORIGINAL_AGENT_OUTPUT"
    required_evidence: list[str] = Field(default_factory=list)
    check_type: CheckType
    params: dict[str, Any] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)


class Assessment(_Model):
    case_id: str
    claims: list[Claim]
    gaps: list[str]
    produced_by: str  # "mock" | model id


class Evidence(_Model):
    evidence_id: str
    case_id: str
    source_type: str
    source_ref: str
    tool_receipt_id: Optional[str] = None
    document_id: Optional[str] = None
    entity_id: Optional[str] = None
    published_at: Optional[str] = None
    retrieved_at: Optional[str] = None
    content_sha256: Optional[str] = None
    data_categories: list[str] = Field(default_factory=list)
    status: EvidenceStatus
    original_excerpt: Optional[str] = None
    fields: dict[str, Any] = Field(default_factory=dict)
    authenticity_verification: str = "NOT_VERIFIED"
    authorized_for_case: bool = True
    untrusted_instruction_detected: bool = False


# ---------------------------------------------------------------- plan, preflight, approval
class PlanStep(_Model):
    step_id: str
    claim_ids: list[str]
    objective: str
    tool_id: str
    action: str = "READ"
    arguments: dict[str, Any] = Field(default_factory=dict)
    allowed_source_ref: Optional[str] = None
    data_categories: list[str] = Field(default_factory=list)
    max_calls: int = 1
    depends_on: list[str] = Field(default_factory=list)
    expected_evidence: str = ""


class InvestigationPlan(_Model):
    plan_id: str
    case_id: str
    version: int
    plan_hash: str = ""
    created_by: str = "INVESTIGATION_AGENT"
    objective: str
    purpose: str
    data_categories: list[str]
    source_allowlist: list[str]
    forbidden_tools: list[str] = Field(default_factory=list)
    reviewer_restrictions: list[str] = Field(default_factory=list)
    global_max_tool_calls: int
    expires_at: str
    rationale: str = ""
    steps: list[PlanStep]
    supersedes: Optional[str] = None
    status: str = "DRAFT"  # DRAFT | APPROVED | SUPERSEDED | REJECTED


class PreflightCheckResult(_Model):
    check_id: str
    step_id: Optional[str] = None
    category: str
    result: PolicyCheck
    rule_id: str
    explanation: str = ""


class Preflight(_Model):
    preflight_id: str
    plan_id: str
    plan_hash: str
    policy_version: str
    legal_reference_snapshot: str
    status: PreflightStatus
    checks: list[PreflightCheckResult]
    conditions: list[str] = Field(default_factory=list)
    legal_review_required: bool = False
    ai_act_notes: list[dict[str, str]] = Field(default_factory=list)
    checked_at: str


class Approval(_Model):
    decision_id: str
    plan_id: str
    plan_hash: str
    preflight_id: Optional[str]
    decision: PlanDecision
    reviewer_id: str
    reviewer_role: str
    restrictions: list[str] = Field(default_factory=list)
    structured_restrictions: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    decided_at: str
    authorization_expires_at: Optional[str] = None
    revoked: bool = False


# ---------------------------------------------------------------- execution
class ToolReceipt(_Model):
    tool_receipt_id: str
    case_id: str
    plan_id: Optional[str]
    step_id: Optional[str]
    tool_id: str
    arguments_hash: str
    authorization_decision: AuthorizationDecision
    authorization_rule_ids: list[str]
    denial_reasons: list[str] = Field(default_factory=list)
    tool_call_status: ToolCallStatus
    invoked_at: Optional[str] = None
    completed_at: Optional[str] = None
    response_evidence_ids: list[str] = Field(default_factory=list)
    response_digest: Optional[str] = None
    error: Optional[str] = None


class Finding(_Model):
    finding_id: str
    claim_id: str
    verdict: ClaimVerdict
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    reason: str
    reason_codes: list[str] = Field(default_factory=list)
    authenticity_limitations: list[str] = Field(default_factory=list)
    requires_human_review: bool = True
    next_action_proposal: Optional[str] = None
    explanation: Optional[str] = None


class FinalReviewRecord(_Model):
    signoff_id: str
    case_id: str
    decision: FinalReview
    reviewer_id: str
    reviewer_role: str
    acknowledged_unresolved: bool = False
    note: str = ""
    decided_at: str
    banking_decision_separate: bool = True


class Event(_Model):
    event_id: str
    case_id: str
    event_type: str
    actor_type: str  # SYSTEM | AI_AGENT | HUMAN
    actor_id: str
    timestamp: str
    summary: str = ""
    payload_refs: list[str] = Field(default_factory=list)
    previous_event_hash: str
    event_hash: str = ""
