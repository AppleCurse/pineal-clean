"""BOSS-1 — 9Router yapılandırma sözleşmesi.

Röntgen bulgusu: README ".env" bölümü `PINEAL_LLM_BASE_URL/API_KEY` diyordu,
gateway ise yalnız `NINEROUTER_*` / `OPENROUTER_*` okuyordu. Bu iki ad
tanımlandığında kod hiçbirini görmüyor, kullanıcı sessizce bulut OpenRouter'a
düşüyordu. Ayrıca kanıt zincirine ("provider") trafik yerel hub'da olsa bile
"openrouter" yazılıyordu.

Bu dosya sözleşmeyi kilitler:
  1) Üç ad da (NINEROUTER_*, PINEAL_LLM_*, OPENROUTER_*) aynı çözümleyiciden geçer.
  2) Öncelik sırası: NINEROUTER_* > PINEAL_LLM_* > OPENROUTER_*.
  3) Sağlayıcı etiketi gerçeği söyler: yerel hub → "9router", bulut → "openrouter".
  4) Hiçbir env tanımlı değilse davranış ESKİSİYLE birebir aynıdır (regresyon kapısı).
"""

import pytest

from agent_core.services.llm_gateway import (
    LLMGateway,
    NINEROUTER_DEFAULT_BASE_URL,
    provider_label_for_endpoint,
    resolve_legacy_endpoint,
)

_ENV_NAMES = (
    "NINEROUTER_BASE_URL",
    "NINEROUTER_API_KEY",
    "PINEAL_LLM_BASE_URL",
    "PINEAL_LLM_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_API_KEY",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_readme_alias_names_are_honoured(monkeypatch):
    """README'yi uygulayan operatör buluta DÜŞMEMELİ."""
    monkeypatch.setenv("PINEAL_LLM_BASE_URL", "http://127.0.0.1:20128/v1")
    monkeypatch.setenv("PINEAL_LLM_API_KEY", "sk-readme")

    base_url, api_key, label = resolve_legacy_endpoint()

    assert base_url == "http://127.0.0.1:20128/v1"
    assert api_key == "sk-readme"
    assert label == "9router"
    gateway = LLMGateway()
    assert gateway.transport_provider == "9router"
    assert gateway.api_key == "sk-readme"


def test_ninerouter_wins_over_legacy_names(monkeypatch):
    monkeypatch.setenv("PINEAL_LLM_BASE_URL", "https://reader.example/v1")
    monkeypatch.setenv("PINEAL_LLM_API_KEY", "sk-readme")
    monkeypatch.setenv("NINEROUTER_BASE_URL", "http://127.0.0.1:20128/v1")
    monkeypatch.setenv("NINEROUTER_API_KEY", "sk-ninerouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-cloud")

    base_url, api_key, label = resolve_legacy_endpoint()

    assert base_url == "http://127.0.0.1:20128/v1"
    assert api_key == "sk-ninerouter"
    assert label == "9router"


def test_default_is_cloud_and_labelled_truthfully(monkeypatch):
    """Hiçbir env yoksa eski davranış korunur; etiket bulutu söyler."""
    base_url, api_key, label = resolve_legacy_endpoint()

    assert base_url == "https://openrouter.ai/api/v1"
    assert api_key is None
    assert label == "openrouter"
    assert LLMGateway().transport_provider == "openrouter"


def test_remote_hub_address_is_still_labelled_9router(monkeypatch):
    """Operatör hub'ı uzak makinede çalıştırıyorsa etiket yine dürüst olmalı."""
    monkeypatch.setenv("NINEROUTER_BASE_URL", "https://hub.internal.example/v1")
    monkeypatch.setenv("NINEROUTER_API_KEY", "sk-hub")

    assert resolve_legacy_endpoint()[2] == "9router"


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("http://127.0.0.1:20128/v1", "9router"),
        ("http://localhost:20128/v1", "9router"),
        ("https://openrouter.ai/api/v1", "openrouter"),
        ("not-a-url", "openrouter"),
    ],
)
def test_endpoint_label_truthfulness(base_url, expected):
    assert provider_label_for_endpoint(base_url) == expected


def test_default_constant_matches_documented_port():
    """Varsayılan hub adresi README/.env belgeleriyle aynı olmalı."""
    assert NINEROUTER_DEFAULT_BASE_URL == "http://127.0.0.1:20128/v1"
