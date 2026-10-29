# backend/workflow/

The investigation loop. It is a plain, explicit state machine in Python, with model calls embedded at a few points. State changes, access grants and approval records are never delegated to an LLM.

## `state_machine.py`

A table of allowed transitions (`TRANSITIONS`) and one function, `check_transition(current, new)`, that raises `InvalidTransition` for anything else. A closed case (`CLOSED_*`) can't move at all. The orchestrator calls this before every state change, so a bug or a crafted API request can't skip a step (for example from `PLAN_DRAFTED` straight to `EXECUTING`).

```
RECEIVED → ASSESSED → PLAN_DRAFTED
PLAN_DRAFTED → PREFLIGHT_BLOCKED | LEGAL_REVIEW_REQUIRED | AWAITING_PLAN_APPROVAL
PREFLIGHT_BLOCKED → PLAN_DRAFTED | CLOSED_BLOCKED
LEGAL_REVIEW_REQUIRED → PLAN_DRAFTED | CLOSED_UNRESOLVED
AWAITING_PLAN_APPROVAL → PLAN_DRAFTED | APPROVED
APPROVED → EXECUTING | CLOSED_BLOCKED
EXECUTING → FINDINGS_READY | REPLAN_REQUIRED | CLOSED_BLOCKED
FINDINGS_READY → REPLAN_REQUIRED | AWAITING_FINAL_REVIEW
REPLAN_REQUIRED → PLAN_DRAFTED
AWAITING_FINAL_REVIEW → REPLAN_REQUIRED | CLOSED_VERIFIED | CLOSED_WITH_ISSUES | CLOSED_UNRESOLVED | CLOSED_BLOCKED
```

## `orchestrator.py`

`Orchestrator` owns one `Repository`, `Policy`, `FakeMCPServer`, `LLM`, `Planner` and `ToolProxy`. The API holds a single instance.

| Method | Pipeline step | What it guarantees |
|---|---|---|
| `create_case` | 1. Intake | Reviewer must be allowed on this case; the finding is hashed; cited evidence that was not attached is stored as `NOT_CAPTURED` |
| `assess` | 2. Claims + gaps | No external calls; the planner splits the finding; gaps are listed (historical source, identity not checked, versions disagree…) |
| `draft_plan` | 3 + 4. Plan + preflight | A new version every time; reviewer restrictions carry forward and can't be dropped by a later plan; calls already made are not repeated; the preflight runs **before** anyone sees the plan |
| `decide_plan` | 5. Human decision | Only the latest version can be decided; `plan_hash` must match the stored plan; `APPROVE` is refused unless the preflight is `ALLOWED` or `ALLOWED_WITH_CONDITIONS` (the refusal is logged); approval expires after `approval_ttl_minutes`; `MODIFY` / `REJECT` never authorise anything and always create a new version |
| `execute` | 6–8. Run + verify | Runs the approved steps in dependency order, each through `ToolProxy.invoke`; skips steps whose claims are already settled; stops at the first denial; computes verdicts with the deterministic verifier; asks the LLM only for explanations |
| `_after_findings` | Loop | If a finding proposes a next action (for example a signature check) or a claim is still `NOT_CHECKED`, and there is budget left (max 3 approved plans, 8 calls), it drafts the next plan and the case goes back to `AWAITING_PLAN_APPROVAL`. Otherwise `AWAITING_FINAL_REVIEW` |
| `final_review` | 9. Sign-off | Only approver roles; the closing state is computed from the verdicts (any `CONTRADICTED` → `CLOSED_WITH_ISSUES`; unresolved claims need `acknowledge_unresolved` → `CLOSED_UNRESOLVED`; all supported → `CLOSED_VERIFIED`); marked "not a banking or credit decision" |
| `stop` | Any time | Sets the stop flag and revokes every approval of the case; the gate then denies everything (`STOP-001`) |
| `close_blocked`, `close_unresolved_legal` | Dead ends | Close a case that has no lawful investigation path |

Every one of these writes events through `repo.append_event`, so the ledger tells the whole story: who did what, when, and with which plan hash.

## Why not an agent framework

The loop is small and has to be auditable. With an explicit state machine, every transition is a line of code that a test can hit, and the spec forbids letting a model decide state changes or access. The "agent" part is the planner proposing and re-planning; the control flow around it is deterministic.
