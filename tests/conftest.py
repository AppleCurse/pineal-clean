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
