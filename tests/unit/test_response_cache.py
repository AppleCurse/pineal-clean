"""
agent_core.services.response_cache ve LLMGateway cache entegrasyonu testleri.

Canlı LLM/para çağrısı YAPILMAZ; ağ katmanı AsyncMock ile sahtelenir.
Sözleşmeler:
  * Birebir aynı istek cache'ten döner (ağa bir kez gidilir).
  * Farklı model / system_prompt / sıcaklık AYRI cache'lenir (yanlış yanıt
    zehirlenmesi olmaz).
  * Görselli (vision) istekler cache'lenmez.
  * Hatalı/boş yanıt cache'e yazılmaz.
  * PINEAL_RESPONSE_CACHE=0 cache'i tamamen kapatır.
  * TTL süresi dolan girdi miss sayılır.
"""
import pytest
from unittest.mock import AsyncMock

from agent_core.services.response_cache import (
    ResponseCache,
    NullCache,
    build_cache_from_env,
)
from agent_core.services.llm_gateway import LLMGateway


# ---------------- ResponseCache birim testleri ----------------

def test_exact_key_round_trip(tmp_path):
    cache = ResponseCache(db_path=str(tmp_path / "c.db"))
    key = cache.make_key(prompt="merhaba", model="m1", system_prompt="s", temperature=0.1)
    assert cache.get(key) is None  # miss
    cache.put(key, "DÜNYA")
    assert cache.get(key) == "DÜNYA"  # hit
    assert cache.hits == 1 and cache.misses == 1


def test_key_differs_by_model_system_and_temperature():
    k1 = ResponseCache.make_key("p", model="m1", system_prompt="s", temperature=0.1)
    k2 = ResponseCache.make_key("p", model="m2", system_prompt="s", temperature=0.1)
    k3 = ResponseCache.make_key("p", model="m1", system_prompt="X", temperature=0.1)
    k4 = ResponseCache.make_key("p", model="m1", system_prompt="s", temperature=0.9)
    assert len({k1, k2, k3, k4}) == 4, "tüm bileşenler anahtarı farklılaştırmalı"


def test_images_and_oversized_prompt_not_cachable():
    cache = ResponseCache(db_path=":memory:")
    assert cache.is_cachable("prompt", images=["data:image/png;base64,abc"]) is False
    assert cache.is_cachable("", images=None) is False
    assert cache.is_cachable("x" * 100_000, images=None) is False
    assert cache.is_cachable("normal metin", images=None) is True


def test_ttl_expiration():
    cache = ResponseCache(db_path=":memory:", ttl_seconds=0)  # anında süresi dolar
    key = cache.make_key("p", model="m")
    cache.put(key, "v")
    assert cache.get(key) is None  # TTL=0 → miss


def test_null_cache_is_noop():
    cache = NullCache()
    assert cache.is_cachable("p", None) is False
    assert cache.get("x") is None
    cache.put("x", "v")  # hata fırlatmaz
    assert cache.stats()["enabled"] is False


def test_build_cache_from_env_toggle(monkeypatch, tmp_path):
    monkeypatch.setenv("PINEAL_RESPONSE_CACHE", "0")
    assert isinstance(build_cache_from_env(), NullCache)

    monkeypatch.setenv("PINEAL_RESPONSE_CACHE", "1")
    monkeypatch.setenv("PINEAL_CACHE_PATH", str(tmp_path / "env.db"))
    c = build_cache_from_env()
    assert isinstance(c, ResponseCache)
    assert c.enabled


# ---------------- LLMGateway entegrasyon testleri ----------------

def _live_gateway(tmp_path, monkeypatch) -> LLMGateway:
    """LIVE_LLM_E2E kapısını geçen, geçici db kullanan bir gateway."""
    monkeypatch.setenv("PINEAL_CACHE_PATH", str(tmp_path / "gw.db"))
    monkeypatch.delenv("PINEAL_RESPONSE_CACHE", raising=False)
    gw = LLMGateway()
    gw.api_key = "sk-test"
    gw.live_unlocked = True
    return gw


@pytest.mark.asyncio
async def test_gateway_caches_repeated_identical_query(tmp_path, monkeypatch):
    gw = _live_gateway(tmp_path, monkeypatch)

    call_count = 0

    async def fake_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "aynı yanıt"})()})()]})()

    fake_client = AsyncMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=fake_create)
    gw.client = fake_client

    r1 = await gw.query("aynı prompt", model="anthropic/claude-sonnet-4.5")
    r2 = await gw.query("aynı prompt", model="anthropic/claude-sonnet-4.5")

    assert r1 == r2 == "aynı yanıt"
    assert call_count == 1, "ikinci çağrı cache'ten gelmeli, ağ'a yalnızca 1 kez gidilmeli"
    assert gw.cache.hits == 1


@pytest.mark.asyncio
async def test_gateway_does_not_cross_contaminate_models(tmp_path, monkeypatch):
    gw = _live_gateway(tmp_path, monkeypatch)
    answers = {
        "anthropic/claude-sonnet-4.5": "CLAUDE YANITI",
        "deepseek/deepseek-chat": "DEEPSEEK YANITI",
    }

    async def fake_create(*args, **kwargs):
        content = answers[kwargs["model"]]
        return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": content})()})()]})()

    gw.client = AsyncMock()
    gw.client.chat.completions.create = AsyncMock(side_effect=fake_create)

    assert await gw.query("soru", model="anthropic/claude-sonnet-4.5") == "CLAUDE YANITI"
    # Aynı prompt, farklı model -> kendi yanıtını getirmeli, diğerini cache'den çalmamalı
    assert await gw.query("soru", model="deepseek/deepseek-chat") == "DEEPSEEK YANITI"


@pytest.mark.asyncio
async def test_gateway_does_not_cache_vision_queries(tmp_path, monkeypatch):
    gw = _live_gateway(tmp_path, monkeypatch)
    gw.client = AsyncMock()
    gw.client.chat.completions.create = AsyncMock(
        return_value=type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "gorsel yorumu"})()})()]})()
    )
    img = "data:image/png;base64,AAAA"
    await gw.query("görece bak", model="anthropic/claude-sonnet-5", images=[img])
    await gw.query("görece bak", model="anthropic/claude-sonnet-5", images=[img])

    assert gw.client.chat.completions.create.await_count == 2, "vision istekleri asla cache'lenmemeli"
    assert gw.cache.hits == 0


@pytest.mark.asyncio
async def test_gateway_cache_disabled_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PINEAL_RESPONSE_CACHE", "0")
    gw = LLMGateway()
    gw.api_key = "sk-test"
    gw.live_unlocked = True
    gw.client = AsyncMock()
    gw.client.chat.completions.create = AsyncMock(
        return_value=type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "x"})()})()]})()
    )
    await gw.query("p", model="m")
    await gw.query("p", model="m")
    assert gw.client.chat.completions.create.await_count == 2
    assert isinstance(gw.cache, NullCache)
