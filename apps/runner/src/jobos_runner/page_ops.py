"""Page operations: extract a FormPage, fill a FillPlan, click buttons, submit, navigate.

All DOM knowledge lives here and in js/extract.js. The server never sends selectors it invented;
it only refers to field keys produced by our own extraction (prompt-injection resistant).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import difflib
import re
from importlib import resources
from pathlib import Path
from typing import Any

from playwright.async_api import Frame, Locator, Page

from jobos_common.forms import (
    ButtonKind,
    FieldResult,
    FieldType,
    FillPlan,
    FillResult,
    FillValue,
    FormButton,
    FormField,
    FormPage,
    PageKind,
    SubmitResult,
)
from jobos_common.runner import Artifact, InteractiveElement, NavAction, Observation

from .human import Human

EXTRACT_JS = resources.files("jobos_runner").joinpath("js/extract.js").read_text()

ATS_PATTERNS: list[tuple[str, str]] = [
    (r"greenhouse\.io", "greenhouse"),
    (r"jobs\.lever\.co", "lever"),
    (r"ashbyhq\.com", "ashby"),
    (r"myworkdayjobs\.com|workday\.com", "workday"),
    (r"smartrecruiters\.com", "smartrecruiters"),
    (r"icims\.com", "icims"),
    (r"workable\.com", "workable"),
    (r"docs\.google\.com/forms", "google_forms"),
    (r"forms\.office\.com|forms\.microsoft\.com", "microsoft_forms"),
    (r"linkedin\.com", "linkedin"),
    (r"naukri\.com", "naukri"),
]


LOCATION_LABEL = re.compile(r"\b(location|city|town|where are you (based|located))\b", re.I)


def detect_ats(url: str) -> str:
    for pat, name in ATS_PATTERNS:
        if re.search(pat, url, re.I):
            return name
    return "unknown"


def norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", s.lower()).split())


def best_option(value: str, options: list[str]) -> str | None:
    if not options:
        return None
    v = norm(value)
    for o in options:
        if norm(o) == v:
            return o
    for o in options:
        no = norm(o)
        if v and (no.startswith(v) or v.startswith(no)) and min(len(v), len(no)) >= 2:
            return o
    for o in options:
        if v and v in norm(o):
            return o
    scored = sorted(((difflib.SequenceMatcher(None, v, norm(o)).ratio(), o) for o in options), reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 0.6 else None


class PageOps:
    def __init__(self, page: Page, human: Human, files_dir: Path):
        self.page = page
        self.human = human
        self.files_dir = files_dir
        self.suggested: set[str] = set()  # keys whose value was replaced by a site suggestion

    # ------------------------------------------------------------------ helpers
    def _frames(self) -> list[Frame]:
        return [self.page.main_frame] + [f for f in self.page.frames if f != self.page.main_frame]

    def _frame_for_key(self, key: str) -> Frame:
        m = re.match(r"^f(\d+)\|", key)
        if m:
            idx = int(m.group(1))
            frames = self._frames()
            if idx < len(frames):
                return frames[idx]
        return self.page.main_frame

    def _loc(self, key: str) -> Locator:
        return self._frame_for_key(key).locator(f'[data-jobos-key="{key}"]')

    async def screenshot(self, name: str = "page") -> Artifact:
        data = await self.page.screenshot(type="jpeg", quality=60, full_page=True)
        if len(data) > 1_500_000:
            data = await self.page.screenshot(type="jpeg", quality=45, full_page=False)
        return Artifact(name=name, content_type="image/jpeg", data_b64=base64.b64encode(data).decode())

    async def settle(self, timeout_ms: int = 8000) -> None:
        with contextlib.suppress(Exception):
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        with contextlib.suppress(Exception):
            await self.page.wait_for_load_state("networkidle", timeout=timeout_ms)

    async def dismiss_banners(self) -> None:
        """Close cookie/consent banners that block clicks (accepting only necessary where offered)."""
        for pattern in [r"^(reject all|reject|decline|deny|only necessary|necessary only)$",
                        r"^(accept( all)?( cookies)?|i agree|agree|got it|allow all|ok)$"]:
            btns = self.page.get_by_role("button", name=re.compile(pattern, re.I))
            with contextlib.suppress(Exception):
                if await btns.count() and await btns.first.is_visible():
                    container_text = await btns.first.evaluate(
                        "el => (el.closest('[class*=cookie],[id*=cookie],[class*=consent],[id*=consent],[class*=cc-]') || {}).innerText || ''")
                    if container_text:
                        await btns.first.click(timeout=3000)
                        await asyncio.sleep(0.4)
                        return

    # ------------------------------------------------------------------ extraction
    async def extract(self, page_index: int = 0, harvest: bool = True) -> FormPage:
        merged: dict[str, Any] = {"fields": [], "buttons": [], "errors": [], "kind": "other", "text_excerpt": ""}
        main: dict[str, Any] | None = None
        for i, frame in enumerate(self._frames()):
            if i > 0 and (frame.is_detached() or not frame.url or frame.url == "about:blank"):
                continue
            try:
                data = await frame.evaluate(EXTRACT_JS, {"framePrefix": f"f{i}|" if i else "", "maxText": 4000})
            except Exception:
                continue
            if i == 0:
                main = data
            # include a frame only if it has a form (e.g. embedded Greenhouse iframe)
            if i == 0 or len(data["fields"]) >= 2:
                merged["fields"] += data["fields"]
                merged["buttons"] += [b for b in data["buttons"]
                                      if b["kind"] not in {x["kind"] for x in merged["buttons"]}]
                merged["errors"] += data["errors"]
                if data["kind"] != "other" and (merged["kind"] in ("other", "job_description") or i > 0):
                    merged["kind"] = data["kind"]
        if main:
            merged["text_excerpt"] = main["text_excerpt"]
            if merged["kind"] == "other":
                merged["kind"] = main["kind"]
        fields = [FormField.model_validate(f) for f in merged["fields"]]
        if harvest:
            await self._harvest_combobox_options(fields)
        return FormPage(
            url=self.page.url, title=await self.page.title(), ats=detect_ats(self.page.url), page_index=page_index,
            kind=PageKind(merged["kind"]), fields=fields,
            buttons=[FormButton.model_validate(b) for b in merged["buttons"]], errors=merged["errors"][:20],
            text_excerpt=merged["text_excerpt"],
        )

    async def _read_open_options(self, loc: Locator) -> list[str]:
        return await loc.evaluate("""el => {
            const vis = (n) => { const r = n.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
            let scope = null;
            const ctl = el.getAttribute('aria-controls') || el.getAttribute('aria-owns');
            if (ctl) scope = document.getElementById(ctl);
            const sel = "[role=option], [class*='select__option'], [class*='option--'], .dropdown-results > div, " +
                        ".dropdown-location, .pac-item, [class*='suggestion'] li, [class*='autocomplete'] li, ul[role=listbox] li";
            const nodes = Array.from((scope || document).querySelectorAll(sel));
            const out = [];
            for (const n of nodes) { if (!vis(n)) continue; const t = (n.innerText || '').replace(/\\s+/g,' ').trim(); if (t && !out.includes(t) && !/^no (options|results)/i.test(t)) out.push(t); }
            return out.slice(0, 300);
        }""")

    async def _harvest_combobox_options(self, fields: list[FormField]) -> None:
        for f in fields:
            if f.type != FieldType.combobox or f.options:
                continue
            loc = self._loc(f.key).first
            try:
                await self.human.move_to(loc)
                await loc.click(timeout=5000)
                await asyncio.sleep(0.5)
                opts = await self._read_open_options(loc)
                await loc.press("Escape")
            except Exception:
                opts = []
            if opts:
                f.options = opts
                f.type = FieldType.select
                f.locator["widget"] = "combobox"
            else:
                f.locator["widget"] = "autocomplete"

    # ------------------------------------------------------------------ filling
    async def fill(self, plan: FillPlan, files: dict[str, Path]) -> FillResult:
        page = await self.extract(plan.page_index, harvest=False)  # re-tag elements
        by_key = {f.key: f for f in page.fields}
        results: list[FieldResult] = []
        for fv in plan.values:
            field = by_key.get(fv.key)
            if field is None:
                results.append(FieldResult(key=fv.key, ok=False, error="field not found on page"))
                continue
            try:
                await self.human.think()
                await self._fill_one(field, fv, files)
                results.append(FieldResult(key=fv.key, ok=True))
            except Exception as exc:
                results.append(FieldResult(key=fv.key, ok=False, error=str(exc)[:300]))
            await self.human.pause()
        after = await self.extract(plan.page_index, harvest=False)
        after_by_key = {f.key: f for f in after.fields}
        for r in results:
            f = after_by_key.get(r.key)
            fv = plan.get(r.key)
            if f is None or fv is None:
                continue
            r.actual = f.current_value
            if r.key in self.suggested:
                r.ok = r.ok and bool(f.current_value)
                continue
            if r.ok and not _value_matches(f, fv):
                r.ok = False
                r.error = r.error or f"read back {f.current_value!r}"
        return FillResult(results=results, page=after)

    async def _fill_one(self, field: FormField, fv: FillValue, files: dict[str, Path]) -> None:
        loc = self._loc(field.key)
        value = fv.value
        widget = field.locator.get("widget", "")
        if field.type == FieldType.file:
            path = files.get(fv.file_ref or "")
            if not path:
                raise ValueError("file not available on runner")
            await loc.first.set_input_files(str(path))
            await asyncio.sleep(1.0)
            return
        if field.type in (FieldType.radio, FieldType.multiselect) and field.locator.get("kind") in ("group", "aria-radiogroup"):
            wanted = value if isinstance(value, list) else [value]
            for w in wanted:
                await self._choose_in_group(field, str(w))
            return
        if field.type == FieldType.checkbox:
            await self._set_checkbox(loc.first, bool(value) if not isinstance(value, str) else value.lower() in ("yes", "true", "1"))
            return
        if widget == "native-select":
            opts = await loc.first.evaluate("el => Array.from(el.options).map(o => o.text.trim())")
            target = best_option(str(value[0] if isinstance(value, list) else value), opts)
            if target is None:
                raise ValueError(f"option {value!r} not found")
            await self.human.move_to(loc.first)
            await loc.first.select_option(label=target)
            return
        if widget in ("combobox", "autocomplete") or field.type == FieldType.combobox:
            values = value if isinstance(value, list) else [value]
            for v in values:
                await self._choose_combobox(loc.first, str(v), field.options)
            return
        if field.type == FieldType.date and await loc.first.get_attribute("type") == "date":
            await loc.first.fill(str(value))
            return
        await self.human.type_text(loc.first, "" if value is None else str(value))
        if LOCATION_LABEL.search(field.label) and value:
            await self._maybe_pick_suggestion(loc.first, str(value))

    async def _maybe_pick_suggestion(self, loc: Locator, value: str) -> None:
        """Text inputs with a suggestion dropdown (e.g. Lever location): pick the closest suggestion."""
        options: list[str] = []
        for _ in range(6):
            await asyncio.sleep(0.4)
            options = await self._read_open_options(loc)
            if options:
                break
        if not options:
            return
        choice = best_option(value, options) or best_option(value.split(",")[0], options) or options[0]
        target = self.page.get_by_role("option", name=choice, exact=True)
        if await target.count() == 0:
            target = self.page.locator(".dropdown-results > div, .dropdown-location, .pac-item, ul[role=listbox] li").filter(
                has_text=choice)
        if await target.count():
            await self.human.click(target.first)
            self.suggested.add(await loc.get_attribute("data-jobos-key") or "")
            await asyncio.sleep(0.3)

    async def _choose_in_group(self, field: FormField, wanted: str) -> None:
        loc = self._loc(field.key)
        if field.locator.get("kind") == "aria-radiogroup":
            radios = loc.first.locator("[role=radio]")
            labels = [(await radios.nth(i).inner_text()).strip() for i in range(await radios.count())]
            target = best_option(wanted, labels)
            if target is None:
                raise ValueError(f"option {wanted!r} not found")
            await self.human.click(radios.nth(labels.index(target)))
            return
        count = await loc.count()
        labels = []
        for i in range(count):
            labels.append(await loc.nth(i).evaluate(
                "el => ((el.labels && el.labels[0]) ? el.labels[0].innerText : (el.closest('label') || el.parentElement || {}).innerText || el.value || '').trim()"))
        target = best_option(wanted, labels)
        if target is None:
            raise ValueError(f"option {wanted!r} not found among {labels[:8]}")
        el = loc.nth(labels.index(target))
        await self._set_checkbox(el, True)

    async def _set_checkbox(self, el: Locator, desired: bool) -> None:
        if await el.is_checked() == desired:
            return
        await self.human.move_to(el)
        try:
            await el.set_checked(desired, timeout=3000)
        except Exception:
            await el.evaluate("el => ((el.labels && el.labels[0]) || el.closest('label') || el.parentElement || el).click()")
        if await el.is_checked() != desired:
            await el.evaluate("(el, d) => { el.checked = d; el.dispatchEvent(new Event('change', {bubbles:true})); el.dispatchEvent(new Event('click', {bubbles:true})); }", desired)

    async def _choose_combobox(self, loc: Locator, value: str, known: list[str]) -> None:
        target = best_option(value, known) if known else None
        query = target or value
        await self.human.click(loc)
        await asyncio.sleep(0.3)
        # type a prefix: enough to filter, like a person would
        typed = query if len(query) <= 24 else query[:24]
        for ch in typed:
            await self.human.page.keyboard.type(ch, delay=40 if self.human.slow else 0)
        options: list[str] = []
        for _ in range(12):  # wait for (async) suggestions
            await asyncio.sleep(0.35)
            options = await self._read_open_options(loc)
            if options:
                break
        choice = best_option(query, options) if options else None
        if choice is None and options and not known:
            choice = options[0]  # autocomplete: first suggestion for our query
        if choice is None:
            await loc.press("Escape")
            if not known and not options:
                return  # autocomplete offered nothing (e.g. location service down): keep the typed text
            raise ValueError(f"no matching option for {value!r} (saw {options[:5]})")
        opt = self.page.get_by_role("option", name=choice, exact=True)
        if await opt.count() == 0:
            opt = self.page.locator("[class*='select__option'], [class*='option--']").filter(has_text=choice)
        await self.human.click(opt.first)
        await asyncio.sleep(0.3)

    # ------------------------------------------------------------------ buttons
    async def click_button(self, kind: str) -> FormPage:
        page = await self.extract(harvest=False)
        btn = page.button(ButtonKind(kind))
        if btn is None:
            raise LookupError(f"no '{kind}' button on page")
        key = btn.locator["button"]
        frame = self._frame_for_key(key)
        await self.human.click(frame.locator(f'[data-jobos-button="{key}"]').first)
        await self.settle()
        await asyncio.sleep(1.0)
        return await self.extract(page.page_index + (1 if kind == "next" else 0))

    async def submit(self) -> SubmitResult:
        before_url = self.page.url
        page = await self.extract(harvest=False)
        btn = page.button(ButtonKind.submit)
        if btn is None:
            return SubmitResult(submitted=False, page=page, final_url=self.page.url)
        key = btn.locator["button"]
        await self.human.pause(0.6, 1.5)
        await self.human.click(self._frame_for_key(key).locator(f'[data-jobos-button="{key}"]').first)
        after: FormPage | None = None
        for _ in range(20):  # up to ~20s for confirmation
            await asyncio.sleep(1.0)
            with contextlib.suppress(Exception):
                after = await self.extract(page.page_index, harvest=False)
                if after.kind in (PageKind.confirmation, PageKind.captcha):
                    break
                if after.errors and after.kind == PageKind.form:
                    break
        if after is None:
            after = await self.extract(page.page_index, harvest=False)
        confirmed = after.kind == PageKind.confirmation or bool(
            re.search(r"(thank|confirm|success|submitted)", self.page.url, re.I) and self.page.url != before_url)
        submitted = confirmed or (after.kind != PageKind.form and not after.errors)
        return SubmitResult(submitted=submitted, confirmed=confirmed,
                            confirmation_text=after.text_excerpt[:500] if confirmed else "",
                            final_url=self.page.url, page=after)

    # ------------------------------------------------------------------ navigator
    async def observe(self) -> Observation:
        elements = await self.page.evaluate("""() => {
            const vis = (n) => { const r = n.getBoundingClientRect(); const s = getComputedStyle(n);
              return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
            const els = Array.from(document.querySelectorAll("a[href], button, [role=button], [role=link], input[type=submit]")).filter(vis);
            return els.slice(0, 150).map((el, i) => { el.setAttribute('data-jobos-nav', String(i));
              return { index: i, role: el.getAttribute('role') || el.tagName.toLowerCase(),
                name: ((el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim()).slice(0, 80),
                tag: el.tagName.toLowerCase(), href: el.href || '' }; });
        }""")
        text = await self.page.evaluate("() => (document.body ? document.body.innerText : '').slice(0, 3000)")
        return Observation(url=self.page.url, title=await self.page.title(),
                           elements=[InteractiveElement.model_validate(e) for e in elements], text_excerpt=text)

    async def act(self, action: NavAction, allowed_hosts: list[str]) -> None:
        if action.kind == "click" and action.index is not None:
            el = self.page.locator(f'[data-jobos-nav="{action.index}"]').first
            href = await el.get_attribute("href") or ""
            if href.startswith("http") and allowed_hosts:
                from urllib.parse import urlparse

                host = urlparse(href).hostname or ""
                if not any(host == h or host.endswith("." + h) for h in allowed_hosts):
                    raise PermissionError(f"navigation to {host} not allowed")
            await self.human.click(el)
            await self.settle()
        elif action.kind == "scroll":
            await self.page.mouse.wheel(0, 700)
            await asyncio.sleep(0.6)
        elif action.kind == "back":
            await self.page.go_back()
            await self.settle()
        elif action.kind == "wait":
            await asyncio.sleep(2)


def _value_matches(field: FormField, fv: FillValue) -> bool:
    want, got = fv.value, field.current_value
    if field.type == FieldType.file:
        return bool(got)
    if field.type == FieldType.checkbox:
        return bool(got) == (want if isinstance(want, bool) else str(want).lower() in ("yes", "true", "1"))
    if field.locator.get("widget") == "autocomplete":
        return True  # free-text autocomplete: value may be normalised by the site or left as typed
    if isinstance(want, list):
        got_list = got if isinstance(got, list) else (str(got).split(" | ") if got else [])
        return all(any(norm(str(w)) in norm(str(g)) or norm(str(g)) in norm(str(w)) for g in got_list) for w in want)
    if got is None:
        return want in (None, "")
    w, g = norm(str(want)), norm(str(got))
    if field.type in (FieldType.phone,):
        return re.sub(r"\D", "", str(want))[-8:] in re.sub(r"\D", "", str(got))
    return w == g or (bool(w) and (w in g or g in w))
