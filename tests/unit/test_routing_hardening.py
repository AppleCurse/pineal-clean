"""Routing hardening regression tests (agent-identity wiring + MP ladder gaps).

Covered fixes:
- O-1  MODEL_SUBSTITUTION_DENIED records carry structured ``provider_returned_model``
       (asserted against the real routed executor path in the cost-firewall suite;
       here against gateway.query denial records via the direct route transport).
- O-2  Provider circuit breaker: a provider in transient cooldown is skipped by
       ``agent_route_variants`` and re-enters after the cooldown window.
- O-3  Capability filter: ``agent_route_variants(model, required=...)`` never offers
       a direct transport whose catalog capabilities miss a required capability
       (e.g. vision requests never fall to a vision-less free tier).
- F-1  AspasiaChief default path uses its own agent chain (query_chain with
       agent_name="aspasia"); only explicit operator selection goes direct.
- F-2/F-3 Every LLM-producing agent resolves to an explicit AGENT_CHAINS entry and
       forwards its identity to the gateway (no anonymous task-chain fallthrough).
"""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_core.agents.authenticity_auditor import (
    AuthenticityAuditorAgent,
    AuthenticityProfile,
)
from agent_core.aspasia.aspasia_chief import AspasiaChief
from agent_core.services.llm_gateway import LLMGateway

# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


def _gateway(monkeypatch, **api_keys) -> LLMGateway:
    monkeypatch.delenv("PINEAL_ALLOW_PAID_ESCALATION", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("NOUS_API_KEY", raising=False)
    for name, value in api_keys.items():
        monkeypatch.setenv(name, value)
    return LLMGateway()


def _providers(variants) -> set:
    return {r.provider_id for r in variants if r is not None}


# --------------------------------------------------------------------------- #
# O-3: capability filter inside the model@provider ladder
# --------------------------------------------------------------------------- #


def test_ladder_offers_free_chat_transports_when_capability_satisfied(monkeypatch):
    gateway = _gateway(monkeypatch, GROQ_API_KEY="gk", CEREBRAS_API_KEY="ck")
    variants = gateway.agent_route_variants("openai/gpt-oss-120b", required=frozenset({"chat"}))
    providers = _providers(variants)
    # Both free providers serve the model for chat-only work.
    assert {"groq", "cerebras"} <= providers


def test_ladder_never_offers_visionless_transport_for_vision_request(monkeypatch):
    gateway = _gateway(monkeypatch, GROQ_API_KEY="gk", CEREBRAS_API_KEY="ck")
    # Same model, but the request needs vision: both free tiers lack it, so the
    # ladder must NOT degrade a vision request onto them (returns [None]).
    variants = gateway.agent_route_variants(
        "openai/gpt-oss-120b", required=frozenset({"chat", "vision"})
    )
    assert variants == [None], "vision request must not fall to a vision-less free tier"


def test_ladder_keeps_vision_capable_paid_direct_route(monkeypatch):
    # Nous'un claude-sonnet-5 rotası ücretli frontier rotasıdır; capability
    # filtresini izole test etmek için bilinçli paid-escalation verilir.
    gateway = _gateway(
        monkeypatch, GROQ_API_KEY="gk", NOUS_API_KEY="nk",
        PINEAL_ALLOW_PAID_ESCALATION="1",
    )
    variants = gateway.agent_route_variants(
        "anthropic/claude-sonnet-5", required=frozenset({"chat", "vision"})
    )
    assert _providers(variants) == {"nous-research"}


# --------------------------------------------------------------------------- #
# O-2: provider cooldown (circuit breaker inside the ladder)
# --------------------------------------------------------------------------- #


def test_cooldown_skips_provider_and_route_returns_after_window(monkeypatch):
    gateway = _gateway(monkeypatch, GROQ_API_KEY="gk", CEREBRAS_API_KEY="ck")
    before = _providers(gateway.agent_route_variants("openai/gpt-oss-120b"))
    assert {"groq", "cerebras"} <= before

    gateway._mark_provider_cooldown("groq")
    during = _providers(gateway.agent_route_variants("openai/gpt-oss-120b"))
    assert "groq" not in during
    assert "cerebras" in during, "healthy provider must remain available after sibling cooldown"

    # Cooldown window expires -> provider re-enters the ladder.
    gateway._provider_cooldown_until["groq"] = time.time() - 1.0
    after = _providers(gateway.agent_route_variants("openai/gpt-oss-120b"))
    assert "groq" in after


def test_cooldown_does_not_hide_deny_style_failures(monkeypatch):
    """Cooldown marking is only wired into transient fallback branches; verify the
    breaker primitive itself is inert by default and scoped per provider."""
    gateway = _gateway(monkeypatch, GROQ_API_KEY="gk")
    assert gateway._provider_in_cooldown("groq") is False
    gateway._mark_provider_cooldown("groq")
    assert gateway._provider_in_cooldown("groq") is True
    assert gateway._provider_in_cooldown("cerebras") is False


# --------------------------------------------------------------------------- #
# O-1: substitution denial telemetry carries the provider-returned model
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_substitution_denial_record_carries_provider_returned_model(monkeypatch):
    from agent_core.services.llm_gateway import GatewayRoute

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gateway = LLMGateway()
    gateway.live_unlocked = True

    route = GatewayRoute(
        connection_id="agent-groq",
        provider_id="groq",
        model="openai/gpt-oss-120b",
        base_url="https://api.groq.com/openai/v1",
        api_key="gk",
        input_per_million_usd=0.0,
        output_per_million_usd=0.0,
    )

    class Completions:
        async def create(self, **kwargs):
            return SimpleNamespace(
                model="provider-default-model",  # substituted, not the requested one
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(gateway, "_client_for_route", lambda r: fake_client)

    with pytest.raises(RuntimeError, match="MODEL_SUBSTITUTION_DENIED"):
        await gateway.query("hi", model="openai/gpt-oss-120b", route=route)

    record = next(
        r for r in gateway.call_log if "MODEL_SUBSTITUTION_DENIED" in (r.get("error") or "")
    )
    assert record["provider_returned_model"] == "provider-default-model"
    assert record["requested_model"] == "openai/gpt-oss-120b"
    assert record["actual_model"] == "openai/gpt-oss-120b"
    assert record["provider"] == "groq"


# --------------------------------------------------------------------------- #
# F-1: Aspasia chief uses its own agent chain unless an explicit override exists
# --------------------------------------------------------------------------- #


class _RecordingGateway:
    """Minimal async stub recording which seam the caller selected."""

    def __init__(self):
        self.query_calls = []
        self.query_chain_calls = []

    async def query(self, *a, **k):
        self.query_calls.append(k)
        return "cevap"

    async def query_chain(self, *a, **k):
        self.query_chain_calls.append(k)
        return "cevap"


@pytest.mark.asyncio
async def test_aspasia_default_uses_agent_chain():
    stub = _RecordingGateway()
    chief = AspasiaChief(llm_gateway=stub)

    response = await chief.chat("Merhaba Mösyö, nasılsınız?", None)

    assert response.message == "cevap"
    assert stub.query_chain_calls, "default Aspasia path must go through query_chain"
    assert stub.query_chain_calls[-1].get("agent_name") == "aspasia"
    assert stub.query_chain_calls[-1].get("task") == "dialogue"
    assert not stub.query_calls, "default path must not issue an anonymous single-model query"


@pytest.mark.asyncio
async def test_aspasia_explicit_override_goes_direct_to_that_model():
    stub = _RecordingGateway()
    chief = AspasiaChief(llm_gateway=stub)

    await chief.chat("Analiz et", None, model_override="anthropic/claude-sonnet-5")

    assert stub.query_calls, "explicit model override must go direct"
    assert stub.query_calls[-1].get("model") == "anthropic/claude-sonnet-5"
    assert not stub.query_chain_calls


@pytest.mark.asyncio
async def test_aspasia_local_keyword_goes_to_local_transport():
    stub = _RecordingGateway()
    chief = AspasiaChief(llm_gateway=stub)

    await chief.chat("Bunu yerel modelde çalıştır", None)

    assert stub.query_calls and stub.query_calls[-1].get("model") == "local"
    assert not stub.query_chain_calls


# --------------------------------------------------------------------------- #
# F-2/F-3: every LLM-producing agent has an explicit identity chain entry and
# forwards its agent_name to the gateway
# --------------------------------------------------------------------------- #


def test_agent_identity_map_covers_all_llm_producers():
    gateway = LLMGateway()
    required_entries = {
        "authenticity_auditor",
        "depth_analyst",
        "human_behavior",
        "mirror_truth",
        "pattern_interrupt",
        "aspasia",
    }
    assert required_entries <= set(gateway.AGENT_CHAINS)
    for name in sorted(required_entries):
        chain = gateway.AGENT_CHAINS[name]
        assert chain, f"AGENT_CHAINS[{name}] must not be empty"
        assert all(model in gateway.MODEL_REGISTRY.values() for model in chain)


def test_capable_chain_resolves_agent_identity_not_plain_task():
    gateway = LLMGateway()
    agent_chain = gateway.capable_chain(task="depth", agent_name="aspasia")
    # aspasia is a two-model chain; plain depth has a third fallback model.
    assert agent_chain == gateway.AGENT_CHAINS["aspasia"]


@pytest.mark.asyncio
async def test_authenticity_auditor_forwards_agent_identity():
    mock_gateway = MagicMock(spec=LLMGateway)
    expected = AuthenticityProfile(
        authenticity_score=0.9,
        visual_text_gaps=["x"],
        supported_claims=["y"],
        confidence=0.9,
    )
    mock_gateway.query_json_chain = AsyncMock(return_value=expected)
    agent = AuthenticityAuditorAgent(llm_gateway=mock_gateway)

    result = await agent.execute({
        "target_profile": {"bio": "Minimalist yazar", "posts": ["İnziva."]},
        "visual_evidence": {
            "detected_objects": ["kamera"],
            "environment_and_places": ["masa"],
            "activity_signals": ["yazı"],
            "aesthetic_style": "vintage",
        },
    })

    assert isinstance(result, AuthenticityProfile)
    mock_gateway.query_json_chain.assert_awaited_once()
    kwargs = mock_gateway.query_json_chain.call_args.kwargs
    assert kwargs["agent_name"] == "authenticity_auditor"
    assert kwargs["task"] == "depth"


def test_gateway_query_chain_accepts_agent_identity():
    """query_chain exposes the same agent_name contract as query_json_chain."""
    import inspect

    signature = inspect.signature(LLMGateway.query_chain)
    assert "agent_name" in signature.parameters
