"""Runner protocol v1 (see docs/architecture/browser-execution.md §4).

The runner keeps an outbound HTTPS long-poll to the API:
  POST /runner/v1/hello                    -> RunnerHello
  POST /runner/v1/tasks/next?wait=25       -> RunnerTask | 204
  POST /runner/v1/tasks/{id}/result        -> TaskResult
Task payloads and results are typed per task type below.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .forms import FillPlan, FillResult, FormPage, SubmitResult


class TaskType(StrEnum):
    open_page = "open_page"  # navigate a browser session to a URL, return FormPage
    extract = "extract"  # re-extract the current page
    fill = "fill"  # fill a page from a FillPlan, return FillResult
    click = "click"  # click a FormButton (apply / next) and return the new page
    submit = "submit"  # final submit; requires a gate token
    observe = "observe"  # list interactive elements for the Navigator agent
    act = "act"  # perform one Navigator action
    check_session = "check_session"  # is the user logged in on a site?
    close_session = "close_session"
    fetch_text = "fetch_text"  # load a URL and return visible text (career pages, webmail)
    auth = "auth"  # get past a sign-in wall: Google SSO, sign in, or create an account


class ErrorKind(StrEnum):
    retryable = "retryable"
    session_lost = "session_lost"  # the browser tab for this session no longer exists
    login_required = "login_required"
    captcha = "captcha"
    blocked = "blocked"  # site blocked / unusual activity page
    not_found = "not_found"
    fatal = "fatal"


class Artifact(BaseModel):
    name: str
    content_type: str = "image/jpeg"
    data_b64: str  # small artifacts inline (screenshots, ≤ ~1MB)


class FileSpec(BaseModel):
    ref: str  # document id
    filename: str
    download_path: str  # API path the runner downloads from (authenticated)


class OpenPagePayload(BaseModel):
    url: str
    recipe: dict[str, Any] | None = None


class FillPayload(BaseModel):
    plan: FillPlan
    files: list[FileSpec] = Field(default_factory=list)


class ClickPayload(BaseModel):
    button_kind: str  # ButtonKind value
    label: str = ""
    locator: dict[str, Any] = Field(default_factory=dict)


class SubmitPayload(BaseModel):
    gate_token: str
    locator: dict[str, Any] = Field(default_factory=dict)


class InteractiveElement(BaseModel):
    index: int
    role: str
    name: str
    tag: str = ""
    href: str = ""


class Observation(BaseModel):
    url: str
    title: str
    elements: list[InteractiveElement]
    text_excerpt: str = ""  # UNTRUSTED


class NavAction(BaseModel):
    kind: str  # click | scroll | back | wait | done | fail
    index: int | None = None
    reason: str = ""


class ActPayload(BaseModel):
    action: NavAction
    allowed_hosts: list[str] = Field(default_factory=list)


class AuthPayload(BaseModel):
    method: str  # google | login | create
    email: str = ""
    # The password itself never travels in task payloads or workflow history: the runner fetches it with
    # GET /runner/v1/secrets/{account_ref} at the moment it types it.
    account_ref: str = ""
    google_account: str = ""  # which Google account to pick in the chooser (default: first)


class CheckSessionPayload(BaseModel):
    site: str
    url: str
    logged_in_markers: list[str] = Field(default_factory=list)
    logged_out_markers: list[str] = Field(default_factory=list)


class RunnerTask(BaseModel):
    id: str
    type: TaskType
    session_id: str  # browser session (tab) key, usually the application attempt id
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_s: int = 180


class TaskResult(BaseModel):
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    error_kind: ErrorKind | None = None
    artifacts: list[Artifact] = Field(default_factory=list)


class RunnerHello(BaseModel):
    runner_version: str
    protocol_version: int
    os: str
    browser: str = ""
    max_sessions: int = 1


# Typed views of TaskResult.data per task type ------------------------------------------------

class PageData(BaseModel):
    page: FormPage


class FillData(BaseModel):
    result: FillResult


class SubmitData(BaseModel):
    result: SubmitResult


class ObserveData(BaseModel):
    observation: Observation


class SessionData(BaseModel):
    logged_in: bool
    url: str = ""


class TextData(BaseModel):
    url: str
    title: str = ""
    text: str
