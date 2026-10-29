# Agent Assurance

**Checks what a bank's AI agent claims, before anyone relies on it.**
Team **CCC — Claude Code Crusaders** · NEXXT AI Hackathon 2026 · Raiffeisen Bank challenge "AI for Operational Efficiency" · synthetic data only.

Banks already run AI agents that read documents and call tools. Before a person can rely on what such an agent says, someone has to check, by hand, whether each statement is backed by an original source, is about the right customer, is still current, and whether the bank was even allowed to look it up. Agent Assurance does that investigation for the reviewer, inside limits a person sets:

1. It splits the agent's finding into separate **claims** ("a dispute existed in 2024" vs "it is ongoing now").
2. It proposes an **investigation plan**: which read-only sources to query, for which claim.
3. A deterministic **legal + policy check** runs on the exact plan (GDPR-style purpose, data and source rules, no LLM).
4. A **person approves the exact plan**, bound to its SHA-256 fingerprint. Any edit makes a new version that needs a new check and a new approval.
5. The agent calls **only approved tools**, through a gate that checks every call and fails closed.
6. Each claim gets a verdict: **SUPPORTED · CONTRADICTED · INSUFFICIENT_EVIDENCE · NOT_CHECKED**, with the evidence that decided it. If new sources are needed, the agent asks for another approval round.
7. The reviewer signs off and gets an **evidence pack**: every plan version, decision, tool call (including the blocked ones) and verdict, on a hash-chained, tamper-evident log.

> We don't replace the bank's agents. We make their output verifiable, with a human in charge of every new step.

**Pitch deck:** [presentation/ClaudeCodeCrusaders_Presentation.pdf](presentation/ClaudeCodeCrusaders_Presentation.pdf) (13 slides).

---

## Quick start (about 3 minutes)

**Requirements:** Python **3.10+** (tested on 3.10 and 3.13) and a modern browser. No database, no Docker, no API key needed for the demo.

```bash
git clone https://github.com/DanielDumi/CCC---Claude-Code-Crusaders.git
cd CCC---Claude-Code-Crusaders
python dev.py setup     # installs requirements.txt and creates .env (deterministic mode)
python dev.py check     # 69 tests + evaluation; must end with "CHECK PASSED"
python dev.py run       # open http://127.0.0.1:8000
```

On Windows use `python` in Command Prompt or PowerShell; on macOS/Linux use `python3` if `python` is Python 2.
Port busy? `PORT=8010 python dev.py run` (PowerShell: `$env:PORT=8010; python dev.py run`).

### What to click (scenario S01, about 2 minutes)
1. Open **Verify the claims → S01 "Outdated dispute status"**. The bank's agent said *"NOVA Logistics SRL is currently involved in an ongoing legal dispute."*
2. It's split into two claims. The agent's first plan includes an **open web search**, so the policy check **blocks** the plan and the server refuses an approval.
3. Click **"Remove Open web search and re-check"** → plan v2, new fingerprint, check passes → **Approve**.
4. Under **Try to break it**, press *"Agent tries an open web search"*: the gate blocks it and the tool is never called.
5. **Run the checks**: the company registry confirms the identity; the licensed court registry says case C-001 was **closed on 2026-09-03** → claim 1 *Confirmed*, claim 2 *Contradicted*. The agent asks for one more check (document signature) → approve → run.
6. **Sign off** → *Closed with issues* → open the **report**; under **Log**, press *Check the log*, then *Simulate a tampered entry* → the broken entry is named.

Or press **▶ Watch the demo** to have every scenario play by itself.

---

## Dependencies

| Package | Why |
|---|---|
| `fastapi`, `uvicorn` | HTTP API and the local server for the UI |
| `pydantic` v2 | typed contracts for every object (`backend/domain/models.py`) |
| `pyyaml` | the versioned policy file (`fixtures/policies/demo-policy.yaml`) |
| `holidays` | Romanian public holidays for the ANAF "5 working days" consent rule |
| `httpx`, `pytest` | tests (`fastapi.testclient`) |
| `certifi` | HTTPS root certificates for the optional model providers |

The UI is plain HTML/CSS/JavaScript served by FastAPI (no build step, no Node). The Inter font loads from Google Fonts; offline the page falls back to system fonts.

## Optional: use a real AI model

By default (`LLM_MODE=mock`) a deterministic planner extracts claims and proposes plans, so the demo and the tests are reproducible and free. To let a model do that work, edit `.env`:

| `LLM_MODE` | What runs | Needs |
|---|---|---|
| `mock` (default) | deterministic planner, zero tokens | nothing |
| `bedrock` | Claude (Haiku 4.5 / 5.5), Amazon Nova, Llama on AWS Bedrock, Converse API | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `BEDROCK_MODEL_ID` |
| `featherless` | open-weight models, OpenAI-compatible | `FEATHERLESS_API_KEY`, `FEATHERLESS_MODEL` |
| `ollama` | a local model; nothing leaves the machine | Ollama running, `OLLAMA_MODEL` |
| `openai_compatible` | any server with that API | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` |

`python dev.py smoke` checks a Bedrock key. Model IDs need the `us.`/`eu.` prefix (e.g. `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Every model output is schema-validated; if it is missing, malformed or over the spend cap (`LLM_SPEND_CAP_USD`, default 20), the deterministic planner takes over and the plan card and the log say so. **The model never sets a verdict, a policy result or an access grant.**

## Sample inputs and outputs

Everything is in [`samples/`](samples/README.md):

| File | What it is |
|---|---|
| `S01-input-case.json` | the case the bank's agent hands over (finding, subject, origin system, attached evidence ids) |
| `custom-case-request.json` | a case you can post yourself to `POST /cases` |
| `api-walkthrough.sh` / `api-walkthrough.ps1` | S01 end to end through the HTTP API, step by step |
| `S01-evidence-pack.json` | the full evidence pack produced by that run (plans, preflights, approvals, tool receipts, evidence, verdicts, ledger, checksum) |
| `S01-report.md` | the human-readable investigation report |
| `S01-ledger.jsonl` | the hash-chained event log, one event per line |

All 14 demo scenarios live in `fixtures/scenarios/*.json` (input case, attached documents, the synthetic tool data and the expected verdicts).

| Scenario | What it shows | Expected result |
|---|---|---|
| S01 | outdated "ongoing dispute" | blocked plan v1 → approved v2 → v3; `SUPPORTED` + `CONTRADICTED` |
| S01-INJ | a registry response tries to give the agent orders | instruction ignored, same verdicts |
| S02 | bad news about a similarly named German company | `CONTRADICTED` (wrong entity) |
| S03 | "unpaid taxes" with no source | `INSUFFICIENT_EVIDENCE`, nothing invented |
| S04 | two report versions disagree | `INSUFFICIENT_EVIDENCE` (no approved version) |
| S05 | "revenue fell 20%" | `SUPPORTED`, computed in code |
| S06 | search for a person's private data | plan `BLOCKED`, case closed blocked |
| S07 / -OK / -HOL / -WD | loan file under Romanian ANAF consent rules (5 working days, holidays, withdrawn application) | lapsed consent `CONTRADICTED`, ANAF query denied; day 5 and holiday cases stay valid; withdrawn file untouched |
| S08 / -OK | payslip vs bank statement, planted instruction, special-category rows | income `CONTRADICTED`; injected call refused; CNP/IBAN masked; Art. 9 rows removed |
| S09 | purpose the bank never approved | `LEGAL_REVIEW_REQUIRED`, nothing runs |

## How it works

```
finding from the bank's agent (or an employee)
  → intake: hash the original, mark missing traces NOT_CAPTURED      backend/workflow/orchestrator.py
  → claims + gaps (model or deterministic)                            backend/agents/planner.py
  → plan vN with a canonical SHA-256 fingerprint                      backend/security/policy_engine.py
  → legal + policy preflight (YAML rules, no LLM)                     fixtures/policies/demo-policy.yaml
  → human: approve / modify / reject / ask compliance                 bound to plan hash + preflight
  → tool gate on every call (fail closed)                             backend/security/tool_proxy.py
      source permission (consent, application status, RO working days)  backend/security/source_rules.py
      result filter (mask CNP/IBAN, drop Art. 9 rows, flag instructions) backend/security/result_filter.py
  → read-only tools (fake MCP server over synthetic data)            backend/tools/
  → deterministic verification per claim                              backend/evidence/claim_verification.py
  → new scope? new plan → new preflight → new approval (max 3 plans, 8 calls)
  → final human sign-off → evidence pack (JSON + Markdown, checksum)   backend/evidence/pack_builder.py
  → append-only, hash-chained event ledger (SQLite)                    backend/storage/repository.py
```

Contracts and status names follow `docs/spec/build-spec/06_DATA_MODELS_AND_CONTRACTS.md`; the workflow follows `03_PIPELINE.md`; the security rules follow `07_SECURITY_AND_GUARDRAILS.md`.

### HTTP API (used by the UI and the samples)
Reviewer identity for the demo is the `X-Reviewer-Id` header (users in `fixtures/users.json`).

| Method | Path | Does |
|---|---|---|
| POST | `/cases` | create a case (body: `samples/custom-case-request.json`) |
| POST | `/cases/{id}/assess` | split into claims; no external calls |
| POST | `/cases/{id}/plans` | new plan version + preflight |
| POST | `/plans/{id}/decisions` | `APPROVE` / `MODIFY` / `REJECT` with `plan_hash` |
| POST | `/cases/{id}/execute` | run approved steps through the gate |
| POST | `/cases/{id}/final-review` | `SIGN_OFF` / `REQUEST_MORE_WORK` |
| GET | `/cases/{id}` · `/cases/{id}/events` | case view · event log |
| GET | `/cases/{id}/pack` · `/pack.md` · `/ledger.jsonl` | evidence pack · report · raw log |
| POST | `/packs/verify` · `/ledger/verify` | verify a pack or a log |
| POST | `/demo/scenarios/{sid}/load` · `/demo/reset` | demo helpers |

Interactive API docs: http://127.0.0.1:8000/docs

## Testing and evaluation

```bash
python dev.py test    # 69 tests: functional FUN-01..12, security SEC-01..10, Romanian consent rules, result filter, verifier robustness
python dev.py eval    # 14 scenarios, wrong claims marked SUPPORTED reported first -> eval/report.md
python dev.py bench   # time / tokens / cost per case -> eval/bench.md   (add --llm for a live model)
```
Current result (deterministic mode): **0 wrong claims marked SUPPORTED, 26/26 verdicts as expected, 14/14 forbidden-tool probes denied with zero tool invocations, 14/14 evidence packs verify.** These are our measurements on synthetic cases, not bank figures. CI (`.github/workflows/check.yml`) runs the same `dev.py check` on every push.

## Mapping to the Raiffeisen criteria

| Criterion | Where to look |
|---|---|
| Agent design & orchestration (25%) | plan → preflight → approval → gated tool use → adaptive re-plan loop; unexpected cases: blocked plan, denied call, timeout, injected instruction, unapproved purpose |
| Functional completeness & testability (20%) | `python dev.py check`, `samples/`, evidence pack + `verify` |
| Originality (15%) | the human approves the *exact* investigation plan; permission is checked separately from truth; one governance record per case |
| Domain understanding (15%) | Romanian ANAF consent rules and holidays, GDPR Art. 5/6/9/22 references in the policy, AI Act Art. 12/14/26 evidence mapping, `docs/spec/` |
| Architecture & reproducibility (15%) | typed contracts, modular backend, one-command setup/run/test, offline deterministic mode |

## Honest limits

- All companies, people, documents, policies and tools are **synthetic**; the signature check is a simulated fixture. No real bank data or system is used.
- The evidence pack **supports** AI Act / GDPR reviews; it is **not** a certification or legal opinion. The verified agent's AI Act risk class is shown as `UNCONFIRMED`; the tool does not classify AI systems.
- Reviewer identity is a demo header, not bank IAM. The log is tamper-evident, not bank-grade immutable storage.
- The ANAF 5-working-day consent rule comes from a **draft** order (Sep 2026); our counting convention (signing day excluded) is stated in the rules.
- No measured bank time savings; state is in memory by default (`AA_DB=file.sqlite3` to persist).

## Code documentation

Start with **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** (module map, the life of one case, trust boundaries, where the AI is and isn't). Every folder then has its own README:

| Folder | What it explains |
|---|---|
| [backend/](backend/README.md) | How the modules fit together; every HTTP route |
| [backend/domain/](backend/domain/README.md) | The data contracts and enums (verdicts, preflight statuses, case states) |
| [backend/workflow/](backend/workflow/README.md) | The investigation loop and the state machine |
| [backend/agents/](backend/agents/README.md) | The investigation planner and how model answers are validated |
| [backend/llm/](backend/llm/README.md) | The model adapter: providers, token caps, retries, spend cap |
| [backend/security/](backend/security/README.md) | Preflight, the gate, Romanian source rules, result filter |
| [backend/tools/](backend/tools/README.md) | Tool catalogue and the fake read-only MCP server |
| [backend/evidence/](backend/evidence/README.md) | Verdicts in code and the evidence pack |
| [backend/storage/](backend/storage/README.md) | SQLite store and the hash-chained ledger |
| [frontend/](frontend/README.md) | The review UI |
| [fixtures/](fixtures/README.md) | Scenarios, the demo policy, demo users |
| [eval/](eval/README.md) · [tests/](tests/README.md) · [ops/](ops/README.md) | Evaluation, the 69 tests, the key check and hosting |

## Repository layout

```
backend/     API, workflow, planner, gate, verification, evidence pack, storage
frontend/    review UI (HTML/CSS/JS, no build step)
fixtures/    14 synthetic scenarios, demo policy, demo users
eval/        evaluation and bench scripts + latest reports
tests/       69 automated tests
samples/     sample inputs, API walkthrough, sample evidence pack and report
docs/        build spec 01-10, gate spec, developer README
ops/         Bedrock key smoke test
presentation/ pitch deck (PDF)
dev.py       setup / check / test / eval / bench / run / smoke
```

AI use: built with Claude (Anthropic) and the team's AI coding agents during the hackathon; `AGENTS.md` / `CLAUDE.md` are the rules those agents followed.
