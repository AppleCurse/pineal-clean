"""MP-ROUTING: provider-aware agent chains — cost ladder, fail-closed gates.

Ajan zincirleri artık tek santrale (OpenRouter) mahkûm değil: aynı model için
doğrudan sağlayıcı rotaları (MODEL@PROVIDER) credential + policy + kota
kapılarından geçerse maliyet merdiveniyle önce denenir. Anahtarsız varsayılan
üretim davranışı BİREBİR korunur.
"""

import asyncio
from types import SimpleNamespace

import pytest

from agent_core.services.llm_gateway import (
    GatewayRoute,
    LLMGateway,
    SpendCapExceeded,
)

_DIRECT_ENVS = (
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
    "CEREBRAS_API_KEY",
    "NOUS_API_KEY",
    "PINEAL_ALLOW_PAID_ESCALATION",
    "PINEAL_ALLOW_UNPRICED_MODELS",
    "OPENROUTER_MAX_SPEND_USD",
    "OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in _DIRECT_ENVS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def run(coro):
    return asyncio.run(coro)


class _JsonSchema:  # sadece şema meta'sı için; query_json patch'li
    @staticmethod
    def model_json_schema():
        return {"type": "object"}


# ------------------------------------------------------------------ resolver

def test_default_env_is_pure_legacy(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    assert gw.agent_route_variants("deepseek/deepseek-v4-pro") == [None]
    assert gw.agent_route_variants("anthropic/claude-sonnet-5") == [None]


def test_free_groq_route_wins_cost_ladder(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    gw = LLMGateway()
    variants = gw.agent_route_variants("openai/gpt-oss-120b")
    assert variants[0] is not None
    route = variants[0]
    assert route.provider_id == "groq"
    assert route.model == "openai/gpt-oss-120b"
    assert route.base_url == "https://api.groq.com/openai/v1"
    assert route.input_per_million_usd == 0.0  # ROUTES free-tier doğrulaması
    assert None in variants  # legacy OpenRouter taşımaları merdivende kalır


def test_paid_direct_route_requires_escalation(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("NOUS_API_KEY", "nk")
    gw = LLMGateway()
    # claude-sonnet-5@nous ROUTES'ta PAID: escalation kapalıyken rota teklif edilmez
    assert gw.agent_route_variants("anthropic/claude-sonnet-5") == [None]
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    variants = gw.agent_route_variants("anthropic/claude-sonnet-5")
    nous = [v for v in variants if isinstance(v, GatewayRoute) and v.provider_id == "nous-research"]
    assert len(nous) == 1
    # indirimli fiyat ROUTES'tan gelir: $1.6/$8 (liste $2/$10)
    assert nous[0].input_per_million_usd == pytest.approx(1.6)
    assert nous[0].output_per_million_usd == pytest.approx(8.0)


def test_unknown_priced_direct_route_blocked_by_spend_cap(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dk")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    monkeypatch.setenv("OPENROUTER_MAX_SPEND_USD", "5")
    gw = LLMGateway()
    # deepseek@deepseek katalogda fiyatlanmamış -> cap'li cüzdanda rota teklif edilmez
    assert gw.agent_route_variants("deepseek/deepseek-v4-pro") == [None]


def test_exhausted_quota_skips_provider_route(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    gw = LLMGateway()
    from agent_core.services.provider_manager import QuotaStatus

    gw._agent_governor = SimpleNamespace(
        status=lambda provider: SimpleNamespace(
            status=QuotaStatus.EXHAUSTED if provider == "groq" else QuotaStatus.OK
        )
    )
    assert gw.agent_route_variants("openai/gpt-oss-120b") == [None]


# ------------------------------------------------------------------ chain flow

def _patch_transport(gw, recorder, behavior):
    async def fake_query_json(prompt=None, schema=None, temperature=0.7, tier=1,
                              model=None, images=None, route=None):
        recorder.append((model, route.provider_id if route is not None else None))
        outcome = behavior(len(recorder), model, route)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    gw.query_json = fake_query_json


def test_chain_walks_provider_ladder_then_fallback_transport(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setenv("OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR", "openai/gpt-oss-120b")
    gw = LLMGateway()
    attempts = []
    # 1) gpt-oss@GROQ (free, en ucuz) timeout -> 2) AYNI modelin OpenRouter
    #    taşıması kurtarır; zincir modeli atlamadan önce merdiven yürür.
    _patch_transport(gw, attempts, lambda n, m, r: TimeoutError("408 timed out") if n < 2 else '{"ok":1}')
    run(gw.query_json_chain("p", _JsonSchema, task="depth", agent_name="friction_detector"))
    assert attempts == [
        ("openai/gpt-oss-120b", "groq"),
        ("openai/gpt-oss-120b", None),
    ]


def test_unpriced_direct_route_tails_the_ladder(monkeypatch):
    # deepseek@deepseek katalogda fiyatlanmamış: fiyatı BİLİNEN OpenRouter taşıması
    # merdivende önce gelir; bilinmeyen en sonda (ve cap varsa hiç teklif edilmez).
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dk")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    variants = gw.agent_route_variants("deepseek/deepseek-v4-pro")
    assert variants[0] is None
    assert isinstance(variants[1], GatewayRoute) and variants[1].provider_id == "deepseek"


def test_policy_rejection_stops_entire_ladder(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dk")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    attempts = []

    def deny(n, m, r):
        raise SpendCapExceeded("spend cap reached")

    _patch_transport(gw, attempts, deny)
    with pytest.raises(SpendCapExceeded):
        run(gw.query_json_chain("p", _JsonSchema, task="depth", agent_name="friction_detector"))
    # zincir DURDU: tek deneme, ne yedek taşıma ne yedek model denenmedi
    assert len(attempts) == 1


def test_no_openrouter_key_uses_direct_only(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    gw = LLMGateway()  # OR key yok
    variants = gw.agent_route_variants("openai/gpt-oss-120b")
    assert [v for v in variants if v is None] == []  # ölü OR taşıması teklif edilmez
    assert variants and variants[0].provider_id == "groq"


# ------------------------------------------------------------------ query() routed transport

def _fake_route():
    return GatewayRoute(
        connection_id="agent-groq",
        provider_id="groq",
        model="openai/gpt-oss-120b",
        base_url="https://api.groq.com/openai/v1",
        api_key="gk",
        input_per_million_usd=0.0,
        output_per_million_usd=0.0,
    )


def _fake_client(response_model, content='{"ok": true}'):
    class _Completions:
        async def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                usage=None,
                model=response_model,
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            )

    captured = {}
    client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    return client, captured


def test_routed_query_live_gate(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    gw.live_unlocked = False
    with pytest.raises(RuntimeError, match="REAL_LLM_CALL_NOT_EXECUTED"):
        run(gw.query("p", model="openai/gpt-oss-120b", route=_fake_route()))


def test_routed_query_executes_and_annotates_provider(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    gw.live_unlocked = True
    client, captured = _fake_client("openai/gpt-oss-120b")
    monkeypatch.setattr(gw, "_client_for_route", lambda route: client)
    out = run(gw.query("p", model="anthropic/gpt-oss-120b", route=_fake_route()))
    assert out == '{"ok": true}'
    assert captured["kwargs"]["model"] == "openai/gpt-oss-120b"
    rec = gw.call_log[-1]
    assert rec["provider"] == "groq"
    assert rec["requested_model"] == "anthropic/gpt-oss-120b"
    assert rec["actual_model"] == "openai/gpt-oss-120b"


def test_routed_query_substitution_firewall(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    gw.live_unlocked = True
    client, _ = _fake_client("some-other-default-model")
    monkeypatch.setattr(gw, "_client_for_route", lambda route: client)
    with pytest.raises(RuntimeError, match="MODEL_SUBSTITUTION_DENIED"):
        run(gw.query("p", model="openai/gpt-oss-120b", route=_fake_route()))
