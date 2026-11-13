"""Candidate, profile and settings access."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobos.db.models import Candidate, Org, ProfileVersion
from jobos.domain.settings import CandidateSettings
from jobos_common.profile import MasterProfile


def get_or_create_default_candidate(s: Session, name: str = "Owner") -> Candidate:
    """Single-owner mode (ADR-0013): exactly one org + candidate unless more are created explicitly."""
    cand = s.scalar(select(Candidate).order_by(Candidate.created_at).limit(1))
    if cand:
        return cand
    org = Org(name="Personal")
    s.add(org)
    s.flush()
    cand = Candidate(org_id=org.id, name=name, settings=CandidateSettings().model_dump(mode="json"))
    s.add(cand)
    s.flush()
    return cand


def get_profile(s: Session, candidate_id: uuid.UUID) -> MasterProfile:
    cand = s.get(Candidate, candidate_id)
    if cand is None or cand.current_profile_version is None:
        return MasterProfile()
    pv = s.scalar(select(ProfileVersion).where(ProfileVersion.candidate_id == candidate_id,
                                               ProfileVersion.version == cand.current_profile_version))
    return MasterProfile.model_validate(pv.data) if pv else MasterProfile()


def save_profile(s: Session, candidate_id: uuid.UUID, profile: MasterProfile, source: str = "manual") -> int:
    current = s.scalar(select(func.max(ProfileVersion.version)).where(ProfileVersion.candidate_id == candidate_id)) or 0
    version = current + 1
    s.add(ProfileVersion(candidate_id=candidate_id, version=version, data=profile.model_dump(mode="json"),
                         source=source))
    cand = s.get(Candidate, candidate_id)
    assert cand is not None
    cand.current_profile_version = version
    if profile.basics.full_name:
        cand.name = profile.basics.full_name
    return version


def get_candidate_settings(s: Session, candidate_id: uuid.UUID) -> CandidateSettings:
    cand = s.get(Candidate, candidate_id)
    return CandidateSettings.model_validate(cand.settings or {}) if cand else CandidateSettings()


def save_candidate_settings(s: Session, candidate_id: uuid.UUID, settings: CandidateSettings) -> None:
    cand = s.get(Candidate, candidate_id)
    assert cand is not None
    cand.settings = settings.model_dump(mode="json")
