"""FINAL-KARAR-MATRIX policy contracts: free-first firewall, pricing, quotas."""

import pytest

from agent_core.services.final_routing_policy import (
    QUOTAS,
    ROUTES,
    PaidEscalationDenied,
    UnknownRouteDenied,
    assert_executable,
    capabilities_for,
    effective_pricing,
    executable_task_groups,
    is_paid,
    model_substitution_allowed,
    paid_escalation_enabled,
    verify_free_route_ids,
)


# --------------------------------------------------------------------------- #
# Cost firewall
# --------------------------------------------------------------------------- #
def test_paid_escalation_is_denied_by_default(monkeypatch):
    monkeypatch.delenv("PINEAL_ALLOW_PAID_ESCALATION", raising=False)
    assert paid_escalation_enabled() is False
    with pytest.raises(PaidEscalationDenied):
        assert_executable("openai/gpt-5.6-luna", "nous-research")


def test_paid_escalation_requires_explicit_switch(monkeypatch):
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    assert_executable("openai/gpt-5.6-luna", "nous-research")


def test_free_routes_never_select_a_paid_model(monkeypatch):
    monkeypatch.delenv("PINEAL_ALLOW_PAID_ESCALATION", raising=False)
    groups = executable_task_groups()
    assert "fast" in groups
    assert all(
        not is_paid(route.split("/", 1)[1], route.split("/", 1)[0])
        for route in groups["fast"]
    )
    # research keeps free candidates only while escalation is off.
    assert all(route.startswith(("groq/", "cerebras/", "nous-research/")) for route in groups["research"])
    assert not any("stepfun" in route or "solar" in route or "luna" in route for route in groups["research"])


def test_paid_escalation_enabled_opens_policy_paid_routes_only(monkeypatch):
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    groups = executable_task_groups()
    assert any("stepfun/step-3.7-flash" in route for route in groups["research"])
    assert any("upstage/solar-pro4" in route for route in groups["research"])
    assert any("meituan/longcat-2.0" in route for route in groups["research"])
    assert any("gpt-5.6-luna" in route for route in groups["research"])


def test_free_routes_come_first_even_when_escalation_enabled(monkeypatch):
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    groups = executable_task_groups()
    research = groups["research"]
    first_paid = next(
        (index for index, route in enumerate(research) if route in {
            "nous-research/stepfun/step-3.7-flash",
            "nous-research/upstage/solar-pro4",
            "nous-research/meituan/longcat-2.0",
            "nous-research/openai/gpt-5.6-luna",
        }),
        None,
    )
    assert first_paid is not None
    assert all(":free" in route or route.startswith(("groq/", "cerebras/")) for route in research[:first_paid])


# --------------------------------------------------------------------------- #
# Unknown model / unknown price DENY
# --------------------------------------------------------------------------- #
def test_unknown_model_is_denied():
    with pytest.raises(UnknownRouteDenied):
        assert_executable("nous-research/naked-alias", "nous-research")
    assert effective_pricing("some/unknown-model", "some-provider") is None


def test_unknown_price_is_not_reported_as_free():
    # An unknown model must never be classified free or paid; it is unknown.
    assert effective_pricing("glm-5.3-flash", "nous-research") is None
    with pytest.raises(UnknownRouteDenied):
        assert_executable("glm-5.3-flash", "nous-research")


def test_verified_free_routes_are_known_free():
    free = verify_free_route_ids([
        "laguna-s-2.1:free",
        "xs-2.1:free",
        "ling-3.0-flash-fin:free",
        "dots-3-note-preview:free",
        "stepfun/step-3.7-flash",
        "glm-5.3-flash",
    ])
    assert set(free) == {
        "laguna-s-2.1:free",
        "xs-2.1:free",
        "ling-3.0-flash-fin:free",
        "dots-3-note-preview:free",
    }


# --------------------------------------------------------------------------- #
# Pricing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "model, provider, expected",
    [
        ("stepfun/step-3.7-flash", "nous-research", (0.20, 1.15)),
        ("upstage/solar-pro4", "nous-research", (0.03, 0.12)),
        ("meituan/longcat-2.0", "nous-research", (0.30, 1.20)),
        ("openai/gpt-5.6-luna", "nous-research", (0.20, 1.20)),
        ("anthropic/claude-sonnet-5", "nous-research", (1.60, 8.00)),
        ("google/gemini-3.7-flash", "openrouter", (0.75, 3.75)),
        ("openai/gpt-5.6-sol-pro", "openrouter", (2.0, 10.0)),
    ],
)
def test_effective_prices_match_decision_matrix(model, provider, expected):
    assert effective_pricing(model, provider) == expected


def test_luna_discount_cost_example():
    in_rate, out_rate = effective_pricing("openai/gpt-5.6-luna", "nous-research")
    cost = 2 * in_rate + 0.4 * out_rate
    assert cost == pytest.approx(0.88)


def test_sonnet_discount_cost_example():
    in_rate, out_rate = effective_pricing("anthropic/claude-sonnet-5", "nous-research")
    cost = 1 * in_rate + 0.2 * out_rate
    assert cost == pytest.approx(3.20)


def test_free_routes_have_zero_effective_price():
    for model in ("laguna-s-2.1:free", "xs-2.1:free", "ling-3.0-flash-fin:free", "dots-3-note-preview:free"):
        assert effective_pricing(model, "nous-research") == (0.0, 0.0)


# --------------------------------------------------------------------------- #
# Provider quotas
# --------------------------------------------------------------------------- #
def test_groq_account_quota_is_recorded():
    assert QUOTAS["groq"]["rpm"] == 30
    assert QUOTAS["groq"]["rpd"] == 14_400


def test_cerebras_account_quota_is_recorded():
    assert QUOTAS["cerebras"]["rpm"] == 5
    assert QUOTAS["cerebras"]["tpm"] == 30_000
    assert QUOTAS["cerebras"]["tpd"] == 1_000_000


# --------------------------------------------------------------------------- #
# Model availability / capability
# --------------------------------------------------------------------------- #
def test_verified_routes_are_available_and_free_routes_executable(monkeypatch):
    monkeypatch.delenv("PINEAL_ALLOW_PAID_ESCALATION", raising=False)
    assert_executable("laguna-s-2.1:free", "nous-research")
    assert_executable("openai/gpt-oss-120b", "groq")
    assert_executable("gpt-oss-120b", "cerebras")


def test_discovered_but_unverified_route_is_denied():
    with pytest.raises(UnknownRouteDenied):
        assert_executable("poolside/laguna:free", "nous-research")


def test_provider_default_substitution_is_denied():
    assert model_substitution_allowed("openai/gpt-oss-120b", "openai/gpt-oss-120b")
    assert not model_substitution_allowed("openai/gpt-oss-120b", "some-provider-default-model")


def test_vision_task_requires_vision_capability():
    assert "vision" in capabilities_for("google/gemini-3.7-flash", "openrouter")
    assert "vision" not in capabilities_for("meituan/longcat-2.0", "nous-research")
    assert "vision" not in capabilities_for("laguna-s-2.1:free", "nous-research")


def test_frontier_routes_are_explicit_paid():
    assert is_paid("openai/gpt-5.6-sol-pro", "openrouter")
    assert is_paid("anthropic/claude-sonnet-5", "nous-research")


def test_route_table_is_well_formed():
    for spec in ROUTES.values():
        assert spec.tier in {"free", "subscription", "cheap", "paid"}
        if spec.tier != "paid":
            assert spec.input_per_million_usd == 0.0
            assert spec.output_per_million_usd == 0.0
