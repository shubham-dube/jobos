"""Form schema and fill plan models (see docs/architecture/form-filling-engine.md)."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FieldType(StrEnum):
    text = "text"
    textarea = "textarea"
    email = "email"
    phone = "phone"
    number = "number"
    date = "date"
    url = "url"
    select = "select"  # single choice dropdown (native or custom)
    radio = "radio"  # single choice, options visible
    checkbox = "checkbox"  # single boolean (consent, "I agree")
    multiselect = "multiselect"  # checkbox group / multi-select
    combobox = "combobox"  # free text with autocomplete suggestions (location, school)
    file = "file"
    unknown = "unknown"


CHOICE_TYPES = {FieldType.select, FieldType.radio, FieldType.multiselect}


class FormField(BaseModel):
    key: str  # unique within the page; produced by the runner
    label: str
    type: FieldType = FieldType.text
    required: bool = False
    options: list[str] = Field(default_factory=list)
    placeholder: str = ""
    description: str = ""  # help text near the field
    max_length: int | None = None
    accept: str = ""  # file input accept attribute
    section: str = ""
    current_value: str | list[str] | bool | None = None
    # Opaque data that only the runner understands (selectors, frame ids). Never shown to LLMs.
    locator: dict[str, Any] = Field(default_factory=dict)

    @property
    def signature(self) -> str:
        """Stable signature used by learned recipes (ADR-0014)."""
        norm = " ".join(self.label.lower().split())
        opts = "|".join(sorted(o.strip().lower() for o in self.options))
        raw = f"{norm}::{self.type}::{opts}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]


class ButtonKind(StrEnum):
    apply = "apply"  # opens the application form
    next = "next"
    submit = "submit"
    other = "other"


class FormButton(BaseModel):
    kind: ButtonKind
    label: str
    locator: dict[str, Any] = Field(default_factory=dict)


class PageKind(StrEnum):
    form = "form"
    job_description = "job_description"  # posting with an "Apply" button
    login = "login"
    confirmation = "confirmation"
    closed = "closed"  # job no longer accepting applications
    captcha = "captcha"
    other = "other"


class FormPage(BaseModel):
    url: str
    title: str = ""
    ats: str = "unknown"
    page_index: int = 0
    kind: PageKind = PageKind.other
    fields: list[FormField] = Field(default_factory=list)
    buttons: list[FormButton] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)  # visible validation errors
    text_excerpt: str = ""  # UNTRUSTED page text, for context only
    screenshot_ref: str | None = None

    def field(self, key: str) -> FormField | None:
        return next((f for f in self.fields if f.key == key), None)

    def button(self, kind: ButtonKind) -> FormButton | None:
        return next((b for b in self.buttons if b.kind == kind), None)


class ValueSource(StrEnum):
    profile = "profile"
    preset = "preset"
    answer_bank = "answer_bank"
    recipe = "recipe"
    generated = "generated"  # composed by an LLM from cited facts
    user = "user"  # answered by the user for this application
    document = "document"  # file upload


class FillValue(BaseModel):
    key: str
    value: str | list[str] | bool | None = None
    source: ValueSource
    source_ref: str = ""  # e.g. "basics.email", "answer:42", fact ids "w1h2,p3"
    confidence: float = 1.0
    file_ref: str | None = None  # document id for file fields
    note: str = ""

    @property
    def generated(self) -> bool:
        return self.source == ValueSource.generated


class Unresolved(BaseModel):
    key: str
    label: str
    type: FieldType
    options: list[str] = Field(default_factory=list)
    required: bool = True
    reason: str = ""
    suggestion: str | list[str] | bool | None = None  # best guess shown to the user


class FillPlan(BaseModel):
    page_index: int = 0
    values: list[FillValue] = Field(default_factory=list)
    unresolved: list[Unresolved] = Field(default_factory=list)

    def get(self, key: str) -> FillValue | None:
        return next((v for v in self.values if v.key == key), None)


class FieldResult(BaseModel):
    key: str
    ok: bool
    actual: str | list[str] | bool | None = None
    error: str = ""


class FillResult(BaseModel):
    results: list[FieldResult] = Field(default_factory=list)
    page: FormPage | None = None  # page re-extracted after filling (values read back)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results) and not (self.page and self.page.errors)


class SubmitResult(BaseModel):
    submitted: bool
    confirmed: bool = False
    confirmation_text: str = ""
    final_url: str = ""
    page: FormPage | None = None
