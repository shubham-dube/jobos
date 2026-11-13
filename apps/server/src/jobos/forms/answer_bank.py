"""Answer bank: ask once, remember forever (FR-ANS-*)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from jobos.db.models import Answer


def normalize_question(q: str) -> str:
    q = q.lower()
    q = re.sub(r"[*✱]", " ", q)
    q = re.sub(r"[^a-z0-9 ]+", " ", q)
    return " ".join(q.split())


@dataclass
class AnswerCandidate:
    id: str
    question: str
    value: Any
    options: list[str]
    similarity: int
    scope: str


def find_candidates(s: Session, candidate_id: uuid.UUID, question: str, *, company: str = "", job_id: str = "",
                    limit: int = 3, min_similarity: int = 70) -> list[AnswerCandidate]:
    qn = normalize_question(question)
    rows = s.scalars(select(Answer).where(
        Answer.candidate_id == candidate_id,
        or_(Answer.scope == "global",
            (Answer.scope == "company") & (Answer.scope_ref == company.lower()),
            (Answer.scope == "job") & (Answer.scope_ref == job_id)),
    )).all()
    scored = []
    for a in rows:
        sim = int(max(fuzz.token_set_ratio(qn, a.question_norm), fuzz.ratio(qn, a.question_norm)))
        if sim >= min_similarity:
            # job/company scoped answers win ties
            bonus = {"job": 2, "company": 1}.get(a.scope, 0)
            scored.append((sim + bonus, AnswerCandidate(str(a.id), a.question, a.value, a.options or [], sim, a.scope)))
    scored.sort(key=lambda t: -t[0])
    return [c for _, c in scored[:limit]]


def save_answer(s: Session, candidate_id: uuid.UUID, question: str, value: Any, *, field_type: str = "text",
                options: list[str] | None = None, scope: str = "global", scope_ref: str = "",
                source: str = "user") -> Answer:
    qn = normalize_question(question)
    existing = s.scalar(select(Answer).where(Answer.candidate_id == candidate_id, Answer.question_norm == qn,
                                             Answer.scope == scope, Answer.scope_ref == scope_ref))
    if existing:
        existing.value = value
        existing.options = options or existing.options
        existing.source = source
        existing.updated_at = datetime.now(UTC)
        return existing
    a = Answer(candidate_id=candidate_id, question=question.strip(), question_norm=qn, field_type=field_type,
               options=options or [], value=value, scope=scope, scope_ref=scope_ref, source=source)
    s.add(a)
    s.flush()
    return a


def mark_used(s: Session, answer_ids: list[str]) -> None:
    for aid in answer_ids:
        a = s.get(Answer, uuid.UUID(aid))
        if a:
            a.use_count += 1
            a.last_used_at = datetime.now(UTC)
