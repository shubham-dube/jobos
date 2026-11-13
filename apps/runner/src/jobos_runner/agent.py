"""Runner main loop: long-poll tasks from the API, execute them in the browser, report results."""

from __future__ import annotations

import asyncio
import contextlib
import platform
import traceback
from pathlib import Path

import httpx

from jobos_common import PROTOCOL_VERSION
from jobos_common.forms import FillPlan
from jobos_common.runner import (
    ActPayload,
    CheckSessionPayload,
    ClickPayload,
    ErrorKind,
    FillPayload,
    OpenPagePayload,
    RunnerHello,
    RunnerTask,
    TaskResult,
    TaskType,
)

from . import __version__
from .browser import BrowserManager
from .config import RunnerConfig
from .human import Human
from .page_ops import PageOps


class RunnerAgent:
    def __init__(self, cfg: RunnerConfig, log=print):
        self.cfg = cfg
        self.log = log
        self.browser = BrowserManager(cfg)
        self.http = httpx.AsyncClient(base_url=cfg.api_url.rstrip("/"), timeout=httpx.Timeout(70.0, connect=15.0),
                                      headers={"Authorization": f"Bearer {cfg.token}"})
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._slots = asyncio.Semaphore(max(1, cfg.max_sessions))
        self._stop = asyncio.Event()
        self.files_dir = cfg.resolved_downloads_dir()
        self.files_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ lifecycle
    async def run(self) -> None:
        await self.browser.start()
        r = await self.http.post("/runner/v1/hello", json=RunnerHello(
            runner_version=__version__, protocol_version=PROTOCOL_VERSION, os=f"{platform.system()} {platform.release()}",
            browser=self.cfg.browser_channel or "chromium", max_sessions=self.cfg.max_sessions).model_dump())
        r.raise_for_status()
        self.log(f"connected to {self.cfg.api_url} as {r.json().get('name')}")
        running: set[asyncio.Task] = set()
        backoff = 1.0
        gc_at = 0
        while not self._stop.is_set():
            await self._slots.acquire()
            try:
                resp = await self.http.post("/runner/v1/tasks/next", params={"wait": 25})
            except httpx.HTTPError as exc:
                self._slots.release()
                self.log(f"poll failed: {exc}; retrying in {backoff:.0f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            backoff = 1.0
            if resp.status_code == 204:
                self._slots.release()
                gc_at += 1
                if gc_at % 20 == 0:
                    await self.browser.gc()
                continue
            if resp.status_code >= 400:
                self._slots.release()
                self.log(f"server error {resp.status_code}: {resp.text[:200]}")
                await asyncio.sleep(5)
                continue
            task = RunnerTask.model_validate(resp.json())
            t = asyncio.create_task(self._run_task(task))
            running.add(t)
            t.add_done_callback(running.discard)
        for t in running:
            t.cancel()
        await self.browser.stop()
        await self.http.aclose()

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------ execution
    async def _run_task(self, task: RunnerTask) -> None:
        lock = self._session_locks.setdefault(task.session_id, asyncio.Lock())
        try:
            async with lock:
                self.log(f"→ {task.type} [{task.session_id[-12:]}]")
                try:
                    result = await asyncio.wait_for(self.execute(task), timeout=task.timeout_s)
                except TimeoutError:
                    result = TaskResult(ok=False, error="task timed out", error_kind=ErrorKind.retryable)
                except Exception as exc:  # never crash the loop
                    result = TaskResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:800],
                                        error_kind=ErrorKind.retryable, data={"trace": traceback.format_exc()[-1500:]})
                self.log(f"← {task.type} ok={result.ok} {result.error[:120]}")
            for attempt in range(5):
                try:
                    r = await self.http.post(f"/runner/v1/tasks/{task.id}/result", json=result.model_dump(mode="json"))
                    if r.status_code < 500:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(2 ** attempt)
            if task.type == TaskType.close_session:
                self._session_locks.pop(task.session_id, None)
        finally:
            self._slots.release()

    async def execute(self, task: RunnerTask) -> TaskResult:
        if task.type == TaskType.close_session:
            await self.browser.close_session(task.session_id)
            return TaskResult(ok=True)
        create = task.type in (TaskType.open_page, TaskType.check_session, TaskType.fetch_text)
        page = await self.browser.page_for(task.session_id, create=create)
        if page is None:
            return TaskResult(ok=False, error="browser tab for this session is gone", error_kind=ErrorKind.session_lost)
        ops = PageOps(page, Human(page, slow=self.cfg.slow_typing), self.files_dir)
        p = task.payload

        if task.type == TaskType.open_page:
            body = OpenPagePayload.model_validate(p)
            status = None
            for attempt in range(3):  # transient network errors (proxy/tunnel resets, DNS hiccups)
                try:
                    resp = await page.goto(body.url, wait_until="domcontentloaded", timeout=60000)
                    status = resp.status if resp else None
                    break
                except Exception as exc:
                    if attempt == 2 or "net::ERR" not in str(exc):
                        return TaskResult(ok=False, error=str(exc)[:500], error_kind=ErrorKind.retryable)
                    await asyncio.sleep(3 * (attempt + 1))
            if "error=true" in page.url and "greenhouse.io" in page.url:
                return TaskResult(ok=False, error="job closed (board redirected with error)", error_kind=ErrorKind.not_found)
            if status == 404:
                return TaskResult(ok=False, error="page not found (HTTP 404)", error_kind=ErrorKind.not_found,
                                  artifacts=[await ops.screenshot("404")])
            await ops.settle()
            await ops.dismiss_banners()
            fp = await ops.extract()
            return TaskResult(ok=True, data={"page": fp.model_dump(mode="json")},
                              artifacts=[await ops.screenshot("open")])
        if task.type == TaskType.extract:
            fp = await ops.extract()
            return TaskResult(ok=True, data={"page": fp.model_dump(mode="json")})
        if task.type == TaskType.fill:
            body = FillPayload.model_validate(p)
            files = await self._download_files(body)
            result = await ops.fill(FillPlan.model_validate(body.plan), files)
            return TaskResult(ok=True, data={"result": result.model_dump(mode="json")},
                              artifacts=[await ops.screenshot("filled")])
        if task.type == TaskType.click:
            body = ClickPayload.model_validate(p)
            fp = await ops.click_button(body.button_kind)
            return TaskResult(ok=True, data={"page": fp.model_dump(mode="json")})
        if task.type == TaskType.submit:
            if not p.get("gate_token"):
                return TaskResult(ok=False, error="refusing to submit without a gate token", error_kind=ErrorKind.fatal)
            result = await ops.submit()
            return TaskResult(ok=True, data={"result": result.model_dump(mode="json")},
                              artifacts=[await ops.screenshot("submitted")])
        if task.type == TaskType.observe:
            obs = await ops.observe()
            return TaskResult(ok=True, data={"observation": obs.model_dump(mode="json")})
        if task.type == TaskType.act:
            body = ActPayload.model_validate(p)
            await ops.act(body.action, body.allowed_hosts)
            fp = await ops.extract()
            return TaskResult(ok=True, data={"page": fp.model_dump(mode="json")})
        if task.type == TaskType.auth:
            from jobos_common.runner import AuthPayload

            from .page_ops import auth_flow

            body = AuthPayload.model_validate(p)
            password = ""
            if body.account_ref:  # fetch the secret only now, never persisted on the runner
                r = await self.http.get(f"/runner/v1/secrets/{body.account_ref}")
                r.raise_for_status()
                password = r.json()["password"]
            out = await auth_flow(ops, body.method, body.email, password, body.google_account)
            return TaskResult(ok=True, data={"page": out["page"].model_dump(mode="json"),
                                             "verify_email": out["verify_email"]},
                              artifacts=[await ops.screenshot("auth")])
        if task.type == TaskType.check_session:
            body = CheckSessionPayload.model_validate(p)
            await page.goto(body.url, wait_until="domcontentloaded", timeout=45000)
            await ops.settle(5000)
            text = (await page.content()).lower()
            logged_in = any(m.lower() in text for m in body.logged_in_markers) and not any(
                m.lower() in text for m in body.logged_out_markers)
            return TaskResult(ok=True, data={"logged_in": logged_in, "url": page.url})
        if task.type == TaskType.fetch_text:
            await page.goto(p["url"], wait_until="domcontentloaded", timeout=45000)
            await ops.settle(5000)
            text = await page.evaluate("() => document.body ? document.body.innerText : ''")
            return TaskResult(ok=True, data={"url": page.url, "title": await page.title(), "text": text[:100000]})
        return TaskResult(ok=False, error=f"unsupported task {task.type}", error_kind=ErrorKind.fatal)

    async def _download_files(self, body: FillPayload) -> dict[str, Path]:
        out: dict[str, Path] = {}
        for f in body.files:
            dest = self.files_dir / f.ref / f.filename
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                r = await self.http.get(f.download_path)
                r.raise_for_status()
                dest.write_bytes(r.content)
            out[f.ref] = dest
        return out


def run_forever(cfg: RunnerConfig) -> None:
    agent = RunnerAgent(cfg)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(agent.run())

