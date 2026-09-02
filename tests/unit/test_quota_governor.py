"""Quota governor: header-aware rate/token accounting, unknown-as-unknown."""

import pytest

from agent_core.services.provider_manager import QuotaStatus
from agent_core.services.quota_governor import QuotaGovernor, QuotaLimits


def _governor(**overrides) -> QuotaGovernor:
    limits = {
        "groq": QuotaLimits(rpm=30, rpd=14_400),
        "cerebras": QuotaLimits(rpm=5, tpm=30_000, tpd=1_000_000),
    }
    limits.update(overrides)
    return QuotaGovernor(limits)


def test_policy_seeded_governor_knows_groq_and_cerebras():
    governor = QuotaGovernor.from_policy()
    assert governor.limits_for("groq").rpm == 30
    assert governor.limits_for("groq").rpd == 14_400
    assert governor.limits_for("cerebras").rpm == 5
    assert governor.limits_for("cerebras").tpm == 30_000
    assert governor.limits_for("cerebras").tpd == 1_000_000


def test_unknown_provider_quota_is_unknown_not_unlimited():
    governor = _governor()
    snapshot = governor.snapshot("openrouter", "upstage/solar-pro4")
    assert snapshot.status is QuotaStatus.UNKNOWN
    assert snapshot.source == "unknown"


def test_groq_local_accounting_approaches_then_exhausts_rpm():
    governor = _governor()
    for _ in range(29):
        governor.record_success("groq", "openai/gpt-oss-120b")
    snapshot = governor.snapshot("groq", "openai/gpt-oss-120b")
    assert snapshot.status in {QuotaStatus.HEALTHY, QuotaStatus.APPROACHING_LIMIT}
    for _ in range(29, 40):
        governor.record_success("groq", "openai/gpt-oss-120b")
    assert governor.snapshot("groq", "openai/gpt-oss-120b").status is QuotaStatus.EXHAUSTED


def test_cerebras_token_limit_exhausts_by_tokens():
    governor = _governor()
    governor.record_success(
        "cerebras",
        "gpt-oss-120b",
        prompt_tokens=30_000,
        completion_tokens=0,
    )
    assert governor.snapshot("cerebras", "gpt-oss-120b").status is QuotaStatus.EXHAUSTED


def test_header_remaining_requests_is_authoritative():
    governor = _governor()
    governor.record_success(
        "groq",
        "openai/gpt-oss-120b",
        headers={"x-ratelimit-remaining-requests": "0"},
    )
    snapshot = governor.snapshot("groq", "openai/gpt-oss-120b")
    assert snapshot.status is QuotaStatus.EXHAUSTED
    assert snapshot.source == "response_header"


def test_header_remaining_tokens_reports_approaching_limit():
    governor = _governor()
    governor.record_success(
        "cerebras",
        "gpt-oss-120b",
        headers={"x-ratelimit-remaining-tokens": "1000"},  # 1000/30000 < 10%
    )
    snapshot = governor.snapshot("cerebras", "gpt-oss-120b")
    assert snapshot.status is QuotaStatus.APPROACHING_LIMIT


def test_failed_attempts_consume_local_headroom():
    governor = _governor()
    for _ in range(5):
        governor.record_failure("cerebras", "gpt-oss-120b", status_code=503)
    assert governor.snapshot("cerebras", "gpt-oss-120b").status is QuotaStatus.EXHAUSTED


def test_429_headers_capture_exhaustion():
    governor = _governor()
    governor.record_failure(
        "groq",
        "openai/gpt-oss-120b",
        status_code=429,
        headers={"x-ratelimit-remaining-requests": "0"},
    )
    assert governor.snapshot("groq", "openai/gpt-oss-120b").status is QuotaStatus.EXHAUSTED


def test_quota_limits_validation():
    with pytest.raises(ValueError):
        QuotaLimits(rpm=0)
    with pytest.raises(ValueError):
        QuotaLimits(rpm=-5)
