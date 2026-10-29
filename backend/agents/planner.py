"""Investigation planner: claim extraction + plan proposal (spec 03 §2–3, 05 §3).

Two modes behind the same interface:
- LLM (Bedrock): the model proposes claims and plan steps from the case, the tool catalogue and the
  reviewer's restrictions. Output is schema-validated; anything invalid falls back to the mock.
- Mock (deterministic, used in tests and when no key is present): a scripted extractor (scenario
  fixture) and a rule-based tool chooser. The mock deliberately over-reaches in round 1 for
  current-status and presence claims (proposes an open web search), like a typical first LLM plan,
  so the preflight and the reviewer have something real to cut.

The planner can PROPOSE. It cannot add permissions, mark a step lawful or bypass restrictions:
restrictions are re-applied deterministically after the model answers, and the preflight + tool
proxy decide what may run.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Optional

from pydantic import ValidationError

from backend.domain.models import (
    Assessment, Case, CheckType, Claim, Evidence, Finding, InvestigationPlan, PlanStep,
)
from backend.llm.adapter import LLM, LLMError
from backend.security.policy_engine import Policy, compute_plan_hash
from backend.tools.catalog import CATALOG, catalog_for_model
from backend.util import clock


CLAIM_SCHEMA = """{"claims":[{"claim_text":str,"temporal_scope":"HISTORICAL|CURRENT|UNSPECIFIED",
"check_type":"HISTORICAL_EVENT|CURRENT_STATUS|ENTITY_ATTRIBUTION|FACT_PRESENCE|VERSIONED_FIGURE|CALCULATION",
"required_evidence":[str],"params":{...}}],"gaps":[str]}
params per check_type: HISTORICAL_EVENT {case_ref, period_year}; CURRENT_STATUS {case_ref, asserted_status};
ENTITY_ATTRIBUTION {source_evidence_id, source_entity_id}; FACT_PRESENCE {field, tool, subject_kind?};
VERSIONED_FIGURE {field, asserted_value, document_ids}; CALCULATION {field, from_year, to_year, asserted_change_pct}.
Split compound findings into atomic claims (e.g. 'existed in 2024' vs 'is ongoing now')."""

PLAN_SCHEMA = """{"objective":str,"rationale":str,"steps":[{"claim_ids":[str],"objective":str,"tool_id":str,
"arguments":{...},"expected_evidence":str,"depends_on":[str]}]}
Use only tool_id values from the catalogue. Propose the smallest set of checks that can settle each claim.
Before relying on any source about the subject, confirm the subject's identity with company_registry_lookup
(company_id = subject.reference_id) unless an earlier round already did. Do not repeat calls listed in already_done.
Respect every reviewer restriction. Do not include tools listed as forbidden by the reviewer."""


REQUIRED_PARAMS = {
    CheckType.HISTORICAL_EVENT: {"case_ref", "period_year"},
    CheckType.CURRENT_STATUS: {"case_ref", "asserted_status"},
    CheckType.ENTITY_ATTRIBUTION: {"source_evidence_id"},
    CheckType.FACT_PRESENCE: {"field"},
    CheckType.VERSIONED_FIGURE: {"field", "asserted_value", "document_ids"},
    CheckType.CALCULATION: {"field", "from_year", "to_year", "asserted_change_pct"},
}

EXPLAIN_SCHEMA = """{"explanations":[{"claim_id":str,"en":str,"ro":str}]}
One or two plain sentences per claim for a bank reviewer. Restate only what the finding and evidence say;
do not change any verdict, add facts or give legal conclusions."""


class Planner:
    def __init__(self, llm: LLM, policy: Policy) -> None:
        self.llm = llm
        self.policy = policy

    # ---------------------------------------------------------------- assessment
    def assess(self, case: Case, evidence: list[Evidence], scenario: Optional[dict]) -> Assessment:
        claims: list[Claim] = []
        produced_by = "mock"
        if self.llm.mode != "mock":
            try:
                out = self.llm.complete("extract_claims", {
                    "raw_finding": case.raw_finding, "subject": case.subject.model_dump(),
                    "attached_evidence": [_ev_summary(e) for e in evidence]}, CLAIM_SCHEMA)
                claims = [self._claim(case, i, c) for i, c in enumerate(out.get("claims", []), 1)]
                if not claims:
                    raise LLMError("no claims")
                for c in claims:  # the deterministic verifier needs these parameters
                    missing = REQUIRED_PARAMS[c.check_type] - set(c.params)
                    if missing:
                        raise LLMError(f"{c.claim_id} missing params {missing}")
                produced_by = self.llm.label
            except (LLMError, ValidationError, KeyError, TypeError, ValueError):
                claims = []
        if not claims:
            raw = (scenario or {}).get("mock_claims") or [{
                "claim_text": case.raw_finding, "check_type": "FACT_PRESENCE", "params": {"field": "unknown"}}]
            claims = [self._claim(case, i, c) for i, c in enumerate(raw, 1)]
        gaps = self._gaps(case, claims, evidence)
        return Assessment(case_id=case.case_id, claims=claims, gaps=gaps, produced_by=produced_by)

    @staticmethod
    def _claim(case: Case, i: int, c: dict) -> Claim:
        return Claim(claim_id=f"CL-{i:03d}", case_id=case.case_id, claim_text=c["claim_text"],
                     temporal_scope=c.get("temporal_scope", "UNSPECIFIED"),
                     required_evidence=list(c.get("required_evidence", [])),
                     check_type=CheckType(c["check_type"]), params=dict(c.get("params", {})))

    @staticmethod
    def _gaps(case: Case, claims: list[Claim], evidence: list[Evidence]) -> list[str]:
        gaps = []
        for c in claims:
            if c.check_type == CheckType.CURRENT_STATUS:
                c.gaps.append("current_status_not_established")
                gaps.append(f"{c.claim_id}: attached source is historical; current status is not established")
            if c.check_type in (CheckType.HISTORICAL_EVENT, CheckType.ENTITY_ATTRIBUTION):
                c.gaps.append("identity_not_verified")
                gaps.append(f"{c.claim_id}: entity identity not verified against a registry")
            if c.check_type == CheckType.FACT_PRESENCE:
                c.gaps.append("no_supporting_source")
                gaps.append(f"{c.claim_id}: no attached source contains '{c.params.get('field')}'")
            if c.check_type == CheckType.VERSIONED_FIGURE:
                c.gaps.append("conflicting_versions")
                gaps.append(f"{c.claim_id}: attached document versions disagree")
            if c.check_type == CheckType.CALCULATION:
                c.gaps.append("figures_not_attached")
                gaps.append(f"{c.claim_id}: underlying figures are not attached")
        if case.original_execution_trace_status != "CAPTURED":
            gaps.append(f"Original agent trace: {case.original_execution_trace_status}")
        missing = [e.evidence_id for e in evidence if e.status.value == "NOT_CAPTURED"]
        if missing:
            gaps.append(f"Cited but not captured: {', '.join(missing)}")
        return gaps

    # ---------------------------------------------------------------- explanations (LLM only, never verdicts)
    def explain(self, findings: list[Finding], evidence: list[Evidence]) -> dict[str, str]:
        if self.llm.mode == "mock" or not findings:
            return {}
        try:
            out = self.llm.complete("explain_findings", {
                "findings": [f.model_dump(mode="json") for f in findings],
                "evidence": [_ev_summary(e) for e in evidence]}, EXPLAIN_SCHEMA, max_tokens=900)
            return {x["claim_id"]: f"{x.get('en', '')} / RO: {x.get('ro', '')}" for x in out.get("explanations", [])
                    if isinstance(x, dict) and "claim_id" in x}
        except (LLMError, KeyError, TypeError, ValueError):
            return {}

    # ---------------------------------------------------------------- planning
    def propose_plan(self, case: Case, claims: list[Claim], findings: list[Finding], evidence: list[Evidence],
                     restrictions: dict[str, Any], version: int, supersedes: Optional[str],
                     done_calls: Optional[set[str]] = None) -> InvestigationPlan:
        done_calls = done_calls or set()
        round_no = version
        drafts: list[dict] = []
        produced_by = "mock"
        open_claims = [c for c in claims if not findings or _needs_work(c, findings)]
        followups = [f.next_action_proposal for f in findings if f.next_action_proposal]

        if self.llm.mode != "mock":
            try:
                out = self.llm.complete("propose_plan", {
                    "case": {"purpose": case.purpose, "subject": case.subject.model_dump()},
                    "claims": [c.model_dump(mode="json") for c in open_claims],
                    "findings_so_far": [f.model_dump(mode="json") for f in findings],
                    "proposed_followups": followups, "tool_catalog": catalog_for_model(),
                    "reviewer_restrictions": restrictions, "round": round_no,
                    "already_done": sorted(done_calls)}, PLAN_SCHEMA)
                drafts = [dict(s) for s in out.get("steps", [])]
                for d in drafts:
                    if not isinstance(d.get("tool_id"), str) or not isinstance(d.get("arguments", {}), dict):
                        raise LLMError("bad step")
                    spec = CATALOG.get(d["tool_id"])
                    if spec and set(d.get("arguments", {})) != set(spec.arguments):
                        raise LLMError(f"arguments for {d['tool_id']} do not match the catalogue")
                produced_by = self.llm.label
            except (LLMError, KeyError, TypeError, ValueError):
                drafts = []
        if not drafts:
            drafts = self._mock_steps(case, open_claims, findings, followups, first_round=not findings)

        drafts = [d for d in drafts if call_key(d["tool_id"], d.get("arguments", {})) not in done_calls]
        drafts = self._apply_restrictions(drafts, restrictions)
        steps = self._normalise(drafts)
        forbidden = sorted(set(restrictions.get("forbid_tools", [])))
        restriction_text = list(restrictions.get("notes", []))
        if forbidden:
            restriction_text.append("Excluded by reviewer: " + ", ".join(forbidden))
        if restrictions.get("allow_only_tools"):
            restriction_text.append("Only: " + ", ".join(restrictions["allow_only_tools"]))
        plan = InvestigationPlan(
            plan_id=f"PLAN-{case.case_id}-v{version}", case_id=case.case_id, version=version,
            created_by=f"INVESTIGATION_AGENT ({produced_by})",
            objective=_objective(open_claims, followups), purpose=case.purpose,
            data_categories=sorted({c for s in steps for c in s.data_categories}),
            source_allowlist=sorted({s.allowed_source_ref for s in steps if s.allowed_source_ref}),
            forbidden_tools=forbidden, reviewer_restrictions=restriction_text,
            global_max_tool_calls=min(int(restrictions.get("max_calls", self.policy.max_total_tool_calls)),
                                      self.policy.max_total_tool_calls),
            expires_at=(clock.now() + timedelta(minutes=self.policy.approval_ttl_minutes)).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"),
            rationale=_rationale(steps, followups, first_round=not findings, by_model=produced_by != "mock"),
            steps=steps, supersedes=supersedes,
        )
        plan.plan_hash = compute_plan_hash(plan)
        return plan

    # ------------------------------------------------------------------ helpers
    def _mock_steps(self, case: Case, claims: list[Claim], findings: list[Finding], followups: list[str],
                    first_round: bool) -> list[dict]:
        sid = case.subject.reference_id
        steps: list[dict] = []

        def add(tool: str, args: dict, claim_ids: list[str], objective: str, expected: str, depends: list[str] = ()):
            for s in steps:
                if s["tool_id"] == tool and s["arguments"] == args:
                    s["claim_ids"] = sorted(set(s["claim_ids"]) | set(claim_ids))
                    return s["step_id"]
            step_id = f"S{len(steps) + 1}"
            steps.append({"step_id": step_id, "tool_id": tool, "arguments": args, "claim_ids": claim_ids,
                          "objective": objective, "expected_evidence": expected, "depends_on": list(depends)})
            return step_id

        if not first_round:
            for f in followups:
                tool, _, arg = f.partition(":")
                if tool == "document_signature_check":
                    add(tool, {"document_id": arg}, [_claim_of(findings, f)],
                        f"Check authenticity of {arg} before relying on it", "signature metadata match")
            # claims that no approved step has looked at yet: propose their normal checks, never the open web
            unchecked = [c for c in claims if any(x.claim_id == c.claim_id and x.verdict.value == "NOT_CHECKED"
                                                  for x in findings)]
            for d in self._mock_steps(case, unchecked, [], [], first_round=True):
                if d["tool_id"] != "unrestricted_web_search":
                    add(d["tool_id"], d["arguments"], d["claim_ids"], d["objective"], d["expected_evidence"])
            return steps

        for c in claims:
            p = c.params
            if p.get("tool") and (p.get("arguments") is not None or p.get("documents")) and c.check_type in (
                    CheckType.CURRENT_STATUS, CheckType.FACT_PRESENCE):
                # The claim names its authorised source and lookup key (the bank's consent register, the loan
                # application system, ANAF income, the documents in the file). Read those records. Round 1 still
                # over-reaches with a web search about the person, which the preflight blocks and the reviewer removes.
                for doc in p.get("documents") or []:
                    add(p["tool"], {"document_id": doc}, [c.claim_id], f"Read the typed fields of {doc}",
                        "typed document fields (identifiers masked)")
                if p.get("arguments") is not None:
                    add(p["tool"], dict(p["arguments"]), [c.claim_id],
                        f"Read {p.get('case_ref') or p.get('field')} from {p['tool']}", "dated record from the authorised source")
                add("unrestricted_web_search", {"query": f"{case.subject.display_name} income and loans"},
                    [c.claim_id], "Broad web search about the client", "web pages")
                continue
            if c.check_type in (CheckType.HISTORICAL_EVENT, CheckType.CURRENT_STATUS):
                reg = add("company_registry_lookup", {"company_id": sid}, [c.claim_id],
                          "Check legal-entity identifier", "entity ID and registration metadata")
                if c.check_type == CheckType.CURRENT_STATUS:
                    add("legal_case_status_lookup", {"company_id": sid, "case_ref": p.get("case_ref")}, [c.claim_id],
                        f"Verify current status of case {p.get('case_ref')}", "dated case status", [reg])
                    add("unrestricted_web_search", {"query": f"{case.subject.display_name} lawsuit latest news"},
                        [c.claim_id], "Broad web search for recent coverage", "news articles")
            elif c.check_type == CheckType.ENTITY_ATTRIBUTION:
                add("company_registry_lookup", {"company_id": sid}, [c.claim_id], "Check case subject identifier",
                    "subject entity ID and jurisdiction")
                if p.get("source_entity_id") and p["source_entity_id"] != sid:
                    add("company_registry_lookup", {"company_id": p["source_entity_id"]}, [c.claim_id],
                        "Check identifier of the entity named in the source", "source entity ID and jurisdiction")
            elif c.check_type == CheckType.FACT_PRESENCE:
                tool = p.get("tool")
                if p.get("subject_kind") == "NATURAL_PERSON":
                    add("unrestricted_web_search", {"query": f"{case.subject.display_name} director personal loans"},
                        [c.claim_id], "Search the web for the director's personal credit history", "web pages")
                elif tool:
                    add(tool, {"company_id": sid}, [c.claim_id], f"Query the authorised source for '{p.get('field')}'",
                        f"official {p.get('field')}")
                    add("unrestricted_web_search", {"query": f"{case.subject.display_name} {p.get('field')}"},
                        [c.claim_id], "Broad web search for corroboration", "web pages")
            elif c.check_type == CheckType.VERSIONED_FIGURE:
                for doc in p.get("document_ids", []):
                    add("document_metadata_lookup", {"document_id": doc}, [c.claim_id],
                        f"Get version/approval metadata for {doc}", "approved-version flag")
            elif c.check_type == CheckType.CALCULATION:
                for year in (p.get("from_year"), p.get("to_year")):
                    add("financial_report_lookup", {"company_id": sid, "year": year}, [c.claim_id],
                        f"Get filed {p.get('field')} for {year}", f"{p.get('field')} {year}")
        return steps

    @staticmethod
    def _apply_restrictions(drafts: list[dict], restrictions: dict[str, Any]) -> list[dict]:
        forbid = set(restrictions.get("forbid_tools", []))
        only = set(restrictions.get("allow_only_tools", []))
        kept = [d for d in drafts if d["tool_id"] not in forbid and (not only or d["tool_id"] in only)]
        kept_ids = {d.get("step_id") for d in kept}
        for d in kept:
            d["depends_on"] = [x for x in d.get("depends_on", []) if x in kept_ids]
        return kept

    @staticmethod
    def _normalise(drafts: list[dict]) -> list[PlanStep]:
        steps = []
        remap = {}
        for i, d in enumerate(drafts, 1):
            remap[d.get("step_id", f"S{i}")] = f"S{i}"
        for i, d in enumerate(drafts, 1):
            spec = CATALOG.get(d["tool_id"])
            steps.append(PlanStep(
                step_id=f"S{i}", claim_ids=[c for c in d.get("claim_ids", []) if c], objective=d.get("objective", ""),
                tool_id=d["tool_id"], action="READ", arguments=d.get("arguments", {}),
                allowed_source_ref=spec.source_ref if spec else None,
                data_categories=[spec.data_category] if spec else ["UNKNOWN"], max_calls=1,
                depends_on=[remap.get(x, x) for x in d.get("depends_on", [])],
                expected_evidence=d.get("expected_evidence", ""),
            ))
        return steps


def _needs_work(claim: Claim, findings: list[Finding]) -> bool:
    f = next((x for x in findings if x.claim_id == claim.claim_id), None)
    return f is None or f.verdict.value in ("NOT_CHECKED", "INSUFFICIENT_EVIDENCE") or bool(f.next_action_proposal)


def _claim_of(findings: list[Finding], followup: str) -> str:
    f = next((x for x in findings if x.next_action_proposal == followup), None)
    return f.claim_id if f else ""


def _objective(claims: list[Claim], followups: list[str]) -> str:
    if followups:
        return "Close remaining evidence gaps: " + "; ".join(followups)
    return "Verify: " + " | ".join(c.claim_text for c in claims)


def call_key(tool_id: str, arguments: dict) -> str:
    return tool_id + "|" + json.dumps(arguments or {}, sort_keys=True)


def _rationale(steps: list[PlanStep], followups: list[str], first_round: bool, by_model: bool = False) -> str:
    if not first_round:
        if followups:
            return ("The newer record settles the claim, but nobody has checked that the record itself is genuine. "
                    "The agent proposes one more read-only check. It's a new step, so it needs a new policy check and your approval.")
        return ("Some claims couldn't be checked with the steps you approved. The agent proposes the missing read-only "
                "checks. New steps always need a new policy check and your approval.")
    if by_model:
        return f"The AI model proposed {len(steps)} read-only check(s) to settle the claims."
    return f"{len(steps)} read-only checks proposed to settle each claim with an original, identifiable source."


def _ev_summary(e: Evidence) -> dict:
    return {"evidence_id": e.evidence_id, "source_ref": e.source_ref, "published_at": e.published_at,
            "status": e.status.value, "excerpt": (e.original_excerpt or "")[:400], "fields": json.loads(json.dumps(e.fields, default=str))}
