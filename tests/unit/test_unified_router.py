"""Pure planning, strategy, stickiness, cooldown, and circuit contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime

import pytest

from agent_core.services.provider_manager import (
    AccessMethod,
    ConnectionType,
    ConnectionVerification,
    ModelDescriptor,
    ModelPricing,
    ProviderCatalog,
    ProviderConnection,
    ProviderDescriptor,
    ProviderManager,
    ProviderProtocol,
    QuotaSnapshot,
    QuotaStatus,
    RouteTier,
    VerificationStatus,
)
from agent_core.services.unified_router import (
    CircuitState,
    FailureKind,
    FailureSignal,
    RouteMode,
    RouteRequest,
    RouteUnavailable,
    RouterConfig,
    RouterError,
    RoutingStrategy,
    TaskComplexity,
    UnifiedRouter,
    classify_failure,
    parse_retry_after,
)


class FakeClock:
    def __init__(self, monotonic: float = 100.0, wall: float = 1_800_000_000.0):
        self.monotonic = monotonic
        self.wall = wall

    def tick(self, seconds: float) -> None:
        self.monotonic += seconds
        self.wall += seconds


def _provider(
    provider_id: str,
    *,
    tier: RouteTier,
    context: int = 32_000,
    input_price: float | None = None,
    output_price: float | None = None,
) -> ProviderDescriptor:
    model = ModelDescriptor(
        provider_id=provider_id,
        id="chat",
        display_name=f"{provider_id} chat",
        capabilities=frozenset({"chat", "tools", "streaming"}),
        context_window=context,
        pricing=ModelPricing(
            input_per_million_usd=input_price,
            output_per_million_usd=output_price,
        ),
    )
    return ProviderDescriptor(
        id=provider_id,
        display_name=provider_id,
        protocol=ProviderProtocol.OPENAI_CHAT,
        access_method=AccessMethod.OFFICIAL_API,
        connection_types=(ConnectionType.API_KEY,),
        default_tier=tier,
        base_url=f"https://{provider_id}.example.test/v1",
        models=(model,),
    )


def _connection(
    provider_id: str,
    *,
    connection_id: str | None = None,
    priority: int = 100,
    weight: float = 1.0,
) -> ProviderConnection:
    return ProviderConnection(
        id=connection_id or f"{provider_id}-connection",
        tenant_id="tenant-a",
        provider_id=provider_id,
        connection_type=ConnectionType.API_KEY,
        credential_ref=f"vault/{provider_id}/secret-key",
        priority=priority,
        weight=weight,
    )


def _router(
    providers: tuple[ProviderDescriptor, ...] | None = None,
    *,
    connections: tuple[ProviderConnection, ...] | None = None,
    clock: FakeClock | None = None,
    config: RouterConfig | None = None,
    quality_scores: dict[str, float] | None = None,
) -> tuple[UnifiedRouter, ProviderManager, FakeClock]:
    providers = providers or (
        _provider("subscription", tier=RouteTier.SUBSCRIPTION, input_price=10, output_price=20),
        _provider("api-key", tier=RouteTier.API_KEY, input_price=1, output_price=2),
        _provider("cheap", tier=RouteTier.CHEAP, input_price=0.1, output_price=0.2),
        _provider("free", tier=RouteTier.FREE, input_price=0, output_price=0),
    )
    manager = ProviderManager(ProviderCatalog(providers), "tenant-a")
    for connection in connections or tuple(_connection(provider.id) for provider in providers):
        manager.configure_connection(connection)
    clock = clock or FakeClock()
    return (
        UnifiedRouter(
            manager,
            config=config,
            quality_scores=quality_scores,
            clock=lambda: clock.monotonic,
            wall_clock=lambda: clock.wall,
        ),
        manager,
        clock,
    )


def test_priority_plan_uses_four_tiers_and_never_resolves_credentials():
    router, _, _ = _router()
    plan = router.plan(RouteRequest(strategy=RoutingStrategy.PRIORITY))

    assert [candidate.target.tier for candidate in plan.candidates] == list(RouteTier)
    assert plan.selected_execution_key.startswith("subscription-connection:")
    assert plan.attempt_order == tuple(candidate.execution_key for candidate in plan.candidates)
    preview = plan.as_dict()
    assert preview["plan_only"] is True
    assert "vault/" not in repr(preview)
    assert router.public_snapshot()["active_attempts"] == 0


@pytest.mark.parametrize("strategy", list(RoutingStrategy))
def test_every_declared_strategy_produces_a_bounded_non_executing_plan(strategy):
    router, _, _ = _router()
    plan = router.plan(RouteRequest(strategy=strategy, seed=7, preview=True))

    assert len(plan.attempt_order) == 4
    assert set(plan.attempt_order) == {candidate.execution_key for candidate in plan.candidates}
    assert all(0 <= candidate.score <= 1 for candidate in plan.candidates)
    expected_mode = {
        RoutingStrategy.CONTEXT_RELAY: RouteMode.CONTEXT_RELAY,
        RoutingStrategy.FUSION: RouteMode.FUSION,
        RoutingStrategy.PIPELINE: RouteMode.PIPELINE,
    }.get(strategy, RouteMode.FALLBACK)
    assert plan.mode is expected_mode
    assert plan.parallel_width == (3 if strategy is RoutingStrategy.FUSION else 1)
    assert router.public_snapshot()["active_attempts"] == 0


def test_round_robin_rotates_but_preview_is_side_effect_free():
    provider = _provider("shared", tier=RouteTier.API_KEY)
    connections = (
        _connection("shared", connection_id="first"),
        _connection("shared", connection_id="second"),
        _connection("shared", connection_id="third"),
    )
    router, _, _ = _router((provider,), connections=connections)
    request = RouteRequest(model="shared/chat", strategy=RoutingStrategy.ROUND_ROBIN)

    first = router.plan(request).selected_execution_key
    assert (
        router.plan(
            RouteRequest(
                model="shared/chat",
                strategy=RoutingStrategy.ROUND_ROBIN,
                preview=True,
            )
        ).selected_execution_key
        == "second:shared/chat"
    )
    second = router.plan(request).selected_execution_key
    third = router.plan(request).selected_execution_key
    assert [first, second, third] == [
        "first:shared/chat",
        "second:shared/chat",
        "third:shared/chat",
    ]


def test_strict_random_avoids_repeats_within_its_bounded_window():
    router, _, _ = _router()
    request = RouteRequest(strategy=RoutingStrategy.STRICT_RANDOM, seed=17)
    selections = [router.plan(request).selected_execution_key for _ in range(4)]
    assert len(set(selections)) == 4
    assert router.plan(request).selected_execution_key in set(selections)


def test_cost_headroom_context_and_cache_strategies_use_explicit_metadata():
    providers = (
        _provider("expensive", tier=RouteTier.API_KEY, context=8_000, input_price=10, output_price=20),
        _provider("cheap", tier=RouteTier.API_KEY, context=128_000, input_price=0.1, output_price=0.2),
    )
    router, manager, _ = _router(providers)
    manager.update_quota(
        "expensive-connection",
        QuotaSnapshot(status=QuotaStatus.HEALTHY, remaining_fraction=0.9),
    )
    manager.update_quota(
        "cheap-connection",
        QuotaSnapshot(status=QuotaStatus.APPROACHING_LIMIT, remaining_fraction=0.1),
    )

    assert (
        router.plan(RouteRequest(strategy=RoutingStrategy.COST_OPTIMIZED)).candidates[0].target.provider.id == "cheap"
    )
    assert router.plan(RouteRequest(strategy=RoutingStrategy.HEADROOM)).candidates[0].target.provider.id == "expensive"
    assert (
        router.plan(RouteRequest(strategy=RoutingStrategy.CONTEXT_OPTIMIZED)).candidates[0].target.provider.id
        == "cheap"
    )

    cheap_key = "cheap-connection:cheap/chat"
    router.record_cache_affinity(cheap_key, 0.95)
    assert router.plan(RouteRequest(strategy=RoutingStrategy.CACHE_OPTIMIZED)).selected_execution_key == cheap_key


def test_auto_strategy_changes_quality_cost_balance_with_task_complexity():
    providers = (
        _provider("high-quality", tier=RouteTier.API_KEY, input_price=20, output_price=40),
        _provider("economy", tier=RouteTier.API_KEY, input_price=0, output_price=0),
    )
    router, _, _ = _router(
        providers,
        quality_scores={"high-quality/chat": 1.0, "economy/chat": 0.1},
    )

    simple = router.plan(
        RouteRequest(
            strategy=RoutingStrategy.AUTO,
            complexity=TaskComplexity.SIMPLE,
        )
    )
    critical = router.plan(
        RouteRequest(
            strategy=RoutingStrategy.AUTO,
            complexity=TaskComplexity.CRITICAL,
            minimum_quality=0.8,
        )
    )
    assert simple.candidates[0].target.provider.id == "economy"
    assert critical.selected_execution_key == "high-quality-connection:high-quality/chat"
    assert not critical.candidate("economy-connection:economy/chat").eligible


def test_exhausted_targets_are_explained_but_never_attempted():
    router, manager, _ = _router()
    manager.update_quota(
        "subscription-connection",
        QuotaSnapshot(status=QuotaStatus.EXHAUSTED, remaining_fraction=0),
    )

    plan = router.plan(RouteRequest(strategy=RoutingStrategy.PRIORITY))
    exhausted = next(candidate for candidate in plan.candidates if candidate.target.provider.id == "subscription")
    assert not exhausted.eligible
    assert exhausted.reasons == ("quota=exhausted",)
    assert exhausted.execution_key not in plan.attempt_order
    assert plan.selected_execution_key.startswith("api-key-connection:")


def test_failed_connection_verification_is_not_routed():
    router, manager, _ = _router()
    manager.update_verification(
        "subscription-connection",
        ConnectionVerification(status=VerificationStatus.FAILED),
    )
    plan = router.plan(RouteRequest(strategy=RoutingStrategy.PRIORITY))

    failed = plan.candidate("subscription-connection:subscription/chat")
    assert not failed.eligible
    assert failed.reasons == ("verification=failed",)
    assert plan.selected_execution_key.startswith("api-key-connection:")


def test_attempt_revalidates_manager_state_after_planning():
    provider = _provider("shared", tier=RouteTier.API_KEY)
    router, manager, _ = _router((provider,))
    stale = router.plan(RouteRequest(model="shared/chat"))
    manager.update_quota(
        "shared-connection",
        QuotaSnapshot(status=QuotaStatus.EXHAUSTED, remaining_fraction=0),
    )

    with pytest.raises(RouteUnavailable, match="became unavailable"):
        router.begin_attempt(stale)


def test_retry_after_cools_one_account_and_allows_bounded_failover():
    provider = _provider("shared", tier=RouteTier.API_KEY)
    router, _, clock = _router(
        (provider,),
        connections=(
            _connection("shared", connection_id="first"),
            _connection("shared", connection_id="second"),
        ),
    )
    plan = router.plan(RouteRequest(model="shared/chat", strategy=RoutingStrategy.PRIORITY))
    lease = router.begin_attempt(plan)
    decision = router.finish_failure(
        lease,
        FailureSignal(status_code=429, headers={"Retry-After": "30"}),
    )

    assert decision.kind is FailureKind.RATE_LIMIT
    assert decision.failover_allowed
    assert decision.retry_after_seconds == 30
    cooldown_plan = router.plan(RouteRequest(model="shared/chat", strategy=RoutingStrategy.PRIORITY))
    assert cooldown_plan.selected_execution_key == "second:shared/chat"
    assert not cooldown_plan.candidate("first:shared/chat").eligible

    clock.tick(30)
    assert router.plan(RouteRequest(model="shared/chat")).candidate("first:shared/chat").eligible


def test_authentication_error_is_not_blindly_failed_over_and_cools_bad_account():
    provider = _provider("shared", tier=RouteTier.API_KEY)
    router, _, _ = _router(
        (provider,),
        connections=(
            _connection("shared", connection_id="first"),
            _connection("shared", connection_id="second"),
        ),
    )
    request = RouteRequest(model="shared/chat", strategy=RoutingStrategy.PRIORITY)
    lease = router.begin_attempt(router.plan(request))
    decision = router.finish_failure(lease, FailureSignal(status_code=401))

    assert decision.kind is FailureKind.AUTHENTICATION
    assert not decision.failover_allowed
    new_call = router.plan(request)
    assert new_call.selected_execution_key == "second:shared/chat"
    assert not new_call.candidate("first:shared/chat").eligible


def test_nonretryable_model_error_locks_model_across_accounts_without_blind_failover():
    provider = _provider("shared", tier=RouteTier.API_KEY)
    router, _, _ = _router(
        (provider,),
        connections=(
            _connection("shared", connection_id="first"),
            _connection("shared", connection_id="second"),
        ),
    )
    plan = router.plan(RouteRequest(model="shared/chat"))
    lease = router.begin_attempt(plan)
    decision = router.finish_failure(lease, FailureSignal(status_code=404, message="model_not_found"))

    assert decision.kind is FailureKind.MODEL_UNAVAILABLE
    assert not decision.failover_allowed
    locked = router.plan(RouteRequest(model="shared/chat"))
    assert locked.attempt_order == ()
    assert all("model_lock_seconds=" in candidate.reasons[0] for candidate in locked.candidates)
    assert router.public_snapshot()["model_lock_count"] == 1


def test_provider_circuit_opens_then_allows_one_half_open_probe():
    provider = _provider("unstable", tier=RouteTier.API_KEY)
    config = RouterConfig(
        provider_failure_threshold=3,
        provider_open_seconds=20,
        transient_cooldown_seconds=0,
    )
    router, _, clock = _router((provider,), config=config)
    request = RouteRequest(model="unstable/chat")

    for _ in range(3):
        lease = router.begin_attempt(router.plan(request))
        decision = router.finish_failure(lease, FailureSignal(status_code=503))
    assert decision.circuit_state is CircuitState.OPEN
    assert router.plan(request).attempt_order == ()

    clock.tick(20)
    probe_plan = router.plan(request)
    first_probe = router.begin_attempt(probe_plan)
    with pytest.raises(Exception, match="probe is already active"):
        router.begin_attempt(probe_plan)
    router.finish_success(first_probe)
    assert router.public_snapshot()["provider_circuits"] == {"unstable": "closed"}


def test_cancellation_is_not_a_failure_and_attempt_identity_is_single_use():
    router, _, _ = _router()
    lease = router.begin_attempt(router.plan(RouteRequest()))
    decision = router.cancel_attempt(lease)

    assert decision.kind is FailureKind.CANCELLED
    assert not decision.failover_allowed
    assert router.public_snapshot()["active_attempts"] == 0
    with pytest.raises(RouterError, match="already settled"):
        router.cancel_attempt(lease)


def test_lkgp_is_session_scoped_and_session_value_is_not_exposed():
    router, _, _ = _router()
    session_secret = "customer@example.test/raw-session-token"
    original = router.plan(RouteRequest(session_key=session_secret))
    second_key = original.attempt_order[1]
    lease = router.begin_attempt(original, second_key)
    router.finish_success(lease)

    sticky = router.plan(
        RouteRequest(
            strategy=RoutingStrategy.LKGP,
            session_key=session_secret,
        )
    )
    unrelated = router.plan(
        RouteRequest(
            strategy=RoutingStrategy.LKGP,
            session_key="another-session",
        )
    )
    assert sticky.selected_execution_key == second_key
    assert unrelated.selected_execution_key != second_key
    assert session_secret not in repr(sticky)
    assert session_secret not in repr(sticky.as_dict())


def test_p2c_prefers_target_without_an_active_request():
    provider = _provider("shared", tier=RouteTier.API_KEY)
    router, _, _ = _router(
        (provider,),
        connections=(
            _connection("shared", connection_id="first"),
            _connection("shared", connection_id="second"),
        ),
    )
    priority_plan = router.plan(RouteRequest(model="shared/chat", strategy=RoutingStrategy.PRIORITY))
    active = router.begin_attempt(priority_plan, "first:shared/chat")
    p2c = router.plan(RouteRequest(model="shared/chat", strategy=RoutingStrategy.P2C, seed=1))
    assert p2c.selected_execution_key == "second:shared/chat"
    router.finish_success(active)


def test_fallback_schedule_has_an_explicit_attempt_bound():
    providers = tuple(_provider(f"provider-{index}", tier=RouteTier.API_KEY) for index in range(12))
    router, _, _ = _router(providers, config=RouterConfig(max_attempts=3))
    plan = router.plan(RouteRequest(strategy=RoutingStrategy.PRIORITY))

    assert len(plan.candidates) == 12
    assert len(plan.attempt_order) == 3
    with pytest.raises(RouteUnavailable, match="no eligible selected target"):
        router.begin_attempt(plan, plan.candidates[4].execution_key)


def test_runtime_observation_state_is_bounded():
    router, _, _ = _router(config=RouterConfig(max_state_entries=100))
    for index in range(150):
        router.record_cache_affinity(f"synthetic-{index}", 0.5)
    assert router.public_snapshot()["target_state_entries"] == 100


def test_failure_classification_is_conservative_and_retry_after_supports_http_dates():
    assert classify_failure(FailureSignal(status_code=401)) is FailureKind.AUTHENTICATION
    assert classify_failure(FailureSignal(status_code=429, message="insufficient_quota")) is FailureKind.QUOTA_EXHAUSTED
    assert classify_failure(FailureSignal(status_code=429)) is FailureKind.RATE_LIMIT
    assert classify_failure(FailureSignal(status_code=500)) is FailureKind.SERVER
    assert classify_failure(FailureSignal(message="unmatched vendor failure")) is FailureKind.UNKNOWN

    wall = datetime(2027, 1, 15, tzinfo=timezone.utc).timestamp()
    retry_date = format_datetime(datetime.fromtimestamp(wall + 90, timezone.utc), usegmt=True)
    assert parse_retry_after({"retry-after": retry_date}, wall_clock=wall) == 90
    assert parse_retry_after({"Retry-After": "not-a-date"}, wall_clock=wall) is None
    assert parse_retry_after({"Retry-After": "9999"}, wall_clock=wall, maximum=120) == 120
