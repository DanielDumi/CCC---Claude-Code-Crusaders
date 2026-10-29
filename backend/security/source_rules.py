"""Source-permission facts and rules for the gate (gate spec §5 steps 9 and 11, §6; task C1).

Who may query which source about this client, now? The answers come from the bank's own records
(consents, application status) that the scenario fixture seeds. Facts are small pure functions,
rules compare facts and return hits. No LLM, no side effects, and no personal data in the facts:
only ids, dates, booleans and counts.

Rule metadata (title, citation, effect, next step, preflight mapping) lives in
fixtures/policies/demo-policy.yaml under `rules:`. The conditions live here, because facts are code.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Optional

import holidays

ROMANIA = holidays.country_holidays("RO", years=range(2020, 2036))

DEFAULTS: dict[str, Any] = {
    "anaf_consent_window_days": 5,                  # draft ANAF order reported 12 Sep 2026 [draft]
    "anaf_window_rule_effective_from": "2026-09-12",
    "consent_sources_with_window": ["ANAF"],
    "closed_application_statuses": ["withdrawn", "rejected", "closed"],
    "purposes_allowed_after_closure": ["deletion", "legal_obligation"],
}

RULE_STATUS = "SRC-STATUS-001"       # withdrawn / rejected / closed application: no new processing
RULE_HOLD = "SRC-HOLD-001"           # a fact needed for the decision could not be read: hold, never allow
RULE_BASIS = "SRC-BASIS-001"         # personal-data query without a legal-basis reference
RULE_ANAF_ABSENT = "SRC-ANAF-001"
RULE_ANAF_LAPSED = "SRC-ANAF-002"
RULE_ANAF_MISMATCH = "SRC-ANAF-003"
RULE_ANAF_WITHDRAWN = "SRC-ANAF-004"


# ------------------------------------------------------------------ dates and Romanian working days
def parse_at(value: Any) -> dt.datetime:
    """ISO 8601 with offset -> aware datetime (naive input is taken as UTC)."""
    if isinstance(value, dt.datetime):
        at = value
    else:
        at = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    return at if at.tzinfo else at.replace(tzinfo=dt.timezone.utc)


def parse_date(value: Any) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    return parse_at(text).date() if ("T" in text or " " in text) else dt.date.fromisoformat(text)


def is_working_day(day: dt.date) -> bool:
    return day.weekday() < 5 and day not in ROMANIA


def add_working_days(start: dt.date, n: int) -> dt.date:
    """Date of the n-th Romanian working day after `start`.

    Convention [team]: the signing day is excluded and the window is valid through the returned day,
    inclusive. Mon 2 Nov 2026 -> Mon 9 Nov 2026. Fri 27 Nov 2026 -> Tue 8 Dec 2026 (30 Nov and 1 Dec
    are public holidays). No source states a counting convention; this one is written down here.
    """
    day, counted = start, 0
    while counted < n:
        day += dt.timedelta(days=1)
        if is_working_day(day):
            counted += 1
    return day


def working_days_elapsed(start: dt.date, until: dt.date) -> int:
    """Working days in the half-open interval (start, until]."""
    count, day = 0, start
    while day < until:
        day += dt.timedelta(days=1)
        if is_working_day(day):
            count += 1
    return count


# ------------------------------------------------------------------ facts
@dataclass
class Fact:
    """Tri-state fact: `absent` evaluates normally (no consent = deny); `unavailable` makes every
    rule that needs it a hold (the store did not answer)."""
    value: Any = None
    status: str = "ok"  # ok | absent | unavailable
    ref: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def unavailable(self) -> bool:
        return self.status == "unavailable"


class Records:
    """Read-only view over a scenario's bank records: the same fixture tables the lookup tools serve.

    The gate reads them directly. A fact lookup is not a tool call, needs no approval and never
    counts as an MCP invocation. `fail_modes` (tool_id -> mode) simulates a store that does not answer.
    """

    def __init__(self, scenario: Optional[dict], fail_modes: Optional[dict] = None) -> None:
        self.scenario = scenario or {}
        self.fail_modes = fail_modes or {}
        self.tables: dict[str, dict] = self.scenario.get("tool_data", {}) or {}
        meta = self.scenario.get("records", {}) or {}
        self.client_id: Optional[str] = meta.get("client_id")
        self.application_id: Optional[str] = meta.get("application_id")
        raw = self.scenario.get("case_time") or meta.get("case_time")
        self.case_time: Optional[dt.datetime] = parse_at(raw) if raw else None

    def _table(self, tool_id: str) -> Fact:
        if self.fail_modes.get(tool_id):
            return Fact(status="unavailable", ref=f"{tool_id}:{self.fail_modes[tool_id]}")
        table = self.tables.get(tool_id)
        if table is None:
            return Fact(status="absent", ref=tool_id)
        rows = [v for v in table.values() if isinstance(v, dict)]
        if any(v.get("__unavailable__") for v in rows):
            return Fact(status="unavailable", ref=f"{tool_id}:unavailable")
        return Fact(value=rows, ref=tool_id)

    def consent(self, consent_id: Optional[str]) -> Fact:
        table = self._table("consent_lookup")
        if not table.ok:
            return table
        for rec in table.value:
            if rec.get("consent_id") == consent_id:
                return Fact(value=rec, ref=f"consent:{consent_id}")
        return Fact(status="absent", ref=f"consent:{consent_id}")

    def application(self, application_id: Optional[str]) -> Fact:
        table = self._table("application_status_lookup")
        if not table.ok:
            return table
        for rec in table.value:
            if rec.get("application_id") == application_id:
                return Fact(value=rec, ref=f"application:{application_id}")
        return Fact(status="absent", ref=f"application:{application_id}")


def config(policy_data: Optional[dict]) -> dict:
    return {**DEFAULTS, **((policy_data or {}).get("source_rules") or {})}


def consent_valid_until(consent: dict, cfg: dict, at: Optional[dt.datetime] = None) -> Optional[dt.date]:
    """ANAF consents: signed_at + N Romanian working days once the dated draft rule is active; otherwise
    no window (OPANAF 146/2022 in force has none). CRC and Credit Bureau windows are not modelled here."""
    if consent.get("source") not in cfg["consent_sources_with_window"]:
        return None
    if at is not None and at.date() < parse_date(cfg["anaf_window_rule_effective_from"]):
        return None
    return add_working_days(parse_date(consent["signed_at"]), int(cfg["anaf_consent_window_days"]))


def consent_status_at(consent: dict, at: dt.datetime, cfg: Optional[dict] = None) -> tuple[str, dict]:
    """VALID | LAPSED | WITHDRAWN | INVALIDATED | EXPIRED | NOT_GIVEN, plus the derived facts (no personal data)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    status = str(consent.get("status", "")).upper()
    facts: dict[str, Any] = {"consent.id": consent.get("consent_id"), "consent.status": consent.get("status"),
                             "consent.signed_at": consent.get("signed_at"), "at": at.isoformat()}
    if status in ("WITHDRAWN", "INVALIDATED", "EXPIRED"):
        return status, facts
    if status != "GIVEN":
        return "NOT_GIVEN", facts
    valid_until = consent_valid_until(consent, cfg, at)
    if valid_until is None:
        facts["consent.valid_until"] = None
        return "VALID", facts
    facts.update({
        "consent.valid_until": valid_until.isoformat(),
        "working_days_elapsed": working_days_elapsed(parse_date(consent["signed_at"]), at.date()),
        "window_working_days": int(cfg["anaf_consent_window_days"]),
    })
    return ("VALID" if at.date() <= valid_until else "LAPSED"), facts


def application_status_at(application: dict, at: dt.datetime) -> str:
    """Status at time `at` from `status_history` (lower-case); 'unknown' before the first entry."""
    history = sorted(application.get("status_history", []), key=lambda h: parse_at(h["at"]))
    if not history:
        return str(application.get("status") or "unknown").lower()
    status = None
    for h in history:
        if parse_at(h["at"]) <= at:
            status = h["status"]
    return str(status or "unknown").lower()


# ------------------------------------------------------------------ rules
@dataclass
class RuleHit:
    rule_id: str
    outcome: str                      # deny | hold
    reason: str
    next_step: str = "none"           # none | request_consent | retry_later | escalate | human_approval
    facts: dict = field(default_factory=dict)


def evaluate_call(tool_id: str, arguments: dict, purpose: str, policy_data: dict, records: Records,
                  at: dt.datetime) -> list[RuleHit]:
    """Source-permission rules for one planned or attempted call. Deny beats hold; an empty list is no
    objection. Same code runs in the preflight (prediction) and in the tool proxy (enforcement)."""
    cfg = config(policy_data)
    hits: list[RuleHit] = []
    allowed = ((policy_data or {}).get("allowed_tools") or {}).get(tool_id) or {}
    arguments = arguments or {}

    # 1. Application status: no new processing of a withdrawn, rejected or closed file (SRC-STATUS-001).
    if records.application_id and allowed.get("subject_data", True):
        app = records.application(records.application_id)
        if app.unavailable:
            hits.append(RuleHit(RULE_HOLD, "hold",
                                f"Application status for {records.application_id} could not be read ({app.ref}); "
                                "the call is held, never allowed.", "retry_later",
                                {"application.id": records.application_id, "fact.unavailable": "application.status"}))
        elif not app.ok:
            hits.append(RuleHit(RULE_HOLD, "hold",
                                f"Application {records.application_id} is not on record; its status cannot be established.",
                                "escalate", {"application.id": records.application_id, "fact.absent": "application"}))
        else:
            status = application_status_at(app.value, at)
            when = next((h["at"] for h in app.value.get("status_history", []) if h["status"] == status), None)
            if status in cfg["closed_application_statuses"] and purpose not in cfg["purposes_allowed_after_closure"]:
                hits.append(RuleHit(RULE_STATUS, "deny",
                                    f"Application {records.application_id} is {status}" + (f" since {when}" if when else "")
                                    + f"; no further processing of the file for purpose '{purpose}' "
                                    "(only deletion or a legal obligation).", "none",
                                    {"application.id": records.application_id, "application.status": status,
                                     "application.status_since": when, "at": at.isoformat()}))
            elif status == "unknown":
                hits.append(RuleHit(RULE_HOLD, "hold",
                                    f"Application {records.application_id} has no status at {at.isoformat()}.",
                                    "escalate", {"application.id": records.application_id, "application.status": status}))

    # 2. Legal basis per source: consent for this client, this source, this application, still valid.
    requires = allowed.get("requires_basis") or {}
    if requires.get("kind") == "consent":
        source = requires.get("source")
        consent_id = arguments.get("consent_id")
        client_id = arguments.get("client_id") or records.client_id
        if not consent_id:
            hits.append(RuleHit(RULE_BASIS, "deny",
                                f"{tool_id} asks for personal data without a legal-basis reference (no consent_id).",
                                "human_approval", {"tool": tool_id, "source": source}))
            return hits
        fact = records.consent(consent_id)
        if fact.unavailable:
            hits.append(RuleHit(RULE_HOLD, "hold",
                                f"Consent register unavailable ({fact.ref}); consent {consent_id} cannot be verified. "
                                "Held, never allowed.", "retry_later",
                                {"consent.id": consent_id, "fact.unavailable": "consent.record"}))
        elif not fact.ok:
            hits.append(RuleHit(RULE_ANAF_ABSENT, "deny",
                                f"No consent {consent_id} on record for {source}. A consent must exist before the query.",
                                "request_consent", {"consent.id": consent_id, "fact.absent": "consent.record"}))
        else:
            consent = fact.value
            status, facts = consent_status_at(consent, at, cfg)
            mismatch = []
            if consent.get("source") != source:
                mismatch.append(f"consent is for {consent.get('source')}, not {source}")
            if client_id and consent.get("client_id") != client_id:
                mismatch.append("consent belongs to another client")
            if records.application_id and consent.get("application_id") \
                    and consent.get("application_id") != records.application_id:
                mismatch.append(f"consent is for application {consent.get('application_id')}, not {records.application_id}")
            if mismatch:
                hits.append(RuleHit(RULE_ANAF_MISMATCH, "deny",
                                    f"Consent {consent_id} does not cover this query ({'; '.join(mismatch)}). "
                                    "Request a consent for this purpose.", "request_consent", facts))
            elif status in ("WITHDRAWN", "INVALIDATED", "EXPIRED", "NOT_GIVEN"):
                hits.append(RuleHit(RULE_ANAF_WITHDRAWN, "deny",
                                    f"Consent {consent_id} is {status.lower().replace('_', ' ')}; it cannot be used.",
                                    "request_consent", facts))
            elif status == "LAPSED":
                hits.append(RuleHit(RULE_ANAF_LAPSED, "deny",
                                    f"{source} income consent {consent_id} lapsed on {facts['consent.valid_until']} "
                                    f"({facts['window_working_days']} Romanian working days from {facts['consent.signed_at']}, "
                                    f"signing day excluded); {facts['working_days_elapsed']} working days had elapsed at case time. "
                                    "Request a new consent.", "request_consent", facts))
    return hits


# ------------------------------------------------------------------ record providers
@lru_cache(maxsize=1)
def _scenarios_from_disk() -> dict:
    from backend.tools.mcp_fixture_server import load_scenarios
    return load_scenarios()


def records_for(scenario_id: Optional[str], provider: Optional[Callable[[str], Records]] = None) -> Records:
    """Records for a case. The tool proxy injects a provider bound to its fixture server (so fail modes
    apply); without one, the fixtures are read from disk."""
    if provider is not None:
        return provider(scenario_id or "")
    return Records(_scenarios_from_disk().get(scenario_id or ""))
