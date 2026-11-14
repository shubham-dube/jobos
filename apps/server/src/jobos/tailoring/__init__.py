"""Grounded tailoring: job-specific resume variants and cover letters (spec 0002, ADR-0008, ADR-0018)."""

from .model import CoverLetter, ResumeVariant, TailorResult
from .tailor import tailor_resume

__all__ = ["CoverLetter", "ResumeVariant", "TailorResult", "tailor_resume"]
