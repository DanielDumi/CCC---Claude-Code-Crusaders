# backend/domain/

`models.py` holds every data contract in the system as Pydantic v2 models. Names and enum values are copied verbatim from `docs/spec/build-spec/06_DATA_MODELS_AND_CONTRACTS.md`, so the code, the API, the evidence pack and the spec use the same words.

All models use `extra="forbid"`: an unknown field is an error, not something silently stored. This matters because some inputs come from a model.

## Enums

| Enum | Values | Meaning |
|---|---|---|
| `CaseState` | 15 states, `RECEIVED` … `CLOSED_BLOCKED` | Where a case is; transitions in `workflow/state_machine.py` |
| `ClaimVerdict` | `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`, `NOT_CHECKED` | Is the claim true, according to the evidence (truth track) |
| `PreflightStatus` | `ALLOWED`, `ALLOWED_WITH_CONDITIONS`, `BLOCKED`, `LEGAL_REVIEW_REQUIRED` | May this plan run (permission track) |
| `PlanDecision` | `APPROVE`, `MODIFY`, `REJECT` | The reviewer's decision on one plan version |
| `AuthorizationDecision` | `ALLOW`, `DENY`, `HOLD` | The gate's decision on one call. `HOLD` = a fact needed to decide could not be read, so the call does not run |
| `ToolCallStatus` | `EXECUTED`, `DENIED`, `FAILED`, `CANCELED` | What happened to a call |
| `EvidenceStatus` | `AVAILABLE`, `UNAVAILABLE`, `NOT_CAPTURED`, `REDACTED` | `NOT_CAPTURED` = cited but never received; we never invent it |
| `FinalReview` | `SIGN_OFF`, `REQUEST_MORE_WORK`, `REJECT_FINDINGS` | The final human decision |
| `CheckType` | `HISTORICAL_EVENT`, `CURRENT_STATUS`, `ENTITY_ATTRIBUTION`, `FACT_PRESENCE`, `VERSIONED_FIGURE`, `CALCULATION` | How a claim is verified (each one is a branch in `claim_verification.py`) |
| `PolicyCheck` | `PASS`, `FAIL`, `NEEDS_REVIEW`, `NOT_APPLICABLE` | Result of one preflight check |

`ClaimVerdict` and `PreflightStatus` are deliberately separate: a claim can be `SUPPORTED` by a source the bank was not allowed to use, and an `ALLOWED` plan can still find the claim is false.

## Objects, in the order a case creates them

| Model | Created by | Key fields |
|---|---|---|
| `CreateCaseRequest` → `Case` | API / intake | `raw_finding` + `raw_finding_sha256`, `purpose`, `subject`, `origin_system` (AI Act class `UNCONFIRMED` by default), `original_execution_trace_status`, `state`, `tool_calls_used` |
| `Claim`, `Assessment` | planner | `claim_text`, `temporal_scope` (HISTORICAL / CURRENT), `check_type`, `params` the verifier needs, `gaps` |
| `InvestigationPlan`, `PlanStep` | planner | `version`, `plan_hash`, `purpose`, `steps` (tool, arguments, claim ids, max calls, depends on), `forbidden_tools`, `reviewer_restrictions`, `expires_at`, `supersedes` |
| `Preflight`, `PreflightCheckResult` | policy engine | `plan_hash`, `policy_version`, `status`, one check per rule with `rule_id` and an explanation, `conditions`, `ai_act_notes` |
| `Approval` | reviewer | `plan_hash`, `preflight_id`, `decision`, `reviewer_role`, `restrictions`, `authorization_expires_at`, `revoked` |
| `ToolReceipt` | gate | `arguments_hash`, `authorization_decision`, `authorization_rule_ids`, `denial_reasons`, `tool_call_status`, `response_digest` |
| `Evidence` | gate / intake | `source_ref`, `content_sha256`, `status`, `fields` (the filtered record), `authenticity_verification`, `untrusted_instruction_detected` |
| `Finding` | verifier | `verdict`, supporting / contradicting evidence ids, `reason`, `reason_codes`, `authenticity_limitations`, `next_action_proposal`, `explanation` (LLM text) |
| `FinalReviewRecord` | reviewer | `decision`, `acknowledged_unresolved`, `banking_decision_separate=True` |
| `Event` | everything, through the repository | `event_type`, `actor_type` (SYSTEM / AI_AGENT / HUMAN), `actor_id`, `previous_event_hash`, `event_hash` |

## Changing a contract

Every other module depends on these names. A new field or enum value has to be agreed with the tech lead first, then reflected in the spec, the code and the tests in the same change.
