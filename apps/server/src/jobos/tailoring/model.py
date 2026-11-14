"""Data model for tailored documents. Everything the LLM writes cites source ids (ADR-0008)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Bullet(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=list)


class VariantItem(BaseModel):
    id: str  # profile work/project id
    bullets: list[Bullet] = Field(default_factory=list)


class ResumeVariant(BaseModel):
    """What goes on the page besides header/education, which always come straight from the profile."""

    summary: Bullet | None = None
    experience: list[VariantItem] = Field(default_factory=list)
    projects: list[VariantItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)  # canonical profile skill names, in display order
    awards: list[str] = Field(default_factory=list)  # award ids


class DiffLine(BaseModel):
    section: str  # summary | experience | projects
    item_id: str
    item_name: str
    sources: list[str]
    source_text: str
    final_text: str
    status: Literal["verbatim", "reworded", "kept_original"]
    reason: str = ""  # why a rewording was rejected


class GroundingReport(BaseModel):
    reworded: int = 0
    verbatim: int = 0
    rejected: int = 0
    dropped_items: list[str] = Field(default_factory=list)  # "Project X" (not shown on the page)
    dropped_skills: int = 0  # LLM-listed skills not in the profile (ignored)
    notes: list[str] = Field(default_factory=list)


class TailorResult(BaseModel):
    variant: ResumeVariant
    diff: list[DiffLine]
    grounding: GroundingReport
    keywords: list[str] = Field(default_factory=list)  # posting terms the variant covers
    used_llm: bool = True


class Sentence(BaseModel):
    text: str
    kind: Literal["claim", "context"] = "claim"  # claim = about the candidate (needs sources)
    sources: list[str] = Field(default_factory=list)


class CoverLetter(BaseModel):
    greeting: str = "Dear Hiring Team,"
    paragraphs: list[list[Sentence]] = Field(default_factory=list)
    closing: str = "Sincerely,"
