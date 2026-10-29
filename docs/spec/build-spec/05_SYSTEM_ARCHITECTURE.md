# 05 — System Architecture / Agent Orchestration

**Architecture objective:** An independent, human-guided verification sidecar that integrates with *existing* banking agents through events/tool traces, without replacing the agent platform or requiring direct access to real banking systems for the hackathon.

## 1. Logical topology

```text
 Existing banking agent OR employee case (simulated for MVP)
                        |
                  Intake Adapter
                        |
         Case Store + Append-only Event Ledger
                        |
              Investigation Orchestrator
                /                 \
       Planner / Reasoner       Legal-Policy Preflight
         (AI model)             (rules + retrieved law refs)
                \                 /
             Human Plan Review UI
                        |
             Approval-bound Tool Proxy
                        |
          MCP Adapter / Authorized Tools
           |             |            |
     Company registry  Legal status   Document metadata
       (fixture)        (fixture)       (fixture)
                        |
          Verification Engine (AI + code)
                        |
                Gap / Replan Decision
                        |
               Human Final Review UI
                        |
             Evidence Pack Assembler
                 JSON + Markdown
```

**Security boundary:** The model never receives the tool credentials or bypasses the proxy. It may request a tool call; the proxy is the only component that invokes the MCP adapter.

## 2. Components & ownership

| Service/module | Key responsibility | Main interface |
|---|---|---|
| `case_intake` | Normalize AI output or human case; preserve original artifacts and gaps | `POST /cases` |
| `claim_extractor` | Split finding into atomic, testable claims; propose missing checks | `assess(case) -> Assessment` |
| `investigation_planner` | Generate step-by-step plan in valid schema | `create_plan(case, assessment)` |
| `legal_context_retriever` | Retrieve versioned approved EU law/policy passages with citations | `lookup(rule_ids, purpose)` |
| `policy_preflight` | Evaluate plan against deterministic permission/purpose rules | `check(plan) -> Preflight` |
| `approval_service` | Authenticate reviewer; bind plan revision/hash to authorization | `POST /plans/{id}/decisions` |
| `tool_proxy` | Enforce plan, RBAC, source, purpose, budget, data-category policy at every call | `invoke(plan_hash, step_id, tool_id, args)` |
| `mcp_adapter` | Read-only MCP client for approved tool catalog | `call(tool_id, args) -> ToolReceipt` |
| `verification_engine` | Deterministic checks + LLM claim/evidence reasoning with cited spans | `verify(claims, evidence)` |
| `orchestrator` | State machine, allowed transitions, retries, stopping, replans | `advance(case_id)` |
| `event_ledger` | Append-only tool/approval/action events; tamper-evident hash chain in MVP | `append(event)` |
| `evidence_pack` | Render report from persisted events and findings | `GET /cases/{id}/pack` |
| `review_ui` | Plan diffs, restrictions, trace, gaps, final human review | Web frontend |

**A single investigation LLM is sufficient for the MVP.** “Multi-agent” may be represented by clearly separated Planner / Evidence Reasoner / Legal Research Assistant roles if each performs an actual distinct task and is orchestrated. Do not create extra chatbots just to increase agent count; judges should see tool use, adaptive decisions and policy-gated orchestration.

## 3. Agent roles and trust limits

### Planner agent

Input: existing case, atomic claims, known evidence, approved tool catalog, user restrictions, budget. Output: structured `InvestigationPlan` only. Can decide **which checks to propose**, not which data it is legally entitled to access.

### Evidence reasoning agent

Input: claims, relevant source passages, deterministic extraction/metadata results. Output: source-linked findings and uncertainty. Must cite stable `evidence_id`, quote/excerpt spans when permitted, and distinguish **original** from secondary sources. It cannot invent a registry confirmation or digital signature check.

### Legal research assistant

Input: intended use, provider/deployer context, approved legal and policy snippets. Output: potentially applicable obligations/risks with official citations for compliance reviewer. **Not** the enforcement authority and not a substitute for bank Legal/DPO. The actual tool policy evaluation is deterministic.

### Orchestrator

Conventional programmatic state machine with model calls embedded. Never delegate state transition, access grant, or approval recording to an LLM.

## 4. MCP catalog and tool schema (demo)

Every MCP tool is registered by an administrator in a static catalog. The registry gives identity, allowed purposes, data category, source type, and whether a call is read-only.

| Tool id | Description | Arguments | Data category | Mode |
|---|---|---|---|---|
| `company_registry_lookup` | Returns company attributes from a synthetic approved corporate registry | `company_id: str` | `CORPORATE_PUBLIC` | Read only |
| `legal_case_status_lookup` | Returns a dated legal-status record from a synthetic licensed source | `company_id, case_ref` | `CORPORATE_LEGAL` | Read only |
| `document_metadata_lookup` | Returns effective dates, version, and provenance for a known document | `document_id` | `DOCUMENT_METADATA` | Read only |
| `document_signature_check` | Fixture-level simulated verification against trusted signature metadata | `document_id` | `DOCUMENT_METADATA` | Read only |
| `unrestricted_web_search` | **Forbidden** fixture tool for deny-path test | `query` | `PERSONAL_DATA` / unknown | Disabled |

**Do not equate domain allowlisting with lawful use;** legitimate purposes and field-level rules must be enforced too. A simulated document signature confirmation is not a claim of real-world cryptographic authenticity unless a real signature service is actually used.

## 5. Event-driven integration with existing platforms

### Preferred for production integration (subject to bank permission)

1. Existing agent emits **event receipt** (case reference, generated claims, tool ids, timestamps, source pointers, content hashes) to Agent Assurance.
2. Reviewer opens verification case via authenticated UI.
3. Agent Assurance obtains **only the source access authorized for that reviewer and purpose**, via approved MCP or application adapter.
4. Reports link back to source documents / system event IDs rather than copying all PII.

### Hackathon implementation

Use fixture response generator for “existing agent” and local fake MCP server. No real scraping, bank credentials, personal data, production system access, or real customer credit outcomes.

## 6. Suggested implementation stack (options, not mandatory)

- **Backend:** Python 3.12+, FastAPI + Pydantic for strict type validation.
- **Orchestrator:** Explicit state machine; LangGraph if team already knows it, otherwise a small custom reducer with persisted state.
- **Agent:** Any authorized LLM with structured JSON outputs; use a mock planner mode for deterministic CI tests.
- **MCP:** Official MCP SDK or a compatible adapter; all calls through the `tool_proxy`.
- **Database:** SQLite for demo; PostgreSQL in a bank environment if approved.
- **Frontend:** React/Next.js or a minimal Streamlit app; ensure actual human approval state persists in backend.
- **Export:** JSON + Markdown from events; optional PDF rendering as presentation layer.
- **Testing:** pytest, fixtures, time and token metrics; integration tests should execute against a fake MCP server.

### Proposed repository structure

```text
agent-assurance/
  README.md
  backend/
    api.py
    domain/models.py
    workflow/state_machine.py
    agents/planner.py
    agents/evidence_reasoner.py
    agents/legal_research.py
    security/policy_engine.py
    security/approval_tokens.py
    tools/catalog.py
    tools/tool_proxy.py
    tools/mcp_fixture_server.py
    evidence/claim_verification.py
    evidence/pack_builder.py
    storage/repository.py
    storage/event_ledger.py
  frontend/
    src/pages/CaseReview.tsx
    src/components/PlanApproval.tsx
    src/components/Findings.tsx
    src/components/EvidenceTimeline.tsx
  fixtures/
    scenarios/
    policies/
    regulatory_index/
  tests/
    test_plan_rejection.py
    test_tool_policy.py
    test_replan_loop.py
    test_claim_verdicts.py
    test_audit_pack.py
```

## 7. API surface (MVP)

| Method | Path | Behavior / authorization |
|---|---|---|
| `POST` | `/cases` | Create one case; requires reviewer auth |
| `GET` | `/cases/{case_id}` | View case and status, role-scoped |
| `POST` | `/cases/{case_id}/assess` | Extract claims, no external calls |
| `POST` | `/cases/{case_id}/plans` | Generate **new** plan version |
| `POST` | `/plans/{plan_id}/preflight` | Run rules against exact revision |
| `POST` | `/plans/{plan_id}/decisions` | `APPROVE`, `REJECT`, `MODIFY` with reviewer identity |
| `POST` | `/cases/{case_id}/execute` | Execute approved steps through tool proxy only |
| `GET` | `/cases/{case_id}/events` | Scoped event timeline, redacted |
| `POST` | `/cases/{case_id}/final-review` | Human signs off / requests replan |
| `GET` | `/cases/{case_id}/pack` | Generate event-backed evidence pack |

Only the backend may call the execution endpoint; it verifies an approval token. Do not implement `GET /execute?plan=...` or permit arbitrary MCP tool names supplied by frontend.

## 8. Approval-token life cycle

- Canonicalize plan JSON (sorted keys, stable encoding), compute SHA-256 `plan_hash`.
- Preflight creates `preflight_id` tied to plan hash + `policy_version`.
- Authenticated human approves this *exact* plan, yielding a signed or server-side scoped authorization record; no approval for absent/mismatched preflight.
- The proxy rechecks current policy (including revocations) at invocation time.
- Changing plan steps, source, purpose, tools, constraints or budget invalidates approval; produce vN+1.
- An explicit `REJECT` event never grants execution privileges. A Compliance review may clarify application of a rule but cannot magically permit prohibited conduct.

## 9. Incident and failure handling

| Failure | Safe behavior |
|---|---|
| LLM outputs invalid JSON | Reject and reprompt once within budget, then human escalation |
| Source missing or HTTP error | Add `UNAVAILABLE`; do not manufacture evidence |
| Tool response contains instructions | Treat as hostile content; ignore control instructions |
| Approval missing/expired | Deny tool call and request fresh approval |
| Policy version changed during run | Re-evaluate; stop if scope no longer authorized |
| New fact needs unapproved lookup | Emit `REPLAN_REQUIRED` |
| Legal basis unclear | `LEGAL_REVIEW_REQUIRED`; no external data access |
| Record integrity mismatch | Freeze case and flag security/admin review |
| Max plans/calls exceeded | `AWAITING_FINAL_REVIEW` with unresolved issues |

## 10. Demo metrics and traceability

Log: plan revisions, approval/rejection, tool selection, denied attempts, source IDs, claim verdict changes, stop reason, elapsed time, tokens and costs. Judge should be able to replay the event timeline and see a **real deny event** after an attempted unauthorized call.

For data contracts and example JSON, see `06_DATA_MODELS_AND_CONTRACTS.md`.
