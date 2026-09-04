"""ROUTING-HARDENING — O-gaps kapanislarinin kilit testleri.

Kapsam: (1) reddedilen ikamenin STRUCTURED telemetry'si, (2) gecici-transport
hata devresi (yalniz transport; policy redi sayilmaz), (3) ROUTES.capabilities
uyumu merdiven filtreleme, (4) catalog<->ROUTES fiyat tek-kaynak guard'i.
Routing kararinin kendisi (fiyat/kota/policy siralamasi) degismedi — bu testler
bunu da kilitler.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

import agent_core.services.llm_gateway as gwl
from agent_core.services.llm_gateway import LLMGateway

_ENV_KEYS = (
    "OPENROUTER_API_KEY", "GROQ_API_KEY", "DEEPSEEK_API_KEY", "CEREBRAS_API_KEY",
    "NOUS_API_KEY", "PINEAL_ALLOW_PAID_ESCALATION", "PINEAL_ALLOW_UNPRICED_MODELS",
    "OPENROUTER_MAX_SPEND_USD", "OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR",
    "OPENROUTER_AGENT_CHAIN_HARD_TESTER", "USE_LOCAL_LLM", "LIVE_LLM_E2E",
    "PINEAL_ROUTER_LIVE", "PINEAL_PROVIDER_FAILURE_THRESHOLD",
    "PINEAL_PROVIDER_COOLDOWN_SECONDS",
)


def run(coro):
    return asyncio.run(coro)


class FakeHttp:
    """AsyncOpenAI ctor dikişi; hata davranisi base_url-anahtarli verilebilir."""

    def __init__(self, failures=None, returned_model=None):
        self.calls = []
        self._failures = failures or {}
        self._returned = returned_model

    def factory(self, *, base_url, api_key, max_retries=0, **kw):
        outer = self

        class _C:
            def __init__(self, bu):
                self.chat = SimpleNamespace(completions=self._X(bu, outer))

            class _X:
                def __init__(self, bu, owner):
                    self.bu, self.owner = bu, owner

                async def create(self, **kwargs):
                    self.owner.calls.append({"base": self.bu, "model": kwargs["model"]})
                    for frag, exc in self.owner._failures.items():
                        should_fail = exc() if callable(exc) else exc
                        if frag in self.bu and should_fail:
                            raise ConnectionError("simulated connection refused")
                    model = self.owner._returned or kwargs["model"]
                    return SimpleNamespace(
                        model=model,
                        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
                        choices=[SimpleNamespace(
                            message=SimpleNamespace(content='{"a": 1}'))],
                    )

        return _C(base_url)


@pytest.fixture()
def env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def _gw(fake):
    monkey = gwl
    monkey.AsyncOpenAI = lambda **kw: fake.factory(**kw)
    gw = LLMGateway()
    gw.live_unlocked = True
    return gw


# ------------------------------------------ 1) structured substitution denial
def test_denial_record_carries_structured_models(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("NOUS_API_KEY", "nous")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    fake = FakeHttp(returned_model="baska/model")
    gw = _gw(fake)
    with pytest.raises(RuntimeError, match="MODEL_SUBSTITUTION_DENIED"):
        run(gw.query_chain("p", task="depth", agent_name="friction_detector"))
    rec = gw.call_log[-1]
    # Eskiden actual_model=selected model'di; simdi provider'in dondurdugu:
    assert rec["requested_model"] == "anthropic/claude-sonnet-5"
    assert rec["actual_model"] == "baska/model"
    # extras MERGE edildi — route_key/pricing kaybolmadi:
    assert rec["route_key"] == "anthropic/claude-sonnet-5@nous-research"
    assert "MODEL_SUBSTITUTION_DENIED" in rec["error"]
    # red = transport sayilir MI? HAYIR — policy ihlali cooldown streak'ine
    # girmez (devre yalniz gecici hatalari sayar):
    assert gw.provider_health() == {}


# ------------------------------------------------------ 2) health circuit
def test_transient_failures_cool_provider_and_recover(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("OPENROUTER_AGENT_CHAIN_HARD_TESTER", "openai/gpt-oss-120b")
    monkeypatch.setenv("PINEAL_PROVIDER_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("PINEAL_PROVIDER_COOLDOWN_SECONDS", "1")
    state = {"groq": True}
    fake = FakeHttp(failures={"api.groq.com": lambda: state["groq"]})
    gw = _gw(fake)
    # 1) groq duser -> transient -> cerebras basarili; groq streak tetikledi
    out = run(gw.query_chain("p", task="dialogue", agent_name="hard_tester"))
    assert out == '{"a": 1}'
    bases = [c["base"] for c in fake.calls]
    assert bases[0].startswith("https://api.groq.com")
    assert len(bases) == 2 and "groq" not in bases[1]
    health = gw.provider_health()
    assert health and "groq" in health and health["groq"] > 0
    # 2) merdiven artik groq'u TEKLIF ETMEZ (cerebras onceli) — HTTP'siz kanit
    laddered = gw.agent_route_variants("openai/gpt-oss-120b")
    assert [r.provider_id for r in laddered if r is not None] == ["cerebras"]
    # 3) cooldown suresi dolunca geri gelir (kalici karantina YOK)
    time.sleep(1.15)
    laddered2 = gw.agent_route_variants("openai/gpt-oss-120b")
    assert "groq" in [r.provider_id for r in laddered2 if r is not None]
    # 4) basarili groq turlugu streak'i de block'u da sifirlar
    state["groq"] = False
    fake.calls.clear()
    run(gw.query_chain("p", task="dialogue", agent_name="hard_tester"))
    assert gw.provider_health() == {}


def test_auth_and_denial_never_count_toward_cooldown(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("OPENROUTER_AGENT_CHAIN_HARD_TESTER", "openai/gpt-oss-120b")
    monkeypatch.setenv("PINEAL_PROVIDER_FAILURE_THRESHOLD", "1")
    # groq daima 401 verirse hata NON-retryable: zincir durur, cooldown YOK
    class _C401:
        def __init__(self, bu):
            self.chat = SimpleNamespace(completions=self._X())
        class _X:
            async def create(self, **kw):
                err = RuntimeError("401 unauthorized")
                err.status_code = 401
                raise err
    gwl.AsyncOpenAI = lambda **kw: _C401(kw["base_url"])
    gw = LLMGateway()
    gw.live_unlocked = True
    with pytest.raises(RuntimeError, match="401"):
        run(gw.query_chain("p", task="dialogue", agent_name="hard_tester"))
    assert gw.provider_health() == {}


# ------------------------------------------------ 3) capability-filtered ladder
def test_ladder_respects_declared_route_capabilities(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    fake = FakeHttp()
    gw = _gw(fake)
    m = "openai/gpt-oss-120b"
    plain = [r.provider_id for r in gw.agent_route_variants(m, required=frozenset({"chat"}))
             if r is not None]
    assert plain == ["groq", "cerebras"]  # ikisi de free, direct-oncelikli: sabit sira
    # cerebras ROUTES beyani {"chat","streaming"} — tools gereksinimi duser
    with_tools = [r.provider_id for r in
                  gw.agent_route_variants(m, required=frozenset({"chat", "tools"}))
                  if r is not None]
    assert with_tools == ["groq"]
    # gorunur OR-pool varyanti davranisi degismedi (unpriced -> sonda, None)
    assert gw.agent_route_variants(m, required=frozenset({"chat", "tools"}))[-1] is None


# -------------------------------------- 4) catalog vs ROUTES single source
def test_catalog_and_routes_price_consistency(env):
    """Iki fiyalli rota katalog ile ROUTES'un AYNI effective fiyati gostermelidir;
    ROUTES birincil SoT'tur — katalog fiyat cakismasi regresyon KIRMIZI yakar."""
    from agent_core.services import final_routing_policy as pol
    from agent_core.services.provider_manager import load_builtin_catalog

    catalog = load_builtin_catalog()
    checked = 0
    for pid in ("groq", "cerebras", "nous-research", "openrouter", "deepseek"):
        try:
            provider = catalog.get_provider(pid)
        except Exception:
            continue
        for model in provider.models:
            pricing = getattr(model, "pricing", None)
            if pricing is None or not pricing.known:
                continue
            spec = pol.ROUTES.get(f"{model.id}@{provider.id}")
            if spec is None:
                continue
            assert spec.input_per_million_usd == pytest.approx(
                pricing.input_per_million_usd), f"in-price drift {model.id}@{provider.id}"
            assert spec.output_per_million_usd == pytest.approx(
                pricing.output_per_million_usd), f"out-price drift {model.id}@{provider.id}"
            checked += 1
    assert checked >= 3, "guard hicbir cift-fiyatli rota gormedi — katalog mu degisti?"


# ------------------------------------------------ interface digest health line
def test_digest_shows_cooldown_from_gateway(env):
    from agent_core.aspasia.interface import build_oversight_digest

    class _Gw:
        call_log = []

        def get_agent_chain(self, agent, task):
            return ["m1"]

        def agent_route_variants(self, model, required=frozenset()):
            return []

        AGENT_CHAINS = {"friction_detector": ["m1"]}

        def budget_status(self):
            return {"spend_usd": 0.0, "reserved_usd": 0.0, "cap_usd": None,
                    "active_reservations": 0}

        def provider_health(self):
            return {"groq": 42.0}

    digest = build_oversight_digest(_Gw(), None, None, None)
    assert "SAĞLIK: groq cooldown=42s" in digest


def test_digest_omits_health_line_when_all_healthy(env):
    from agent_core.aspasia.interface import build_oversight_digest

    class _Gw:
        call_log = []

        def get_agent_chain(self, agent, task):
            return ["m1"]

        def agent_route_variants(self, model, required=frozenset()):
            return []

        AGENT_CHAINS = {"friction_detector": ["m1"]}

        def budget_status(self):
            return {"spend_usd": 0.0, "reserved_usd": 0.0, "cap_usd": None,
                    "active_reservations": 0}

        def provider_health(self):
            return {}

    assert "SAĞLIK" not in build_oversight_digest(_Gw(), None, None, None)
