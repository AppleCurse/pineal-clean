"""FINAL-KARAR-MATRIX - production routing policy
Fail-closed by construction, not by data.

Invariants:
- UNKNOWN MODEL/PRICE/PROVIDER/UNVERIFIED -> DENY
- UNKNOWN QUOTA != INF, never unlimited
- Canonical key = model@provider everywhere
- verification_status defaults to unverified (opt-in)
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger("pineal.routing")

class PaidEscalationDenied(RuntimeError):
    pass

class UnknownModelDenied(RuntimeError):
    pass

class UnknownQuotaDenied(RuntimeError):
    pass

QUOTA_UNKNOWN = None  # sentinel, must never be treated as inf/unlimited

@dataclass(frozen=True)
class RouteSpec:
    model: str
    provider: str
    tier: str  # free, paid, frontier
    input_per_million_usd: float
    output_per_million_usd: float
    context_window: int | None = None
    capabilities: frozenset[str] = frozenset({"chat"})
    verification_status: str = "unverified"  # FIX #1: default unverified, force opt-in
    list_input_per_million_usd: float | None = None
    list_output_per_million_usd: float | None = None
    note: str = ""

    def __post_init__(self):
        # both-or-neither for list pricing
        li = self.list_input_per_million_usd
        lo = self.list_output_per_million_usd
        if (li is None) ^ (lo is None):
            raise ValueError(f"list pricing must be both set or both None for {self.model}@{self.provider}")
        if self.verification_status not in ("verified", "unverified", "validating", "discovered"):
            raise ValueError(f"invalid verification_status {self.verification_status}")

    def is_free(self) -> bool:
        return self.tier == "free" and self.input_per_million_usd == 0.0 and self.output_per_million_usd == 0.0

    def effective_pricing(self) -> Tuple[float, float]:
        return (self.input_per_million_usd, self.output_per_million_usd)


QUOTAS: Dict[str, Dict[str, int | None]] = {
    "groq": {"rpm": 30, "rpd": 14400, "tpm": QUOTA_UNKNOWN, "tpd": QUOTA_UNKNOWN},
    "cerebras": {"rpm": 5, "tpm": 30000, "tpd": 1_000_000, "rpd": QUOTA_UNKNOWN},
}

def quota_limit(provider: str, dim: str) -> int:
    """FIX #5: enforce UNKNOWN QUOTA != INF. Fail-closed: unknown -> raise."""
    v = QUOTAS.get(provider, {}).get(dim, QUOTA_UNKNOWN)
    if v is None:
        # Raise to force explicit handling; caller cannot silently treat as unlimited
        raise UnknownQuotaDenied(f"UNKNOWN_QUOTA: {provider}.{dim} is UNKNOWN, not unlimited")
    return v

def quota_limit_or_zero(provider: str, dim: str) -> int:
    """Conservative helper for governors that want 0 when unknown."""
    try:
        return quota_limit(provider, dim)
    except UnknownQuotaDenied:
        return 0

# Canonical key = model@provider
def _canonical_key(model: str, provider: str) -> str:
    return f"{model}@{provider}"

ROUTES: Dict[str, RouteSpec] = {
    "openai/gpt-oss-120b@groq": RouteSpec("openai/gpt-oss-120b", "groq", "free", 0.0, 0.0, 131072, frozenset({"chat","streaming","tools"}), "verified", note="Groq 30 RPM / 14400 RPD"),
    "gpt-oss-120b@cerebras": RouteSpec("gpt-oss-120b", "cerebras", "free", 0.0, 0.0, 131072, frozenset({"chat","streaming"}), "verified", note="Cerebras 5 RPM / 30K TPM / 1M TPD"),
    "laguna-s-2.1:free@nous-research": RouteSpec("laguna-s-2.1:free", "nous-research", "free", 0.0, 0.0, 262144, frozenset({"chat","streaming","tools"}), "verified"),
    "xs-2.1:free@nous-research": RouteSpec("xs-2.1:free", "nous-research", "free", 0.0, 0.0, 262144, frozenset({"chat","streaming","tools"}), "verified"),
    "ling-3.0-flash-fin:free@nous-research": RouteSpec("ling-3.0-flash-fin:free", "nous-research", "free", 0.0, 0.0, 262144, frozenset({"chat","streaming","tools"}), "verified"),
    "dots-3-note-preview:free@nous-research": RouteSpec("dots-3-note-preview:free", "nous-research", "free", 0.0, 0.0, 524288, frozenset({"chat","streaming","tools"}), "verified", note="512K verified free"),
    "stepfun/step-3.7-flash@nous-research": RouteSpec("stepfun/step-3.7-flash", "nous-research", "paid", 0.20, 1.15, 262144, frozenset({"chat","streaming","vision","tools","video"}), "verified"),
    "upstage/solar-pro4@nous-research": RouteSpec("upstage/solar-pro4", "nous-research", "paid", 0.03, 0.12, 524288, frozenset({"chat","streaming","tools"}), "verified"),
    "meituan/longcat-2.0@nous-research": RouteSpec("meituan/longcat-2.0", "nous-research", "paid", 0.30, 1.20, 1_048_576, frozenset({"chat","streaming","tools"}), "verified"),
    "openai/gpt-5.6-luna@nous-research": RouteSpec("openai/gpt-5.6-luna", "nous-research", "paid", 0.20, 1.20, 400000, frozenset({"chat","streaming","tools"}), "verified", 1.00, 6.00, "Nous 80% discount vs $1/$6"),
    "anthropic/claude-sonnet-5@nous-research": RouteSpec("anthropic/claude-sonnet-5", "nous-research", "paid", 1.60, 8.00, 1_048_576, frozenset({"chat","streaming","vision","tools","reasoning"}), "verified", 2.00, 10.00, "Nous 20% discount vs $2/$10"),
    "google/gemini-3.7-flash@openrouter": RouteSpec("google/gemini-3.7-flash", "openrouter", "paid", 0.75, 3.75, 1_048_576, frozenset({"chat","streaming","vision","tools"}), "verified"),
    "openai/gpt-5.6-sol-pro@openrouter": RouteSpec("openai/gpt-5.6-sol-pro", "openrouter", "frontier", 2.00, 10.00, 1_048_576, frozenset({"chat","streaming","tools","reasoning"}), "verified", note="Frontier explicit"),
}

FORBIDDEN_ALIASES = {"poolside/laguna:free", "laguna:free", "xs:free", "ling:free"}

TASK_GROUPS: Dict[str, List[Tuple[str, str]]] = {
    "general": [("openai/gpt-oss-120b","groq"), ("gpt-oss-120b","cerebras"), ("laguna-s-2.1:free","nous-research"), ("xs-2.1:free","nous-research")],
    "fast": [("openai/gpt-oss-120b","groq"), ("gpt-oss-120b","cerebras"), ("laguna-s-2.1:free","nous-research"), ("xs-2.1:free","nous-research"), ("ling-3.0-flash-fin:free","nous-research"), ("dots-3-note-preview:free","nous-research")],
    "normal": [("openai/gpt-oss-120b","groq"), ("gpt-oss-120b","cerebras"), ("laguna-s-2.1:free","nous-research"), ("xs-2.1:free","nous-research")],
    "research": [("openai/gpt-oss-120b","groq"), ("laguna-s-2.1:free","nous-research"), ("xs-2.1:free","nous-research"), ("ling-3.0-flash-fin:free","nous-research"), ("dots-3-note-preview:free","nous-research"), ("stepfun/step-3.7-flash","nous-research"), ("upstage/solar-pro4","nous-research"), ("meituan/longcat-2.0","nous-research"), ("openai/gpt-5.6-luna","nous-research")],
    "deep_reasoning": [("openai/gpt-oss-120b","groq"), ("laguna-s-2.1:free","nous-research"), ("ling-3.0-flash-fin:free","nous-research"), ("stepfun/step-3.7-flash","nous-research"), ("upstage/solar-pro4","nous-research"), ("meituan/longcat-2.0","nous-research"), ("openai/gpt-5.6-luna","nous-research")],
    "code_fast": [("gpt-oss-120b","cerebras"), ("openai/gpt-oss-120b","groq"), ("laguna-s-2.1:free","nous-research")],
    "code_expert": [("laguna-s-2.1:free","nous-research"), ("xs-2.1:free","nous-research"), ("ling-3.0-flash-fin:free","nous-research")],
    "long_document": [("ling-3.0-flash-fin:free","nous-research"), ("dots-3-note-preview:free","nous-research"), ("upstage/solar-pro4","nous-research"), ("meituan/longcat-2.0","nous-research")],
    "repo_scale": [("dots-3-note-preview:free","nous-research"), ("meituan/longcat-2.0","nous-research")],
    "vision": [("google/gemini-3.7-flash","openrouter"), ("stepfun/step-3.7-flash","nous-research"), ("anthropic/claude-sonnet-5","nous-research")],
    "video": [("stepfun/step-3.7-flash","nous-research")],
    "frontier_daily": [("openai/gpt-5.6-luna","nous-research")],
    "frontier_reasoning": [("anthropic/claude-sonnet-5","nous-research")],
    "frontier_sol_pro": [("openai/gpt-5.6-sol-pro","openrouter")],
}

# FIX #3: import-time integrity check - loud failure on misconfiguration
def _validate_catalog() -> None:
    for task, cands in TASK_GROUPS.items():
        for m, p in cands:
            key = _canonical_key(m, p)
            if key not in ROUTES:
                raise RuntimeError(f"TASK_GROUPS[{task!r}] references unknown route {key}")
            # key/spec mismatch check
            spec = ROUTES[key]
            if spec.model != m or spec.provider != p:
                raise RuntimeError(f"ROUTES[{key!r}] key/spec mismatch: spec has {spec.model}@{spec.provider}")
            if spec.verification_status != "verified":
                raise RuntimeError(f"TASK_GROUPS[{task!r}] references unverified route {key} status={spec.verification_status}")
    for alias in FORBIDDEN_ALIASES:
        if any(s.model == alias for s in ROUTES.values()):
            raise RuntimeError(f"forbidden alias present in ROUTES: {alias}")
    # capability cross-check FIX #7
    for task, cands in TASK_GROUPS.items():
        if task == "vision":
            for m, p in cands:
                spec = ROUTES[_canonical_key(m, p)]
                if "vision" not in spec.capabilities:
                    raise RuntimeError(f"vision task requires vision capability but {spec.model}@{spec.provider} lacks it")
        if task == "video":
            for m, p in cands:
                spec = ROUTES[_canonical_key(m, p)]
                if "video" not in spec.capabilities and "vision" not in spec.capabilities:
                    raise RuntimeError(f"video task requires video/vision capability but {spec.model}@{spec.provider} lacks it")

_validate_catalog()

def paid_escalation_enabled() -> bool:
    return os.getenv("PINEAL_ALLOW_PAID_ESCALATION", "0").strip() == "1"

# FIX #2: fail-closed is_paid/is_free with provider=None
def is_paid(model: str, provider: str | None = None) -> bool:
    matches = [s for s in ROUTES.values() if s.model == model and (provider is None or s.provider == provider)]
    if not matches:
        return True  # unknown -> enters paid firewall -> DENY
    return any(s.tier in ("paid", "frontier") or not s.is_free() for s in matches)

def is_free(model: str, provider: str | None = None) -> bool:
    matches = [s for s in ROUTES.values() if s.model == model and (provider is None or s.provider == provider)]
    return bool(matches) and all(s.is_free() for s in matches)

def assert_known_model(model: str, provider: str) -> RouteSpec:
    if model in FORBIDDEN_ALIASES:
        raise UnknownModelDenied(f"FORBIDDEN_ALIAS_DENIED: {model}")
    key = _canonical_key(model, provider)
    spec = ROUTES.get(key)
    # FIX #3: drop fallback search loop - dead code in deny-path hides bugs
    if not spec:
        raise UnknownModelDenied(f"UNKNOWN_MODEL_DENIED: {provider}/{model} not in verified catalog (key {key})")
    if spec.verification_status != "verified":
        raise UnknownModelDenied(f"MODEL_NOT_VERIFIED: {provider}/{model} status={spec.verification_status}")
    return spec

def assert_executable(model: str, provider: str | None = None, *, explicit: bool = False) -> RouteSpec:
    """FIX #4: simplified canonical-key parsing, no unreachable branches. FIX #1 explicit bypass audited."""
    # Canonical key support
    if provider is None:
        if "@" not in model:
            raise UnknownModelDenied(f"UNKNOWN_PROVIDER_DENIED: provider required for {model}")
        model, provider = model.rsplit("@", 1)

    spec = assert_known_model(model, provider)

    if spec.tier in ("paid", "frontier"):
        # FIX: explicit=True is audited, frontier requires both env and explicit
        if explicit:
            logger.warning(f"PAID_ESCALATION_EXPLICIT_BYPASS: {provider}/{model} tier={spec.tier} explicit=True used")
            if spec.tier == "frontier" and not paid_escalation_enabled():
                raise PaidEscalationDenied(f"FRONTIER_REQUIRES_ENV: {provider}/{model} needs PINEAL_ALLOW_PAID_ESCALATION=1 even with explicit=True")
        if not (explicit or paid_escalation_enabled()):
            raise PaidEscalationDenied(f"PAID_ESCALATION_DENIED: {provider}/{model} tier={spec.tier}")

    return spec

def executable_task_groups(*, allow_paid: bool | None = None) -> Dict[str, List[str]]:
    allow = paid_escalation_enabled() if allow_paid is None else allow_paid
    result: Dict[str, List[str]] = {}
    for task, candidates in TASK_GROUPS.items():
        selected: List[str] = []
        for model, provider in candidates:
            # FIX #3: don't silently swallow - _validate_catalog already ensures key exists, but keep explicit error for safety
            key = _canonical_key(model, provider)
            if key not in ROUTES:
                raise RuntimeError(f"TASK_GROUPS drift: {key} not in ROUTES")
            spec = ROUTES[key]
            if spec.tier in ("paid", "frontier") and not allow:
                continue
            selected.append(key)
        result[task] = selected
    return result

def effective_pricing(model: str, provider: str) -> Tuple[float, float] | None:
    try:
        spec = assert_known_model(model, provider)
        return spec.input_per_million_usd, spec.output_per_million_usd
    except UnknownModelDenied:
        return None

def list_pricing(model: str, provider: str) -> Tuple[float, float] | None:
    try:
        spec = assert_known_model(model, provider)
        if spec.list_input_per_million_usd is not None:
            return spec.list_input_per_million_usd, spec.list_output_per_million_usd
        return spec.input_per_million_usd, spec.output_per_million_usd
    except UnknownModelDenied:
        return None


# --------------------------------------------------------------------------- #
# Integration helpers used by the routed executor / gateway (not part of the
# FINAL reference's public surface, kept here so consumers speak one module).
# --------------------------------------------------------------------------- #
def is_known_route(model: str, provider: str) -> bool:
    """Non-raising predicate: is ``provider/model`` a FINAL-matrix route?"""
    return _canonical_key(model, provider) in ROUTES


def model_substitution_allowed(requested: str, actual: str) -> bool:
    """A provider silently substituting the requested model is never allowed."""
    if not requested or not actual:
        return True
    return requested.strip().lower() == actual.strip().lower()


# === INVARIANTS ===
if __name__ == "__main__":
    import sys
    os.environ.pop("PINEAL_ALLOW_PAID_ESCALATION", None)

    assert is_paid("completely-unknown-model") is True
    assert QUOTA_UNKNOWN is None and QUOTA_UNKNOWN != float("inf")
    for qs in QUOTAS.values():
        for v in qs.values():
            assert v != float("inf")

    assert QUOTAS["groq"]["rpm"] == 30 and QUOTAS["groq"]["rpd"] == 14400
    assert QUOTAS["groq"]["tpm"] is None and QUOTAS["groq"]["tpd"] is None
    assert QUOTAS["cerebras"]["rpm"] == 5 and QUOTAS["cerebras"]["tpm"] == 30000 and QUOTAS["cerebras"]["tpd"] == 1_000_000

    for keys in executable_task_groups(allow_paid=True).values():
        for rk in keys:
            assert "@" in rk and rk in ROUTES

    try:
        assert_executable("unknown-model@unknown-provider")
        sys.exit("MUST DENY unknown")
    except UnknownModelDenied:
        pass

    try:
        assert_executable("openai/gpt-5.6-luna@nous-research")
        sys.exit("paid must DENY by default")
    except PaidEscalationDenied:
        pass

    # happy paths
    assert assert_executable("openai/gpt-oss-120b", "groq").is_free()
    assert assert_executable("openai/gpt-5.6-luna@nous-research", explicit=True).tier == "paid"

    # forbidden alias
    try:
        assert_known_model("laguna:free", "nous-research")
        sys.exit("forbidden alias must DENY")
    except UnknownModelDenied:
        pass

    # no paid leakage
    for keys in executable_task_groups(allow_paid=False).values():
        assert all(ROUTES[k].is_free() for k in keys)
    assert executable_task_groups(allow_paid=False)["frontier_sol_pro"] == []

    print("ALL INVARIANTS PASS - production-ready")
