# backend/agents/

`planner.py` is the investigation agent: the part that thinks about *what to check*. It can **propose**. It cannot add permissions, mark a step lawful or change a verdict.

## Three jobs

| Method | Job | LLM task name | Output schema |
|---|---|---|---|
| `assess` | Split the finding into atomic claims and list the gaps | `extract_claims` | `CLAIM_SCHEMA` |
| `propose_plan` | Choose the tools and arguments that can settle each open claim | `propose_plan` | `PLAN_SCHEMA` |
| `explain` | Write one or two plain sentences per verdict, in English and Romanian | `explain_findings` | `EXPLAIN_SCHEMA` |

Each job has two implementations behind the same method: the model (any provider through `llm/adapter.py`) and a deterministic fallback.

## How a model answer is checked

- **Claims:** every claim must have a known `check_type` and the parameters the verifier needs (`REQUIRED_PARAMS`, for example `case_ref` and `period_year` for a historical event). If anything is missing, the whole answer is dropped and the scripted extractor is used.
- **Plans:** every step must name a catalogue tool and exactly that tool's argument names. Then, deterministically and after the model: calls already made in an earlier round are removed (`call_key`), reviewer restrictions are re-applied (`forbid_tools`, `allow_only_tools`), and steps are renumbered and given the catalogue's source and data category. The model can't widen a restriction because it never gets the last word.
- **Explanations:** only text; the verdict, evidence ids and reason codes come from the verifier and are not touched.

Any failure (no key, timeout, invalid JSON, a truncated answer, a wrong tool) means the deterministic path is used, and the plan's `created_by` shows which one produced it (`INVESTIGATION_AGENT (mock)` or `INVESTIGATION_AGENT (bedrock:…)`), so the UI and the log tell the reviewer.

The system prompt (in `llm/adapter.py`) states that all case content is untrusted data and that the model cannot grant permissions or declare anything lawful.

## The deterministic planner (`_mock_steps`)

Used in tests, in CI, without a key, and as the fallback. It chooses steps per check type:

| Check type | Steps it proposes |
|---|---|
| `HISTORICAL_EVENT` | company registry (identity) |
| `CURRENT_STATUS` | company registry → licensed court registry; in round 1 also an open web search |
| `ENTITY_ATTRIBUTION` | registry lookup of the case subject and of the entity named in the source |
| `FACT_PRESENCE` | the authorised source for that fact (tax registry, consent register, ANAF…); in round 1 also an open web search |
| `VERSIONED_FIGURE` | document metadata for each version |
| `CALCULATION` | filed financial reports for both years |

The round-1 web search is on purpose. It imitates a typical first LLM plan that over-reaches, so the demo shows the preflight blocking it and the reviewer removing it with **Modify**. In later rounds the planner never proposes it.

In later rounds it proposes only what the findings ask for: a `document_signature_check` when a record's authenticity is not verified, and the normal checks for any claim still `NOT_CHECKED`.

## Gaps

`_gaps` lists what the reviewer should know before approving: the attached source is historical, the entity identity is not verified, document versions disagree, the figures are not attached, the original agent trace was not captured, a cited document was never received.
