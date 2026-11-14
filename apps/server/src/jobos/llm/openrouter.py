"""OpenRouter provider (OpenAI-compatible Chat Completions)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import LLMError, LLMMessage, LLMRequest, LLMResponse

# Anthropic models cache only where asked (cache_control breakpoints); OpenAI/Gemini cache prefixes
# automatically, so for them plain text with the stable part first is enough.
_EXPLICIT_CACHE = ("anthropic/",)
_MIN_CACHE_CHARS = 4000  # ~1k tokens: below the providers' minimum cacheable size it is pointless


def _message(m: LLMMessage, model: str) -> dict[str, Any]:
    explicit = model.startswith(_EXPLICIT_CACHE)
    if not explicit:
        return {"role": m.role, "content": m.full_text()}
    parts: list[dict[str, Any]] = []
    if m.cached_prefix:
        part: dict[str, Any] = {"type": "text", "text": m.cached_prefix}
        if len(m.cached_prefix) >= _MIN_CACHE_CHARS:
            part["cache_control"] = {"type": "ephemeral"}
        parts.append(part)
    if m.role == "system" and len(m.content) >= _MIN_CACHE_CHARS:
        parts.append({"type": "text", "text": m.content, "cache_control": {"type": "ephemeral"}})
    elif m.content:
        parts.append({"type": "text", "text": m.content})
    return {"role": m.role, "content": parts}


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1", timeout_s: float = 120.0):
        headers = {
            # When the key is injected by an egress proxy a placeholder is fine.
            "Authorization": f"Bearer {api_key or 'proxy-injected'}",
            "X-Title": "JobOS",
        }
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout_s)

    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        body: dict[str, Any] = {
            "model": model,
            "messages": [_message(m, model) for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "usage": {"include": True},
        }
        if request.json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": request.schema_name, "strict": False, "schema": request.json_schema},
            }
        started = time.monotonic()
        data = self._post(body)
        if data.get("error") and request.json_schema is not None:
            # Some models reject json_schema; fall back to json_object (schema is also in the prompt).
            body["response_format"] = {"type": "json_object"}
            data = self._post(body)
        if data.get("error"):
            raise LLMError(f"openrouter error: {data['error']}")
        try:
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
        except (KeyError, IndexError) as exc:
            raise LLMError(f"unexpected openrouter response: {str(data)[:500]}") from exc
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            provider=self.name,
            model=data.get("model", model),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            cost_usd=float(usage.get("cost") or 0.0),
            latency_ms=int((time.monotonic() - started) * 1000),
            raw={"id": data.get("id"), "finish_reason": choice.get("finish_reason"),
                 "cached_tokens": int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)},
        )

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._client.post("/chat/completions", json=body)
            except httpx.TransportError as exc:
                last_exc = exc
                time.sleep(2**attempt)
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = LLMError(f"openrouter HTTP {resp.status_code}: {resp.text[:300]}")
                time.sleep(2**attempt * 2)
                continue
            try:
                return resp.json()
            except ValueError as exc:
                raise LLMError(f"openrouter HTTP {resp.status_code}: {resp.text[:300]}") from exc
        raise LLMError(f"openrouter request failed after retries: {last_exc}")
