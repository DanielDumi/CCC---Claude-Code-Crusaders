# 09 — MVP Build Plan / Claude Code Execution Instructions

**Goal:** Implement one **real end-to-end, plan-approved, policy-gated, adaptive verification agent** plus a review UI and evidence pack. Do **not** build a complete bank workflow or only a static flowchart.

## 0. Read this specification in order

1. `01_PROBLEM.md` — target the small repetitive verification task.
2. `02_FINAL_SOLUTION.md` — product contract and two mandatory verification tracks.
3. `03_PIPELINE.md` — authoritative state machine and invariant: approval before tool calls.
4. `04_EU_AI_ACT_AND_LEGAL.md` — versioned legal rules; avoid compliance overclaims.
5. `05_SYSTEM_ARCHITECTURE.md` — services/modules.
6. `06_DATA_MODELS_AND_CONTRACTS.md` — exact domain enums and sample payloads.
7. `07_SECURITY_AND_GUARDRAILS.md` — enforce restrictions in backend.
8. `08_DEMO_SCENARIOS_AND_TESTS.md` — acceptance scenarios and fixtures.
9. `10_RESEARCH_EVIDENCE_AND_ASSUMPTIONS.md` — fact tiers and research links.

**Do not silently change any core names or status values.** If a conflict remains, prioritize enforceable law/security rules, then `06` contracts, `03` state machine, and document an architecture decision.

## 1. Implementation sequence (dependency order, not schedule)

### Milestone A — Foundation and contracts

- Initialize backend/frontend structure from `05`.
- Create strict `Case`, `Claim`, `Evidence`, `InvestigationPlan`, `Preflight`, `Approval`, `ToolReceipt`, `Finding`, `Event`, `EvidencePack` models.
- Implement state machine transitions and event ledger in SQLite.
- Implement static fake MCP server and fixture dataset for S01–S06.
- Unit tests: invalid transitions fail, missing evidence stays explicit, plan hashes are stable.

**Exit:** API can persist a case and its initial source snapshot, regenerate state deterministically, retrieve event timeline.

### Milestone B — Plan approval + legal preflight (core product)

- Build configurable policy rules from demo YAML/JSON: approved tools, case purpose, field/data categories, sources, budgets, forbidden tool IDs.
- Implement deterministic preflight returning exact `PreflightStatus`, conditions and cited rule ids.
- Build plan versioning/canonical SHA-256; bind approval to reviewer identity and plan hash.
- Implement `MODIFY`/`REJECT` -> fresh plan/version + new preflight; approval invalidated.
- Tool proxy must enforce preflight + hash + permissions at call time.
- Tests for blocked source, altered plan, expired approval and changed policy.

**Exit:** With no AI at all, a deliberately unauthorized tool call cannot execute; UI clearly shows why.

### Milestone C — Real investigator (agentic loop)

- Implement a structured-output planner with tool-aware claim-gap assessment.
- Feed the AI **tool catalog only**, no secrets or raw executable privileges.
- After approval, agent chooses next step among approved options; tools run via proxy.
- Implement bounded loop, stopping on resolved/blocked/unknown; new scopes -> `REPLAN_REQUIRED`.
- Add deterministic checks: ID equality, dates, percentages, metadata version/signed fixture flags.
- Add an evidence reasoning step that emits claim-level citations and uncertainty.
- Add a deterministic/mock planner mode in CI, avoiding flaky LLM-dependent security tests.

**Exit:** S01 behavior changes depending on the newer evidence; no fixed “always contradicted” answer hardcoded in the agent.

### Milestone D — Reviewer experience

- Show original agent answer or human notes; claim list and gaps.
- Show side-by-side plan v1 and v2, proposed tools/sources, risk/permission impact, policy citations.
- Buttons: **Approve / Modify / Reject / Request Compliance** backed by authenticated API.
- Real-time or streamed event timeline: preflight, tool attempted, denied/executed, evidence found, replan proposal.
- Human can request new evidence after findings and approve a new plan.

**Exit:** UI can demonstrate a reviewer vetoing unrestricted web search and approving a narrower plan; no tool calls before approval.

### Milestone E — Evidence and legal reporting

- Persist tool receipts and original source refs; add event hash chain.
- Generate `InvestigationReport` and `GovernanceEvidencePack` from case/event store.
- Include legal-policy snapshot and per-rule results, explicit AI Act applicability **or UNCONFIRMED**, reviewer signoff and unresolved issues.
- Render Markdown and JSON; optional PDF rendering only if stable, not required for correctness.
- Validation: generated pack contains **no events or claims absent from ledger**, and all log gaps are explicit.

**Exit:** S01 produces downloadable, reproducible pack documenting a negative claim verdict and the human-approved investigation path.

### Milestone F — Evaluation and hackathon hardening

- S01–S06 integration tests with fixture ground truths.
- Security negative tests from `07` run against fake MCP service.
- Additional 30-case labeled synthetic evaluation; publish raw metric calculations with dataset, not invented results.
- Run demo offline/with reproducible mock model if live LLM is unreliable; keep agentic plan selection observable.
- Prepare concise pitch and live demonstration. Document known limitations.

**Exit:** One command to start demo stack and one command to run tests (document actual commands after implementing).

## 2. MVP must-have priority matrix

| Priority | Feature | Why |
|---|---|---|
| **P0** | Human-approved plan revision loop | Product signature; distinguishes from one-shot verifier |
| **P0** | Legal/internal policy preflight before every approval | User's explicit requirement, not an afterthought |
| **P0** | Deterministic MCP tool gate | Approval and legal restrictions must be real |
| **P0** | Adaptive AI plan and evidence investigation | Makes product genuinely agentic |
| **P0** | Original-source citations and honest `INSUFFICIENT_EVIDENCE` | Prevents false verification claims |
| **P0** | Trace-backed evidence pack with human decisions | Governance output |
| **P1** | 6 scenario fixtures and deterministic tests | Robust demo |
| **P1** | Live timeline and plan diff UI | Legibility to jury |
| **P1** | Event hash chaining and export checksum | Integrity demonstration |
| **P2** | Actual regulatory change monitoring | Future integration; not MVP |
| **P2** | Real bank MCP integrations, real personal data, production IAM | Out of scope for hackathon without authorization |
| **P2** | Full Annex IV/FRIA builder, customer letter writer | Separate products; do not bloat scope |

## 3. Core implementation sketch

```python
async def advance_case(case_id: str):
    case = repo.get_case(case_id)
    assert not case.is_terminal
    # Case assessment uses already-authorized, already-captured artifacts.
    assessment = await investigator.assess(case)
    plan = await investigator.propose_plan(case, assessment)
    plan = validate_and_persist_new_version(plan)

    preflight = rules.preflight(plan, case, current_policy_version())
    ledger.append_preflight(preflight)
    if preflight.status == "BLOCKED":
        return require_safe_replan_or_stop(case, plan, preflight)
    if preflight.status == "LEGAL_REVIEW_REQUIRED":
        return wait_for_compliance(case, preflight)

    return wait_for_exact_plan_human_approval(case, plan, preflight)

async def on_approve(plan_id: str, reviewer: User):
    plan, preflight = load_and_validate(plan_id)
    require_reviewer_authorized(reviewer, plan.case_id)
    require(preflight.status in ["ALLOWED", "ALLOWED_WITH_CONDITIONS"])
    approval = approvals.approve_exact_hash(plan, preflight, reviewer)
    # Engine invokes tool only through proxy; never direct MCP client.
    return await run_approved_steps(plan, approval, tool_proxy)
```

The code must support multiple approvals and replans rather than closing immediately after the first plan.

## 4. Definition of done / demonstrable acceptance

**A. End-to-end:** Submit an existing-agent finding; AI identifies gaps; proposes plan; preflight; human modifies; plan version changes; human approves; agent calls approved MCPs; evidence changes claim verdict; optional v3; final human review; export pack.

**B. Real guardrail:** In tests, attempt to call forbidden `unrestricted_web_search` without or despite forged approval; assert `DENIED` and mock MCP invocation count `0`.

**C. Honest evidence:** For an unavailable source, the system reports `INSUFFICIENT_EVIDENCE`, not “verified.” Citation IDs resolve to persisted artifacts.

**D. Separate legality:** The UI shows legal/policy outcome independently of factual finding. “Claim supported” cannot set legal preflight to allowed automatically.

**E. Evidence completeness:** Export includes original AI claim, source pointers, plan versions, preflights, approvals/rejections, tool receipts, policy version, human signoff, and gaps.

**F. Scope:** No real customer, unrestricted scraping, or automated lending decision.

## 5. UI wireframe (three panes, one main screen)

```text
┌────────────────────┬────────────────────────────────┬─────────────────────────┐
│ ORIGINAL CASE      │ AI INVESTIGATION              │ REVIEW & GOVERNANCE     │
│ Claim + origin     │ Proposed PLAN v2              │ LEGAL PREFLIGHT         │
│ Evidence list      │ - verify company ID           │ Allowed with limits     │
│ Gaps               │ - check licensed legal status │ Policy refs            │
│ [Open source]      │ [Approve] [Modify] [Reject]   │ Human approval state    │
│                    │                                │                         │
│                    │ TOOL TIMELINE                  │ CLAIM VERDICTS          │
│                    │ ✓ allowed registry query       │ ✓ historical claim     │
│                    │ ✓ licensed status result       │ ✕ ongoing claim        │
│                    │ ✕ forbidden tool DENIED        │ ? unresolved aspects   │
│                    │                                │                         │
│                    │ [New plan if needed]           │ [Final review]         │
│                    │                                │ [Export evidence pack]  │
└────────────────────┴────────────────────────────────┴─────────────────────────┘
```

## 6. Hard engineering decisions to settle in code

- Choose deterministic event ledger (SQLite) and JSON Schema contracts first.
- Use a **fake MCP server** rather than an unrestricted web scraper.
- Use a canonical JSON hashing function compatible between backend and pack verifier.
- Tool budgets: config default max 3 approved plans / max 8 total tool calls; enforce server-side.
- Separate data facts from legal/policy screening; legal corpus retrieval cannot grant permission.
- UI approval must call the backend and persist a record; fake front-end state alone fails acceptance.
- Use fixed-source embeddings/retrieval for legal passages if useful; do not pretend a static model is always up to date.

## 7. Hand-off prompt to Claude Code

> Read all 10 Markdown files in numerical order. Treat `03_PIPELINE.md` as the authoritative workflow, `06_DATA_MODELS_AND_CONTRACTS.md` as the authoritative data model, and `07_SECURITY_AND_GUARDRAILS.md` as non-negotiable security invariants. Build an executable MVP that uses a real LLM for adaptive investigation planning, a strict deterministic tool proxy for every MCP call, human approval of each exact plan revision, a legal/policy preflight before approval, and event-backed evidence exports. Use entirely synthetic fixtures. Begin with the minimal vertical slice S01 and its safety tests, then implement S02–S06. Never assert bank-wide missing controls or claim full EU AI Act compliance. Do not implement real credit decisions or unauthorized web scraping. Make tests and local demo reproducible.

## 8. Risks and fallback strategies

| Risk | Safer fallback |
|---|---|
| Live LLM unreliable or unavailable | Deterministic planner fixture for demo/tests; document where live LLM integrates |
| MCP package/version issues | Mock MCP-compatible adapter plus explicit integration point |
| Regulatory question ambiguous | `LEGAL_REVIEW_REQUIRED`; demonstrate escalation |
| Rich UI not ready | Minimal reviewer form, tool timeline and report export |
| Large initial scope | Prioritize S01 with two approval rounds over six superficial demos |
| No real banking data | Use synthetic fixtures; do not request sensitive data |

## 9. Review checklist before presentation

- [ ] S01 runs end to end, including edit/reject and a newly approved plan.
- [ ] At least one real MCP call is executed only after approval.
- [ ] Unauthorized MCP attempt is denied in the backend.
- [ ] AI Act applicability is displayed as reviewed or `UNCONFIRMED`, never guessed.
- [ ] GDPR/source permission checks happen **before** external retrieval.
- [ ] Results have evidence citations, statuses, and explicit uncertainty.
- [ ] At least one scenario ends unresolved.
- [ ] Evidence pack exports real plan revisions, rule version, timestamps and reviewer actions.
- [ ] No claim that the project ensures full regulatory compliance or that Raiffeisen lacks all governance.
- [ ] Hackathon demo works on local synthetic data and can be replayed.
