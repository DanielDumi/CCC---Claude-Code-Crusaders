"""Canonical JSON, hashing, ids and a controllable clock (one implementation for backend and pack verifier)."""
from __future__ import annotations

import hashlib
import itertools
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel


def to_plain(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> str:
    """Sorted keys, UTF-8, no spaces. Used for plan hashes, event hashes and the pack checksum."""
    return json.dumps(to_plain(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_without(obj: Any, *exclude: str) -> str:
    plain = to_plain(obj)
    for key in exclude:
        plain.pop(key, None)
    return sha256_hex(canonical_json(plain))


class Clock:
    """Wall clock by default; tests and the demo can pin it."""

    def __init__(self) -> None:
        self._fixed: datetime | None = None

    def now(self) -> datetime:
        return self._fixed or datetime.now(timezone.utc)

    def iso(self) -> str:
        return self.now().replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def pin(self, value: datetime | None) -> None:
        self._fixed = value

    def advance(self, **kwargs: float) -> None:
        self._fixed = self.now() + timedelta(**kwargs)


clock = Clock()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class IdGen:
    def __init__(self) -> None:
        self._counters: dict[str, itertools.count] = {}
        self._lock = threading.Lock()

    def next(self, prefix: str) -> str:
        with self._lock:
            counter = self._counters.setdefault(prefix, itertools.count(1))
            return f"{prefix}-{next(counter):03d}"


ids = IdGen()
