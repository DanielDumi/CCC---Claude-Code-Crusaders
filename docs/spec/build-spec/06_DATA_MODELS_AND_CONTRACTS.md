# 06 — Data Models, JSON Contracts & Invariants

**Canonical domain names:** `Case`, `Claim`, `Evidence`, `InvestigationPlan`, `PlanStep`, `Preflight`, `Approval`, `ToolReceipt`, `Finding`, `Event`, `EvidencePack`.  
**Contracts are illustrative v1 payloads.** Implement strict validation using JSON Schema/Pydantic. Fields should be mapped to actual UI and source adapter identifiers, not copied blindly into production.

## 1. Canonical enums — use these exact names in code and all docs

```text
CaseOrigin:        AI_AGENT | HUMAN
CaseState:         RECEIVED | ASSESSED | PLAN_DRAFTED |
                   PREFLIGHT_BLOCKED | LEGAL_REVIEW_REQUIRED |
                   AWAITING_PLAN_APPROVAL | APPROVED | EXECUTING |
                   FINDINGS_READY | REPLAN_REQUIRED | AWAITING_FINAL_REVIEW |
                   CLOSED_VERIFIED | CLOSED_WITH_ISSUES |
                   CLOSED_UNRESOLVED | CLOSED_BLOCKED
PlanDecision:      APPROVE | MODIFY | REJECT
PreflightStatus:   ALLOWED | ALLOWED_WITH_CONDITIONS | BLOCKED |
                   LEGAL_REVIEW_REQUIRED
ClaimVerdict:      SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE | NOT_CHECKED
EvidenceStatus:    AVAILABLE | UNAVAILABLE | NOT_CAPTURED | REDACTED
PolicyCheck:       PASS | FAIL | NEEDS_REVIEW | NOT_APPLICABLE
ToolCallStatus:    EXECUTED | DENIED | FAILED | CANCELED
FinalReview:       SIGN_OFF | REQUEST_MORE_WORK | REJECT_FINDINGS
```

**Important separation:** `SUPPORTED` means supported by checked evidence, not objectively guaranteed true, lawful, or suitable for a credit decision. A `PreflightStatus` says whether an *investigation action* is permissible under known rules, not whether a claim is true.

## 2. Create-case request

```json
{
  "origin": "AI_AGENT",
  "case_id": "CASE-DEMO-001",
  "purpose": "corporate_due_diligence_demo",
  "subject": {
    "type": "LEGAL_ENTITY",
    "display_name": "NOVA Logistics SRL",
    "reference_id": "RO-DEMO-48219370"
  },
  "origin_system": {
    "system_id": "SIMULATED-BANK-AGENT",
    "version": "demo-1.0",
    "ai_act_risk_classification": "UNCONFIRMED",
    "provider_deployer_role": "UNCONFIRMED"
  },
  "raw_finding": "NOVA Logistics SRL is currently involved in an ongoing legal dispute.",
  "initial_evidence_ids": ["EVD-OLD-ARTICLE"],
  "original_execution_trace_status": "PARTIALLY_CAPTURED",
  "reviewer_id": "demo-reviewer-01"
}
```

**Mandatory on intake:** `case_id`, `origin`, `purpose`, `raw_finding` or human case notes, reviewer identity, timestamp. For real personal data, documented authority and lawful-basis references would also be mandatory per configured policy.

## 3. Claims

```json
[
  {
    "claim_id": "CL-001",
    "case_id": "CASE-DEMO-001",
    "claim_text": "A legal dispute involving NOVA Logistics SRL existed in 2024.",
    "temporal_scope": "HISTORICAL",
    "source_claim_origin": "ORIGINAL_AGENT_OUTPUT",
    "required_evidence": ["matching_entity_id", "document_publication_date"]
  },
  {
    "claim_id": "CL-002",
    "case_id": "CASE-DEMO-001",
    "claim_text": "That same dispute is ongoing as of October 2026.",
    "temporal_scope": "CURRENT",
    "source_claim_origin": "ORIGINAL_AGENT_OUTPUT",
    "required_evidence": ["same_case_reference", "current_authorized_status"]
  }
]
```

## 4. Evidence objects (with independent provenance)

```json
{
  "evidence_id": "EVD-REGISTRY-2026",
  "case_id": "CASE-DEMO-001",
  "source_type": "AUTHORIZED_MCP_FIXTURE",
  "source_ref": "demo://licensed-legal-registry/NOVA/C-001",
  "tool_receipt_id": "CALL-002",
  "document_id": "DOC-CASE-2026",
  "published_at": "2026-09-03T10:00:00Z",
  "retrieved_at": "2026-10-28T14:30:00Z",
  "content_sha256": "<64-hex-computed-by-runtime>",
  "data_categories": ["CORPORATE_LEGAL"],
  "status": "AVAILABLE",
  "original_excerpt": "Case C-001: status closed on 2026-09-03.",
  "authenticity_verification": "SIMULATED_FIXTURE_ONLY",
  "authorized_for_case": true
}
```

**Rules:** `content_sha256` is calculated by code over preserved bytes, never invented by an LLM. If source inaccessible, `status=UNAVAILABLE`; if no original trace existed, `status=NOT_CAPTURED`. Distinguish authorization, existence, citation support and authenticity in separate fields.

## 5. Investigation plan and tool steps

```json
{
  "plan_id": "PLAN-CASE-DEMO-001-v2",
  "case_id": "CASE-DEMO-001",
  "version": 2,
  "plan_hash": "<sha256-of-canonical-plan-without-plan_hash>",
  "created_by": "INVESTIGATION_AGENT",
  "objective": "Verify company identity and whether dispute C-001 is currently open.",
  "purpose": "corporate_due_diligence_demo",
  "data_categories": ["CORPORATE_PUBLIC", "CORPORATE_LEGAL"],
  "source_allowlist": ["demo://company-registry", "demo://licensed-legal-registry"],
  "forbidden_tools": ["unrestricted_web_search"],
  "global_max_tool_calls": 3,
  "expires_at": "2026-10-28T15:00:00Z",
  "steps": [
    {
      "step_id": "S1",
      "claim_ids": ["CL-001", "CL-002"],
      "objective": "Check legal-entity identifier",
      "tool_id": "company_registry_lookup",
      "action": "READ",
      "arguments": {"company_id": "RO-DEMO-48219370"},
      "allowed_source_ref": "demo://company-registry",
      "data_categories": ["CORPORATE_PUBLIC"],
      "max_calls": 1,
      "depends_on": [],
      "expected_evidence": "entity ID and registration metadata"
    },
    {
      "step_id": "S2",
      "claim_ids": ["CL-002"],
      "objective": "Verify current dispute status",
      "tool_id": "legal_case_status_lookup",
      "action": "READ",
      "arguments": {"company_id": "RO-DEMO-48219370", "case_ref": "C-001"},
      "allowed_source_ref": "demo://licensed-legal-registry",
      "data_categories": ["CORPORATE_LEGAL"],
      "max_calls": 1,
      "depends_on": ["S1"],
      "expected_evidence": "dated case status"
    }
  ]
}
```

A plan cannot authorize arbitrary `*` tool names, “any websites,” unlimited budgets, unspecified data categories, or a changed purpose. If human imposes restriction, plan version **must change** even if objective remains the same. Compute digest after canonical validation.

## 6. Preflight assessment — exact approved plan

```json
{
  "preflight_id": "PREF-002",
  "plan_id": "PLAN-CASE-DEMO-001-v2",
  "plan_hash": "<runtime-computed-sha256>",
  "policy_version": "demo-policy-2026-10-28-v1",
  "legal_reference_snapshot": "eu-ai-act-2026-07-27",
  "status": "ALLOWED_WITH_CONDITIONS",
  "checks": [
    {
      "check_id": "PC-001",
      "category": "TOOL_ALLOWLIST",
      "result": "PASS",
      "rule_id": "POL-TOOL-001"
    },
    {
      "check_id": "PC-002",
      "category": "GDPR_PERSONAL_DATA",
      "result": "NOT_APPLICABLE",
      "rule_id": "POL-DEMO-SYNTHETIC-ONLY",
      "explanation": "Synthetic legal-entity dataset only."
    }
  ],
  "conditions": ["Read-only access", "Exact company and case identifiers only"],
  "legal_review_required": false,
  "checked_at": "2026-10-28T14:28:00Z"
}
```

Do not say “GDPR not applicable” in a production corporate case when records include identifiable natural persons. Here it applies only because the fixture is synthetic and contains no real personal data.

## 7. Human decision / approval

```json
{
  "decision_id": "APR-002",
  "plan_id": "PLAN-CASE-DEMO-001-v2",
  "plan_hash": "<same-runtime-hash>",
  "preflight_id": "PREF-002",
  "decision": "APPROVE",
  "reviewer_id": "demo-reviewer-01",
  "reviewer_role": "BANK_CASE_REVIEWER",
  "restrictions": ["Only the two registry fixtures listed in v2"],
  "decided_at": "2026-10-28T14:29:00Z",
  "authorization_expires_at": "2026-10-28T15:00:00Z"
}
```

`APPROVE` must be bound to same hash and preflight. `MODIFY`/`REJECT` **never** produces an execution authorization. Record the full review chronology, including discarded plans and why.

## 8. Tool receipt / enforcement decision

```json
{
  "tool_receipt_id": "CALL-002",
  "case_id": "CASE-DEMO-001",
  "plan_id": "PLAN-CASE-DEMO-001-v2",
  "step_id": "S2",
  "tool_id": "legal_case_status_lookup",
  "arguments_hash": "<computed-hex>",
  "authorization_decision": "ALLOW",
  "authorization_rule_ids": ["POL-TOOL-001"],
  "tool_call_status": "EXECUTED",
  "invoked_at": "2026-10-28T14:30:00Z",
  "completed_at": "2026-10-28T14:30:01Z",
  "response_evidence_ids": ["EVD-REGISTRY-2026"],
  "response_digest": "<computed-hex>",
  "error": null
}
```

**DENIED event** must still be persisted, with `tool_call_status=DENIED` and `authorization_decision=DENY`; do **not** call the tool first and decide later.

## 9. Finding — per-claim evidence, no fake certainty

```json
{
  "finding_id": "FND-CL-002",
  "claim_id": "CL-002",
  "verdict": "CONTRADICTED",
  "supporting_evidence_ids": ["EVD-OLD-ARTICLE"],
  "contradicting_evidence_ids": ["EVD-REGISTRY-2026"],
  "reason": "Historical article supports that a dispute existed, but the authorized current status record says C-001 is closed.",
  "authenticity_limitations": ["Latest registry response is a demo fixture"],
  "requires_human_review": true,
  "next_action_proposal": null
}
```

Avoid treating latest date alone as proof. Consider source authority, entity and case ID, document status, and provenance. A `CONTRADICTED` conclusion can remain subject to human challenge.

## 10. Event ledger and evidence pack

**Event schema:**

```json
{
  "event_id": "EVT-00042",
  "case_id": "CASE-DEMO-001",
  "event_type": "TOOL_INVOKED",
  "actor_type": "SYSTEM",
  "actor_id": "tool-proxy",
  "timestamp": "2026-10-28T14:30:00Z",
  "payload_refs": ["CALL-002"],
  "previous_event_hash": "<computed-hash>",
  "event_hash": "<computed-hash>"
}
```

Use immutable/append-only storage semantics in app. A hash chain is tamper-*evident* for a local demonstration, not bank-grade immutable or trusted timestamp infrastructure.

**Evidence pack:**

```json
{
  "schema_version": "1.0",
  "pack_id": "PACK-CASE-DEMO-001",
  "case_id": "CASE-DEMO-001",
  "closure_state": "CLOSED_WITH_ISSUES",
  "original_artifact_refs": ["EVD-OLD-ARTICLE"],
  "plan_ids": ["PLAN-CASE-DEMO-001-v1", "PLAN-CASE-DEMO-001-v2"],
  "preflight_ids": ["PREF-001", "PREF-002"],
  "approval_ids": ["APR-002"],
  "tool_receipt_ids": ["CALL-001", "CALL-002"],
  "finding_ids": ["FND-CL-001", "FND-CL-002"],
  "human_signoff_id": "SIGNOFF-001",
  "ai_act_applicability": "UNCONFIRMED",
  "known_trace_gaps": [],
  "legal_assessment_disclaimer": "Supporting evidence only; not a compliance certificate.",
  "generated_at": "2026-10-28T14:35:00Z",
  "pack_sha256": "<computed-by-server>",
  "report_markdown_ref": "reports/CASE-DEMO-001.md"
}
```

`pack_sha256` should be computed over canonical pack bytes **excluding the hash field**. Include `effective_policy_version` and official legal reference identifiers in real pack payload even if snippet abbreviated; `preflight_ids` link back to both.

## 11. Validation invariants

1. `CaseState.APPROVED` implies a valid `APPROVE` record for the latest plan hash and acceptable preflight.
2. Every `EXECUTED` tool receipt has a permitted `step_id`, active approval, and policy authorization.
3. A `DENIED` tool receipt has no corresponding backend tool invocation.
4. Any plan edit generates a new version/hash and invalidates prior approval.
5. A finding with `SUPPORTED` has at least one cited checked evidence ID; contradictions and limitations are recorded.
6. Final pack's chronological events match stored case transitions and receipt IDs.
7. Missing original sources are represented as `NOT_CAPTURED`/`UNAVAILABLE`, not hallucinated.
8. User modifications cannot remove a hard deny or change the case purpose by prompt alone.
9. A new source/tool/action/data category always triggers preflight and approval.
10. Final human signoff is always a separate event from a banking customer decision.

## 12. How to implement

Implement shared Pydantic models first, freeze enum values, and generate OpenAPI schemas from the backend. Run JSON-schema validation both on LLM output and server input. Compare all docs to this file before authoring endpoint handlers.
