"""Persistent browser context and per-session tabs."""

from __future__ import annotations

import asyncio
import contextlib
import time

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from .config import RunnerConfig


class BrowserManager:
    """One persistent Chrome profile (logins survive restarts); one tab per session id."""

    def __init__(self, cfg: RunnerConfig):
        self.cfg = cfg
        self._pw: Playwright | None = None
        self._ctx: BrowserContext | None = None
        self._pages: dict[str, Page] = {}
        self._last_used: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._ctx:
            return
        self._pw = await async_playwright().start()
        profile = self.cfg.resolved_profile_dir()
        profile.mkdir(parents=True, exist_ok=True)
        kwargs: dict = dict(
            user_data_dir=str(profile),
            headless=self.cfg.headless,
            viewport=None if not self.cfg.headless else {"width": 1366, "height": 900},
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check"],
        )
        if self.cfg.executable_path:
            kwargs["executable_path"] = self.cfg.executable_path
        elif self.cfg.browser_channel:
            kwargs["channel"] = self.cfg.browser_channel
        self._ctx = await self._pw.chromium.launch_persistent_context(**kwargs)

    async def stop(self) -> None:
        if self._ctx:
            with contextlib.suppress(Exception):
                await self._ctx.close()
        if self._pw:
            await self._pw.stop()
        self._ctx = None
        self._pw = None
        self._pages.clear()

    @property
    def context(self) -> BrowserContext:
        assert self._ctx is not None, "browser not started"
        return self._ctx

    async def page_for(self, session_id: str, create: bool = True) -> Page | None:
        async with self._lock:
            page = self._pages.get(session_id)
            if page and page.is_closed():
                page = None
                self._pages.pop(session_id, None)
            if page is None and create:
                page = await self.context.new_page()
                self._pages[session_id] = page
            if page is not None:
                self._last_used[session_id] = time.monotonic()
            return page

    async def close_session(self, session_id: str) -> None:
        async with self._lock:
            page = self._pages.pop(session_id, None)
            self._last_used.pop(session_id, None)
        if page and not page.is_closed():
            with contextlib.suppress(Exception):
                await page.close()

    async def gc(self, idle_s: float = 1800) -> None:
        """Close tabs that have been idle for a long time (e.g. waiting days for a review)."""
        now = time.monotonic()
        for sid, ts in list(self._last_used.items()):
            if now - ts > idle_s:
                await self.close_session(sid)
