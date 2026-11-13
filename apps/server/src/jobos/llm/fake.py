"""Deterministic provider for tests and offline development."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .base import LLMRequest, LLMResponse

Handler = Callable[[LLMRequest], Any]


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.handlers: dict[str, Handler] = {}
        self.calls: list[LLMRequest] = []

    def on(self, task_prefix: str, handler: Handler) -> None:
        self.handlers[task_prefix] = handler

    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        self.calls.append(request)
        handler = None
        for prefix, h in sorted(self.handlers.items(), key=lambda kv: -len(kv[0])):
            if request.task.startswith(prefix):
                handler = h
                break
        result: Any = handler(request) if handler else {}
        text = result if isinstance(result, str) else json.dumps(result)
        return LLMResponse(text=text, provider=self.name, model=model, input_tokens=10, output_tokens=10)
