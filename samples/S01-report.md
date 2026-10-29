# Investigation report — CASE-DEMO-001

> Prepared as supporting governance evidence; not a certification or legal opinion. Synthetic demo data and demo policies only. The sign-off is not a banking or credit decision.

- **Subject:** NOVA Logistics SRL (`RO-DEMO-48219370`) — synthetic
- **Purpose:** corporate_due_diligence_demo  ·  **Origin:** AI_AGENT (SIMULATED-BANK-AGENT)
- **Closure state:** `CLOSED_WITH_ISSUES`
- **Policy:** demo-policy-2026-10-28-v2  ·  **Legal snapshot:** eu-ai-act-2026-07-27
- **Model:** mock  ·  **Generated:** 2026-10-29T07:05:05Z
- **Pack SHA-256:** `2206c45a3125f8453b0e4ff94846ba3b23064f89fc23e12ac9f5775c1b7c3494`  ·  **Ledger:** verified (34 events)

## Original finding
> NOVA Logistics SRL is currently involved in an ongoing legal dispute (case C-001).

## Claim verdicts
| Claim | Verdict | Reason | Supporting | Contradicting | Limits |
|---|---|---|---|---|---|
| CL-001: A legal dispute involving NOVA Logistics SRL (case C-001) existed in 2024. | **SUPPORTED** | demo://news-archive/2024-03-14/nova (2024-03-14) reports case C-001; registry confirms NOVA Logistics SRL = RO-DEMO-48219370. | EVD-OLD-ARTICLE, EVD-001 | — | Historical source; says nothing about the current status |
| CL-002: That same dispute (case C-001) is ongoing as of October 2026. | **CONTRADICTED** | demo://licensed-legal-registry: case C-001 is CLOSED since 2026-09-03; the claim says OPEN. The older source supports only the historical claim. | EVD-OLD-ARTICLE | EVD-002, EVD-003 | Signature check is a SIMULATED fixture, not a qualified e-signature validation |

## Plans, preflights and human decisions
### PLAN-CASE-DEMO-001-v1 (v1, `50bf6b5c63bd5ced…`, SUPERSEDED)
- S1: `company_registry_lookup` {'company_id': 'RO-DEMO-48219370'} — Check legal-entity identifier
- S2: `legal_case_status_lookup` {'case_ref': 'C-001', 'company_id': 'RO-DEMO-48219370'} — Verify current status of case C-001
- S3: `unrestricted_web_search` {'query': 'NOVA Logistics SRL lawsuit latest news'} — Broad web search for recent coverage
- **Preflight PREF-001: BLOCKED**
  - TOOL_ALLOWLIST FAIL `POL-DATA-001`: unrestricted_web_search: No unrestricted people-search or open web search.
- Human: **MODIFY** by demo-reviewer-01 (BANK_CASE_REVIEWER) at 2026-10-29T07:05:05Z — No open websites

### PLAN-CASE-DEMO-001-v2 (v2, `b9be2f93cbc616bf…`, APPROVED)
- S1: `company_registry_lookup` {'company_id': 'RO-DEMO-48219370'} — Check legal-entity identifier
- S2: `legal_case_status_lookup` {'case_ref': 'C-001', 'company_id': 'RO-DEMO-48219370'} — Verify current status of case C-001
- Reviewer restrictions: Only the company registry and the licensed court registry.; Excluded by reviewer: unrestricted_web_search
- **Preflight PREF-002: ALLOWED_WITH_CONDITIONS** — conditions: Read-only access; Exact company and case identifiers only; Only the company registry and the licensed court registry.; Excluded by reviewer: unrestricted_web_search
  - GDPR_PERSONAL_DATA NOT_APPLICABLE `POL-DEMO-SYNTHETIC-ONLY`: Synthetic legal-entity fixtures only; no real personal data. Would need a lawful-basis reference in production.
- Human: **APPROVE** by demo-reviewer-01 (BANK_CASE_REVIEWER) at 2026-10-29T07:05:05Z

### PLAN-CASE-DEMO-001-v3 (v3, `c384de03a6e09c92…`, APPROVED)
- S1: `document_signature_check` {'document_id': 'DOC-CASE-2026'} — Check authenticity of DOC-CASE-2026 before relying on it
- Reviewer restrictions: Only the company registry and the licensed court registry.; Excluded by reviewer: unrestricted_web_search
- **Preflight PREF-003: ALLOWED_WITH_CONDITIONS** — conditions: Simulated fixture signature check; not a qualified e-signature validation; Only the company registry and the licensed court registry.; Excluded by reviewer: unrestricted_web_search
  - GDPR_PERSONAL_DATA NOT_APPLICABLE `POL-DEMO-SYNTHETIC-ONLY`: Synthetic legal-entity fixtures only; no real personal data. Would need a lawful-basis reference in production.
- Human: **APPROVE** by demo-reviewer-01 (BANK_CASE_REVIEWER) at 2026-10-29T07:05:05Z

## Tool calls (through the approval-bound proxy)
| Receipt | Plan/step | Tool | Decision | Status | Rules | Note |
|---|---|---|---|---|---|---|
| CALL-001 | PLAN-CASE-DEMO-001-v2/S1 | `unrestricted_web_search` | DENY | DENIED | POL-DATA-001, POL-TOOL-002, PLAN-001, PLAN-001, PLAN-003 | unrestricted_web_search is forbidden by policy (hard deny, cannot be approved); unrestricted_web_search is not an enabled catalogue tool; Tool unrestricted_web_search does not match approved step S1 (company_registry_lookup); Arguments differ from the approved step; unrestricted_web_search was excluded by the reviewer |
| CALL-002 | PLAN-CASE-DEMO-001-v2/S1 | `company_registry_lookup` | ALLOW | EXECUTED | POL-TOOL-001 |  |
| CALL-003 | PLAN-CASE-DEMO-001-v2/S2 | `legal_case_status_lookup` | ALLOW | EXECUTED | POL-TOOL-001 |  |
| CALL-004 | PLAN-CASE-DEMO-001-v3/S1 | `document_signature_check` | ALLOW | EXECUTED | POL-TOOL-001 |  |

## Evidence
- `EVD-OLD-ARTICLE` AVAILABLE — demo://news-archive/2024-03-14/nova (2024-03-14T08:00:00Z); sha256 `5cd215f12274`; authenticity: NOT_VERIFIED
  > NOVA Logistics SRL was involved in an open dispute, case C-001.
- `EVD-001` AVAILABLE — demo://company-registry (n/a); sha256 `d12405d19fb1`; authenticity: NOT_VERIFIED
- `EVD-002` AVAILABLE — demo://licensed-legal-registry (2026-09-03T10:00:00Z); sha256 `2f0c6702b308`; authenticity: NOT_VERIFIED
  > Case C-001: status closed on 2026-09-03.
- `EVD-003` AVAILABLE — demo://documents (n/a); sha256 `654db60a17c6`; authenticity: NOT_VERIFIED
  > trusted demo metadata matched (simulated)

## AI Act relevance (supporting evidence only)
- Verified system: SIMULATED-BANK-AGENT demo-1.0 — risk classification **UNCONFIRMED**, role **UNCONFIRMED**
- Art. 12 logging: event ledger (hash-chained) — NEEDS_LEGAL_CONFIRMATION
- Art. 14 human oversight: plan approvals/modifications, stop, final sign-off — NEEDS_LEGAL_CONFIRMATION
- Art. 26 deployer duties: reviewer actions, input relevance (claim-level checks) — NEEDS_LEGAL_CONFIRMATION

## Open issues and trace gaps
- CL-002 CONTRADICTED: demo://licensed-legal-registry: case C-001 is CLOSED since 2026-09-03; the claim says OPEN. The older source supports only the historical claim.
- Gap: Original agent execution trace: PARTIALLY_CAPTURED

## Event timeline
- 2026-10-29T07:05:05Z `CASE_RECEIVED` (AI_AGENT:SIMULATED-BANK-AGENT) Case received; finding sha256 d4b491ff18a8…; trace PARTIALLY_CAPTURED
- 2026-10-29T07:05:05Z `CLAIMS_ASSESSED` (AI_AGENT:planner (mock)) 2 claims, 3 gaps
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) RECEIVED -> ASSESSED
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) ASSESSED -> PLAN_DRAFTED: PLAN-CASE-DEMO-001-v1
- 2026-10-29T07:05:05Z `PLAN_PROPOSED` (AI_AGENT:INVESTIGATION_AGENT (mock)) v1 hash 50bf6b5c63bd…: company_registry_lookup, legal_case_status_lookup, unrestricted_web_search
- 2026-10-29T07:05:05Z `PREFLIGHT_COMPLETED` (SYSTEM:policy-preflight) BLOCKED (demo-policy-2026-10-28-v2)
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) PLAN_DRAFTED -> PREFLIGHT_BLOCKED: BLOCKED
- 2026-10-29T07:05:05Z `PLAN_MODIFY` (HUMAN:demo-reviewer-01) PLAN-CASE-DEMO-001-v1: No open websites
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) PREFLIGHT_BLOCKED -> PLAN_DRAFTED: PLAN-CASE-DEMO-001-v2
- 2026-10-29T07:05:05Z `PLAN_PROPOSED` (AI_AGENT:INVESTIGATION_AGENT (mock)) v2 hash b9be2f93cbc6…: company_registry_lookup, legal_case_status_lookup
- 2026-10-29T07:05:05Z `PREFLIGHT_COMPLETED` (SYSTEM:policy-preflight) ALLOWED_WITH_CONDITIONS (demo-policy-2026-10-28-v2)
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) PLAN_DRAFTED -> AWAITING_PLAN_APPROVAL: ALLOWED_WITH_CONDITIONS
- 2026-10-29T07:05:05Z `PLAN_APPROVED` (HUMAN:demo-reviewer-01) PLAN-CASE-DEMO-001-v2 hash b9be2f93cbc6… approved
- 2026-10-29T07:05:05Z `STATE_CHANGED` (HUMAN:demo-reviewer-01) AWAITING_PLAN_APPROVAL -> APPROVED
- 2026-10-29T07:05:05Z `TOOL_DENIED` (SYSTEM:tool-proxy) unrestricted_web_search denied: unrestricted_web_search is forbidden by policy (hard deny, cannot be approved); unrestricted_web_search is not an enabled catalogue tool; Tool unrestricted_web_search does not match approved step S1 (company_registry_lookup); Arguments differ from the approved step; unrestricted_web_search was excluded by the reviewer
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) APPROVED -> EXECUTING
- 2026-10-29T07:05:05Z `TOOL_INVOKED` (SYSTEM:tool-proxy) company_registry_lookup({"company_id":"RO-DEMO-48219370"}) -> EXECUTED
- 2026-10-29T07:05:05Z `TOOL_INVOKED` (SYSTEM:tool-proxy) legal_case_status_lookup({"case_ref":"C-001","company_id":"RO-DEMO-48219370"}) -> EXECUTED
- 2026-10-29T07:05:05Z `FINDING_UPDATED` (AI_AGENT:verification-engine) CL-001: SUPPORTED
- 2026-10-29T07:05:05Z `FINDING_UPDATED` (AI_AGENT:verification-engine) CL-002: CONTRADICTED
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) EXECUTING -> FINDINGS_READY: CL-001=SUPPORTED, CL-002=CONTRADICTED
- 2026-10-29T07:05:05Z `STATE_CHANGED` (AI_AGENT:agent:assure-v1) FINDINGS_READY -> REPLAN_REQUIRED: new scope needed: document_signature_check:DOC-CASE-2026
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) REPLAN_REQUIRED -> PLAN_DRAFTED: PLAN-CASE-DEMO-001-v3
- 2026-10-29T07:05:05Z `PLAN_PROPOSED` (AI_AGENT:INVESTIGATION_AGENT (mock)) v3 hash c384de03a6e0…: document_signature_check
- 2026-10-29T07:05:05Z `PREFLIGHT_COMPLETED` (SYSTEM:policy-preflight) ALLOWED_WITH_CONDITIONS (demo-policy-2026-10-28-v2)
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) PLAN_DRAFTED -> AWAITING_PLAN_APPROVAL: ALLOWED_WITH_CONDITIONS
- 2026-10-29T07:05:05Z `PLAN_APPROVED` (HUMAN:demo-reviewer-01) PLAN-CASE-DEMO-001-v3 hash c384de03a6e0… approved
- 2026-10-29T07:05:05Z `STATE_CHANGED` (HUMAN:demo-reviewer-01) AWAITING_PLAN_APPROVAL -> APPROVED
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) APPROVED -> EXECUTING
- 2026-10-29T07:05:05Z `TOOL_INVOKED` (SYSTEM:tool-proxy) document_signature_check({"document_id":"DOC-CASE-2026"}) -> EXECUTED
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) EXECUTING -> FINDINGS_READY: CL-001=SUPPORTED, CL-002=CONTRADICTED
- 2026-10-29T07:05:05Z `STATE_CHANGED` (SYSTEM:orchestrator) FINDINGS_READY -> AWAITING_FINAL_REVIEW
- 2026-10-29T07:05:05Z `FINAL_SIGN_OFF` (HUMAN:demo-reviewer-01) Findings reviewed; any banking decision is separate.
- 2026-10-29T07:05:05Z `STATE_CHANGED` (HUMAN:demo-reviewer-01) AWAITING_FINAL_REVIEW -> CLOSED_WITH_ISSUES: sign-off (not a banking or credit decision)
