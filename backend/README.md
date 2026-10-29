# backend/

The Python service: a FastAPI app around one `Orchestrator` object that runs the investigation loop. No framework for agents, no external services needed: in the default mock mode everything runs offline.

## Folders

| Folder / file | Responsibility | README |
|---|---|---|
| `api.py` | HTTP routes, demo helpers, serves the UI | below |
| `domain/` | Pydantic data contracts and enums (the shared vocabulary) | [domain](domain/README.md) |
| `workflow/` | The investigation loop and the case state machine | [workflow](workflow/README.md) |
| `agents/` | The investigation planner: claims, plans, explanations | [agents](agents/README.md) |
| `llm/` | One adapter for every model provider, with cost and token accounting | [llm](llm/README.md) |
| `security/` | Preflight, the gate (tool proxy), source-permission rules, result filter | [security](security/README.md) |
| `tools/` | Tool catalogue and the fake read-only MCP server | [tools](tools/README.md) |
| `evidence/` | Verdicts in code, evidence pack | [evidence](evidence/README.md) |
| `storage/` | SQLite store and the hash-chained ledger | [storage](storage/README.md) |
| `util.py` | Canonical JSON, SHA-256, ids, a clock tests can pin | below |

## Who calls whom

```
api.py ──► Orchestrator ──► Planner ──► LLM adapter
                 │                 
                 ├──► preflight (policy_engine) ──► source_rules
                 ├──► ToolProxy ──► source_rules, result_filter ──► FakeMCPServer
                 ├──► verify_all (claim_verification)
                 └──► Repository (objects + ledger)
api.py ──► build_pack / verify_pack (pack_builder) ──► Repository
```

Dependencies only point "down": the security, evidence and storage modules never import the orchestrator, and nothing except `ToolProxy` imports the MCP server's `call()`.

## `api.py`

Routes follow build spec 05 §7. Interactive docs are at `http://127.0.0.1:8000/docs` when the app runs.

| Route | What it does |
|---|---|
| `POST /cases` | Create a case from a finding (`CreateCaseRequest`) |
| `GET /cases/{id}` | Everything about a case in one view: claims, gaps, findings, plans, preflights, approvals, receipts, evidence, events |
| `POST /cases/{id}/assess` | Split the finding into claims and gaps |
| `POST /cases/{id}/plans` | Draft a plan (optionally with reviewer restrictions) and run the preflight |
| `POST /plans/{id}/preflight` | Re-run the preflight on a plan |
| `POST /plans/{id}/decisions` | `APPROVE` (with `plan_hash`), `MODIFY` (with restrictions) or `REJECT` |
| `POST /plans/{id}/compliance` | Ask compliance to look at a plan (logged) |
| `POST /cases/{id}/execute` | Run the approved steps through the gate, compute verdicts, maybe propose the next plan |
| `POST /cases/{id}/final-review` | `SIGN_OFF`, `REQUEST_MORE_WORK` or `REJECT_FINDINGS` |
| `POST /cases/{id}/stop` | Stop the case and revoke every approval |
| `POST /cases/{id}/close-blocked`, `/close-unresolved` | Close a case that has no lawful path |
| `GET /cases/{id}/events`, `/ledger.jsonl`, `POST /ledger/verify` | The log and its chain check |
| `GET /cases/{id}/pack`, `/pack.md`, `POST /packs/verify` | The evidence pack (JSON, Markdown) and its check |
| `GET /demo/scenarios`, `POST /demo/scenarios/{id}/load` | List and load the synthetic scenarios |
| `POST /cases/{id}/redteam/attempt-tool` | Send a tool request straight to the gate, like a misbehaving agent (deny-path demo) |
| `POST /demo/fail-mode` | Make a tool time out (failure demo) |
| `POST /demo/reset`, `GET /demo/info` | Fresh in-memory state; which model and policy are active |

Identity for the demo is the `X-Reviewer-Id` header (users in `fixtures/users.json`). Domain errors are turned into HTTP errors in one place (`_call`): a missing `X-Reviewer-Id` is 401, an unknown reviewer or a wrong role is 403, a broken workflow rule (for example approving a blocked plan) is 409.

## `util.py`

- `canonical_json`: sorted keys, UTF-8, no spaces. The same bytes are hashed for plan hashes, event hashes and the pack checksum, so a verifier written elsewhere gets the same result.
- `sha256_hex`, `hash_without`: hashing helpers.
- `clock`: the wall clock by default; tests pin or advance it to test approval expiry and consent windows.
- `ids`: readable sequential ids (`CALL-001`, `EVT-014`, `PREF-002`).
