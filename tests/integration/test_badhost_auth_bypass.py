"""
AUDIT 2026-09-11 P0-1 — CVE-2026-48710 / GHSA-86qp-5c8j-p5mr ("BadHost")
auth bypass regresyon sözleşmesi.

Zafiyet: Starlette <=1.0.0 request.url'u DOĞRULANMAMIŞ Host header'ından
yeniden kurar; Host içine '/', '?', '#' yerleştirilince request.url.path
router'ın dispatch ettiği gerçek path'ten sapar. Eski middleware kararı
`request.url.path.startswith("/api/")` olduğu için zehirlenmiş Host ile
tokensiz istek korumalı uçlardan 200 alabiliyordu (ampirik PoC:
starlette 0.37.2 + fastapi 0.115.2, `Host: x/zzz?y=` -> 200).

Kalıcı çözüm: güvenlik kararları ham ASGI scope path'inden verilir
(backend/api.py `_secure_path`); scope["path"] Host zehirlenmesinden
etkilenmez. Bu dosya o sözleşmeyi kilitler.
"""
import uuid

from fastapi.testclient import TestClient
from starlette.requests import Request

from backend import api as api_module
from backend.api import app

TOKEN = "badhost-regression-token"


def _cid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# Host içinde '/', '?' ve '#' — urlsplit yeniden-parse ederken path/query
# sınırlarını kaydırır (advisory'deki örnek kalıp).
POISONED_HOST = "x/zzz?y="
POISONED_HOST_FRAGMENT = "evil.local/#"


def test_secure_path_reads_raw_scope_not_reconstructed_url():
    """_secure_path her zaman scope['path'] döner; Host'tan bağımsızdır.

    Not: starlette>=1.0.1 Host'u doğruladığı için request.url.path zaten
    sapmaz; bu assert yine de güvenlik kararının KAYNAĞINI (raw scope)
    kilitler — eski/zafiyetli bir stack'e dönülse bile middleware etkilenmez.
    """
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/secret",
        "query_string": b"",
        "headers": [(b"host", POISONED_HOST.encode())],
    }
    request = Request(scope)
    assert api_module._secure_path(request) == "/api/secret"


def test_secure_path_missing_scope_path_fails_closed():
    request = Request({"type": "http", "headers": []})
    assert api_module._secure_path(request) == ""


def test_badhost_does_not_bypass_api_auth(monkeypatch):
    """Tokensiz istek + zehirlenmiş Host -> 401 (eski kodda 200'dü)."""
    monkeypatch.setenv("PINEAL_TOKEN", TOKEN)
    with TestClient(app) as client:
        for host in (POISONED_HOST, POISONED_HOST_FRAGMENT):
            r = client.get(
                "/api/telemetry",
                params={"client_id": _cid("badhost")},
                headers={"Host": host},
            )
            assert r.status_code == 401, (
                f"Host={host!r} auth'u atlatmamalı (CVE-2026-48710)"
            )


def test_badhost_does_not_bypass_openai_auth(monkeypatch):
    """/v1/* ucu da Host zehirlenmesinden etkilenmez."""
    monkeypatch.setenv("PINEAL_TOKEN", TOKEN)
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": [{"role": "user", "content": "x"}]},
            headers={"Host": POISONED_HOST},
        )
        assert r.status_code == 401


def test_valid_token_still_passes_under_poisoned_host(monkeypatch):
    """Doğru token ile istek Host'tan bağımsız geçmeye devam eder
    (düzeltme auth'u aşırı-kapatmamalı)."""
    monkeypatch.setenv("PINEAL_TOKEN", TOKEN)
    with TestClient(app) as client:
        r = client.get(
            "/api/telemetry",
            params={"client_id": _cid("badhost-ok")},
            headers={"Host": POISONED_HOST, "X-API-Key": TOKEN},
        )
        assert r.status_code == 200


def test_normal_auth_paths_unaffected(monkeypatch):
    """Zehirlenme yokken klasik davranış değişmedi: 401/200/401."""
    monkeypatch.setenv("PINEAL_TOKEN", TOKEN)
    with TestClient(app) as client:
        cid = _cid("badhost-plain")
        assert client.get("/api/telemetry", params={"client_id": cid}).status_code == 401
        assert client.get(
            "/api/telemetry", params={"client_id": cid}, headers={"X-API-Key": TOKEN}
        ).status_code == 200
