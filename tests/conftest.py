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


# ⚡ Bolt Optimization: Clear security lru_cache for every test
# What: Clears _environment_secret_values cache before each test.
# Why: Prevents test pollution since we cached the environment secrets parsing which would otherwise ignore monkeypatch.setenv changes.
@pytest.fixture(autouse=True)
def _clear_security_lru_cache():
    try:
        from agent_core.utils.security import _environment_secret_values
        _environment_secret_values.cache_clear()
    except Exception:
        pass
    yield
