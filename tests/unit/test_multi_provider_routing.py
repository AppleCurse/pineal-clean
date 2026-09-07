"""FAZ 3 — cok-saglayici havuzu sozlesmeleri.

R1. Havuz 13 dogrudan saglayiciya acik (4 degil); anahtar varsa okunur.
R2. Operator beyanli modeller (PINEAL_PROVIDER_MODELS_*) eslesir; hicbir
    kapi atlanmaz (firewall/cap/kota aynen gecerli).
R3. route_diagnostics: her anahtarin akibeti gorunur (secret sizdirmaz);
    offered kumesi variants ile birebir tutarli.
R4. Oda-ornekli anahtarlar (set_provider_key): env'yi ezer, bilinmeyen
    provider reddedilir, failover saglayicilar arasi yurur.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from agent_core.services.llm_gateway import (
    GatewayRoute,
    LLMGateway,
    _AGENT_DIRECT_PROVIDER_KEYS,
    _DIAGNOSTIC_ONLY_PROVIDERS,
)


def _all_key_envs():
    envs = [env for _, env in _AGENT_DIRECT_PROVIDER_KEYS]
    envs += [env for _, env in _DIAGNOSTIC_ONLY_PROVIDERS]
    envs += ["OPENROUTER_API_KEY", "PINEAL_ALLOW_PAID_ESCALATION",
             "PINEAL_ALLOW_UNPRICED_MODELS", "OPENROUTER_MAX_SPEND_USD",
             "OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR",
             "NVIDIA_NIM_API_KEY"]  # eski ad; okunmamali (asagida kilitli)
    for pid, _ in _AGENT_DIRECT_PROVIDER_KEYS:
        envs.append("PINEAL_PROVIDER_MODELS_" + pid.upper().replace("-", "_"))
    return envs


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in _all_key_envs():
        monkeypatch.delenv(key, raising=False)


def run(coro):
    return asyncio.run(coro)


class _JsonSchema:
    @staticmethod
    def model_json_schema():
        return {"type": "object"}


def _providers_of(variants):
    return sorted(v.provider_id if v is not None else "openrouter" for v in variants)


# ------------------------------------------------------------------ #
# R1. havuz genisligi
# ------------------------------------------------------------------ #
def test_pool_known_providers_cover_thirteen_direct():
    assert len(_AGENT_DIRECT_PROVIDER_KEYS) == 13
    ids = [pid for pid, _ in _AGENT_DIRECT_PROVIDER_KEYS]
    for expected in ("groq", "deepseek", "cerebras", "nous-research", "mistral",
                     "together", "fireworks", "alibaba-dashscope"):
        assert expected in ids


def test_pool_spans_providers_with_attested_models(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "k1")
    monkeypatch.setenv("TOGETHER_API_KEY", "k2")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_MISTRAL", "vendor/x7")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_TOGETHER", "vendor/x7")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    providers = _providers_of(gw.agent_route_variants("vendor/x7"))
    assert "mistral" in providers and "together" in providers
    assert "openrouter" in providers  # legacy tasima merdivende kalir


def test_default_env_still_pure_legacy(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    for model in ("deepseek/deepseek-v4-pro", "anthropic/claude-sonnet-5",
                  "google/gemini-3.7-flash", "x-ai/grok-4.6"):
        assert gw.agent_route_variants(model) == [None]


# ------------------------------------------------------------------ #
# R2. operator beyani + kapi sozlesmesi
# ------------------------------------------------------------------ #
def test_attested_match_rules(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "k1")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_MISTRAL", "bare-seven, vendor/x7")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    assert "mistral" in _providers_of(gw.agent_route_variants("bare-seven"))
    assert "mistral" in _providers_of(gw.agent_route_variants("vendor/x7"))
    # eslesmeyen model -> yalniz legacy
    assert gw.agent_route_variants("vendor/other") == [None]


def test_attested_blocked_without_escalation(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "k1")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_MISTRAL", "vendor/x7")
    gw = LLMGateway()  # escalation kapali
    assert gw.agent_route_variants("vendor/x7") == [None]


def test_attested_unpriced_blocked_by_spend_cap(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "k1")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_MISTRAL", "vendor/x7")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    monkeypatch.setenv("OPENROUTER_MAX_SPEND_USD", "5")
    gw = LLMGateway()
    assert gw.agent_route_variants("vendor/x7") == [None]


# ------------------------------------------------------------------ #
# R4. oda-ornekli anahtarlar
# ------------------------------------------------------------------ #
def test_instance_key_used_without_env(monkeypatch):
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_FIREWORKS", "vendor/x7")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    assert gw.agent_route_variants("vendor/x7") == [None]  # anahtar yok
    gw.set_provider_key("fireworks", "fw-instance-key")
    variants = gw.agent_route_variants("vendor/x7")
    assert "fireworks" in _providers_of(variants)
    route = [v for v in variants if isinstance(v, GatewayRoute)][0]
    assert route.api_key == "fw-instance-key"  # tasiyici gercek anahtari alir


def test_instance_key_overrides_env(monkeypatch):
    monkeypatch.setenv("FIREWORKS_API_KEY", "fw-env-key")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_FIREWORKS", "vendor/x7")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    gw.set_provider_key("fireworks", "fw-instance-key")
    route = [v for v in gw.agent_route_variants("vendor/x7") if isinstance(v, GatewayRoute)][0]
    assert route.api_key == "fw-instance-key"
    gw.clear_provider_key("fireworks")
    route2 = [v for v in gw.agent_route_variants("vendor/x7") if isinstance(v, GatewayRoute)][0]
    assert route2.api_key == "fw-env-key"  # temizleyince env'ye donulur


def test_unknown_provider_key_rejected():
    gw = LLMGateway()
    with pytest.raises(ValueError, match="unknown provider_id"):
        gw.set_provider_key("grok", "x")


# ------------------------------------------------------------------ #
# R3. tani: nedenler + tutarlilik
# ------------------------------------------------------------------ #
def _route_keys_of_variants(gw, model):
    keys = set()
    for v in gw.agent_route_variants(model):
        keys.add(f"{v.model}@{v.provider_id}" if v is not None else f"{model}@openrouter")
    return keys


@pytest.mark.parametrize("model", [
    "openai/gpt-oss-120b",
    "anthropic/claude-sonnet-5",
    "deepseek/deepseek-v4-pro",
    "google/gemini-3.7-flash",
    "vendor/x7",
])
def test_diagnostics_offered_matches_variants(monkeypatch, model):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setenv("NOUS_API_KEY", "nk")
    monkeypatch.setenv("MISTRAL_API_KEY", "mk")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_MISTRAL", "vendor/x7")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    diag = gw.route_diagnostics(model)
    offered = {o["route_key"] for o in diag["offered"]}
    assert offered == _route_keys_of_variants(gw, model)
    assert diag["pool_size"] == len(offered)


def test_diagnostics_reasons_cover_gates(monkeypatch):
    from agent_core.services.provider_manager import QuotaStatus

    monkeypatch.setenv("NOUS_API_KEY", "nk")
    monkeypatch.setenv("MISTRAL_API_KEY", "mk")
    monkeypatch.setenv("OPENAI_API_KEY", "ok")
    gw = LLMGateway()  # escalation kapali, cap yok
    diag = gw.route_diagnostics("anthropic/claude-sonnet-5")
    assert diag["skipped"]["nous-research"]["reason"] == "paid_firewall"
    assert diag["skipped"]["mistral"]["reason"] == "model_not_served"
    assert diag["skipped"]["groq"]["reason"] == "no_key"
    assert diag["skipped"]["openai"]["reason"] == "transport_unsupported"
    assert diag["skipped"]["openai"]["key_present"] is True

    # kota tukenmesi
    gw._agent_governor = SimpleNamespace(
        status=lambda p: QuotaStatus.EXHAUSTED if p == "mistral" else QuotaStatus.HEALTHY
    )
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_MISTRAL", "anthropic/claude-sonnet-5")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    diag2 = gw.route_diagnostics("anthropic/claude-sonnet-5")
    assert diag2["skipped"]["mistral"]["reason"] == "exhausted"


def test_diagnostics_cooldown_reason(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    gw = LLMGateway()
    assert gw.route_diagnostics("openai/gpt-oss-120b")["skipped"].get("groq") is None
    for _ in range(3):
        gw._note_route_health("groq", ok=False)
    diag = gw.route_diagnostics("openai/gpt-oss-120b")
    assert diag["skipped"]["groq"]["reason"] == "cooldown"
    assert "groq" not in _providers_of(gw.agent_route_variants("openai/gpt-oss-120b"))
    gw._note_route_health("groq", ok=True)  # basari devreyi sifirlar
    assert "groq" in _providers_of(gw.agent_route_variants("openai/gpt-oss-120b"))


def test_diagnostics_never_leaks_secret_values(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "SECRETVALUE123")
    gw = LLMGateway()
    gw.set_provider_key("together", "INSTANCESECRET456")
    dump = json.dumps(gw.route_diagnostics("vendor/x7"))
    assert "SECRETVALUE123" not in dump
    assert "INSTANCESECRET456" not in dump
    assert "or-key" not in dump


# ------------------------------------------------------------------ #
# failover: merdiven saglayicilar arasi yurur
# ------------------------------------------------------------------ #
def test_failover_walks_across_providers(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "k1")
    monkeypatch.setenv("TOGETHER_API_KEY", "k2")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_MISTRAL", "vendor/x7")
    monkeypatch.setenv("PINEAL_PROVIDER_MODELS_TOGETHER", "vendor/x7")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    monkeypatch.setenv("OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR", "vendor/x7")
    gw = LLMGateway()
    attempts = []

    async def fake_query_json(prompt=None, schema=None, temperature=0.7, tier=1,
                              model=None, images=None, route=None):
        attempts.append((model, route.provider_id if route is not None else None))
        if len(attempts) < 2:
            raise TimeoutError("408 timed out")
        return '{"ok": 1}'

    gw.query_json = fake_query_json
    run(gw.query_json_chain("p", _JsonSchema, task="depth", agent_name="friction_detector"))
    assert attempts == [("vendor/x7", "mistral"), ("vendor/x7", "together")]


# ------------------------------------------------------------------ #
# Aspasia aciklamasina "blocked" listesi (eklemeli, kirici degil)
# ------------------------------------------------------------------ #
def test_explain_includes_blocked_providers():
    from agent_core.aspasia.interface import RoutingInspector

    class _DiagGW:
        AGENT_CHAINS = {"friction_detector": ["m1"]}
        MODEL_PRICING = {}
        openrouter_base_url = "https://openrouter.ai/api/v1"

        def get_agent_chain(self, agent, task):
            return ["m1"]

        def agent_route_variants(self, model):
            return [None]

        def route_diagnostics(self, model):
            return {"model": model, "offered": [], "skipped": {
                "groq": {"reason": "no_key", "key_present": False, "key_source": "none"},
            }}

    view = RoutingInspector(_DiagGW()).explain("friction_detector")
    assert view["blocked"] == [{"provider": "groq", "reason": "no_key", "key_present": False}]


def test_explain_without_diagnostics_stays_compatible():
    from agent_core.aspasia.interface import RoutingInspector

    class _LegacyGW:
        AGENT_CHAINS = {"friction_detector": ["m1"]}
        MODEL_PRICING = {}
        openrouter_base_url = "https://openrouter.ai/api/v1"

        def get_agent_chain(self, agent, task):
            return ["m1"]

        def agent_route_variants(self, model):
            return [None]

    view = RoutingInspector(_LegacyGW()).explain("friction_detector")
    assert view["blocked"] == []


# ------------------------------------------------------------------ #
# FAZ 3-EK: gercek envanter adlari + tasiyicisiz gorunurluk
# ------------------------------------------------------------------ #
def test_nvidia_standard_env_name_recognized(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    gw = LLMGateway()
    entry = gw.route_diagnostics("vendor/x7")["skipped"]["nvidia-nim"]
    assert entry["key_present"] is True
    assert entry["key_source"] == "env"


def test_nvidia_legacy_env_name_not_read(monkeypatch):
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "legacy-x")
    gw = LLMGateway()
    entry = gw.route_diagnostics("vendor/x7")["skipped"]["nvidia-nim"]
    assert entry["reason"] == "no_key"
    assert entry["key_present"] is False


def test_inventory_keys_visible_as_diagnostic_only(monkeypatch):
    monkeypatch.setenv("IFLOW_API_KEY", "if-x")
    monkeypatch.setenv("GEMINI_BACKUP_API_KEY", "gb-x")
    monkeypatch.setenv("GEMINI_VERTEX_TOKEN", "gv-x")
    gw = LLMGateway()
    diag = gw.route_diagnostics("vendor/x7")
    for pid in ("iflow", "google-gemini-backup", "google-gemini-vertex"):
        assert diag["skipped"][pid]["reason"] == "transport_unsupported"
        assert diag["skipped"][pid]["key_present"] is True
    # tasiyicisiz anahtar asla rota teklif etmez
    offered_providers = {o["provider"] for o in diag["offered"]}
    assert not (offered_providers & {"iflow", "google-gemini-backup", "google-gemini-vertex"})
    # ...ama kasa/vault kabul eder (gorunurluk icin)
    gw.set_provider_key("iflow", "k")
    assert gw._provider_key_source("iflow", "IFLOW_API_KEY") == "instance"
