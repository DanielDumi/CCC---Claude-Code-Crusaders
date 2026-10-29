"""SQLite store for every domain object plus the append-only, hash-chained event ledger.

Objects are stored as canonical JSON keyed by (kind, id). Events are never updated or deleted.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Iterable, Optional, Type, TypeVar

from pydantic import BaseModel

from backend.domain.models import Event
from backend.util import canonical_json, clock, ids, sha256_hex, to_plain

T = TypeVar("T", bound=BaseModel)

GENESIS = "genesis"


class Repository:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, case_id TEXT, seq INTEGER, body TEXT,"
            " PRIMARY KEY (kind, id))"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT,"
            " event_id TEXT UNIQUE, body TEXT, event_hash TEXT)"
        )
        # Block UPDATE/DELETE on the ledger at the database level (append-only semantics).
        self._db.execute(
            "CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events"
            " BEGIN SELECT RAISE(ABORT, 'event ledger is append-only'); END"
        )
        self._db.execute(
            "CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events"
            " BEGIN SELECT RAISE(ABORT, 'event ledger is append-only'); END"
        )
        self._db.commit()
        self._seq = 0

    # ------------------------------------------------------------ objects
    def put(self, obj: BaseModel, *, kind: Optional[str] = None, key: Optional[str] = None) -> None:
        kind = kind or type(obj).__name__
        key = key or self._key(obj)
        case_id = getattr(obj, "case_id", None)
        with self._lock:
            self._seq += 1
            self._db.execute(
                "INSERT INTO objects(kind, id, case_id, seq, body) VALUES (?,?,?,?,?)"
                " ON CONFLICT(kind, id) DO UPDATE SET body=excluded.body, case_id=excluded.case_id",
                (kind, key, case_id, self._seq, canonical_json(obj)),
            )
            self._db.commit()

    def get(self, model: Type[T], key: str, *, kind: Optional[str] = None) -> Optional[T]:
        kind = kind or model.__name__
        row = self._db.execute("SELECT body FROM objects WHERE kind=? AND id=?", (kind, key)).fetchone()
        return model.model_validate(json.loads(row[0])) if row else None

    def list(self, model: Type[T], case_id: Optional[str] = None, *, kind: Optional[str] = None) -> list[T]:
        kind = kind or model.__name__
        if case_id is None:
            rows = self._db.execute("SELECT body FROM objects WHERE kind=? ORDER BY seq", (kind,)).fetchall()
        else:
            rows = self._db.execute(
                "SELECT body FROM objects WHERE kind=? AND case_id=? ORDER BY seq", (kind, case_id)
            ).fetchall()
        return [model.model_validate(json.loads(r[0])) for r in rows]

    _KEYS = {
        "Case": "case_id", "Assessment": "case_id", "Claim": "claim_id", "Evidence": "evidence_id",
        "InvestigationPlan": "plan_id", "Preflight": "preflight_id", "Approval": "decision_id",
        "ToolReceipt": "tool_receipt_id", "Finding": "finding_id", "FinalReviewRecord": "signoff_id",
    }

    # ids that come from fixtures/agents and can repeat across cases are scoped by case
    _CASE_SCOPED = {"Evidence", "Claim"}

    @classmethod
    def _key(cls, obj: BaseModel) -> str:
        name = type(obj).__name__
        attr = cls._KEYS.get(name)
        if not attr:
            raise ValueError(f"no key for {name}")
        key = getattr(obj, attr)
        return f"{obj.case_id}:{key}" if name in cls._CASE_SCOPED else key

    # ------------------------------------------------------------ ledger
    def append_event(self, case_id: str, event_type: str, actor_type: str, actor_id: str,
                     summary: str = "", payload_refs: Iterable[str] = ()) -> Event:
        with self._lock:
            row = self._db.execute(
                "SELECT event_hash FROM events WHERE case_id=? ORDER BY seq DESC LIMIT 1", (case_id,)
            ).fetchone()
            prev = row[0] if row else GENESIS
            ev = Event(
                event_id=ids.next("EVT"), case_id=case_id, event_type=event_type, actor_type=actor_type,
                actor_id=actor_id, timestamp=clock.iso(), summary=summary, payload_refs=list(payload_refs),
                previous_event_hash=prev,
            )
            ev.event_hash = event_hash(ev)
            self._db.execute(
                "INSERT INTO events(case_id, event_id, body, event_hash) VALUES (?,?,?,?)",
                (case_id, ev.event_id, canonical_json(ev), ev.event_hash),
            )
            self._db.commit()
            return ev

    def events(self, case_id: str) -> list[Event]:
        rows = self._db.execute("SELECT body FROM events WHERE case_id=? ORDER BY seq", (case_id,)).fetchall()
        return [Event.model_validate(json.loads(r[0])) for r in rows]

    def export_jsonl(self, case_id: str) -> str:
        return "\n".join(canonical_json(e) for e in self.events(case_id)) + "\n"


def event_hash(ev: Event) -> str:
    body = to_plain(ev)
    body.pop("event_hash", None)
    return sha256_hex(canonical_json(body))


def verify_chain(events: list[dict] | list[Event]) -> dict:
    """Recompute the chain. Returns {ok, entries, first_bad_index}."""
    prev = GENESIS
    for i, raw in enumerate(events):
        ev = raw if isinstance(raw, Event) else Event.model_validate(raw)
        if ev.previous_event_hash != prev or event_hash(ev) != ev.event_hash:
            return {"ok": False, "entries": len(events), "first_bad_index": i, "event_id": ev.event_id}
        prev = ev.event_hash
    return {"ok": True, "entries": len(events), "first_bad_index": None}


def verify_jsonl(text: str) -> dict:
    lines = [json.loads(line) for line in text.splitlines() if line.strip()]
    return verify_chain(lines)
