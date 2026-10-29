"""Deterministic claim verification (spec 03 §8, 07 §5).

Separate questions are kept separate: source exists / source authorised / content supports claim /
authenticity verified. A second LLM agreeing never makes a claim SUPPORTED. Missing or unavailable
sources give INSUFFICIENT_EVIDENCE, never SUPPORTED.
"""
from __future__ import annotations

import unicodedata
from typing import Iterable, Optional

from backend.domain.models import Case, CheckType, Claim, ClaimVerdict, Evidence, EvidenceStatus, Finding
from backend.security.source_rules import application_status_at, consent_status_at, parse_at
from backend.util import ids


def norm(text: Optional[str]) -> str:
    """Case/diacritics-insensitive compare; treats Romanian cedilla ş/ţ and comma-below ș/ț as equal."""
    if not text:
        return ""
    text = text.replace("ş", "ș").replace("ţ", "ț").replace("Ş", "Ș").replace("Ţ", "Ț")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).casefold().strip()


def _available(evidence: Iterable[Evidence]) -> list[Evidence]:
    return [e for e in evidence if e.status == EvidenceStatus.AVAILABLE and e.authorized_for_case]


def _by_tool(evidence: Iterable[Evidence], tool_id: str) -> list[Evidence]:
    return [e for e in evidence if e.fields.get("tool_id") == tool_id]


def _identity(case: Case, evidence: list[Evidence]) -> Optional[Evidence]:
    for e in _by_tool(_available(evidence), "company_registry_lookup"):
        if e.entity_id == case.subject.reference_id and norm(e.fields.get("legal_name")) == norm(case.subject.display_name):
            return e
    return None


def _unavailable_reason(evidence: list[Evidence], tool_id: str) -> Optional[str]:
    for e in evidence:
        if e.fields.get("tool_id") == tool_id and e.status == EvidenceStatus.UNAVAILABLE:
            return e.fields.get("error", "source unavailable")
    return None


def _finding(claim: Claim, verdict: ClaimVerdict, reason: str, codes: list[str], sup=(), con=(), limits=(),
             next_action: Optional[str] = None) -> Finding:
    return Finding(finding_id=f"FND-{claim.claim_id}", claim_id=claim.claim_id, verdict=verdict,
                   supporting_evidence_ids=list(sup), contradicting_evidence_ids=list(con), reason=reason,
                   reason_codes=codes, authenticity_limitations=list(limits), requires_human_review=True,
                   next_action_proposal=next_action)


def _gate_block(evidence: Iterable[Evidence], tool_id: Optional[str]) -> Optional[Evidence]:
    """The gate's refusal of the claim's authorised source (an SRC-* rule), recorded by the tool proxy."""
    hits = [e for e in evidence if e.source_type == "GATE_DECISION" and e.fields.get("tool_id") == tool_id]
    return hits[-1] if hits else None


def _blocked_finding(claim: Claim, gate: Evidence) -> Finding:
    """A source the gate refused gives INSUFFICIENT_EVIDENCE with the rule ids attached, never SUPPORTED."""
    rule_ids = list(gate.fields.get("rule_ids", []))
    code = "permission_unverifiable" if gate.fields.get("decision") == "HOLD" else "source_not_allowed"
    steps = gate.fields.get("next_steps") or []
    limits = [f"Next step needs a human: {', '.join(s.replace('_', ' ') for s in steps)}"] if steps else []
    return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE,
                    f"The authorised source {gate.fields.get('tool_id')} could not be used ({', '.join(rule_ids)}): "
                    f"{gate.original_excerpt} Nothing was guessed.",
                    [code] + [f"gate:{r}" for r in rule_ids], sup=[gate.evidence_id], limits=limits)


def _as_of(rec: Evidence, case: Case):
    """Reference time for 'current': the fixture's case time (stamped by the proxy) or the case's creation time."""
    return parse_at(rec.fields.get("as_of_case_time") or case.created_at)


def _status_detail(tool: str, rec: Evidence, case: Case) -> tuple[str, str, list[str]]:
    """Status of the referenced record at case time, one sentence for the reviewer, extra reason codes.
    The bank's own registries derive the status in code from dates; other sources report it."""
    if tool == "consent_lookup":
        at = _as_of(rec, case)
        status, facts = consent_status_at(rec.fields, at)
        window = (f"valid through {facts['consent.valid_until']} ({facts['window_working_days']} Romanian working days "
                  f"from {facts['consent.signed_at']}, signing day excluded)" if facts.get("consent.valid_until")
                  else f"signed {facts['consent.signed_at']}, no validity window applies")
        detail = (f"{rec.source_ref}: consent {rec.fields.get('consent_id')} for {rec.fields.get('source')}, {window}; "
                  f"at case time {at.date().isoformat()} it is {status}")
        return status, detail, (["consent_lapsed"] if status == "LAPSED" else [])
    if tool == "application_status_lookup":
        at = _as_of(rec, case)
        status = application_status_at(rec.fields, at).upper()
        return status, (f"{rec.source_ref}: application {rec.fields.get('application_id')} is {status} "
                        f"at case time {at.isoformat()}"), []
    status = (rec.fields.get("status") or "").upper()
    return status, f"{rec.source_ref}: case {rec.fields.get('case_ref')} is {status} since {rec.fields.get('status_date')}", []


def verify_claim(case: Case, claim: Claim, evidence: list[Evidence], tools_attempted: set[str]) -> Finding:
    p = claim.params
    avail = _available(evidence)
    ct = claim.check_type

    if ct == CheckType.HISTORICAL_EVENT:
        docs = [e for e in avail if e.fields.get("case_ref") == p.get("case_ref")
                and e.published_at and e.published_at[:4] == str(p.get("period_year"))
                and norm(e.fields.get("mentions_entity_name")) == norm(case.subject.display_name)]
        ident = _identity(case, evidence)
        if not docs:
            return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE, "No source from the claimed period mentions this case.",
                            ["no_source"])
        if not ident:
            if "company_registry_lookup" in tools_attempted:
                return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE,
                                "The source names the company but the registry did not confirm the identity.",
                                ["identity_unconfirmed"], sup=[docs[0].evidence_id])
            return _finding(claim, ClaimVerdict.NOT_CHECKED, "Entity identity not yet checked against the registry.",
                            ["identity_not_checked"], sup=[docs[0].evidence_id])
        return _finding(claim, ClaimVerdict.SUPPORTED,
                        f"{docs[0].source_ref} ({docs[0].published_at[:10]}) reports case {p.get('case_ref')}; "
                        f"registry confirms {case.subject.display_name} = {ident.entity_id}.",
                        ["source_supports", "identity_confirmed"], sup=[docs[0].evidence_id, ident.evidence_id],
                        limits=["Historical source; says nothing about the current status"])

    if ct == CheckType.CURRENT_STATUS:
        # status of a referenced record from an authorised registry at case time; default: the licensed court registry
        tool = p.get("tool") or "legal_case_status_lookup"
        ref_field = p.get("ref_field") or "case_ref"
        gate = _gate_block(evidence, tool)
        if gate:
            return _blocked_finding(claim, gate)
        recs = [e for e in _by_tool(avail, tool) if e.fields.get(ref_field) == p.get("case_ref")
                and (tool != "legal_case_status_lookup" or e.entity_id == case.subject.reference_id)]
        historical = [e for e in avail if e.source_type == "ORIGINAL_CASE_ARTIFACT" and e.fields.get("case_ref") == p.get("case_ref")]
        if not recs:
            why = _unavailable_reason(evidence, tool)
            if why:
                return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE, f"Current status source unavailable: {why}.",
                                ["tool_error"], sup=[e.evidence_id for e in historical])
            code = "not_checked" if tool not in tools_attempted else "no_current_record"
            verdict = ClaimVerdict.NOT_CHECKED if code == "not_checked" else ClaimVerdict.INSUFFICIENT_EVIDENCE
            if historical:
                return _finding(claim, verdict, "Only a historical source exists; it cannot establish the current status.",
                                ["stale_source", code], sup=[e.evidence_id for e in historical])
            return _finding(claim, verdict, f"No record of {p.get('case_ref')} has been read from {tool}.", [code])
        rec = recs[-1]
        limits, next_action = [], None
        sig = [e for e in _by_tool(avail, "document_signature_check") if e.fields.get("document_id") == rec.document_id]
        if rec.document_id and not sig:
            limits.append(f"Authenticity of {rec.document_id} not verified")
            if "document_signature_check" not in tools_attempted:
                next_action = f"document_signature_check:{rec.document_id}"
        elif sig and sig[-1].fields.get("result") != "MATCH":
            return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE,
                            f"Signature check on {rec.document_id} did not match; the current record cannot be relied on.",
                            ["authenticity_failed"], con=[rec.evidence_id, sig[-1].evidence_id])
        elif sig:
            limits.append("Signature check is a SIMULATED fixture, not a qualified e-signature validation")
        if rec.untrusted_instruction_detected:
            limits.append("Source text contained instruction-like content; ignored as data")
        status, detail, extra = _status_detail(tool, rec, case)
        asserted = (p.get("asserted_status") or "").upper()
        sup_ids = [rec.evidence_id] + ([sig[-1].evidence_id] if sig else [])
        if status == asserted:
            return _finding(claim, ClaimVerdict.SUPPORTED, detail + ".", ["source_supports"] + extra, sup=sup_ids,
                            limits=limits, next_action=next_action)
        return _finding(claim, ClaimVerdict.CONTRADICTED,
                        detail + f"; the claim says {asserted}."
                        + (" The older source supports only the historical claim." if historical else ""),
                        ["source_contradicts"] + (["stale_original_source"] if historical else []) + extra,
                        sup=[e.evidence_id for e in historical], con=sup_ids, limits=limits, next_action=next_action)

    if ct == CheckType.ENTITY_ATTRIBUTION:
        src = next((e for e in avail if e.evidence_id == p.get("source_evidence_id")), None)
        ident = _identity(case, evidence)
        if src is None:
            return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE, "Cited source not captured.", ["no_source"])
        src_id = src.fields.get("entity_id") or p.get("source_entity_id")
        if not src_id:
            return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE,
                            "Source has no stable identifier; same/different entity cannot be decided by name.",
                            ["identity_unconfirmed"], sup=[src.evidence_id])
        other = next((e for e in _by_tool(avail, "company_registry_lookup") if e.entity_id == src_id), None)
        if not ident or (src_id != case.subject.reference_id and not other):
            verdict = ClaimVerdict.NOT_CHECKED if "company_registry_lookup" not in tools_attempted else ClaimVerdict.INSUFFICIENT_EVIDENCE
            return _finding(claim, verdict, "Registry identities not established for both entities.",
                            ["identity_not_checked"], sup=[src.evidence_id])
        if src_id == case.subject.reference_id:
            return _finding(claim, ClaimVerdict.SUPPORTED, "Source identifier matches the case subject.",
                            ["identity_confirmed"], sup=[src.evidence_id, ident.evidence_id])
        return _finding(claim, ClaimVerdict.CONTRADICTED,
                        f"Source concerns {other.fields.get('legal_name')} ({src_id}, {other.fields.get('jurisdiction')}), "
                        f"not {case.subject.display_name} ({case.subject.reference_id}, {ident.fields.get('jurisdiction')}). "
                        "Names are similar; identifiers and jurisdictions differ.",
                        ["wrong_entity"], con=[src.evidence_id, other.evidence_id, ident.evidence_id])

    if ct == CheckType.FACT_PRESENCE:
        tool = p.get("tool")
        gate = _gate_block(evidence, tool) if tool else None
        if gate:
            return _blocked_finding(claim, gate)
        recs = _by_tool(avail, tool) if tool else []
        field = p.get("field")
        docs = p.get("documents") or []
        if tool and docs:
            # the claimed value must hold in every listed document (e.g. payslip and bank statement), within tolerance
            found = {e.document_id: e for e in recs if e.document_id in docs}
            missing = [d for d in docs if d not in found]
            if missing:
                why = _unavailable_reason(evidence, tool)
                if why or tool in tools_attempted:
                    return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE,
                                    f"Could not read {', '.join(missing)}" + (f" ({why})" if why else "") + ". Nothing was guessed.",
                                    ["no_source"] + (["tool_error"] if why else []), sup=[e.evidence_id for e in found.values()])
                return _finding(claim, ClaimVerdict.NOT_CHECKED, f"Documents not read yet: {', '.join(missing)}.", ["not_checked"])
            values = {d: found[d].fields.get(field) for d in docs}
            if any(v is None for v in values.values()):
                empty = [d for d, v in values.items() if v is None]
                return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE, f"No '{field}' field in {', '.join(empty)}.",
                                ["no_source"], sup=[found[d].evidence_id for d in docs if values[d] is not None])
            asserted = p.get("asserted_value")
            tol = float(p.get("tolerance_pct") or 0)

            def matches(v):
                try:
                    return abs(float(v) - float(asserted)) <= abs(float(asserted)) * tol / 100
                except (TypeError, ValueError):
                    return v == asserted

            agree = [d for d in docs if matches(values[d])]
            disagree = [d for d in docs if not matches(values[d])]
            detail = "; ".join(f"{d}: {field}={values[d]}" for d in docs) + f"; the claim says {asserted}" + \
                     (f" (tolerance {tol:g}%)" if tol else "")
            if not disagree:
                return _finding(claim, ClaimVerdict.SUPPORTED, detail + ".", ["source_supports", "value_matches", "sources_agree"],
                                sup=[found[d].evidence_id for d in docs])
            return _finding(claim, ClaimVerdict.CONTRADICTED, detail + ". The sources do not agree within the tolerance.",
                            ["source_contradicts", "value_mismatch", "sources_disagree"],
                            sup=[found[d].evidence_id for d in agree], con=[found[d].evidence_id for d in disagree],
                            limits=["Two documents from the client's own file disagree; which one to trust is the reviewer's call"])
        if recs and field in recs[-1].fields:
            value = recs[-1].fields[field]
            if "asserted_value" in p:
                # the claim states a value: compare it in code, within an explicit tolerance (e.g. income, 2%)
                asserted = p["asserted_value"]
                tol = float(p.get("tolerance_pct") or 0)
                try:
                    matches = abs(float(value) - float(asserted)) <= abs(float(asserted)) * tol / 100
                except (TypeError, ValueError):
                    matches = value == asserted
                detail = f"{tool} reports {field}={value}; the claim says {asserted}" + (f" (tolerance {tol:g}%)" if tol else "")
                if matches:
                    return _finding(claim, ClaimVerdict.SUPPORTED, detail + ".", ["source_supports", "value_matches"],
                                    sup=[recs[-1].evidence_id])
                return _finding(claim, ClaimVerdict.CONTRADICTED, detail + ".", ["source_contradicts", "value_mismatch"],
                                con=[recs[-1].evidence_id])
            if value:
                return _finding(claim, ClaimVerdict.SUPPORTED, f"{tool} reports {field}={value}.", ["source_supports"],
                                sup=[recs[-1].evidence_id])
            return _finding(claim, ClaimVerdict.CONTRADICTED, f"{tool} reports {field}={value}.", ["source_contradicts"],
                            con=[recs[-1].evidence_id])
        why = _unavailable_reason(evidence, tool) if tool else None
        cited = [e.evidence_id for e in avail if e.source_type == "ORIGINAL_CASE_ARTIFACT"]
        if why:
            return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE,
                            f"The cited document has no '{field}' field and the authorised source was unavailable ({why}). "
                            "No record was invented.", ["no_source", "tool_error"], sup=[], con=[], limits=[])
        verdict = ClaimVerdict.NOT_CHECKED if (not tool or tool not in tools_attempted) else ClaimVerdict.INSUFFICIENT_EVIDENCE
        return _finding(claim, verdict,
                        f"No authorised source checked for '{field}'" + (f"; cited documents {cited} do not contain it." if cited else "."),
                        ["no_source"])

    if ct == CheckType.VERSIONED_FIGURE:
        field, asserted = p.get("field"), p.get("asserted_value")
        docs = [e for e in avail if e.document_id in p.get("document_ids", []) and e.source_type == "ORIGINAL_CASE_ARTIFACT"]
        meta = {e.fields.get("document_id"): e for e in _by_tool(avail, "document_metadata_lookup")}
        values = {e.document_id: e.fields.get(field) for e in docs}
        if len(set(values.values())) <= 1 and docs:
            v = next(iter(values.values()))
            verdict = ClaimVerdict.SUPPORTED if v == asserted else ClaimVerdict.CONTRADICTED
            return _finding(claim, verdict, f"All versions report {field}={v}.", ["consistent_versions"],
                            sup=[d.evidence_id for d in docs] if verdict == ClaimVerdict.SUPPORTED else [],
                            con=[d.evidence_id for d in docs] if verdict != ClaimVerdict.SUPPORTED else [])
        approved = [m for m in meta.values() if m.fields.get("approved_version")]
        if approved:
            doc_id = approved[0].fields["document_id"]
            v = values.get(doc_id)
            verdict = ClaimVerdict.SUPPORTED if v == asserted else ClaimVerdict.CONTRADICTED
            return _finding(claim, verdict, f"Approved version {doc_id} reports {field}={v}.", ["approved_version"],
                            sup=[approved[0].evidence_id])
        if "document_metadata_lookup" not in tools_attempted:
            return _finding(claim, ClaimVerdict.NOT_CHECKED, f"Versions disagree ({values}); provenance not checked yet.",
                            ["conflicting_versions"])
        return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE,
                        f"Versions disagree ({values}) and no approved-version metadata exists. Newest file or name is not proof.",
                        ["conflicting_versions", "no_approved_version"],
                        sup=[d.evidence_id for d in docs if values.get(d.document_id) == asserted],
                        con=[d.evidence_id for d in docs if values.get(d.document_id) != asserted])

    if ct == CheckType.CALCULATION:
        field = p.get("field")
        from_year, to_year, asserted = _to_int(p.get("from_year")), _to_int(p.get("to_year")), _to_float(p.get("asserted_change_pct"))
        if from_year is None or to_year is None or asserted is None:
            return _finding(claim, ClaimVerdict.NOT_CHECKED,
                            f"The claim's parameters are not usable for a calculation (years {p.get('from_year')!r}/{p.get('to_year')!r}, "
                            f"asserted change {p.get('asserted_change_pct')!r}); nothing was guessed.", ["unusable_claim_params"])
        recs = {}
        for e in _by_tool(avail, "financial_report_lookup"):
            year = _to_int(e.fields.get("year"))
            if year is not None:
                recs[year] = e
        a, b = recs.get(from_year), recs.get(to_year)
        if not a or not b:
            verdict = ClaimVerdict.NOT_CHECKED if "financial_report_lookup" not in tools_attempted else ClaimVerdict.INSUFFICIENT_EVIDENCE
            return _finding(claim, verdict, "Both years' filed figures are needed.", ["no_source"])
        key_a, key_b = _pick_field(a.fields, field), _pick_field(b.fields, field)
        va, vb = (_to_float(a.fields.get(key_a)) if key_a else None), (_to_float(b.fields.get(key_b)) if key_b else None)
        if va is None or vb is None or va == 0:
            return _finding(claim, ClaimVerdict.INSUFFICIENT_EVIDENCE,
                            f"No usable '{field}' figure in the filed reports for {from_year} and {to_year}; nothing was guessed.",
                            ["no_source", "field_not_found"], sup=[a.evidence_id, b.evidence_id])
        change = round((vb - va) / va * 100, 2)
        detail = f"({vb:,} - {va:,}) / {va:,} = {change}% (computed in code from {key_a}; claim says {asserted}%)"
        if abs(change - asserted) <= 0.5:
            return _finding(claim, ClaimVerdict.SUPPORTED, detail, ["calculation_matches"], sup=[a.evidence_id, b.evidence_id])
        return _finding(claim, ClaimVerdict.CONTRADICTED, detail, ["calculation_mismatch"], con=[a.evidence_id, b.evidence_id])

    return _finding(claim, ClaimVerdict.NOT_CHECKED, "Unsupported check type.", ["unsupported"])


def _to_int(value) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_field(fields: dict, name: Optional[str]) -> Optional[str]:
    """The record key a claim means: exact, then a key that starts with or contains the name (revenue -> revenue_eur)."""
    if not name:
        return None
    if name in fields:
        return name
    low = str(name).lower()
    for key in fields:
        if str(key).lower().startswith(low):
            return key
    for key in fields:
        if low in str(key).lower():
            return key
    return None


def verify_all(case: Case, claims: list[Claim], evidence: list[Evidence], tools_attempted: set[str]) -> list[Finding]:
    """One finding per claim. A check that cannot run on the claim as extracted (a model's parameters may be
    malformed) gives NOT_CHECKED with the reason; it never raises and it never gives SUPPORTED."""
    findings = []
    for c in claims:
        try:
            findings.append(verify_claim(case, c, evidence, tools_attempted))
        except Exception as exc:  # noqa: BLE001 - fail closed per claim, keep the case going
            findings.append(_finding(c, ClaimVerdict.NOT_CHECKED,
                                     f"The deterministic check could not run on this claim as extracted ({type(exc).__name__}: {exc}); "
                                     "nothing was guessed. Re-extraction or a human check is needed.", ["unusable_claim_params"]))
    return findings
