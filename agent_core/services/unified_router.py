"""Explainable multi-provider route planning and resilience state.

This module does not perform network I/O.  It ranks targets from a tenant's
:class:`~agent_core.services.provider_manager.ProviderManager`, issues explicit
attempt leases, and records outcomes.  The separation keeps route policy from
bypassing ``LLMGateway`` accounting, cancellation, cache, or provenance.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

from agent_core.services.provider_manager import (
    ProviderManager,
    QuotaStatus,
    RouteTarget,
    RouteTier,
    VerificationStatus,
)


class RouterError(ValueError):
    """Invalid routing input or state transition."""


class RouteUnavailable(RuntimeError):
    """No eligible target is available for the request."""


class RoutingStrategy(str, Enum):
    PRIORITY = "priority"
    WEIGHTED = "weighted"
    ROUND_ROBIN = "round-robin"
    CONTEXT_RELAY = "context-relay"
    FILL_FIRST = "fill-first"
    P2C = "p2c"
    RANDOM = "random"
    LEAST_USED = "least-used"
    COST_OPTIMIZED = "cost-optimized"
    RESET_AWARE = "reset-aware"
    RESET_WINDOW = "reset-window"
    HEADROOM = "headroom"
    STRICT_RANDOM = "strict-random"
    AUTO = "auto"
    LKGP = "lkgp"
    CONTEXT_OPTIMIZED = "context-optimized"
    CACHE_OPTIMIZED = "cache-optimized"
    FUSION = "fusion"
    PIPELINE = "pipeline"


class RouteMode(str, Enum):
    FALLBACK = "fallback"
    CONTEXT_RELAY = "context_relay"
    FUSION = "fusion"
    PIPELINE = "pipeline"


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class FailureKind(str, Enum):
    CANCELLED = "cancelled"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    INVALID_REQUEST = "invalid_request"
    MODEL_UNAVAILABLE = "model_unavailable"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXHAUSTED = "quota_exhausted"
    TIMEOUT = "timeout"
    NETWORK = "network"
    SERVER = "server"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RouterConfig:
    provider_failure_threshold: int = 3
    provider_open_seconds: float = 60.0
    max_provider_open_seconds: float = 900.0
    rate_limit_cooldown_seconds: float = 60.0
    quota_cooldown_seconds: float = 3600.0
    transient_cooldown_seconds: float = 5.0
    credential_cooldown_seconds: float = 300.0
    model_lock_seconds: float = 300.0
    max_retry_after_seconds: float = 7 * 24 * 3600.0
    lkg_ttl_seconds: float = 15 * 60.0
    max_state_entries: int = 10_000
    max_session_entries: int = 1_000
    max_attempts: int = 8
    fusion_width: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.provider_failure_threshold <= 100:
            raise RouterError("provider_failure_threshold must be between 1 and 100")
        for name in (
            "provider_open_seconds",
            "max_provider_open_seconds",
            "rate_limit_cooldown_seconds",
            "quota_cooldown_seconds",
            "transient_cooldown_seconds",
            "credential_cooldown_seconds",
            "model_lock_seconds",
            "max_retry_after_seconds",
            "lkg_ttl_seconds",
        ):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise RouterError(f"{name} must be a finite non-negative number")
        if self.max_provider_open_seconds < self.provider_open_seconds:
            raise RouterError("max_provider_open_seconds cannot be below provider_open_seconds")
        if not 100 <= self.max_state_entries <= 100_000:
            raise RouterError("max_state_entries must be between 100 and 100000")
        if not 10 <= self.max_session_entries <= 100_000:
            raise RouterError("max_session_entries must be between 10 and 100000")
        if not 1 <= self.max_attempts <= 100:
            raise RouterError("max_attempts must be between 1 and 100")
        if not 2 <= self.fusion_width <= 10:
            raise RouterError("fusion_width must be between 2 and 10")


@dataclass(frozen=True)
class RouteRequest:
    model: Optional[str] = None
    candidate_models: tuple[str, ...] = ()
    strategy: RoutingStrategy = RoutingStrategy.AUTO
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    minimum_context: Optional[int] = None
    minimum_quality: Optional[float] = None
    complexity: TaskComplexity = TaskComplexity.MODERATE
    estimated_input_tokens: int = 0
    max_output_tokens: int = 4096
    session_key: Optional[str] = field(default=None, repr=False)
    seed: Optional[int] = None
    preview: bool = False

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "strategy", RoutingStrategy(self.strategy))
            object.__setattr__(self, "complexity", TaskComplexity(self.complexity))
        except ValueError as exc:
            raise RouterError("unknown routing strategy or task complexity") from exc
        if any(
            not isinstance(model_id, str) or not model_id.strip()
            for model_id in self.candidate_models
        ):
            raise RouterError("candidate_models must be non-empty strings")
        if len(self.candidate_models) > 32:
            raise RouterError("candidate_models cannot exceed 32 entries")
        if self.minimum_context is not None and self.minimum_context <= 0:
            raise RouterError("minimum_context must be positive")
        if self.minimum_quality is not None and (
            not isinstance(self.minimum_quality, (int, float))
            or not math.isfinite(self.minimum_quality)
            or not 0 <= self.minimum_quality <= 1
        ):
            raise RouterError("minimum_quality must be between 0 and 1")
        if self.estimated_input_tokens < 0 or self.max_output_tokens < 1:
            raise RouterError("token estimates are outside the allowed range")
        if self.estimated_input_tokens > 10_000_000 or self.max_output_tokens > 10_000_000:
            raise RouterError("token estimates exceed the routing safety bound")
        if self.session_key is not None and (not isinstance(self.session_key, str) or len(self.session_key) > 1024):
            raise RouterError("session_key must be a string no longer than 1024 characters")
        if self.seed is not None and not isinstance(self.seed, int):
            raise RouterError("seed must be an integer")


@dataclass(frozen=True)
class CandidateScore:
    target: RouteTarget
    eligible: bool
    score: float
    reasons: tuple[str, ...]

    @property
    def execution_key(self) -> str:
        return self.target.execution_key


@dataclass(frozen=True)
class RoutePlan:
    route_id: str
    tenant_id: str
    strategy: RoutingStrategy
    mode: RouteMode
    candidates: tuple[CandidateScore, ...]
    attempt_order: tuple[str, ...]
    selected_execution_key: Optional[str]
    parallel_width: int
    session_scope_hash: Optional[str] = field(default=None, repr=False)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def candidate(self, execution_key: str) -> CandidateScore:
        for candidate in self.candidates:
            if candidate.execution_key == execution_key:
                return candidate
        raise RouterError("candidate does not belong to route plan")

    def as_dict(self) -> dict[str, Any]:
        """Return a credential- and endpoint-free preview/telemetry shape."""
        return {
            "route_id": self.route_id,
            "tenant_id": self.tenant_id,
            "strategy": self.strategy.value,
            "mode": self.mode.value,
            "selected": self.selected_execution_key,
            "attempt_order": list(self.attempt_order),
            "parallel_width": self.parallel_width,
            "created_at": self.created_at,
            "plan_only": True,
            "candidates": [
                {
                    "execution_key": candidate.execution_key,
                    "provider": candidate.target.provider.id,
                    "model": candidate.target.model.canonical_id,
                    "connection_id": candidate.target.connection.id,
                    "tier": candidate.target.tier.name.lower(),
                    "quota": candidate.target.quota.status.value,
                    "verification": candidate.target.verification.status.value,
                    "eligible": candidate.eligible,
                    "score": candidate.score,
                    "reasons": list(candidate.reasons),
                }
                for candidate in self.candidates
            ],
        }


@dataclass(frozen=True)
class AttemptLease:
    attempt_id: str
    route_id: str
    tenant_id: str
    execution_key: str
    target: RouteTarget = field(repr=False)
    session_scope_hash: Optional[str] = field(default=None, repr=False)
    started_monotonic: float = field(default=0.0, repr=False)


@dataclass(frozen=True)
class FailureSignal:
    status_code: Optional[int] = None
    message: str = field(default="", repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    exception: Optional[BaseException] = field(default=None, repr=False)


@dataclass(frozen=True)
class FailureDecision:
    kind: FailureKind
    failover_allowed: bool
    retry_after_seconds: Optional[float]
    circuit_state: CircuitState


@dataclass
class _TargetState:
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    active_requests: int = 0
    total_latency_ms: float = 0.0
    cooldown_until: float = 0.0
    cache_affinity: float = 0.0
    last_used: float = 0.0

    @property
    def average_latency_ms(self) -> Optional[float]:
        return self.total_latency_ms / self.success_count if self.success_count else None

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total else 0.5


@dataclass
class _ProviderCircuit:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    open_until: float = 0.0
    open_cycles: int = 0
    probe_active: bool = False
    last_used: float = 0.0


@dataclass(frozen=True)
class _StickyTarget:
    execution_key: str
    expires_at: float


@dataclass(frozen=True)
class _Eligibility:
    eligible: bool
    reasons: tuple[str, ...]
    circuit_state: CircuitState


_TRANSIENT_FAILURES = frozenset(
    {
        FailureKind.RATE_LIMIT,
        FailureKind.QUOTA_EXHAUSTED,
        FailureKind.TIMEOUT,
        FailureKind.NETWORK,
        FailureKind.SERVER,
    }
)
_PROVIDER_CIRCUIT_FAILURES = frozenset(
    {
        FailureKind.TIMEOUT,
        FailureKind.NETWORK,
        FailureKind.SERVER,
    }
)
_QUOTA_MARKERS = (
    "insufficient_quota",
    "quota exhausted",
    "quota_exhausted",
    "billing hard limit",
    "billing_hard_limit",
    "credit balance",
    "out of credits",
)


class UnifiedRouter:
    """Tenant-scoped route planner with bounded in-memory resilience state."""

    def __init__(
        self,
        provider_manager: ProviderManager,
        *,
        config: Optional[RouterConfig] = None,
        quality_scores: Optional[Mapping[str, float]] = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ):
        self.provider_manager = provider_manager
        self.tenant_id = provider_manager.tenant_id
        self.config = config or RouterConfig()
        validated_quality: dict[str, float] = {}
        for model_id, score in (quality_scores or {}).items():
            if (
                not isinstance(model_id, str)
                or not model_id.strip()
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not 0 <= score <= 1
            ):
                raise RouterError("quality scores require model ids and values between 0 and 1")
            # Ensures scores cannot silently target an unknown cross-tenant model
            # and normalizes provider aliases to the catalog's canonical id.
            model = provider_manager.catalog.resolve_model(model_id)
            validated_quality[model.canonical_id] = float(score)
        self._quality_scores = MappingProxyType(validated_quality)
        self._clock = clock
        self._wall_clock = wall_clock
        self._target_state: dict[str, _TargetState] = {}
        self._provider_circuits: dict[str, _ProviderCircuit] = {}
        self._model_locks: dict[str, float] = {}
        self._active_leases: dict[str, AttemptLease] = {}
        self._round_robin: dict[str, int] = {}
        self._strict_random_decks: dict[str, list[str]] = {}
        self._last_known_good: dict[str, _StickyTarget] = {}
        self._lock = threading.RLock()

    def plan(self, request: RouteRequest) -> RoutePlan:
        now = self._clock()
        targets = self._targets_for_request(request)
        session_scope = self._session_scope(request.session_key, request.model)
        scope = self._strategy_scope(request, session_scope)
        route_id = str(uuid.uuid4())
        seed = request.seed if request.seed is not None else int(uuid.UUID(route_id))
        rng = random.Random(seed)

        with self._lock:
            self._prune_locked(now)
            eligibility = {
                target.execution_key: self._eligibility_locked(
                    target,
                    now,
                    minimum_quality=request.minimum_quality,
                )
                for target in targets
            }
            eligible_targets = [target for target in targets if eligibility[target.execution_key].eligible]
            ordered, scores, score_reasons = self._order_locked(
                request,
                eligible_targets,
                scope=scope,
                session_scope=session_scope,
                rng=rng,
                now=now,
            )
            self._prune_locked(now)

        rank_by_key = {target.execution_key: index for index, target in enumerate(ordered)}
        candidate_scores = []
        for target in targets:
            target_eligibility = eligibility[target.execution_key]
            if target_eligibility.eligible:
                rank = rank_by_key[target.execution_key]
                reasons = score_reasons.get(target.execution_key) or (
                    f"strategy_rank={rank + 1}",
                    f"tier={target.tier.name.lower()}",
                    f"connection_priority={target.connection.priority}",
                )
                score = scores.get(
                    target.execution_key,
                    self._rank_score(rank, len(ordered)),
                )
            else:
                reasons = target_eligibility.reasons
                score = 0.0
            candidate_scores.append(
                CandidateScore(
                    target=target,
                    eligible=target_eligibility.eligible,
                    score=round(max(0.0, min(1.0, score)), 6),
                    reasons=tuple(reasons),
                )
            )

        candidate_scores.sort(
            key=lambda candidate: (
                not candidate.eligible,
                rank_by_key.get(candidate.execution_key, len(rank_by_key)),
                candidate.execution_key,
            )
        )
        attempt_order = tuple(target.execution_key for target in ordered[: self.config.max_attempts])
        mode = _mode_for_strategy(request.strategy)
        parallel_width = min(self.config.fusion_width, len(attempt_order)) if mode is RouteMode.FUSION else 1
        return RoutePlan(
            route_id=route_id,
            tenant_id=self.tenant_id,
            strategy=request.strategy,
            mode=mode,
            candidates=tuple(candidate_scores),
            attempt_order=attempt_order,
            selected_execution_key=attempt_order[0] if attempt_order else None,
            parallel_width=parallel_width,
            session_scope_hash=session_scope,
        )

    def begin_attempt(self, plan: RoutePlan, execution_key: Optional[str] = None) -> AttemptLease:
        if plan.tenant_id != self.tenant_id:
            raise RouterError("TENANT_ROUTE_MISMATCH")
        selected_key = execution_key or plan.selected_execution_key
        if selected_key is None or selected_key not in plan.attempt_order:
            raise RouteUnavailable("route plan has no eligible selected target")
        candidate = plan.candidate(selected_key)
        # Refresh manager-owned state before leasing so a plan cannot revive a
        # connection that was disabled, removed, or exhausted after planning.
        current_target = next(
            (
                target
                for target in self.provider_manager.targets_for(
                    candidate.target.model.canonical_id,
                    include_exhausted=True,
                )
                if target.execution_key == selected_key
            ),
            None,
        )
        if current_target is None:
            raise RouteUnavailable("target became unavailable after route planning")
        now = self._clock()

        with self._lock:
            current = self._eligibility_locked(current_target, now)
            if not current.eligible:
                raise RouteUnavailable("target became unavailable after route planning")
            circuit = self._circuit_locked(current_target.provider.id, now)
            if circuit.state is CircuitState.HALF_OPEN:
                if circuit.probe_active:
                    raise RouteUnavailable("provider circuit half-open probe is already active")
                circuit.probe_active = True
            state = self._state_locked(selected_key, now)
            state.request_count += 1
            state.active_requests += 1
            state.last_used = now
            lease = AttemptLease(
                attempt_id=str(uuid.uuid4()),
                route_id=plan.route_id,
                tenant_id=self.tenant_id,
                execution_key=selected_key,
                target=current_target,
                session_scope_hash=plan.session_scope_hash,
                started_monotonic=now,
            )
            self._active_leases[lease.attempt_id] = lease
            return lease

    def finish_success(
        self,
        lease: AttemptLease,
        *,
        latency_ms: Optional[float] = None,
        cache_hit: bool = False,
    ) -> None:
        now = self._clock()
        with self._lock:
            active = self._pop_lease_locked(lease)
            state = self._state_locked(active.execution_key, now)
            state.active_requests = max(0, state.active_requests - 1)
            state.success_count += 1
            state.consecutive_failures = 0
            state.cooldown_until = 0.0
            self._model_locks.pop(active.target.model.canonical_id, None)
            state.last_used = now
            if latency_ms is None:
                latency_ms = max(0.0, (now - active.started_monotonic) * 1000)
            if math.isfinite(latency_ms) and latency_ms >= 0:
                state.total_latency_ms += latency_ms
            if cache_hit:
                state.cache_affinity = min(1.0, state.cache_affinity + 0.1)

            circuit = self._circuit_locked(active.target.provider.id, now)
            circuit.state = CircuitState.CLOSED
            circuit.failure_count = 0
            circuit.open_until = 0.0
            circuit.open_cycles = 0
            circuit.probe_active = False
            circuit.last_used = now
            if active.session_scope_hash:
                self._last_known_good[active.session_scope_hash] = _StickyTarget(
                    execution_key=active.execution_key,
                    expires_at=now + self.config.lkg_ttl_seconds,
                )
            self._prune_locked(now)

    def finish_failure(self, lease: AttemptLease, signal: FailureSignal) -> FailureDecision:
        kind = classify_failure(signal)
        retry_after = parse_retry_after(
            signal.headers,
            wall_clock=self._wall_clock(),
            maximum=self.config.max_retry_after_seconds,
        )
        now = self._clock()

        with self._lock:
            active = self._pop_lease_locked(lease)
            state = self._state_locked(active.execution_key, now)
            state.active_requests = max(0, state.active_requests - 1)
            state.last_used = now
            circuit = self._circuit_locked(active.target.provider.id, now)
            was_half_open = circuit.state is CircuitState.HALF_OPEN
            circuit.probe_active = False
            circuit.last_used = now

            if kind is not FailureKind.CANCELLED:
                state.failure_count += 1
                state.consecutive_failures += 1
                cooldown = self._cooldown_seconds(kind, retry_after)
                if cooldown > 0:
                    state.cooldown_until = max(state.cooldown_until, now + cooldown)
                if kind is FailureKind.MODEL_UNAVAILABLE:
                    model_id = active.target.model.canonical_id
                    self._model_locks[model_id] = max(
                        self._model_locks.get(model_id, 0.0),
                        now + self.config.model_lock_seconds,
                    )
                if kind in _PROVIDER_CIRCUIT_FAILURES:
                    self._record_provider_failure_locked(circuit, now)
                elif was_half_open or circuit.failure_count:
                    # A non-connectivity response proves provider reachability
                    # even though this request itself was rejected.
                    circuit.state = CircuitState.CLOSED
                    circuit.failure_count = 0
                    circuit.open_until = 0.0
                    circuit.open_cycles = 0

            self._prune_locked(now)
            return FailureDecision(
                kind=kind,
                failover_allowed=kind in _TRANSIENT_FAILURES,
                retry_after_seconds=retry_after,
                circuit_state=circuit.state,
            )

    def cancel_attempt(self, lease: AttemptLease) -> FailureDecision:
        return self.finish_failure(
            lease,
            FailureSignal(exception=asyncio.CancelledError()),
        )

    def record_cache_affinity(self, execution_key: str, affinity: float) -> None:
        if not isinstance(affinity, (int, float)) or not math.isfinite(affinity):
            raise RouterError("cache affinity must be a finite number")
        now = self._clock()
        with self._lock:
            state = self._state_locked(execution_key, now)
            state.cache_affinity = max(0.0, min(1.0, float(affinity)))
            state.last_used = now
            self._prune_locked(now)

    def public_snapshot(self) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            circuits = {
                provider_id: self._refresh_circuit_locked(circuit, now).state.value
                for provider_id, circuit in self._provider_circuits.items()
            }
            active_attempts = len(self._active_leases)
            target_entries = len(self._target_state)
            model_lock_count = sum(expires_at > now for expires_at in self._model_locks.values())
        return {
            "tenant_id": self.tenant_id,
            "active_attempts": active_attempts,
            "target_state_entries": target_entries,
            "model_lock_count": model_lock_count,
            "provider_circuits": circuits,
            "strategies": [strategy.value for strategy in RoutingStrategy],
        }

    def _order_locked(
        self,
        request: RouteRequest,
        targets: list[RouteTarget],
        *,
        scope: str,
        session_scope: Optional[str],
        rng: random.Random,
        now: float,
    ) -> tuple[list[RouteTarget], dict[str, float], dict[str, tuple[str, ...]]]:
        if not targets:
            return [], {}, {}
        baseline = self._baseline_order(request, targets)
        strategy = request.strategy
        scores: dict[str, float] = {}
        reasons: dict[str, tuple[str, ...]] = {}

        if strategy in {RoutingStrategy.PRIORITY, RoutingStrategy.FILL_FIRST, RoutingStrategy.PIPELINE}:
            return baseline, scores, reasons

        if strategy is RoutingStrategy.WEIGHTED:
            ordered = sorted(
                baseline,
                key=lambda target: rng.random() ** (1.0 / target.connection.weight),
                reverse=True,
            )
            return ordered, scores, reasons

        if strategy is RoutingStrategy.ROUND_ROBIN:
            index = self._round_robin.get(scope, 0) % len(baseline)
            ordered = baseline[index:] + baseline[:index]
            if not request.preview:
                self._round_robin[scope] = (index + 1) % len(baseline)
            return ordered, scores, reasons

        if strategy in {RoutingStrategy.RANDOM, RoutingStrategy.STRICT_RANDOM}:
            ordered = list(baseline)
            if strategy is RoutingStrategy.STRICT_RANDOM and not request.preview:
                keys = {target.execution_key for target in baseline}
                recent = [key for key in self._strict_random_decks.get(scope, []) if key in keys]
                available = sorted(keys - set(recent))
                if not available:
                    recent = []
                    available = sorted(keys)
                selected_key = rng.choice(available)
                recent.append(selected_key)
                self._strict_random_decks[scope] = recent[-self.config.max_attempts :]
                selected = next(target for target in baseline if target.execution_key == selected_key)
                remainder = [target for target in baseline if target.execution_key != selected_key]
                rng.shuffle(remainder)
                ordered = [selected, *remainder]
            else:
                rng.shuffle(ordered)
            return ordered, scores, reasons

        if strategy is RoutingStrategy.P2C:
            if len(baseline) == 1:
                return baseline, scores, reasons
            first, second = rng.sample(baseline, 2)
            winner = min(
                (first, second),
                key=lambda target: (
                    self._state_locked(target.execution_key, now).active_requests,
                    _priority_key(target),
                ),
            )
            return [winner, *[target for target in baseline if target != winner]], scores, reasons

        if strategy is RoutingStrategy.LEAST_USED:
            ordered = sorted(
                baseline,
                key=lambda target: (
                    self._state_locked(target.execution_key, now).request_count,
                    _priority_key(target),
                ),
            )
            return ordered, scores, reasons

        if strategy is RoutingStrategy.COST_OPTIMIZED:
            costs = {target.execution_key: _estimated_cost(target, request) for target in baseline}
            ordered = sorted(
                baseline,
                key=lambda target: (costs[target.execution_key], _priority_key(target)),
            )
            finite_costs = [cost for cost in costs.values() if math.isfinite(cost)]
            maximum = max(finite_costs, default=0.0)
            for target in baseline:
                cost = costs[target.execution_key]
                if math.isfinite(cost):
                    scores[target.execution_key] = 1.0 if maximum <= 0 else 1 - cost / maximum
                    reasons[target.execution_key] = (f"estimated_cost_usd={cost:.8f}",)
                else:
                    scores[target.execution_key] = 0.0
                    reasons[target.execution_key] = ("pricing=unknown",)
            return ordered, scores, reasons

        if strategy is RoutingStrategy.HEADROOM:
            return self._sort_by_factor(
                baseline,
                lambda target: _quota_factor(target),
                "quota_headroom",
            )

        if strategy in {RoutingStrategy.RESET_AWARE, RoutingStrategy.RESET_WINDOW}:
            reset_factor = _reset_factor if strategy is RoutingStrategy.RESET_AWARE else _reset_window_factor
            factor_name = "reset_urgency" if strategy is RoutingStrategy.RESET_AWARE else "reset_window"
            return self._sort_by_factor(
                baseline,
                lambda target: reset_factor(target, self._wall_clock()),
                factor_name,
            )

        if strategy in {RoutingStrategy.CONTEXT_OPTIMIZED, RoutingStrategy.CONTEXT_RELAY}:
            known = [target.model.context_window or 0 for target in baseline]
            maximum = max(known, default=0)
            return self._sort_by_factor(
                baseline,
                lambda target: (target.model.context_window or 0) / maximum if maximum else 0.5,
                "context_affinity",
            )

        if strategy is RoutingStrategy.CACHE_OPTIMIZED:
            return self._sort_by_factor(
                baseline,
                lambda target: self._state_locked(target.execution_key, now).cache_affinity,
                "cache_affinity",
            )

        if strategy is RoutingStrategy.LKGP:
            sticky = self._last_known_good.get(session_scope or "")
            if sticky and sticky.expires_at > now:
                match = next(
                    (target for target in baseline if target.execution_key == sticky.execution_key),
                    None,
                )
                if match is not None:
                    reasons[match.execution_key] = ("last_known_good=session_match",)
                    scores[match.execution_key] = 1.0
                    return [match, *[target for target in baseline if target != match]], scores, reasons
            return baseline, scores, reasons

        if strategy in {RoutingStrategy.AUTO, RoutingStrategy.FUSION}:
            factors = {target.execution_key: self._auto_factors(target, baseline, request, now) for target in baseline}
            for target in baseline:
                current = factors[target.execution_key]
                weights = _auto_weights(request.complexity)
                score = sum(weights[name] * current[name] for name in weights)
                scores[target.execution_key] = score
                reasons[target.execution_key] = tuple(f"{name}={value:.3f}" for name, value in current.items())
            ordered = sorted(
                baseline,
                key=lambda target: (-scores[target.execution_key], _priority_key(target)),
            )
            return ordered, scores, reasons

        raise RouterError(f"strategy is not implemented: {strategy.value}")

    def _sort_by_factor(
        self,
        baseline: list[RouteTarget],
        factor: Callable[[RouteTarget], float],
        reason_name: str,
    ) -> tuple[list[RouteTarget], dict[str, float], dict[str, tuple[str, ...]]]:
        scores = {target.execution_key: max(0.0, min(1.0, factor(target))) for target in baseline}
        reasons = {target.execution_key: (f"{reason_name}={scores[target.execution_key]:.3f}",) for target in baseline}
        ordered = sorted(
            baseline,
            key=lambda target: (-scores[target.execution_key], _priority_key(target)),
        )
        return ordered, scores, reasons

    def _auto_factors(
        self,
        target: RouteTarget,
        pool: list[RouteTarget],
        request: RouteRequest,
        now: float,
    ) -> dict[str, float]:
        state = self._state_locked(target.execution_key, now)
        known_costs = [_estimated_cost(item, request) for item in pool]
        finite_costs = [cost for cost in known_costs if math.isfinite(cost)]
        maximum_cost = max(finite_costs, default=0.0)
        cost = _estimated_cost(target, request)
        cost_factor = (
            0.5 if not math.isfinite(cost) else 1.0 if maximum_cost <= 0 else max(0.0, 1 - cost / maximum_cost)
        )
        known_latencies = [self._state_locked(item.execution_key, now).average_latency_ms for item in pool]
        finite_latencies = [value for value in known_latencies if value is not None]
        maximum_latency = max(finite_latencies, default=0.0)
        latency = state.average_latency_ms
        latency_factor = (
            0.5 if latency is None else 1.0 if maximum_latency <= 0 else max(0.0, 1 - latency / maximum_latency)
        )
        context_values = [item.model.context_window or 0 for item in pool]
        max_context = max(context_values, default=0)
        context_factor = (target.model.context_window or 0) / max_context if max_context else 0.5
        tier_factor = 1.0 - (int(target.tier) - int(RouteTier.SUBSCRIPTION)) / 3.0
        verification_factor = 0.2 if target.verification.status is VerificationStatus.FAILED else 1.0
        return {
            "tier": tier_factor,
            "quota": _quota_factor(target),
            "health": state.success_rate * verification_factor,
            "quality": self._quality_scores.get(target.model.canonical_id, 0.5),
            "cost": cost_factor,
            "latency": latency_factor,
            "context": context_factor,
            "cache": state.cache_affinity,
        }

    def _eligibility_locked(
        self,
        target: RouteTarget,
        now: float,
        *,
        minimum_quality: Optional[float] = None,
    ) -> _Eligibility:
        reasons = []
        if target.quota.status is QuotaStatus.EXHAUSTED:
            reasons.append("quota=exhausted")
        if target.verification.status is VerificationStatus.FAILED:
            reasons.append("verification=failed")
        if minimum_quality is not None:
            quality = self._quality_scores.get(target.model.canonical_id)
            if quality is None:
                reasons.append("quality_score=unknown")
            elif quality < minimum_quality:
                reasons.append(f"quality_score={quality:.3f}")
        state = self._state_locked(target.execution_key, now)
        if state.cooldown_until > now:
            reasons.append(f"cooldown_seconds={math.ceil(state.cooldown_until - now)}")
        model_lock_until = self._model_locks.get(target.model.canonical_id, 0.0)
        if model_lock_until > now:
            reasons.append(f"model_lock_seconds={math.ceil(model_lock_until - now)}")
        circuit = self._circuit_locked(target.provider.id, now)
        if circuit.state is CircuitState.OPEN:
            reasons.append(f"circuit_open_seconds={math.ceil(circuit.open_until - now)}")
        return _Eligibility(not reasons, tuple(reasons), circuit.state)

    def _state_locked(self, execution_key: str, now: float) -> _TargetState:
        state = self._target_state.get(execution_key)
        if state is None:
            state = _TargetState(last_used=now)
            self._target_state[execution_key] = state
        return state

    def _circuit_locked(self, provider_id: str, now: float) -> _ProviderCircuit:
        circuit = self._provider_circuits.get(provider_id)
        if circuit is None:
            circuit = _ProviderCircuit(last_used=now)
            self._provider_circuits[provider_id] = circuit
        return self._refresh_circuit_locked(circuit, now)

    @staticmethod
    def _refresh_circuit_locked(circuit: _ProviderCircuit, now: float) -> _ProviderCircuit:
        if circuit.state is CircuitState.OPEN and circuit.open_until <= now:
            circuit.state = CircuitState.HALF_OPEN
            circuit.probe_active = False
        return circuit

    def _record_provider_failure_locked(self, circuit: _ProviderCircuit, now: float) -> None:
        if circuit.state is CircuitState.HALF_OPEN:
            circuit.open_cycles += 1
            duration = min(
                self.config.provider_open_seconds * (2**circuit.open_cycles),
                self.config.max_provider_open_seconds,
            )
            circuit.state = CircuitState.OPEN
            circuit.open_until = now + duration
            circuit.failure_count = self.config.provider_failure_threshold
            return
        circuit.failure_count += 1
        if circuit.failure_count >= self.config.provider_failure_threshold:
            circuit.state = CircuitState.OPEN
            circuit.open_until = now + self.config.provider_open_seconds

    def _cooldown_seconds(
        self,
        kind: FailureKind,
        retry_after: Optional[float],
    ) -> float:
        if retry_after is not None and kind in _TRANSIENT_FAILURES:
            return retry_after
        if kind is FailureKind.RATE_LIMIT:
            return self.config.rate_limit_cooldown_seconds
        if kind is FailureKind.QUOTA_EXHAUSTED:
            return self.config.quota_cooldown_seconds
        if kind in {FailureKind.AUTHENTICATION, FailureKind.PERMISSION}:
            return self.config.credential_cooldown_seconds
        if kind in {FailureKind.TIMEOUT, FailureKind.NETWORK, FailureKind.SERVER}:
            return self.config.transient_cooldown_seconds
        return 0.0

    def _pop_lease_locked(self, lease: AttemptLease) -> AttemptLease:
        if lease.tenant_id != self.tenant_id:
            raise RouterError("TENANT_ATTEMPT_MISMATCH")
        active = self._active_leases.pop(lease.attempt_id, None)
        if active is None or active != lease:
            raise RouterError("attempt lease is unknown or already settled")
        return active

    def _targets_for_request(self, request: RouteRequest) -> tuple[RouteTarget, ...]:
        kwargs = {
            "required_capabilities": request.required_capabilities,
            "minimum_context": request.minimum_context,
            "include_exhausted": True,
        }
        if not request.candidate_models:
            return self.provider_manager.targets_for(request.model, **kwargs)
        targets: list[RouteTarget] = []
        seen: set[str] = set()
        for canonical in request.candidate_models:
            for target in self.provider_manager.targets_for(canonical, **kwargs):
                if target.execution_key in seen:
                    continue
                seen.add(target.execution_key)
                targets.append(target)
        return tuple(targets)

    @staticmethod
    def _baseline_order(request: RouteRequest, targets: list[RouteTarget]) -> list[RouteTarget]:
        if not request.candidate_models:
            return sorted(targets, key=_priority_key)
        rank = {
            model_id: index
            for index, model_id in enumerate(request.candidate_models)
        }
        return sorted(
            targets,
            key=lambda target: (
                rank.get(target.model.canonical_id, len(rank)),
                _priority_key(target),
            ),
        )

    def _session_scope(self, session_key: Optional[str], model: Optional[str]) -> Optional[str]:
        if not session_key:
            return None
        digest = hashlib.sha256(f"{self.tenant_id}\0{session_key}\0{model or '*'}".encode("utf-8")).hexdigest()
        return digest[:24]

    @staticmethod
    def _strategy_scope(request: RouteRequest, session_scope: Optional[str]) -> str:
        return f"{request.model or '*'}:{session_scope or 'global'}"

    def _prune_locked(self, now: float) -> None:
        for model_id, expires_at in tuple(self._model_locks.items()):
            if expires_at <= now:
                self._model_locks.pop(model_id, None)
        while len(self._model_locks) > self.config.max_state_entries:
            oldest_lock = min(self._model_locks, key=self._model_locks.__getitem__)
            self._model_locks.pop(oldest_lock, None)
        for key, sticky in tuple(self._last_known_good.items()):
            if sticky.expires_at <= now:
                self._last_known_good.pop(key, None)
        while len(self._last_known_good) > self.config.max_session_entries:
            self._last_known_good.pop(next(iter(self._last_known_good)))
        while len(self._target_state) > self.config.max_state_entries:
            removable = min(
                ((key, state) for key, state in self._target_state.items() if state.active_requests == 0),
                key=lambda item: item[1].last_used,
                default=None,
            )
            if removable is None:
                break
            self._target_state.pop(removable[0], None)
        while len(self._provider_circuits) > self.config.max_state_entries:
            removable_circuit = min(
                (
                    (key, circuit)
                    for key, circuit in self._provider_circuits.items()
                    if circuit.state is CircuitState.CLOSED and not circuit.probe_active
                ),
                key=lambda item: item[1].last_used,
                default=None,
            )
            if removable_circuit is None:
                break
            self._provider_circuits.pop(removable_circuit[0], None)
        for state_map in (self._round_robin, self._strict_random_decks):
            while len(state_map) > self.config.max_session_entries:
                state_map.pop(next(iter(state_map)))

    @staticmethod
    def _rank_score(index: int, count: int) -> float:
        if count <= 1:
            return 1.0
        return 1.0 - index / (count - 1)


def classify_failure(signal: FailureSignal) -> FailureKind:
    """Classify without retaining or returning secret-bearing error text."""
    if isinstance(signal.exception, asyncio.CancelledError):
        return FailureKind.CANCELLED
    if isinstance(signal.exception, (TimeoutError, asyncio.TimeoutError)):
        return FailureKind.TIMEOUT
    if isinstance(signal.exception, (ConnectionError, OSError)):
        return FailureKind.NETWORK

    status = signal.status_code
    text = signal.message.lower()
    if status == 401 or any(marker in text for marker in ("invalid_api_key", "unauthorized")):
        return FailureKind.AUTHENTICATION
    if status == 403 or "permission denied" in text:
        return FailureKind.PERMISSION
    if status in {400, 409, 413, 415, 422}:
        return FailureKind.INVALID_REQUEST
    if status in {404, 410} or "model_not_found" in text:
        return FailureKind.MODEL_UNAVAILABLE
    if status == 429:
        return (
            FailureKind.QUOTA_EXHAUSTED if any(marker in text for marker in _QUOTA_MARKERS) else FailureKind.RATE_LIMIT
        )
    if status == 408:
        return FailureKind.TIMEOUT
    if isinstance(status, int) and 500 <= status <= 599:
        return FailureKind.SERVER
    if any(marker in text for marker in ("timed out", "timeout")):
        return FailureKind.TIMEOUT
    if any(marker in text for marker in ("connection reset", "connection refused", "network error")):
        return FailureKind.NETWORK
    return FailureKind.UNKNOWN


def parse_retry_after(
    headers: Mapping[str, str],
    *,
    wall_clock: Optional[float] = None,
    maximum: float = 7 * 24 * 3600.0,
) -> Optional[float]:
    """Parse Retry-After seconds or HTTP-date and clamp it to a bounded window."""
    raw = next(
        (value for key, value in headers.items() if key.lower() == "retry-after"),
        None,
    )
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except (TypeError, ValueError):
        try:
            target = parsedate_to_datetime(raw).timestamp()
        except (TypeError, ValueError, OverflowError):
            return None
        seconds = target - (time.time() if wall_clock is None else wall_clock)
    if not math.isfinite(seconds):
        return None
    return max(0.0, min(seconds, maximum))


def _priority_key(target: RouteTarget) -> tuple[int, int, str, str, str]:
    return (
        int(target.tier),
        target.connection.priority,
        target.provider.id,
        target.model.id,
        target.connection.id,
    )


def _estimated_cost(target: RouteTarget, request: RouteRequest) -> float:
    pricing = target.model.pricing
    if not pricing.known:
        return math.inf
    assert pricing.input_per_million_usd is not None
    assert pricing.output_per_million_usd is not None
    return (
        request.estimated_input_tokens * pricing.input_per_million_usd
        + request.max_output_tokens * pricing.output_per_million_usd
    ) / 1_000_000


def _quota_factor(target: RouteTarget) -> float:
    if target.quota.status is QuotaStatus.EXHAUSTED:
        return 0.0
    if target.quota.remaining_fraction is not None:
        return target.quota.remaining_fraction
    if target.quota.status is QuotaStatus.HEALTHY:
        return 1.0
    if target.quota.status is QuotaStatus.APPROACHING_LIMIT:
        return 0.25
    # Unknown and unavailable telemetry remain eligible and neutral.
    return 0.5


def _reset_factor(target: RouteTarget, wall_clock: float) -> float:
    urgency = _reset_window_factor(target, wall_clock)
    remaining = target.quota.remaining_fraction
    utilization = 0.5 if remaining is None else 1.0 - remaining
    return 0.6 * urgency + 0.4 * utilization


def _reset_window_factor(target: RouteTarget, wall_clock: float) -> float:
    if not target.quota.reset_at:
        return 0.5
    try:
        reset_at = datetime.fromisoformat(target.quota.reset_at.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.5
    seconds = max(0.0, reset_at - wall_clock)
    return 1.0 - min(seconds / (7 * 24 * 3600), 1.0)


def _auto_weights(complexity: TaskComplexity) -> Mapping[str, float]:
    if complexity is TaskComplexity.SIMPLE:
        return {
            "tier": 0.15,
            "quota": 0.15,
            "health": 0.15,
            "quality": 0.05,
            "cost": 0.25,
            "latency": 0.10,
            "context": 0.10,
            "cache": 0.05,
        }
    if complexity is TaskComplexity.COMPLEX:
        return {
            "tier": 0.15,
            "quota": 0.15,
            "health": 0.15,
            "quality": 0.25,
            "cost": 0.05,
            "latency": 0.10,
            "context": 0.10,
            "cache": 0.05,
        }
    if complexity is TaskComplexity.CRITICAL:
        return {
            "tier": 0.10,
            "quota": 0.15,
            "health": 0.20,
            "quality": 0.30,
            "cost": 0.00,
            "latency": 0.10,
            "context": 0.10,
            "cache": 0.05,
        }
    return {
        "tier": 0.15,
        "quota": 0.15,
        "health": 0.15,
        "quality": 0.15,
        "cost": 0.15,
        "latency": 0.10,
        "context": 0.10,
        "cache": 0.05,
    }


def _mode_for_strategy(strategy: RoutingStrategy) -> RouteMode:
    if strategy is RoutingStrategy.CONTEXT_RELAY:
        return RouteMode.CONTEXT_RELAY
    if strategy is RoutingStrategy.FUSION:
        return RouteMode.FUSION
    if strategy is RoutingStrategy.PIPELINE:
        return RouteMode.PIPELINE
    return RouteMode.FALLBACK
