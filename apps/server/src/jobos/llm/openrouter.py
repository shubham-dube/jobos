"""OpenRouter provider (OpenAI-compatible Chat Completions)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import LLMError, LLMRequest, LLMResponse


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
            "messages": [m.model_dump() for m in request.messages],
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
            raw={"id": data.get("id"), "finish_reason": choice.get("finish_reason")},
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
