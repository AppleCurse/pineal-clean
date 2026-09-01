"""Health endpoint DEGRADED durum testleri.

Sözleşme (Go/No-Go raporundan):
- status: ready    → HTTP 200
- status: degraded → HTTP 200 (load-balancer geçirir; monitoring degraded_reasons okur)
- status: failed   → HTTP 503
- status: starting → HTTP 503
- PINEAL_LLM_BACKEND=unified + config eksik → degraded_reasons içinde UNIFIED_ROUTER_CONFIG_MISSING
- PINEAL_ENV=production + OPENROUTER_MAX_SPEND_USD=0 → SPEND_CAP_UNLIMITED degraded_reason
- PINEAL_ENV=production + OPENROUTER_MAX_SPEND_USD=5 → spend_cap_unlimited: false
"""

from fastapi.testclient import TestClient


def _make_health(status: str, **extra) -> dict:
    base = {"status": status, "error_code": None, "dependencies": []}
    base.update(extra)
    return base


def test_health_ready_returns_200():
    from backend.api import app

    with TestClient(app) as client:
        app.state.startup_health = _make_health("ready")
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_health_degraded_returns_200_not_503():
    """DEGRADED → HTTP 200 (servis çalışıyor), degraded_reasons alanı taşır."""
    from backend.api import app

    with TestClient(app) as client:
        app.state.startup_health = _make_health(
            "degraded",
            degraded_reasons=["UNIFIED_ROUTER_CONFIG_MISSING"],
        )
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert "UNIFIED_ROUTER_CONFIG_MISSING" in body["degraded_reasons"]


def test_health_failed_returns_503():
    from backend.api import app

    with TestClient(app) as client:
        app.state.startup_health = _make_health("failed", error_code="SOME_ERROR")
        r = client.get("/health")
    assert r.status_code == 503


def test_health_starting_returns_503():
    from backend.api import app

    with TestClient(app) as client:
        app.state.startup_health = {"status": "starting", "error_code": None, "dependencies": []}
        r = client.get("/health")
    assert r.status_code == 503


def test_spend_cap_unlimited_in_production_surfaces_degraded(monkeypatch):
    """PINEAL_ENV=production + spend_cap=0 → SPEND_CAP_UNLIMITED degraded_reason."""
    from backend.api import app

    monkeypatch.setenv("PINEAL_ENV", "production")
    monkeypatch.setenv("OPENROUTER_MAX_SPEND_USD", "0")
    monkeypatch.setenv("PINEAL_TOKEN", "test-token-sentinel")

    with TestClient(app) as client:
        r = client.get("/health")
    body = r.json()
    assert r.status_code == 200          # servis çalışıyor (load-balancer geçirir)
    assert body.get("spend_cap_unlimited") is True
    assert body.get("status") == "degraded"
    assert "SPEND_CAP_UNLIMITED" in body.get("degraded_reasons", [])


def test_spend_cap_set_no_cap_degraded(monkeypatch):
    """production + spend_cap > 0 → SPEND_CAP_UNLIMITED degraded_reasons'a girmez."""
    from backend.api import app

    monkeypatch.setenv("PINEAL_ENV", "production")
    monkeypatch.setenv("OPENROUTER_MAX_SPEND_USD", "10.0")
    monkeypatch.setenv("PINEAL_TOKEN", "test-token-sentinel")

    with TestClient(app) as client:
        r = client.get("/health")
    body = r.json()
    assert body.get("spend_cap_unlimited") is False
    assert "SPEND_CAP_UNLIMITED" not in body.get("degraded_reasons", [])


def test_spend_cap_dev_unlimited_not_degraded(monkeypatch):
    """development ortamında spend_cap=0 → degraded tetiklemez (normal geliştirici kullanımı)."""
    from backend.api import app

    monkeypatch.setenv("PINEAL_ENV", "development")
    monkeypatch.setenv("OPENROUTER_MAX_SPEND_USD", "0")
    monkeypatch.delenv("PINEAL_TOKEN", raising=False)

    with TestClient(app) as client:
        r = client.get("/health")
    body = r.json()
    assert r.status_code == 200
    assert "SPEND_CAP_UNLIMITED" not in body.get("degraded_reasons", [])
