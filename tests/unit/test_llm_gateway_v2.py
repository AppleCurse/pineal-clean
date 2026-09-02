"""llm_gateway_v2 routing fabric — kilit ve pipeline testleri (ağ YOK).

Her test transport'ı enjekte eder; gerçek provider çağrısı yapılmaz.
"""
from __future__ import annotations

import pytest

from agent_core.services.llm_gateway_v2 import (
    Capability,
    CatalogUnavailable,
    CircuitBreaker,
    CostClass,
    ModelCandidate,
    PaidEscalationBlocked,
    ProviderDefaultBlocked,
    ProviderError,
    QuotaConfidence,
    QuotaState,
    RoutingFabric,
    TaskSpec,
    UnknownPriceBlocked,
    ValidationStage,
    catalog_row_to_candidate,
    discover_free_pool,
    passes_hard_constraints,
    score_candidate,
    validate_candidate,
)


def _free_candidate(**kw) -> ModelCandidate:
    base = dict(
        id="prov/model-x", provider="nous", base_url="https://x/v1",
        capabilities=[Capability.FAST_CHEAP], context_length=131_072,
        cost_class=CostClass.FREE, cost_per_1m_in=0.0, cost_per_1m_out=0.0,
        quota=QuotaState(rpm_remaining=30, rpd_remaining=100,
                         confidence=QuotaConfidence.ACCOUNT_VERIFIED, source="t"),
        verified=True, free_verified=True, validation_stage=ValidationStage.ELIGIBLE,
    )
    base.update(kw)
    return ModelCandidate(**base)


def _paid_candidate(**kw) -> ModelCandidate:
    base = dict(
        id="nous/paid-y", provider="nous", base_url="https://x/v1",
        capabilities=[Capability.FAST_CHEAP, Capability.STRONG_REASONING],
        context_length=131_072, cost_class=CostClass.PAID,
        cost_per_1m_in=0.20, cost_per_1m_out=1.20,
        quota=QuotaState(rpm_remaining=30, rpd_remaining=100,
                         confidence=QuotaConfidence.ACCOUNT_VERIFIED, source="t"),
        verified=True, free_verified=False, validation_stage=ValidationStage.ELIGIBLE,
        price_source="t",
    )
    base.update(kw)
    return ModelCandidate(**base)


async def _ok_transport(candidate, task):
    return {"model": candidate.id, "usage": {"prompt_tokens": 3, "completion_tokens": 2}}, {}


# --- KİLİTLER ----------------------------------------------------------------

def test_capability_lock_vision_rejects_text_only():
    task = TaskSpec(name="t", required_caps=[Capability.VISION], cost_class=CostClass.FREE)
    ok, reason = passes_hard_constraints(task, _free_candidate())
    assert not ok and reason == "capability_lock:vision"


def test_capability_lock_vision_accepts_vision_model():
    task = TaskSpec(name="t", required_caps=[Capability.VISION], cost_class=CostClass.FREE)
    ok, _ = passes_hard_constraints(task, _free_candidate(capabilities=[Capability.VISION]))
    assert ok


def test_paid_escalation_lock_free_task_rejects_paid_candidate():
    task = TaskSpec(name="t", cost_class=CostClass.FREE)
    ok, reason = passes_hard_constraints(task, _paid_candidate())
    assert not ok and reason == "paid_escalation_lock"


def test_unknown_model_lock_unverified_excluded():
    task = TaskSpec(name="t", cost_class=CostClass.FREE)
    ok, reason = passes_hard_constraints(task, _free_candidate(verified=False))
    assert not ok and reason == "unknown_model_lock"


def test_free_unverified_candidate_excluded():
    task = TaskSpec(name="t", cost_class=CostClass.FREE)
    ok, reason = passes_hard_constraints(task, _free_candidate(free_verified=False))
    assert not ok and reason == "free_unverified"


def test_unknown_price_lock_blocks_paid_candidate():
    task = TaskSpec(name="t", cost_class=CostClass.PAID, paid_allowed=True, budget_remaining=10.0)
    ok, reason = passes_hard_constraints(task, _paid_candidate(cost_per_1m_in=None))
    assert not ok and reason == "unknown_price_lock"


async def test_provider_default_lock_blocks_implicit_model():
    fabric = RoutingFabric([_free_candidate()])
    task = TaskSpec(name="t", cost_class=CostClass.FREE, requested_model_explicit=False)
    with pytest.raises(ProviderDefaultBlocked):
        await fabric.route(task, _ok_transport)


async def test_free_exhausted_raises_when_paid_forbidden():
    fabric = RoutingFabric([])  # free havuz boş
    task = TaskSpec(name="t", cost_class=CostClass.FREE, paid_allowed=False)
    with pytest.raises(PaidEscalationBlocked):
        await fabric.route(task, _ok_transport)


async def test_escalation_blocked_when_budget_missing():
    fabric = RoutingFabric([_paid_candidate()])
    # Aday var ama FREE görev hard-constraint nedeniyle PAID adayı seçemez,
    # free havuz boş -> escalation; bütçe None -> BLOCK.
    task = TaskSpec(name="t", cost_class=CostClass.FREE, paid_allowed=True, budget_remaining=None)
    with pytest.raises(PaidEscalationBlocked):
        await fabric.route(task, _ok_transport)


async def test_escalation_blocked_when_budget_below_estimated_cost():
    fabric = RoutingFabric([_paid_candidate()])
    task = TaskSpec(name="t", cost_class=CostClass.FREE, paid_allowed=True,
                    budget_remaining=0.01, estimated_cost=0.50)
    with pytest.raises(PaidEscalationBlocked):
        await fabric.route(task, _ok_transport)


async def test_escalation_succeeds_when_three_conditions_met():
    fabric = RoutingFabric([_paid_candidate()])
    task = TaskSpec(name="t", cost_class=CostClass.FREE, paid_allowed=True,
                    budget_remaining=5.0, estimated_cost=0.10)
    result = await fabric.route(task, _ok_transport)
    assert result.audit.cost_class == "paid"
    assert result.audit.provider == "nous"


async def test_escalation_raises_unknown_price_when_paid_unpriced():
    fabric = RoutingFabric([_paid_candidate(cost_per_1m_in=None, cost_per_1m_out=None)])
    task = TaskSpec(name="t", cost_class=CostClass.FREE, paid_allowed=True, budget_remaining=5.0)
    with pytest.raises(UnknownPriceBlocked):
        await fabric.route(task, _ok_transport)


# --- KOTA + DEVRE KESİCİ ------------------------------------------------------ #

async def test_quota_exhausted_candidate_skipped():
    fabric = RoutingFabric([_free_candidate(quota=QuotaState(rpm_remaining=0, rpd_remaining=0))])
    task = TaskSpec(name="t", cost_class=CostClass.FREE)
    with pytest.raises(PaidEscalationBlocked):
        await fabric.route(task, _ok_transport)


async def test_429_cooldowns_provider_and_marks_quota():
    async def rate_limited(candidate, task):
        raise ProviderError(candidate.provider, 429, "rate limit")

    cand = _free_candidate()
    fabric = RoutingFabric([cand])
    task = TaskSpec(name="t", cost_class=CostClass.FREE)
    with pytest.raises(PaidEscalationBlocked):
        await fabric.route(task, rate_limited)
    assert cand.quota.rpm_remaining == 0
    assert fabric.breaker.is_open("nous")


def test_circuit_breaker_quarantines_4xx():
    breaker = CircuitBreaker()
    breaker.record_error(ProviderError("nous", 403, "forbidden"))
    assert breaker.is_open("nous")
    breaker.reset_quarantine("nous")
    assert not breaker.is_open("nous")


# --- AUDIT                                                                    #

async def test_actual_model_audit_records_requested_vs_actual():
    async def swapped(candidate, task):
        return {"model": "başka-model", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}, {}

    fabric = RoutingFabric([_free_candidate()])
    result = await fabric.route(TaskSpec(name="t", cost_class=CostClass.FREE), swapped)
    assert result.audit.requested_model == "prov/model-x"
    assert result.audit.actual_model == "başka-model"


async def test_quota_terfi_observed_when_headers_present():
    async def with_headers(candidate, task):
        return {"model": candidate.id}, {"x-ratelimit-remaining-requests": "17"}

    cand = _free_candidate(quota=QuotaState(confidence=QuotaConfidence.ESTIMATED))
    fabric = RoutingFabric([cand])
    await fabric.route(TaskSpec(name="t", cost_class=CostClass.FREE), with_headers)
    assert cand.quota.rpm_remaining == 17
    assert cand.quota.confidence is QuotaConfidence.OBSERVED


# --- DISCOVERY (network-free parse) ------------------------------------------- #

def test_catalog_row_zero_pricing_is_free_verified():
    row = {"id": "upstage/solar-pro4:free",
           "pricing": {"prompt": "0", "completion": "0.0"},
           "architecture": {"modality": "text+image->text"},
           "context_length": 524_288}
    cand = catalog_row_to_candidate(row, provider="nous", base_url="https://x/v1", api_key_env="NOUS_API_KEY")
    assert cand is not None
    assert cand.free_verified is True
    assert cand.cost_class is CostClass.FREE
    assert cand.verified is False  # DISCOVERY kendi kendini ELIGIBLE yapmaz
    assert cand.validation_stage is ValidationStage.FREE_VALIDATED
    assert Capability.VISION in cand.capabilities
    assert Capability.LONG_CONTEXT in cand.capabilities
    # terfi yalnız validate ile
    validate_candidate(cand)
    assert cand.verified is True and cand.validation_stage is ValidationStage.ELIGIBLE


def test_catalog_row_without_pricing_fails_closed_not_free():
    row = {"id": "meituan/longcat-2.0:free", "context_length": 1_000_000}
    cand = catalog_row_to_candidate(row, provider="nous", base_url="https://x/v1", api_key_env="K")
    assert cand is not None
    assert cand.free_verified is False
    assert cand.cost_class is CostClass.PAID      # fiyat bilinmiyorsa free SAYILMAZ
    assert cand.cost_per_1m_in is None            # UNKNOWN_PRICE_LOCK devrede


async def test_discover_free_pool_filters_and_fail_closed():
    async def fake_get(url, headers):
        return 200, {"data": [
            {"id": "a/free:free", "pricing": {"prompt": 0, "completion": 0}, "context_length": 128_000},
            {"id": "b/paid", "pricing": {"prompt": 0.5, "completion": 1.0}, "context_length": 128_000},
            {"id": "c/noprice", "context_length": 128_000},
        ]}

    pool = await discover_free_pool(provider="nous", base_url="https://x/v1", http_get=fake_get)
    ids = [c.id for c in pool]
    assert ids == ["a/free:free"]
    assert pool[0].free_verified and not pool[0].verified

    async def broken_get(url, headers):
        return 503, {}

    with pytest.raises(CatalogUnavailable):
        await discover_free_pool(provider="nous", base_url="https://x", http_get=broken_get)


# --- SKORLAMA -------------------------------------------------------------------- #

def test_scoring_no_observed_latency_is_neutral_not_fabricated():
    task = TaskSpec(name="t", cost_class=CostClass.FREE)
    a = _free_candidate(id="a/x")
    b = _free_candidate(id="b/x")
    # İkisi de latency'siz -> skorlar eşit (RPM artık latency yerine geçmiyor)
    assert score_candidate(task, a) == score_candidate(task, b)
    b.observed_latency_ms = 0.0
    assert score_candidate(task, b) > score_candidate(task, a)
