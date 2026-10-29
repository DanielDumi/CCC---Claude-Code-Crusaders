# 02 — Final Solution / Product Requirements

**Product:** Agent Assurance  
**Tagline:** Human-approved autonomous investigation, with evidence and legal/policy controls built in.  
**Product category:** Small verification layer for an existing banking agent platform; not a competing agent platform.

## One-paragraph definition

Agent Assurance accepts the output of an existing banking AI agent **or** a human-prepared case. It analyzes claims and missing checks, creates a **concrete investigation plan**, conducts a **legal and internal-policy preflight**, and asks an authorized employee to approve or revise the plan. Only approved, policy-permitted tool calls execute. The investigation agent dynamically chooses further checks within the approved scope, verifies documents and sources, and requests approval for a **new plan** if additional work is needed. It ends with claim-level findings, human review, and a structured evidence pack for audit and applicable AI Act governance.

## The signature interaction

1. **Agent:** “Claim A is based on a 2024 source; it is not enough to establish current status. I propose checking company identity, source provenance, and an approved 2026 legal-status registry.”
2. **Legal/policy preflight:** “Read-only registry calls allowed; unrestricted internet search not allowed; no additional personal data.”
3. **Human:** “Do not search open websites. Use only licensed registry tools.”
4. **Agent:** Generates plan revision v2 that excludes open search; **fresh preflight and approval** occur.
5. **Human:** Approves the exact v2 plan.
6. **Agent:** Calls only the approved MCP tools, discovers conflicting evidence, records provenance.
7. **Agent:** “The newer document contradicts ‘ongoing’, but document authenticity is not established. I propose one official authenticity check.”
8. **Human:** Approves a second plan; agent performs the check or returns `INSUFFICIENT_EVIDENCE` if impossible.
9. **Human:** Reviews the final findings and signs off (including acknowledging unresolved issues).
10. **System:** Creates an evidence pack with the original data, plan revisions, preflight results, approvals, tool events, findings, and remaining gaps.

## Two mandatory verification tracks

| Track | Questions | Output |
|---|---|---|
| **Evidence & facts** | Is this claim supported by its original source? Correct entity? Current? Contradicted? Authenticity independently checked? | Claim verdicts with citations and limitations |
| **Law & policy** | Is the intended use permitted? Are tools/sources/data categories approved? Is there a lawful personal-data basis recorded? Are applicable AI Act oversight/logging controls present? | Preflight status, authority references, conditions, escalation flags |

Both must be visible in the UI. **Factual `SUPPORTED` is never automatically “legally permitted”; `ALLOWED` is never proof that the claim is true.**

## Role split — genuinely agentic, safely bounded

| Component | AI-driven? | Authority |
|---|---|---|
| Investigation planner | Yes | Extract claims, propose hypotheses, choose a next step from approved tools |
| Evidence reasoning | Yes, assisted by deterministic checks | Interpret passages, compare explanations, identify material contradictions |
| Source/identity/date checks | Mostly deterministic | Exact identifiers, expiration dates, hashes, signatures (only where verifiable) |
| Legal interpretation support | AI-assisted retrieval, human-confirmed | Suggest obligations with citations; **cannot grant legal permission** |
| MCP policy gate | No, deterministic | Deny calls outside allowlists, plan hash, scope, purpose, data categories, and budgets |
| Human reviewer | Human | Modify/approve plans; accept/reject findings; require more work |
| Compliance reviewer | Human | Resolve legal ambiguity; approve a permitted exception process if policy allows |
| Evidence-pack builder | Mostly deterministic | Assemble event-backed report; never fabricate missing history |

## Functional requirements

- **FR-01 Case intake:** Accept an AI output or human notes plus available MCP trace/document references; preserve provenance and mark absent artifacts as `NOT_CAPTURED`.
- **FR-02 Claim extraction:** Split an overall recommendation into independently testable factual claims.
- **FR-03 Gap assessment:** Flag freshness, identity, authenticity, missing citation, contradictory evidence, and unknown legal-purpose basis.
- **FR-04 Plan generation:** Propose explicit steps, tools, permitted source classes, data categories, action scopes, max calls, rationale, and stop criteria.
- **FR-05 Mandatory legal/policy preflight:** Assess each plan before showing it as approvable. Block illegal/unauthorized actions; route ambiguities to Compliance.
- **FR-06 Plan approval:** Require authenticated person, specific plan version/hash, bounded scope and timestamp. Reject/edit always triggers new version and preflight.
- **FR-07 Runtime enforcement:** Require tool proxy to reject any call not allowed by both policy and approved plan; an LLM's intention is not authorization.
- **FR-08 Adaptive investigation:** On contradiction/gap, the agent may investigate further **only within currently approved scope**; anything new triggers replanning.
- **FR-09 Verdict:** Each claim receives `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`, or `NOT_CHECKED`, with evidence IDs and reason.
- **FR-10 Explicit resolution limits:** No forced positive result. Cap investigation iterations/time/tool calls. Failure, unclear legal basis, or unavailable sources must cause safe stop.
- **FR-11 Final reviewer signoff:** Reviewer can acknowledge unresolved status; signoff is *not* the banking/customer decision.
- **FR-12 Evidence pack:** Export machine-readable JSON and a human-readable Markdown/PDF-compatible report; log which legal controls were checked, with scope and limitations.

## Nonfunctional requirements (MVP targets, not measured bank SLAs)

- **Reproducibility:** All six demo cases run offline, with seeded fixtures and known expected outputs.
- **Integrity:** Each plan approval binds to a SHA-256 digest of its canonical content; events are append-only in MVP storage and retain source IDs.
- **Principle of least privilege:** Read-only MCP tools only in MVP; no customer-facing action, loan decision, edit/delete tool, or unrestricted scraper.
- **Explainability:** Show source excerpts and identifiers rather than “confidence 95%” invented by an LLM.
- **Observability:** Track decision events, token/tool usage, denied requests, failure reasons, human edits, and latency.
- **Privacy:** Synthetic case fixtures only; real data integration must await bank permission and controls.
- **Accuracy:** Evaluate claim verdicts against fixture ground truth, including false acceptance and false rejection.

## Product scope (strict)

**MVP:** Case screen + AI assessment + plan dialog + legal preflight + tool-gated investigation + iteration + human review + downloadable evidence pack. Three core scenarios end-to-end, with six test fixtures.

**Later:** Platform-wide integration, policy administration and legal expert workflows, external registry subscriptions, continuous agent monitoring, red-team evaluation, independent audits, production access-control integrations, enterprise retention configuration.

## Output artifacts

1. `InvestigationReport`: claims, verifiable findings, uncertainty, sources, and suggested follow-ups.
2. `GovernanceEvidencePack`: event chronology, exact approved plans, legal-policy preflight outcomes, tools used, trace gaps, review actions, and report-integrity checksum.
3. `OpenIssues`: items unresolved by available sources or requiring Compliance/privacy specialist action.

The pack **supports** AI Act documentation and human oversight evidence; it does **not** certify legal compliance, replace a full risk assessment/FRIA, or establish real-world document authenticity by itself.

## The 30-second value proposition

> Existing banking agents can return plausible findings with missing or outdated evidence. Manually investigating each one means reopening documents, checking sources, and writing audit notes. Agent Assurance identifies gaps, **proposes a legally screened investigation plan**, asks a human for approval, uses only authorized MCP tools to investigate, and produces evidence-linked findings and a reviewable audit record. **We do not replace banking agents; we give reviewers an approved, adaptive way to verify them.**

## Definition of done for the product

A demo evaluator can witness: a plan is **rejected**, a narrower plan is **approved**, unauthorized tool usage is technically prevented, an additional evidence gap causes a **new** approval round, and the final report faithfully reconstructs every step. See `08_DEMO_SCENARIOS_AND_TESTS.md`.
