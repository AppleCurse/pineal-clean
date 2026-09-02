"""Gateway-level regression contracts: telemetry, pricing guard, retry, cap."""

import pytest

from agent_core.services.llm_gateway import LLMGateway, SpendCapExceeded


def _gateway(**env) -> LLMGateway:
    gateway = LLMGateway()
    gateway.set_key("sk-test", unlock_live=True)
    gateway.cache = None
    return gateway


# --------------------------------------------------------------------------- #
# Telemetry contract
# --------------------------------------------------------------------------- #
def test_log_record_carries_requested_and_actual_model():
    gateway = LLMGateway()
    record = gateway._log_call(
        "chat.completions",
        "actual/model",
        "provider-x",
        requested_model="requested/model",
        fallback_reason="429_RATE_LIMITED",
        quota_status="healthy",
    )
    assert record["requested_model"] == "requested/model"
    assert record["actual_model"] == "actual/model"
    assert record["model"] == "actual/model"  # backwards-compat alias
    assert record["fallback_reason"] == "429_RATE_LIMITED"
    assert record["quota_status"] == "healthy"
    for field in ("call_id", "task_id", "agent_id", "provider", "attempt",
                  "cache_hit", "prompt_tokens", "completion_tokens", "cost_usd",
                  "started_at", "finished_at", "duration_ms", "error"):
        assert field in record


def test_annotate_call_merges_bounded_fields():
    gateway = LLMGateway()
    record = gateway._log_call("query", "m/1", "p")
    gateway.annotate_call(record["call_id"], fallback_reason="TIMEOUT", quota_status="unknown", bogus="x")
    assert record["fallback_reason"] == "TIMEOUT"
    assert record["quota_status"] == "unknown"
    assert "bogus" not in record


# --------------------------------------------------------------------------- #
# Pricing guard
# --------------------------------------------------------------------------- #
def test_pricing_guard_denies_unknown_price():
    gateway = LLMGateway()
    with pytest.raises(RuntimeError, match="UNKNOWN_PRICING"):
        gateway._pricing_guard("totally/unknown-model", kind="query")


def test_pricing_guard_accepts_explicit_pricing():
    gateway = LLMGateway()
    gateway._pricing_guard(
        "totally/unknown-model",
        kind="query",
        pricing={"in": 0.0, "out": 0.0},
    )


def test_pricing_guard_accepts_known_model():
    gateway = LLMGateway()
    gateway._pricing_guard("upstage/solar-pro4", kind="query")


def test_unknown_pricing_never_bypasses_spend_cap():
    gateway = LLMGateway()
    gateway.spend_cap_usd = 1.0
    # A model with no price cannot reserve, so it must be denied outright when
    # a spend cap is active (rather than being accounted as $0).
    with pytest.raises(RuntimeError, match="UNKNOWN_PRICING"):
        gateway._pricing_guard("totally/unknown-model", kind="query")
    assert gateway.spend_usd == 0.0


# --------------------------------------------------------------------------- #
# Retry classification
# --------------------------------------------------------------------------- #
class _HTTPError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503])
def test_transient_status_codes_are_retryable(status):
    assert LLMGateway._is_retryable_error(_HTTPError(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_permanent_status_codes_are_not_retryable(status):
    assert LLMGateway._is_retryable_error(_HTTPError(status)) is False


def test_connection_and_timeout_errors_are_retryable():
    assert LLMGateway._is_retryable_error(TimeoutError("timed out")) is True
    assert LLMGateway._is_retryable_error(ConnectionError("connection refused")) is True


# --------------------------------------------------------------------------- #
# Spend cap reservation lifecycle
# --------------------------------------------------------------------------- #
def test_reserve_release_settle_lifecycle():
    gateway = LLMGateway()
    gateway.spend_cap_usd = 10.0
    gateway._reserve_budget("call-1", 0.5)
    assert gateway.budget_status()["active_reservations"] == 1
    gateway._release_budget("call-1")
    assert gateway.budget_status()["active_reservations"] == 0
    assert gateway.budget_status()["reserved_usd"] == 0


def test_reserve_over_cap_raises_spend_cap_exceeded():
    gateway = LLMGateway()
    gateway.spend_cap_usd = 1.0
    gateway.spend_usd = 0.9
    with pytest.raises(SpendCapExceeded):
        gateway._reserve_budget("call-2", 0.5)
    assert gateway.budget_status()["active_reservations"] == 0


# --------------------------------------------------------------------------- #
# Model substitution helper
# --------------------------------------------------------------------------- #
def _helper_import():
    from agent_core.services.final_routing_policy import model_substitution_allowed

    return model_substitution_allowed


def test_model_substitution_allowed_semantics():
    allowed = _helper_import()
    assert allowed("openai/gpt-oss-120b", "openai/gpt-oss-120b") is True
    assert allowed("openai/gpt-oss-120b", "gpt-oss-120b") is False
    assert allowed("", "") is True  # unknown on both sides is not a substitution
