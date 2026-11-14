from __future__ import annotations

import hmac
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from jobos.config import get_settings
from jobos.db import session_scope
from jobos.db.models import Runner
from jobos.services.candidates import get_or_create_default_candidate
from jobos.services.runner_gateway import runner_by_token


def db() -> Iterator[Session]:
    with session_scope() as s:
        yield s


@dataclass
class AuthContext:
    """Single place that changes when Clerk arrives (ADR-0013)."""

    candidate_id: uuid.UUID
    actor: str = "owner"


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def owner(authorization: str | None = Header(default=None), s: Session = Depends(db)) -> AuthContext:
    token = _bearer(authorization)
    if not hmac.compare_digest(token, get_settings().api_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    cand = get_or_create_default_candidate(s)
    return AuthContext(candidate_id=cand.id)


def runner_auth(authorization: str | None = Header(default=None), s: Session = Depends(db)) -> Runner:
    r = runner_by_token(s, _bearer(authorization))
    if r is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid runner token")
    return r
