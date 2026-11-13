"""Single entry point for every LLM call: routing, structured output, ledger, budget."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from jobos.config import Settings, get_settings

from .base import BudgetExceeded, LLMError, LLMMessage, LLMProvider, LLMRequest, LLMResponse

log = structlog.get_logger(__name__)
T = TypeVar("T", bound=BaseModel)

# Defaults (ADR-0011). Override with JOBOS_LLM_ROUTES='{"form.resolve": "openrouter:..."}'
DEFAULT_ROUTES: dict[str, str] = {
    "profile.extract": "openrouter:anthropic/claude-sonnet-5.5",
    "job.match": "openrouter:anthropic/claude-haiku-5.5",
    "job.verify": "openrouter:anthropic/claude-haiku-5.5",
    "form.resolve": "openrouter:anthropic/claude-sonnet-5.5",
    "form.generate": "openrouter:anthropic/claude-sonnet-5.5",
    "form.navigate": "openrouter:anthropic/claude-haiku-5.5",
    "answer.match": "openrouter:anthropic/claude-haiku-5.5",
    "email.classify": "openrouter:anthropic/claude-haiku-5.5",
}

Ledger = Callable[[LLMRequest, LLMResponse | None, str], None]
SpendToday = Callable[[], float]


class LLMGateway:
    def __init__(
        self,
        providers: dict[str, LLMProvider],
        routes: dict[str, str] | None = None,
        default_route: str = "openrouter:anthropic/claude-sonnet-5.5",
        ledger: Ledger | None = None,
        spend_today: SpendToday | None = None,
        daily_budget_usd: float | None = None,
    ):
        self.providers = providers
        self.user_routes = dict(routes or {})
        self.routes = dict(DEFAULT_ROUTES)
        self.default_route = default_route
        self.ledger = ledger
        self.spend_today = spend_today
        self.daily_budget_usd = daily_budget_usd

    # ------------------------------------------------------------------ routing
    def route(self, task: str) -> tuple[LLMProvider, str]:
        # precedence: user exact > user prefix ("form" -> all form.*) > default exact > default prefix > default
        prefix = task.split(".")[0]
        spec = (self.user_routes.get(task) or self.user_routes.get(prefix) or self.routes.get(task)
                or self.routes.get(prefix) or self.default_route)
        provider_name, _, model = spec.partition(":")
        if provider_name not in self.providers:
            # fall back to the first provider (e.g. only "fake" in tests)
            provider_name = next(iter(self.providers))
        return self.providers[provider_name], model

    # ------------------------------------------------------------------ calls
    def complete(self, request: LLMRequest) -> LLMResponse:
        if self.daily_budget_usd is not None and self.spend_today is not None:
            spent = self.spend_today()
            if spent >= self.daily_budget_usd:
                raise BudgetExceeded(f"daily LLM budget reached (${spent:.2f} / ${self.daily_budget_usd:.2f})")
        provider, model = self.route(request.task)
        try:
            response = provider.complete(request, model)
        except Exception as exc:
            if self.ledger:
                self.ledger(request, None, str(exc))
            raise
        if self.ledger:
            self.ledger(request, response, "")
        log.info("llm.call", task=request.task, model=response.model, cost=response.cost_usd,
                 tokens_in=response.input_tokens, tokens_out=response.output_tokens, ms=response.latency_ms)
        return response

    def structured(
        self,
        task: str,
        system: str,
        user: str,
        output: type[T],
        *,
        ref: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> T:
        """Ask for JSON matching ``output``; validates and repairs once."""
        schema = output.model_json_schema()
        sys_prompt = (
            f"{system}\n\nRespond with a single JSON object that conforms to this JSON schema. "
            f"No prose, no markdown fences.\nJSON schema:\n{json.dumps(schema)}"
        )
        messages = [LLMMessage(role="system", content=sys_prompt), LLMMessage(role="user", content=user)]
        last_error = ""
        for _attempt in range(2):
            req = LLMRequest(task=task, messages=messages, json_schema=schema, schema_name=output.__name__,
                             temperature=temperature, max_tokens=max_tokens, ref=ref)
            resp = self.complete(req)
            try:
                return output.model_validate(parse_json(resp.text))
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)[:1500]
                messages = [
                    *messages,
                    LLMMessage(role="assistant", content=resp.text[:6000]),
                    LLMMessage(role="user", content=f"That JSON was invalid: {last_error}\nReturn corrected JSON only."),
                ]
        raise LLMError(f"{task}: model did not return valid {output.__name__}: {last_error}")

    def text(self, task: str, system: str, user: str, *, ref: str = "", max_tokens: int = 2000,
             temperature: float = 0.4) -> str:
        req = LLMRequest(task=task, messages=[LLMMessage(role="system", content=system),
                                              LLMMessage(role="user", content=user)],
                         temperature=temperature, max_tokens=max_tokens, ref=ref)
        return self.complete(req).text.strip()


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json(text: str) -> object:
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise ValueError(f"not JSON: {cleaned[:200]}") from None


# ---------------------------------------------------------------------- default wiring ---------

_gateway: LLMGateway | None = None


def _db_ledger(request: LLMRequest, response: LLMResponse | None, error: str) -> None:
    from jobos.db import session_scope
    from jobos.db.models import LLMCall

    try:
        with session_scope() as s:
            s.add(LLMCall(
                task=request.task,
                provider=response.provider if response else "",
                model=response.model if response else "",
                input_tokens=response.input_tokens if response else 0,
                output_tokens=response.output_tokens if response else 0,
                cost_usd=response.cost_usd if response else 0.0,
                latency_ms=response.latency_ms if response else 0,
                ok=response is not None,
                error=error[:2000],
                ref=request.ref[:200],
            ))
    except Exception as exc:  # the ledger must never break the call path
        log.warning("llm.ledger_failed", error=str(exc))


def _db_spend_today() -> float:
    from sqlalchemy import func, select

    from jobos.db import session_scope
    from jobos.db.models import LLMCall

    since = datetime.now(UTC) - timedelta(days=1)
    with session_scope() as s:
        return float(s.scalar(select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(LLMCall.created_at >= since)) or 0)


def build_gateway(settings: Settings | None = None) -> LLMGateway:
    settings = settings or get_settings()
    providers: dict[str, LLMProvider] = {}
    if settings.llm_fake:
        from .fake import FakeProvider

        providers["fake"] = FakeProvider()
    else:
        from .openrouter import OpenRouterProvider

        providers["openrouter"] = OpenRouterProvider(settings.openrouter_api_key, settings.openrouter_base_url)
    return LLMGateway(
        providers,
        routes=settings.llm_routes,
        default_route=settings.llm_default_route,
        ledger=_db_ledger,
        spend_today=_db_spend_today,
        daily_budget_usd=settings.llm_daily_budget_usd,
    )


def get_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = build_gateway()
    return _gateway


def set_gateway(gateway: LLMGateway | None) -> None:
    global _gateway
    _gateway = gateway
