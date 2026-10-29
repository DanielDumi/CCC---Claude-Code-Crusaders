# backend/evidence/

Two things: deciding **whether each claim is supported** (in code), and packaging **everything that happened** into a verifiable evidence pack.

## `claim_verification.py`: verdicts in code

`verify_all(case, claims, evidence, tools_attempted)` returns one `Finding` per claim. It is deterministic: the same evidence always gives the same verdict, and no model is asked. A second model agreeing never makes a claim `SUPPORTED`.

It keeps separate questions separate: does a source exist, was it authorised for this case, does its content support the claim, is its authenticity verified.

| Check type | `SUPPORTED` when | Typical other outcomes |
|---|---|---|
| `HISTORICAL_EVENT` | A source from the claimed year reports the event **and** the registry confirms the entity | `NOT_CHECKED` while the identity is not checked; `INSUFFICIENT_EVIDENCE` with no source or an unconfirmed identity |
| `CURRENT_STATUS` | An authorised registry, dated at case time, shows the asserted status for the right entity | `CONTRADICTED` when it shows another status (S01: "ongoing" vs `CLOSED` on 2026-09-03); `INSUFFICIENT_EVIDENCE` when the source failed (`tool_error`) or the gate refused it |
| `ENTITY_ATTRIBUTION` | The entity in the source is the case subject | `CONTRADICTED` with `wrong_entity` (S02: SRL vs GmbH) |
| `FACT_PRESENCE` | The authorised source or the documents contain the field with the asserted value (with a tolerance where set, e.g. 2% for income) | `CONTRADICTED` when sources disagree; `INSUFFICIENT_EVIDENCE` when the fact is absent |
| `VERSIONED_FIGURE` | All versions agree, or the approved version has the asserted value | `NOT_CHECKED` while versions disagree and provenance is unknown; `INSUFFICIENT_EVIDENCE` with `no_approved_version` |
| `CALCULATION` | The change computed from both years' filed figures matches the asserted percentage | `CONTRADICTED` on a mismatch; `INSUFFICIENT_EVIDENCE` without both figures |

Rules that apply to every type:

- Unavailable source or tool failure → `INSUFFICIENT_EVIDENCE` or `NOT_CHECKED`, never `SUPPORTED`.
- A source the gate refused → `INSUFFICIENT_EVIDENCE` with the rule ids attached (`_blocked_finding`).
- Text compare ignores case and diacritics, and treats Romanian ş/ș and ţ/ț as equal (`norm`).
- Every `SUPPORTED` or `CONTRADICTED` cites evidence ids; limits such as "historical source" or "authenticity not verified" are listed.
- When a record's authenticity is not verified, the finding carries a `next_action_proposal` (a signature check). That is what makes the agent ask for plan v3 in S01.
- Odd parameters from a model must never crash the verifier or produce `SUPPORTED` (`tests/test_verifier_robustness.py`).

## `pack_builder.py`: the evidence pack

`build_pack(orch, case_id)` assembles the pack **only from stored objects and the ledger**. It never fabricates history: a missing original trace is reported as `NOT_CAPTURED`.

Contents: the case and its finding hash; claims and findings; every plan version, preflight and approval (including modifications and refusals); every tool receipt, with the denied ones listed separately; all evidence; the human sign-off; the full event list with the chain check; known trace gaps; open issues (every claim that is not `SUPPORTED`); the policy version and legal snapshot; the model label; an AI Act section (risk class `UNCONFIRMED`, Art. 12 / 14 / 26 evidence map marked `NEEDS_LEGAL_CONFIRMATION`); and a disclaimer: supporting evidence, not a certification or legal opinion, and the sign-off is not a credit decision.

`pack_sha256` = SHA-256 of the canonical JSON of everything else.

`verify_pack(pack)` checks three things and returns `ok` only if all hold:
1. the pack hash matches its content;
2. the event chain verifies;
3. every approval id and tool receipt id appears in the ledger.

`render_markdown(pack)` produces the human-readable report (see `samples/S01-report.md`).
