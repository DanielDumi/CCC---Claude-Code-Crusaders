"""Case state machine (spec/build-spec/03_PIPELINE.md, 'State machine (source of truth')."""
from __future__ import annotations

from backend.domain.models import CaseState as S

TERMINAL = {S.CLOSED_VERIFIED, S.CLOSED_WITH_ISSUES, S.CLOSED_UNRESOLVED, S.CLOSED_BLOCKED}
CLOSED = TERMINAL

TRANSITIONS: dict[S, set[S]] = {
    S.RECEIVED: {S.ASSESSED},
    S.ASSESSED: {S.PLAN_DRAFTED},
    S.PLAN_DRAFTED: {S.PREFLIGHT_BLOCKED, S.LEGAL_REVIEW_REQUIRED, S.AWAITING_PLAN_APPROVAL},
    S.PREFLIGHT_BLOCKED: {S.PLAN_DRAFTED, S.CLOSED_BLOCKED},
    S.LEGAL_REVIEW_REQUIRED: {S.PLAN_DRAFTED, S.CLOSED_UNRESOLVED},
    S.AWAITING_PLAN_APPROVAL: {S.PLAN_DRAFTED, S.APPROVED},
    S.APPROVED: {S.EXECUTING, S.CLOSED_BLOCKED},
    S.EXECUTING: {S.FINDINGS_READY, S.REPLAN_REQUIRED, S.CLOSED_BLOCKED},
    S.FINDINGS_READY: {S.REPLAN_REQUIRED, S.AWAITING_FINAL_REVIEW},
    S.REPLAN_REQUIRED: {S.PLAN_DRAFTED},
    S.AWAITING_FINAL_REVIEW: {S.REPLAN_REQUIRED} | CLOSED,
}


class InvalidTransition(Exception):
    pass


def check_transition(current: S, new: S) -> None:
    if current in TERMINAL:
        raise InvalidTransition(f"case is closed ({current.value})")
    if new not in TRANSITIONS.get(current, set()):
        raise InvalidTransition(f"{current.value} -> {new.value} is not allowed")
