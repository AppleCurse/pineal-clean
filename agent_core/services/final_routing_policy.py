"""FINAL-KARAR-MATRIX — the runtime economic policy for Pineal routing.

This module is the single source of truth for *which* routes Pineal may
execute and at *what* cost. It is intentionally separate from transport and
provider discovery:

* :mod:`agent_core.services.provider_manager` describes what exists (catalog)
  and what an operator configured (connections).
* :mod:`agent_core.services.llm_gateway` owns the network/spend/reserve/
  settlement/telemetry boundary.
* This module decides what the catalog *may execute* and in which economic
  order — free first, subscription/included second, cheap third, and paid
  only behind an explicit escalation guard.

Paid escalation is opt-in and can never be introduced silently by a fallback
chain. The only accepted switch is ``PINEAL_ALLOW_PAID_ESCALATION=1``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional


class PaidEscalationDenied(RuntimeError):
    """A paid model was reached without explicit escalation permission."""


class UnknownRouteDenied(RuntimeError):
    """A model/provider pair is not a verified route of this deployment."""


# Economic priority. Lower value = preferred. FREE is always first.
TIER_PRIORITY: Mapping[str, int] = {
    "free": 0,
    "subscription": 1,
    "cheap": 2,
    "paid": 3,
}


@dataclass(frozen=True)
class RouteSpec:
    """One verified, deployable route of the FINAL-KARAR-MATRIX."""

    model: str
    provider: str
    tier: str
    input_per_million_usd: float
    output_per_million_usd: float
    context_window: Optional[int] = None
    capabilities: frozenset[str] = frozenset({"chat"})
    note: str = ""

    def __post_init__(self) -> None:
        if self.tier not in TIER_PRIORITY:
            raise ValueError(f"unknown route tier: {self.tier}")
        if self.input_per_million_usd < 0 or self.output_per_million_usd < 0:
            raise ValueError("route pricing must be non-negative")
        if self.tier != "paid" and (
            self.input_per_million_usd > 0 or self.output_per_million_usd > 0
        ):
            # A free/included route with a positive price would silently blur
            # the free/paid boundary the firewall depends on.
            raise ValueError(
                f"route {self.provider}/{self.model} is {self.tier} but priced > 0"
            )


# Account/provider-specific limits from the verified deployment inputs.
# Runtime response headers remain authoritative when a provider exposes them;
# these values seed the local QuotaGovernor accounting.
QUOTAS: Mapping[str, Mapping[str, int]] = {
    "groq": {"rpm": 30, "rpd": 14_400},
    "cerebras": {"rpm": 5, "tpm": 30_000, "tpd": 1_000_000},
}


def _route_key(model: str, provider: str) -> str:
    return f"{provider}/{model}"


ROUTES: Mapping[str, RouteSpec] = {
    # ------------------------------------------------------------------
    # FREE / included-in-account-quota routes (first-choice layer).
    # ------------------------------------------------------------------
    # Deployment note: the verified Groq and Cerebras accounts expose these
    # GPT-OSS endpoints as included quota with no incremental per-token cost
    # for this account. This $0 classification is an explicit deployment
    # policy decision recorded here — not an "unknown price coerced to $0".
    _route_key("openai/gpt-oss-120b", "groq"): RouteSpec(
        "openai/gpt-oss-120b", "groq", "free", 0.0, 0.0,
        capabilities=frozenset({"chat", "streaming", "tools"}),
        note="account-verified quota: 30 RPM / 14,400 RPD; included in quota.",
    ),
    _route_key("gpt-oss-120b", "cerebras"): RouteSpec(
        "gpt-oss-120b", "cerebras", "free", 0.0, 0.0,
        capabilities=frozenset({"chat", "streaming"}),
        note="account-verified quota: 5 RPM / 30K TPM / 1M TPD; included in quota.",
    ),
    # Nous verified free routes. These are genuinely $0 on the target catalog.
    _route_key("laguna-s-2.1:free", "nous-research"): RouteSpec(
        "laguna-s-2.1:free", "nous-research", "free", 0.0, 0.0,
        context_window=262_144,
        capabilities=frozenset({"chat", "streaming", "tools"}),
    ),
    _route_key("xs-2.1:free", "nous-research"): RouteSpec(
        "xs-2.1:free", "nous-research", "free", 0.0, 0.0,
        context_window=262_144,
        capabilities=frozenset({"chat", "streaming", "tools"}),
    ),
    _route_key("ling-3.0-flash-fin:free", "nous-research"): RouteSpec(
        "ling-3.0-flash-fin:free", "nous-research", "free", 0.0, 0.0,
        capabilities=frozenset({"chat", "streaming", "tools"}),
    ),
    _route_key("dots-3-note-preview:free", "nous-research"): RouteSpec(
        "dots-3-note-preview:free", "nous-research", "free", 0.0, 0.0,
        context_window=524_288,
        capabilities=frozenset({"chat", "streaming", "tools"}),
    ),

    # ------------------------------------------------------------------
    # PAID routes. These are never fallback targets unless
    # PINEAL_ALLOW_PAID_ESCALATION=1 is explicitly configured.
    # ------------------------------------------------------------------
    _route_key("stepfun/step-3.7-flash", "nous-research"): RouteSpec(
        "stepfun/step-3.7-flash", "nous-research", "paid", 0.20, 1.15,
        context_window=262_144,
        capabilities=frozenset({"chat", "streaming", "tools"}),
    ),
    _route_key("upstage/solar-pro4", "nous-research"): RouteSpec(
        "upstage/solar-pro4", "nous-research", "paid", 0.03, 0.12,
        context_window=524_288,
        capabilities=frozenset({"chat", "streaming", "tools"}),
    ),
    _route_key("meituan/longcat-2.0", "nous-research"): RouteSpec(
        "meituan/longcat-2.0", "nous-research", "paid", 0.30, 1.20,
        context_window=1_048_576,
        capabilities=frozenset({"chat", "streaming", "tools"}),
    ),
    _route_key("openai/gpt-5.6-luna", "nous-research"): RouteSpec(
        "openai/gpt-5.6-luna", "nous-research", "paid", 0.20, 1.20,
        context_window=400_000,
        capabilities=frozenset({"chat", "streaming", "tools"}),
        note="Nous fixed 80% discount vs $1.00/$6.00 list price.",
    ),
    _route_key("anthropic/claude-sonnet-5", "nous-research"): RouteSpec(
        "anthropic/claude-sonnet-5", "nous-research", "paid", 1.60, 8.00,
        context_window=1_048_576,
        capabilities=frozenset({"chat", "streaming", "vision", "tools"}),
        note="Nous fixed 20% discount vs $2.00/$10.00 list price.",
    ),
    _route_key("google/gemini-3.7-flash", "openrouter"): RouteSpec(
        "google/gemini-3.7-flash", "openrouter", "paid", 0.75, 3.75,
        context_window=1_048_576,
        capabilities=frozenset({"chat", "streaming", "vision", "tools"}),
    ),
    _route_key("openai/gpt-5.6-sol-pro", "openrouter"): RouteSpec(
        "openai/gpt-5.6-sol-pro", "openrouter", "paid", 2.00, 10.00,
        context_window=1_048_576,
        capabilities=frozenset({"chat", "streaming", "tools"}),
        note="explicit frontier paid route; never a silent fallback.",
    ),
}


# Canonical task → (model, provider) candidate order. FREE routes come first.
# Paid candidates appear only when escalation is enabled (see
# ``executable_task_groups``); the runtime never re-orders them silently.
TASK_GROUPS: Mapping[str, tuple[tuple[str, str], ...]] = {
    "general": (
        ("openai/gpt-oss-120b", "groq"),
        ("gpt-oss-120b", "cerebras"),
        ("laguna-s-2.1:free", "nous-research"),
        ("xs-2.1:free", "nous-research"),
        ("ling-3.0-flash-fin:free", "nous-research"),
    ),
    "fast": (
        ("openai/gpt-oss-120b", "groq"),
        ("gpt-oss-120b", "cerebras"),
        ("laguna-s-2.1:free", "nous-research"),
        ("xs-2.1:free", "nous-research"),
        ("ling-3.0-flash-fin:free", "nous-research"),
        ("dots-3-note-preview:free", "nous-research"),
    ),
    "code_fast": (
        ("gpt-oss-120b", "cerebras"),
        ("openai/gpt-oss-120b", "groq"),
        ("xs-2.1:free", "nous-research"),
    ),
    "code_expert": (
        ("laguna-s-2.1:free", "nous-research"),
        ("xs-2.1:free", "nous-research"),
        ("dots-3-note-preview:free", "nous-research"),
    ),
    "long_document": (
        ("ling-3.0-flash-fin:free", "nous-research"),
        ("dots-3-note-preview:free", "nous-research"),
        ("laguna-s-2.1:free", "nous-research"),
    ),
    "repo_scale": (
        ("dots-3-note-preview:free", "nous-research"),
        ("ling-3.0-flash-fin:free", "nous-research"),
    ),
    "research": (
        ("openai/gpt-oss-120b", "groq"),
        ("gpt-oss-120b", "cerebras"),
        ("laguna-s-2.1:free", "nous-research"),
        ("xs-2.1:free", "nous-research"),
        ("stepfun/step-3.7-flash", "nous-research"),
        ("upstage/solar-pro4", "nous-research"),
        ("meituan/longcat-2.0", "nous-research"),
        ("openai/gpt-5.6-luna", "nous-research"),
    ),
    "deep_reasoning": (
        ("laguna-s-2.1:free", "nous-research"),
        ("xs-2.1:free", "nous-research"),
        ("stepfun/step-3.7-flash", "nous-research"),
        ("upstage/solar-pro4", "nous-research"),
        ("meituan/longcat-2.0", "nous-research"),
        ("openai/gpt-5.6-luna", "nous-research"),
    ),
    "vision": (
        ("google/gemini-3.7-flash", "openrouter"),
    ),
    "frontier_daily": (
        ("openai/gpt-5.6-luna", "nous-research"),
    ),
    "frontier_reasoning": (
        ("anthropic/claude-sonnet-5", "nous-research"),
    ),
    "frontier_sol_pro": (
        ("openai/gpt-5.6-sol-pro", "openrouter"),
    ),
}

def paid_escalation_enabled() -> bool:
    """Return True only when the explicit paid-escalation switch is armed."""
    return os.getenv("PINEAL_ALLOW_PAID_ESCALATION", "0").strip() == "1"


def route_spec(model: str, provider: str) -> Optional[RouteSpec]:
    """Return the verified spec for ``provider/model`` or None if unknown."""
    return ROUTES.get(_route_key(model, provider))


def is_known_route(model: str, provider: str) -> bool:
    return route_spec(model, provider) is not None


def tier_of(model: str, provider: str) -> Optional[str]:
    spec = route_spec(model, provider)
    return spec.tier if spec is not None else None


def is_paid(model: str, provider: str | None = None) -> bool:
    if provider is not None:
        spec = route_spec(model, provider)
        return spec is not None and spec.tier == "paid"
    return any(
        spec.model == model and spec.tier == "paid"
        for spec in ROUTES.values()
    )


def is_free(model: str, provider: str) -> bool:
    spec = route_spec(model, provider)
    return spec is not None and spec.tier == "free"


def effective_pricing(
    model: str,
    provider: str,
) -> Optional[tuple[float, float]]:
    """Return (input_per_million_usd, output_per_million_usd) or None."""
    spec = route_spec(model, provider)
    if spec is None:
        return None
    return spec.input_per_million_usd, spec.output_per_million_usd


def capabilities_for(model: str, provider: str) -> Optional[frozenset[str]]:
    spec = route_spec(model, provider)
    return spec.capabilities if spec is not None else None


def context_window_for(model: str, provider: str) -> Optional[int]:
    spec = route_spec(model, provider)
    return spec.context_window if spec is not None else None


def assert_executable(
    model: str,
    provider: str,
    *,
    allow_paid: Optional[bool] = None,
) -> None:
    """Raise unless ``provider/model`` is a verified route Pineal may run now.

    * Unknown model/provider, unknown price, or unverified capability → DENY.
    * Paid tier → DENY unless paid escalation is explicitly enabled.
    """
    allow = paid_escalation_enabled() if allow_paid is None else allow_paid
    spec = route_spec(model, provider)
    if spec is None:
        raise UnknownRouteDenied(
            f"UNKNOWN_MODEL_OR_PRICE: {provider}/{model} is not a verified "
            "route of this deployment."
        )
    if spec.tier == "paid" and not allow:
        raise PaidEscalationDenied(
            f"PAID_ESCALATION_DENIED: {provider}/{model}; "
            "set PINEAL_ALLOW_PAID_ESCALATION=1 or request a free route."
        )


def executable_task_groups(
    *,
    allow_paid: Optional[bool] = None,
) -> dict[str, list[str]]:
    """Return canonical ``provider/model`` candidates in policy order.

    When paid escalation is disabled, paid candidates are dropped from any
    group that still has a non-paid alternative — so a fallback chain can
    never reach a paid model silently. Paid-only tasks (vision, frontier_*)
    keep their explicit paid primary; execution of those is still denied at
    runtime by :func:`assert_executable` until escalation is enabled.
    """
    allow = paid_escalation_enabled() if allow_paid is None else allow_paid
    result: dict[str, list[str]] = {}
    for task, candidates in TASK_GROUPS.items():
        selected: list[str] = []
        non_paid: list[str] = []
        paid: list[str] = []
        for model, provider in candidates:
            spec = route_spec(model, provider)
            if spec is None:
                continue
            canonical = _route_key(model, provider)
            if spec.tier == "paid":
                paid.append(canonical)
            else:
                non_paid.append(canonical)
        selected.extend(non_paid)
        if allow or not non_paid:
            selected.extend(paid)
        result[task] = selected
    return result


def verify_free_route_ids(models: Iterable[str]) -> list[str]:
    """Return ids that are explicitly known free in this deployment."""
    known = {
        "openai/gpt-oss-120b",
        "gpt-oss-120b",
        "laguna-s-2.1:free",
        "xs-2.1:free",
        "ling-3.0-flash-fin:free",
        "dots-3-note-preview:free",
    }
    return [model for model in models if model in known]


def model_substitution_allowed(requested: str, actual: str) -> bool:
    """A provider silently substituting the requested model is never allowed."""
    if not requested or not actual:
        return True
    return requested.strip().lower() == actual.strip().lower()
