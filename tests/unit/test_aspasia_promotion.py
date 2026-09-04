"""ASPASIA PROMOTION — merkezi doğal-dil arayüzü sözleşme testleri.

Kabller (spec #34):
1) Görünürlük: Aspasia routing/quota/maliyet/telemetri durumunu GERÇEK SoT
   okumalarından görür (uydurma alan yok; unknown -> "unknown").
2) Komut akışı: doğal dil -> AspasiaIntent (extra=forbid) -> doğrulama ->
   dispatch tek kanaldan; kabul edilmeyen niyet görev başlatamaz.
3) Güvenlik: komut katmanı politika atlatamaz — provider istemcisi/anahtar/
   quota/spend mutasyon yüzeyi YOK (statik + davranış kanıtı). Aspasia'nın
   kendi LLM çağrısı gerçek aspasia dialogue zincirinden geçer.
4) Regression: mevcut chat() sözleşmesi (AspasiaResponse şekli, persona) bozulmaz.
Gerçek network yok: dış sağlayıcı sınırı (AsyncOpenAI ctor) fake'tir — bu bir
transport dikişidir, başarı mock'u değildir.
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import agent_core.services.llm_gateway as gwl
from agent_core.aspasia.aspasia_chief import ASPASIA_SYSTEM_PROMPT, AspasiaChief
from agent_core.aspasia.interface import (
    AgentInspector,
    AspasiaCommandGateway,
    AspasiaIntent,
    CostReader,
    QuotaReader,
    RoutingInspector,
    TelemetryReader,
)
from agent_core.services.llm_gateway import LLMGateway

_ENV_KEYS = (
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
    "CEREBRAS_API_KEY",
    "NOUS_API_KEY",
    "PINEAL_ALLOW_PAID_ESCALATION",
    "PINEAL_ALLOW_UNPRICED_MODELS",
    "OPENROUTER_MAX_SPEND_USD",
    "OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR",
    "OPENROUTER_AGENT_CHAIN_ASPASIA",
    "USE_LOCAL_LLM",
    "LIVE_LLM_E2E",
    "PINEAL_ROUTER_LIVE",
)


def run(coro):
    return asyncio.run(coro)


class FakeGatewayHttp:
    """Dış sağlayıcı sınırı: AsyncOpenAI ctor dikişi (FINAL-SPEC kalıbı)."""

    def __init__(self, behavior=None):
        self.calls: list[tuple[str, dict]] = []
        self._behavior = behavior or (lambda n: None)

    def factory(self, *, base_url, api_key, max_retries=0, **kw):
        outer = self

        class _C:
            def __init__(self, bu):
                self.chat = SimpleNamespace(completions=self._Comp(bu, outer))

            class _Comp:
                def __init__(self, bu, owner):
                    self.bu = bu
                    self.owner = owner

                async def create(self, **kwargs):
                    self.owner.calls.append((self.bu, kwargs))
                    outcome = self.owner._behavior(len(self.owner.calls))
                    if isinstance(outcome, Exception):
                        raise outcome
                    content = '{"a": 1}'
                    model = kwargs["model"]
                    usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=200)
                    if isinstance(outcome, dict):
                        content = outcome.get("content", content)
                        model = outcome.get("model", model)
                    elif isinstance(outcome, str):
                        content = outcome
                    return SimpleNamespace(
                        usage=usage,
                        model=model,
                        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                    )

        return _C(base_url)

    @property
    def or_calls(self):
        return [c for c in self.calls if c[0].rstrip("/") == "https://openrouter.ai/api/v1"]


@pytest.fixture()
def clean_env(monkeypatch):
    fake = FakeGatewayHttp()
    monkeypatch.setattr(gwl, "AsyncOpenAI", lambda **kw: fake.factory(**kw))
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    # aspasia/depth zincirlerinin ilk modeli paid (claude-sonnet-5): kapı
    # env'siz zinciri DURDURUR — testler routing'i sonuna kadar görebilir.
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    return fake


def _gw():
    gw = LLMGateway()
    gw.live_unlocked = True
    return gw


class _Schema(BaseModel):
    a: int = 1


# ------------------------------------------------------- 1) görünürlük (read)
def test_routing_inspector_explains_real_selection(clean_env, monkeypatch):
    monkeypatch.setenv("NOUS_API_KEY", "nous-secret")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = _gw()
    view = RoutingInspector(gw).explain("friction_detector", task="depth")
    assert view["chain_source"] == "agent_matrix"
    assert view["chain"]  # gercek AGENT_CHAINS girdisi
    sel = view["selected"]
    # Merdiven Nous'u one alir (effective 1.6/8 < OR 2/10) — FINAL-SPEC aynisi.
    assert sel["route_key"] == "anthropic/claude-sonnet-5@nous-research"
    assert sel["endpoint"].startswith("https://inference-api.nousresearch.com")
    assert sel["discount_pct"] == pytest.approx(20.0)
    assert "Zincir durur" in view["fallback_rule"] or "DURUR" in view["fallback_rule"]


def test_quota_reader_limits_are_never_invented(clean_env):
    gw = _gw()
    groq = QuotaReader(gateway=gw).snapshot("groq")
    assert groq["limits"]["rpm"] == 30 and groq["limits"]["rpd"] == 14400
    assert groq["limits"]["tpm"] == "unknown"  # unknown != unlimited (fail-closed)
    assert groq["limits"].get("tpd") in (None, "unknown") or groq["limits"]["tpd"] == "unknown"
    assert "unlimited" not in str(groq["limits"])
    cere = QuotaReader(gateway=gw).snapshot("cerebras")
    assert cere["limits"]["tpm"] == 30000 and cere["limits"]["tpd"] == 1_000_000
    # Politika'da olmayan provider: uydurma limit YOK.
    ghost = QuotaReader(gateway=gw).snapshot("ghost-provider")
    assert ghost["limits"] == {}


def test_cost_reader_budget_and_discount_table(clean_env, monkeypatch):
    monkeypatch.setenv("NOUS_API_KEY", "nous-secret")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = _gw()
    rows = CostReader(gw).pricing_overview()
    sonnet = next(r for r in rows if r["route_key"] == "anthropic/claude-sonnet-5@nous-research")
    assert sonnet["list"] == {"in": 2.0, "out": 10.0}
    assert sonnet["effective"] == {"in": 1.6, "out": 8.0}
    assert sonnet["discount_pct"] == pytest.approx(20.0)
    luna = next(r for r in rows if r["route_key"] == "openai/gpt-5.6-luna@nous-research")
    assert luna["effective"] == {"in": 0.2, "out": 1.2}
    assert luna["discount_pct"] == pytest.approx(80.0)
    # Gercek harcama: Nous sonnet turu -> budget snapshot'i bunu gostermeli
    before = CostReader(gw).snapshot()["spend_usd"]
    run(gw.query_json_chain("merhaba", _Schema, task="depth", agent_name="friction_detector"))
    after = CostReader(gw).snapshot()["spend_usd"]
    assert after > before
    assert len(clean_env.or_calls) == 0  # merdiven Nous: OR'a sifir istek


def test_telemetry_reader_flags_real_anomalies(clean_env, monkeypatch):
    monkeypatch.setenv("NOUS_API_KEY", "nous-secret")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = _gw()
    # Dagitim modeli FARKLI dondurur -> substitution reddi kaydi gercekten uretilir.
    clean_env._behavior = lambda n: {"model": "someone-elses/model", "content": '{"a": 1}'}
    with pytest.raises(Exception):
        run(gw.query_chain("p", task="depth", agent_name="friction_detector"))
    anomalies = TelemetryReader(gw).anomalies()
    assert anomalies["substitution_denials"], "reddedilen ikame telemetride gorunmeli"
    denial = anomalies["substitution_denials"][-1]
    assert denial["requested_model"] == "anthropic/claude-sonnet-5"
    assert denial["actual_model"] == "someone-elses/model"
    rows = TelemetryReader(gw).recent()
    assert any(r.get("error") and "MODEL_SUBSTITUTION_DENIED" in r["error"] for r in rows)


def test_agent_inspector_uses_real_registry_and_lifecycle():
    executor = SimpleNamespace(agents={"osint": object(), "mirror_truth": object()})
    assert AgentInspector(executor).registry() == ["mirror_truth", "osint"]
    room = {"active_tasks": {"t1": {
        "task_id": "t1", "status": "running", "planned_agents": ["mirror_truth"],
        "completed_agents": [], "current_agent": "mirror_truth",
        "agent_runs": {"mirror_truth": {"status": "done"}},
    }}}
    st = AgentInspector(executor).run_status(room)
    assert st["task_id"] == "t1" and st["current"] == "mirror_truth"
    assert st["runs"]["mirror_truth"]["status"] == "done"


# ---------------------------------------------------------- 2) komut akışı
def _content(payload: dict) -> dict:
    return {"content": json.dumps(payload)}


def test_command_gateway_dispatches_only_validated_intent(clean_env):
    gw = _gw()
    launched: list[dict] = []
    commands = AspasiaCommandGateway(
        dispatch=lambda spec: launched.append(spec) or "op_test_0001",
        gateway=gw,
    )
    clean_env._behavior = lambda n: _content({
        "intent": "run_profile_analysis",
        "target_url": "https://www.instagram.com/someuser/",
    })
    res = run(commands.submit("Şu profili incele: https://www.instagram.com/someuser/", client_id="c1"))
    assert res.accepted and res.intent == "run_profile_analysis" and res.task_id == "op_test_0001"
    assert launched == [{"client_id": "c1",
                         "target_url": "https://www.instagram.com/someuser/",
                         # goal tasinmazsa bos liste gitmeli (compat sozlesmesi)
                         "goals": []}]
    # Niyet cikarimi GERCEK aspasia dialogue zincirinden gecti (ayni routing yigini):
    assert len(clean_env.calls) == 1
    base, kwargs = clean_env.calls[0]
    assert base.rstrip("/") == "https://openrouter.ai/api/v1"
    assert kwargs["model"] in gw.get_agent_chain("aspasia", "dialogue")
    audit = commands.audit()
    assert audit[-1]["status"] == "dispatched" and audit[-1]["task_id"] == "op_test_0001"
    # Mevcut telemetri sozlesmesi: cagri capture_calls kapsamiyla 'aspasia'
    # olarak etiketlenir (paralel sistem degil, gateway'in kendi alani).
    assert gw.call_log[-1]["agent_id"] == "aspasia"
    assert gw.call_log[-1]["model"] == "anthropic/claude-sonnet-5"


def test_command_gateway_rejects_fabricated_or_foreign_target(clean_env):
    gw = _gw()
    launched: list[dict] = []
    commands = AspasiaCommandGateway(dispatch=lambda spec: launched.append(spec), gateway=gw)
    # a) hedef URL mesajda yokken model uydursa da dispatch YOK
    clean_env._behavior = lambda n: _content({
        "intent": "run_profile_analysis", "target_url": "https://instagram.example.com/victim/",
    })
    res = run(commands.submit("rastgele bir şey yap", client_id="c1"))
    assert not res.accepted and res.reason == "unsupported_or_missing_target"
    # b) bos/eksik hedef
    clean_env._behavior = lambda n: _content({"intent": "run_profile_analysis"})
    res = run(commands.submit("analiz başlat", client_id="c1"))
    assert not res.accepted and res.reason == "unsupported_or_missing_target"
    assert launched == []  # HICBIR uydurma hedef gorev baslatamaz


def test_intent_schema_forbids_policy_fields(clean_env):
    gw = _gw()
    dispatched: list[dict] = []
    commands = AspasiaCommandGateway(dispatch=lambda spec: dispatched.append(spec), gateway=gw)
    # Model/agent listesi uydurmaya calisan niyet: extra=forbid + zincir tukendigi
    # icin intent Unavailable -> dispatch YOK (politika alani Aspasia'da degil).
    clean_env._behavior = lambda n: _content({
        "intent": "run_profile_analysis",
        "target_url": "https://www.instagram.com/someuser/",
        "model": "gpt-9-ultra",
        "agents": ["osint", "jailbreak_agent"],
    })
    res = run(commands.submit("su profile bak: https://www.instagram.com/someuser/", client_id="c1"))
    assert not res.accepted
    assert res.reason == "intent_unavailable"
    assert dispatched == []
    # schema duzeyinde de kanit:
    with pytest.raises(Exception):
        AspasiaIntent(intent="run_profile_analysis", model="gpt-9-ultra")


def test_no_action_and_read_only_intents_never_dispatch(clean_env):
    gw = _gw()
    dispatched: list[dict] = []
    commands = AspasiaCommandGateway(dispatch=lambda spec: dispatched.append(spec), gateway=gw)
    clean_env._behavior = lambda n: _content({"intent": "none"})
    res = run(commands.submit("bugun nasilsin", client_id="c1"))
    assert res.accepted and res.reason == "no_action"
    clean_env._behavior = lambda n: _content({"intent": "explain_status"})
    res = run(commands.submit("sistem ne alemde", client_id="c1"))
    assert res.accepted and res.reason == "read_only"
    assert dispatched == []


def test_dispatch_failure_is_reported_not_swallowed(clean_env):
    gw = _gw()

    def _boom(spec):
        raise RuntimeError("orchestrator kapali")

    commands = AspasiaCommandGateway(dispatch=_boom, gateway=gw)
    clean_env._behavior = lambda n: _content({
        "intent": "run_profile_analysis", "target_url": "https://www.instagram.com/u/",
    })
    res = run(commands.submit("incele: https://www.instagram.com/u/", client_id="c1"))
    assert not res.accepted and res.reason == "dispatch_failed"
    assert commands.audit()[-1]["status"] == "dispatch_failed"


# ------------------------------------------------------------- 3) güvenlik
def test_interface_module_has_no_mutation_or_provider_surface():
    src = Path("agent_core/aspasia/interface.py").read_text(encoding="utf-8")
    forbidden = (".set_key(", "set_spend", "record_success(", "record_failure(",
                 "AsyncOpenAI", "httpx", "requests.", "resolve_credentials")
    for token in forbidden:
        assert token not in src, f"interface.py politika/yazma yuzeyi icermemeli: {token}"


def test_command_gateway_holds_no_provider_client(clean_env):
    gw = _gw()
    commands = AspasiaCommandGateway(dispatch=lambda spec: None, gateway=gw)
    # Tek yetkiler: dispatch callable'i + salt-okur gateway + audit kuyrugu.
    assert set(vars(commands)) == {"_dispatch", "_gateway", "_audit"}
    assert not hasattr(commands, "set_key") and not hasattr(commands, "llm_client")
    # gateway dogrudan degistirilemez:
    assert not any(callable(getattr(commands, n, None)) for n in
                   ("record_success", "record_failure", "set_spend_cap"))


def test_governor_state_survives_reader_reads(clean_env):
    # Salt-okur reader'lar governor'a YAZMAZ (quota/spend mutasyonu yok).
    gw = _gw()
    gov = gw._quota_governor()

    def _view():
        return {
            "statuses": {p: repr(gov.status(p)) for p in ("groq", "cerebras")},
            "limits": {p: repr(gov.limits_for(p)) for p in ("groq", "cerebras")},
            "spend": gw.spend_usd,
        }

    before = _view()
    QuotaReader(gateway=gw).snapshot("groq")
    TelemetryReader(gw).recent()
    RoutingInspector(gw).explain("aspasia")
    assert _view() == before


# ---------------------------------------------------- 4) chat gerileme + digest
def test_prompt_role_extension_and_persona_kept():
    # Yeni gorevler eklendi...
    assert "MERKEZİ ARAYÜZ" in ASPASIA_SYSTEM_PROMPT
    assert "CommandGateway" in ASPASIA_SYSTEM_PROMPT
    assert "Politika atlatma" in ASPASIA_SYSTEM_PROMPT or "Politika atlat" in ASPASIA_SYSTEM_PROMPT
    # ...persona + mevcut sinirlar AYNEN duruyor:
    assert "Mösyö" in ASPASIA_SYSTEM_PROMPT
    assert "KANIT SÖZLEŞMESİ" in ASPASIA_SYSTEM_PROMPT
    assert "SINIR: Sisteme doğrudan müdahale yetkin yok" in ASPASIA_SYSTEM_PROMPT


def test_chat_prompt_carries_oversight_digest():
    captured: dict = {}

    class _StubGw:
        call_log: list = []
        def get_agent_chain(self, agent, task):
            return ["ghost-model"]

        def agent_route_variants(self, model):
            return []

        AGENT_CHAINS = {"friction_detector": ["ghost-model"]}

        def budget_status(self):
            return {"spend_usd": 0.01, "reserved_usd": 0.0, "cap_usd": 5.0,
                    "active_reservations": 0}

        async def query_chain(self, **kwargs):
            captured.update(kwargs)
            return "Elbette Mösyö."

    chief = AspasiaChief(llm_gateway=_StubGw())
    res = run(chief.chat("routing neden boyle?", room_state=None))
    assert res.message == "Elbette Mösyö."
    assert res.confidence_assessment == "high"  # AspasiaResponse sozlesmesi
    prompt = captured["prompt"]
    assert "DENETİM KATMANI" in prompt
    assert "ROUTING[friction_detector]" in prompt
    assert "MALİYET: harcama=$0.0100" in prompt


def test_chat_without_oversight_data_has_no_fabricated_block():
    captured: dict = {}

    class _DeadGw:
        async def query_chain(self, **kwargs):
            captured.update(kwargs)
            return "Veri yok Mösyö."

    chief = AspasiaChief(llm_gateway=_DeadGw())
    run(chief.chat("durum?", room_state=None))
    # gateway'inden okunabilir sey yok -> digest bloğu eklenmez, uydurulmaz.
    assert "DENETİM KATMANI" not in captured["prompt"]
