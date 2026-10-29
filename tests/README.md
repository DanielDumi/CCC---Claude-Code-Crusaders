# tests/

69 automated tests, run with `python dev.py test` (or as part of `python dev.py check`, which CI runs on every push). They use the deterministic planner (`LLM("mock")`), so they need no key, no network and give the same result every time.

`conftest.py` provides an `orch` fixture (a fresh orchestrator in memory) and `load(orch, scenario_id)`, which creates a scenario's case, assesses it and drafts plan v1.

| File | Tests | What it proves |
|---|---|---|
| `test_scenarios.py` | 16 | Functional acceptance FUN-01..12 from build spec 08: compound finding split in two; blocked v1 can't be approved and a modification gives a new hash; a new tool needs a new approval; S01 to S06 outcomes and closing states; pack matches ledger; preflight before every approval; a human-created case uses the same contract; injected text causes no extra call; a model that skips the identity check makes the agent ask for it next round |
| `test_security.py` | 15 | Security SEC-01..10 from build spec 07: no approval → denied; a changed plan invalidates the old approval; a reviewer-excluded tool can't run; a call caused by a document is denied; legal review blocks queries; a reviewer from another case is denied; case and step budgets; a missing original is `NOT_CAPTURED`; expired approval denied; an unverified authority claim stays unverified. Plus: stop revokes and denies, ledger tampering is detected and the ledger is append-only, cases are isolated, model output can't change a verdict |
| `test_gate_source_permission.py` | 6 | Romanian source rules end to end: the preflight names the step that will be refused; a lapsed consent is refused at run time with zero invocations and recorded; day 5 passes; a withdrawn application blocks even a forged approval; an unreadable register holds, never allows |
| `test_source_rules.py` | 12 | The pure functions: Romanian working days and holidays, consent validity, application status at case time, each `SRC-*` hit |
| `test_maria_scenarios.py` | 4 | S07 and its variants through the whole orchestrator |
| `test_document_scenarios.py` | 2 | S08 / S08-OK: income compared in code with a 2% tolerance, the planted instruction refused, Art. 9 rows and identifiers never reach the view |
| `test_result_filter.py` | 3 | Masking, Art. 9 row removal, instruction detection in English and Romanian, the refused call put on the record |
| `test_llm_accounting.py` | 10 | The LLM adapter without live calls: per-task caps, no sampling parameters, usage and cost, one retry, truncation fails closed, the spend cap falls back to the deterministic planner |
| `test_verifier_robustness.py` | 1 | A model-extracted claim with odd parameters never crashes the verifier or becomes `SUPPORTED` |

## Conventions

- Every deny-path test asserts that the fake MCP server was **never called** (`orch.mcp.total_invocations == 0` or a per-tool counter), not only that the receipt says `DENIED`.
- Some tests forge state on purpose (mark a plan `APPROVED` directly in storage) to show that the gate still refuses.
- A test is never weakened to make it pass; new behaviour comes with its test.
