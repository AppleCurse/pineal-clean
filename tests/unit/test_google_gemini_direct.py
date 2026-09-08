"""FAZ-2-P4 — Google Gemini direkt transport + 429→backup rotasyonu.

Kapsam (kilitli): google-gemini provider katalogda model taşır; ROUTES'ta
paid spec vardır; escalation=1 ile vision istekleri Google'in resmi
OpenAI-uyumlu endpoint'ine (generativelanguage .../v1beta/openai/) gider ve
model adı OR'daki "google/gemini-3.7-flash" DEĞİL, Google'in kendi adı
"gemini-3.7-flash" olur. 429/limit → merdiven aynı endpoint'in 2. anahtarına
(google-gemini-backup) düşer. Escalation=0'da google direct teklif EDİLMEZ
(padi firewall) — OR legacy (only_channel) kalır, kırılma yok.

Gerçek network yok: AsyncOpenAI kurulumu deterministik fake ile değiştirilir;
base_url + api_key + model boundary'si assert edilir (spec #22 deseni).
"""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import agent_core.services.llm_gateway as gwl
from agent_core.services.llm_gateway import LLMGateway

_ENV_KEYS = (
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
    "CEREBRAS_API_KEY",
    "NOUS_API_KEY",
    "GEMINI_API_KEY",
    "GEMINI_BACKUP_API_KEY",
    "GEMINI_VERTEX_TOKEN",
    "PINEAL_ALLOW_PAID_ESCALATION",
    "PINEAL_ALLOW_UNPRICED_MODELS",
    "OPENROUTER_MAX_SPEND_USD",
    "USE_LOCAL_LLM",
    "LIVE_LLM_E2E",
    "PINEAL_ROUTER_LIVE",
    "PINEAL_AGENT_TIERS_PATH",
)

GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def run(coro):
    return asyncio.run(coro)


class _Schema(BaseModel):
    a: int = 1


class _FakeGoogleHttp:
    """AsyncOpenAI ctor dikişi: construction + call kaydı (key sızıntısı yok)."""

    def __init__(self, behavior=None):
        self.constructions: list[dict] = []
        self.calls: list[tuple[str, dict]] = []
        self._behavior = behavior or (lambda n: None)

    def factory(self, *, base_url, api_key, max_retries=0, **kw):
        self.constructions.append({"base_url": base_url, "api_key": api_key})
        outer = self

        class _C:
            def __init__(self, bu):
                self.chat = SimpleNamespace(completions=self._Comp(bu, outer))

            class _Comp:
                def __init__(self, bu, owner):
                    self.bu, self.owner = bu, owner

                async def create(self, **kwargs):
                    self.owner.calls.append((self.bu, kwargs))
                    outcome = self.owner._behavior(len(self.owner.calls))
                    if isinstance(outcome, Exception):
                        raise outcome
                    model = kwargs["model"]
                    usage = SimpleNamespace(prompt_tokens=1_000, completion_tokens=200)
                    return SimpleNamespace(
                        usage=usage,
                        model=model,
                        choices=[SimpleNamespace(
                            message=SimpleNamespace(content='{"a": 1}'))],
                    )

        return _C(base_url)

    @property
    def or_calls(self):
        return [c for c in self.calls if c[0].rstrip("/") == "https://openrouter.ai/api/v1"]

    def google_calls(self):
        return [c for c in self.calls if c[0].startswith(GOOGLE_BASE)]


@pytest.fixture()
def fake(monkeypatch):
    f = _FakeGoogleHttp()
    monkeypatch.setattr(gwl, "AsyncOpenAI", lambda **kw: f.factory(**kw))
    return f


@pytest.fixture()
def clean_env(monkeypatch, fake):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    return fake


def _gw():
    gw = LLMGateway()
    gw.live_unlocked = True
    return gw


def test_google_direct_transport_identity_escalated(clean_env, monkeypatch):
    """P4: escalation=1 + GEMINI key → vision isteği Google endpoint'ine gider,
    model adı öneksiz (gemini-3.7-flash), OpenRouter SIFIR çağrı."""
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = _gw()
    run(gw.query_json_chain(
        "p", _Schema, task="vision", agent_name="vision_analyzer"
    ))
    assert len(clean_env.calls) == 1
    base, kwargs = clean_env.calls[0]
    assert base.startswith(GOOGLE_BASE)
    assert kwargs["model"] == "gemini-3.7-flash"  # Google'in kendi adı (öneksiz)
    assert len(clean_env.or_calls) == 0
    # doğru anahtarla kuruldu (Google client'ı — OR client'ı init'te ayrı kurulur)
    g_cons = [c for c in clean_env.constructions if c["base_url"].startswith(GOOGLE_BASE)]
    assert len(g_cons) == 1 and g_cons[0]["api_key"] == "gemini-secret"
    rec = gw.call_log[-1]
    assert rec["provider"] == "google-gemini"
    assert rec["route_key"] == "gemini-3.7-flash@google-gemini"


def test_google_direct_not_offered_without_escalation(clean_env, monkeypatch):
    """P4: escalation=0 → google direct (paid) teklif EDİLMEZ; vision OR legacy
    (only_channel) ile kalır — kırılma yok, sessiz fatura yok."""
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    gw = _gw()
    gw.get_agent_chain("vision_analyzer", "vision")
    ladder = gw.agent_route_variants("google/gemini-3.7-flash")
    offered = [r.provider_id for r in ladder if r is not None]
    assert "google-gemini" not in offered
    assert "google-gemini-backup" not in offered
    # OR legacy yalnız-kanal olduğu için koşulsuz kalır
    assert ladder[-1] is None


def test_google_429_rotates_to_backup_key(clean_env, monkeypatch):
    """P4: birincil key 429 verir → AYNI endpoint 2. anahtarla (backup) denenir;
    ikisi de biterse OR legacy'ye düşülür. Key'ler sırayla doğru."""
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-primary")
    monkeypatch.setenv("GEMINI_BACKUP_API_KEY", "gemini-backup")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")

    def behavior(n):
        if n == 1:
            err = RuntimeError("429 Too Many Requests")
            err.status_code = 429
            raise err
        return None

    clean_env._behavior = behavior
    gw = _gw()
    run(gw.query_json_chain("p", _Schema, task="vision", agent_name="vision_analyzer"))
    # iki google çağrısı: primary (429) + backup (başarı)
    google = clean_env.google_calls()
    assert len(google) == 2
    assert len(clean_env.or_calls) == 0
    # primary ve backup farklı key'lerle kuruldu
    g_cons = [c for c in clean_env.constructions if c["base_url"].startswith(GOOGLE_BASE)]
    keys = [c["api_key"] for c in g_cons]
    assert keys[0] == "gemini-primary" and keys[1] == "gemini-backup"
    # 429 → backup rotasyonu: tek başarılı sonuç, backup key üzerinden döndü.
    # (Streak 1 < threshold 3 olduğu için cooldown yok — provider_health {} beklenir;
    # devre yalnız eşik aşılınca kapanır, kalıcı karantina yok.)


def test_google_route_registry_policy(clean_env):
    """P4: ROUTES kimliği — google-gemini paid (liste fiyatı), free DEĞİL
    (AI Studio free tier canlı teyit bekler; Cerebras dersi: teyitsiz free yok)."""
    from agent_core.services import final_routing_policy as pol

    spec = pol.ROUTES["gemini-3.7-flash@google-gemini"]
    assert spec.tier == "paid"
    assert (spec.input_per_million_usd, spec.output_per_million_usd) == (0.75, 3.75)
    assert "vision" in spec.capabilities
    assert not spec.is_free()
    assert pol.is_free("gemini-3.7-flash", "google-gemini") is False
    assert pol.is_paid("gemini-3.7-flash", "google-gemini") is True
    # backup da aynı paid kayıtta
    spec_b = pol.ROUTES["gemini-3.7-flash@google-gemini-backup"]
    assert spec_b.tier == "paid"
    assert not spec_b.is_free()
