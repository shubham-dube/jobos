"""Application state machine (docs/architecture/agents-and-workflows.md §4).

All transitions go through :func:`transition` so the event log stays complete.
"""

from __future__ import annotations

from enum import StrEnum


class AppState(StrEnum):
    queued = "queued"
    in_progress = "in_progress"
    needs_input = "needs_input"
    ready_for_review = "ready_for_review"
    submitting = "submitting"
    submitted = "submitted"
    uncertain = "uncertain"  # submit clicked but no confirmation seen: never auto-retried
    acknowledged = "acknowledged"  # confirmation email received
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    ghosted = "ghosted"
    skipped = "skipped"
    failed = "failed"
    expired = "expired"
    cancelled = "cancelled"


A = AppState

ALLOWED: dict[AppState, set[AppState]] = {
    A.queued: {A.in_progress, A.skipped, A.cancelled, A.failed},
    A.in_progress: {A.needs_input, A.ready_for_review, A.submitting, A.failed, A.skipped, A.cancelled, A.queued},
    A.needs_input: {A.in_progress, A.expired, A.cancelled, A.skipped},
    A.ready_for_review: {A.submitting, A.skipped, A.in_progress, A.cancelled, A.expired},
    A.submitting: {A.submitted, A.uncertain, A.failed},
    A.uncertain: {A.submitted, A.acknowledged, A.failed, A.queued},
    A.submitted: {A.acknowledged, A.interviewing, A.rejected, A.ghosted, A.offer},
    A.acknowledged: {A.interviewing, A.rejected, A.ghosted, A.offer},
    A.interviewing: {A.offer, A.rejected},
    A.offer: set(),
    A.rejected: {A.interviewing},
    A.ghosted: {A.interviewing, A.rejected, A.acknowledged},
    A.skipped: {A.queued},
    A.failed: {A.queued},
    A.expired: {A.queued},
    A.cancelled: {A.queued},
}

ACTIVE = {A.queued, A.in_progress, A.needs_input, A.ready_for_review, A.submitting}
APPLIED = {A.submitted, A.acknowledged, A.interviewing, A.offer, A.rejected, A.ghosted, A.uncertain}


class InvalidTransition(ValueError):
    pass


def check_transition(current: str, new: str) -> None:
    cur, nxt = AppState(current), AppState(new)
    if cur == nxt:
        return
    if nxt not in ALLOWED[cur]:
        raise InvalidTransition(f"{cur} -> {nxt} is not allowed")


class InterventionKind(StrEnum):
    missing_answer = "missing_answer"
    review_before_submit = "review_before_submit"
    login_required = "login_required"
    captcha = "captcha"
    unknown_page = "unknown_page"
    runner_offline = "runner_offline"
    blocked = "blocked"
