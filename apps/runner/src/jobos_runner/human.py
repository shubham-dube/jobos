"""Human-like interaction primitives: pauses, mouse movement, typing cadence.

We behave like one person using a normal browser; we never try to defeat bot detection beyond that.
"""

from __future__ import annotations

import asyncio
import random

from playwright.async_api import Locator, Page


class Human:
    def __init__(self, page: Page, slow: bool = True):
        self.page = page
        self.slow = slow

    async def pause(self, lo: float = 0.25, hi: float = 0.9) -> None:
        if self.slow:
            await asyncio.sleep(random.uniform(lo, hi))

    async def think(self) -> None:
        """Occasional longer pause, like reading a question."""
        if self.slow and random.random() < 0.15:
            await asyncio.sleep(random.uniform(1.0, 2.5))

    async def move_to(self, loc: Locator) -> None:
        try:
            await loc.scroll_into_view_if_needed(timeout=5000)
            box = await loc.bounding_box()
            if box and self.slow:
                x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                await self.page.mouse.move(x, y, steps=random.randint(8, 20))
        except Exception:
            pass

    async def click(self, loc: Locator) -> None:
        await self.move_to(loc)
        await self.pause(0.1, 0.35)
        await loc.click(timeout=10000)

    async def type_text(self, loc: Locator, text: str) -> None:
        """Clear and type. Long answers are partly typed then inserted, like a paste."""
        await self.click(loc)
        await loc.press("Control+A")
        await loc.press("Delete")
        if not self.slow:
            await loc.fill(text)
            return
        head, tail = (text, "") if len(text) <= 120 else (text[:30], text[30:])
        for ch in head:
            await self.page.keyboard.type(ch, delay=random.randint(25, 95))
            if ch in " ,." and random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.15, 0.5))
        if tail:
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await self.page.keyboard.insert_text(tail)
