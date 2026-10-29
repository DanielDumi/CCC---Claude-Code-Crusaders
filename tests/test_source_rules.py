"""C1 · Source-permission facts and rules (gate spec §5-6): Romanian working days, consent validity,
application status at case time, and the SRC-* hits. Pure functions, no orchestrator."""
import datetime as dt

from backend.evidence.claim_verification import norm
from backend.security import source_rules as sr


def at(text):
    return dt.datetime.fromisoformat(text)


def test_working_days_signing_day_excluded_inclusive_day_5():
    assert sr.add_working_days(dt.date(2026, 11, 2), 5) == dt.date(2026, 11, 9)
    assert sr.working_days_elapsed(dt.date(2026, 11, 2), dt.date(2026, 11, 9)) == 5
    assert sr.working_days_elapsed(dt.date(2026, 11, 2), dt.date(2026, 11, 10)) == 6


def test_working_days_span_romanian_holidays():
    assert not sr.is_working_day(dt.date(2026, 11, 30))  # Sf. Andrei
    assert not sr.is_working_day(dt.date(2026, 12, 1))   # Ziua Națională
    assert sr.add_working_days(dt.date(2026, 11, 27), 5) == dt.date(2026, 12, 8)


CONSENT = {"consent_id": "cons_0192", "client_id": "cl_0412", "source": "ANAF", "purpose": "credit_application",
           "application_id": "app_0931", "signed_at": "2026-11-02", "status": "Given"}


def test_consent_valid_through_day_5_and_lapsed_on_day_6():
    assert sr.consent_status_at(CONSENT, at("2026-11-09T23:30:00+02:00"))[0] == "VALID"
    status, facts = sr.consent_status_at(CONSENT, at("2026-11-10T08:00:00+02:00"))
    assert status == "LAPSED" and facts["consent.valid_until"] == "2026-11-09" and facts["working_days_elapsed"] == 6
    status, facts = sr.consent_status_at(CONSENT, at("2026-11-12T09:00:00+02:00"))
    assert status == "LAPSED" and facts["working_days_elapsed"] == 8


def test_consent_across_holidays():
    consent = {**CONSENT, "signed_at": "2026-11-27"}
    assert sr.consent_status_at(consent, at("2026-12-08T10:00:00+02:00"))[0] == "VALID"
    assert sr.consent_status_at(consent, at("2026-12-09T10:00:00+02:00"))[0] == "LAPSED"


def test_withdrawn_consent_is_never_valid():
    assert sr.consent_status_at({**CONSENT, "status": "Withdrawn"}, at("2026-11-03T10:00:00+02:00"))[0] == "WITHDRAWN"


def test_no_window_before_the_dated_rule_is_active():
    old = {**CONSENT, "signed_at": "2026-08-03"}
    assert sr.consent_status_at(old, at("2026-09-01T10:00:00+02:00"))[0] == "VALID"


APP = {"application_id": "app_0931", "client_id": "cl_0412", "status": "withdrawn",
       "status_history": [{"status": "active", "at": "2026-11-02T10:15:00+02:00"},
                          {"status": "withdrawn", "at": "2026-11-12T15:00:00+02:00"}]}


def test_application_status_at_case_time():
    assert sr.application_status_at(APP, at("2026-11-12T09:00:00+02:00")) == "active"
    assert sr.application_status_at(APP, at("2026-11-12T15:00:00+02:00")) == "withdrawn"
    assert sr.application_status_at(APP, at("2026-11-01T09:00:00+02:00")) == "unknown"


def test_diacritics_never_cause_a_mismatch():
    assert norm("Ştefan Ţăranu") == norm("Ștefan Țăranu") == norm("stefan taranu")


POLICY = {"allowed_tools": {"anaf_income_query": {"requires_basis": {"kind": "consent", "source": "ANAF"}},
                            "consent_lookup": {}}}
ANAF = ("anaf_income_query", {"client_id": "cl_0412", "consent_id": "cons_0192"})
CONSENT_READ = ("consent_lookup", {"client_id": "cl_0412", "source": "ANAF"})


def scenario(case_time, consent=CONSENT, app=APP):
    return {"case_time": case_time, "records": {"client_id": "cl_0412", "application_id": "app_0931"},
            "tool_data": {"consent_lookup": {"cl_0412|ANAF": consent}, "application_status_lookup": {"app_0931": app}}}


def hits(tool, args, scen, fail_modes=None, purpose="credit_file_review_demo"):
    rec = sr.Records(scen, fail_modes)
    return sr.evaluate_call(tool, args, purpose, POLICY, rec, rec.case_time)


def test_lapsed_consent_denies_anaf_query_on_day_6_and_8_but_not_on_day_5():
    assert [h.rule_id for h in hits(*ANAF, scenario("2026-11-12T09:00:00+02:00"))] == ["SRC-ANAF-002"]
    assert [h.rule_id for h in hits(*ANAF, scenario("2026-11-10T09:00:00+02:00"))] == ["SRC-ANAF-002"]
    assert hits(*ANAF, scenario("2026-11-09T09:00:00+02:00")) == []


def test_absent_mismatched_withdrawn_consent_and_missing_basis():
    day2 = "2026-11-03T09:00:00+02:00"
    assert [h.rule_id for h in hits("anaf_income_query", {"client_id": "cl_0412", "consent_id": "cons_9999"},
                                    scenario(day2))] == ["SRC-ANAF-001"]
    assert [h.rule_id for h in hits(*ANAF, scenario(day2, consent={**CONSENT, "application_id": "app_0001"}))] == ["SRC-ANAF-003"]
    assert [h.rule_id for h in hits(*ANAF, scenario(day2, consent={**CONSENT, "status": "Withdrawn"}))] == ["SRC-ANAF-004"]
    assert [h.rule_id for h in hits("anaf_income_query", {"client_id": "cl_0412"}, scenario(day2))] == ["SRC-BASIS-001"]


def test_withdrawn_application_denies_every_call_except_deletion():
    scen = scenario("2026-11-13T09:00:00+02:00")
    assert [h.rule_id for h in hits(*CONSENT_READ, scen)] == ["SRC-STATUS-001"]
    assert all(h.outcome == "deny" for h in hits(*ANAF, scen)) and hits(*ANAF, scen)[0].rule_id == "SRC-STATUS-001"
    assert hits(*CONSENT_READ, scen, purpose="deletion") == []


def test_unavailable_register_holds_and_never_allows():
    held = hits(*ANAF, scenario("2026-11-03T09:00:00+02:00"), fail_modes={"consent_lookup": "timeout"})
    assert [(h.rule_id, h.outcome) for h in held] == [("SRC-HOLD-001", "hold")]
    held = hits(*CONSENT_READ, scenario("2026-11-03T09:00:00+02:00"), fail_modes={"application_status_lookup": "timeout"})
    assert [(h.rule_id, h.outcome) for h in held] == [("SRC-HOLD-001", "hold")]
