"""
Test ortamı için ortak ayarlar.

Önemli: LLM yanıt önbelleği (ResponseCache) varsayılan olarak ./cache/responses.db
konumunu kullanır. Testler aynı kısa prompt'ları (ör. "ping") tekrar kullandığından,
bir testin başarılı yanıtı başka bir testin hata senaryosuna sızabilir (ör. 429
sonrası başarı cache'lenir, 401 testi hatayı görmez).

Bu otomatik fixture, her test için cache'i geçici, izole bir veritabanına yönlendirir.
Cache davranışını özel olarak test edenler (tests/unit/test_response_cache.py)
PINEAL_RESPONSE_CACHE / PINEAL_CACHE_PATH değişkenlerini kendileri ayarlayabilir.
"""
import pytest


@pytest.fixture(autouse=True)
def _isolate_response_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PINEAL_CACHE_PATH", str(tmp_path / "test_responses.db"))
    # Tests are hermetic even when invoked from a production-configured shell;
    # individual auth tests explicitly opt back into production/token modes.
    monkeypatch.setenv("PINEAL_ENV", "development")
    monkeypatch.setenv("PINEAL_REQUIRE_AUTH", "false")
    monkeypatch.delenv("PINEAL_TOKEN", raising=False)
    monkeypatch.delenv("LIVE_LLM_E2E", raising=False)
    monkeypatch.delenv("PINEAL_ROUTER_LIVE", raising=False)
    monkeypatch.delenv("OPENROUTER_MAX_SPEND_USD", raising=False)
    yield


@pytest.fixture(autouse=True)
def _isolate_rate_limit_state():
    """[AUDIT P1-18a] `backend.api._rate_buckets` süreç genelinde paylaşılan
    mutable durumdur.

    Hız sınırı anahtarı artık SUNUCU kimliğine bağlı (eskiden istemcinin
    gönderdiği `client_id` idi). Eski davranış testler arasında kazara
    izolasyon sağlıyordu: her test benzersiz bir client_id kullandığı için
    kovalar çakışmıyordu. Anahtar sunucu kimliğine geçince tüm TestClient
    istekleri aynı kovayı paylaşmaya başladı ve bir testin tükettiği bütçe
    sonraki testte erken 429'a yol açtı (ölçülen: test_initiate_rate_limit_429
    ve test_ws_ordering tam pakette kırmızı, tek başına yeşil).
    """
    try:
        from backend import api
    except Exception:  # api yüklenemiyorsa test zaten kendi hatasını verir
        yield
        return
    api._rate_buckets.clear()
    yield
    api._rate_buckets.clear()


@pytest.fixture(autouse=True)
def _isolate_gateway_contextvars():
    """Gateway contextvar'larını testler arasında temizle.

    (b'') kural 1 gereği `get_agent_chain` `_active_agent_tier`'ı BİLİNÇLİ
    reset etmez (overwrite disiplini; değer resolve->query arasında yaşamalı).
    Üretimde her istek kendi context'inde olduğu için sorun yok; ama pytest
    aynı OS-thread context'ini paylaşır — bir testin `get_agent_chain` çağrısı
    tier'ı arkada bırakır ve sonraki testler (ör. eski "tier yok == eski
    davranış" senaryoları) sessizce yanlış semantiğe düşer. Bu fixture,
    süreç-geneli mutable durum izolasyonu deseninin (rate bucket/cache) aynısını
    contextvar'lara uygular.
    """
    try:
        from agent_core.services import llm_gateway as gwmod
    except Exception:  # gateway yüklenemiyorsa test zaten kendi hatasını verir
        yield
        return
    vars_ = (
        gwmod._active_agent_tier,
        gwmod._active_chain_source,
        gwmod._active_task_hint,
        gwmod._active_agent_hint,
        gwmod._active_call_scope,
    )
    for var in vars_:
        var.set(None)
    yield
    for var in vars_:
        var.set(None)
