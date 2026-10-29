# backend/storage/

`repository.py`: a small SQLite store for every domain object, plus the append-only, hash-chained event ledger.

## Objects

Table `objects(kind, id, case_id, seq, body)`. Each object is stored as canonical JSON under its type name and id (`put`, `get`, `list`). Evidence and claim ids come from fixtures or models and can repeat across cases, so they are stored as `<case_id>:<id>`. `list` returns objects in insertion order.

Default database is in memory (`:memory:`): a fresh state on every start, which suits a demo. Set `AA_DB=agent-assurance.sqlite3` to keep it on disk.

## The ledger

Table `events(seq, case_id, event_id, body, event_hash)`.

`append_event(case_id, event_type, actor_type, actor_id, summary, payload_refs)`:
1. reads the hash of the last event of this case (`"genesis"` for the first one);
2. builds the `Event` with `previous_event_hash` = that hash;
3. sets `event_hash = sha256(canonical JSON of the event without event_hash)`;
4. inserts it.

Two SQLite triggers abort any `UPDATE` or `DELETE` on `events` ("event ledger is append-only").

`verify_chain(events)` recomputes the chain and returns `{ok, entries, first_bad_index, event_id}`: if someone edits an event, the first broken entry is named. `export_jsonl` / `verify_jsonl` do the same for a downloaded log (see `samples/S01-ledger.jsonl`). The UI's "Simulate a tampered entry" button changes one event in a copy and shows the check catching it.

Typical events: `CASE_RECEIVED`, `CLAIMS_ASSESSED`, `PLAN_PROPOSED`, `PREFLIGHT_COMPLETED`, `PLAN_MODIFY`, `APPROVAL_REFUSED`, `PLAN_APPROVED`, `TOOL_INVOKED`, `TOOL_DENIED`, `TOOL_FAILED`, `INJECTION_FLAGGED`, `FINDING_UPDATED`, `EXPLANATIONS_WRITTEN`, `STATE_CHANGED`, `STOP`, `FINAL_SIGN_OFF`. Each carries the actor (SYSTEM, AI_AGENT or HUMAN) and references to the objects involved.

## Limits

This is **tamper-evident**, not tamper-proof: someone with write access to the database file could rewrite the whole chain. In production the head hash would be anchored in WORM storage or a separate system, and the store would be a multi-user database. We deliberately don't claim more than that.
