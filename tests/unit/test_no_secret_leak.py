"""
FAZ 3 / G3.2 — sır sızma kilidi (log redaction).

Sözleşme: API anahtarı ve cookie'ler oda belleğinde tutulur (çalışmak zorunda)
ama ASLA log mesajlarına, telemetri event'lerine veya HTTP yanıtlarına sızamaz.
"""
import json
import time
import uuid

from fastapi.testclient import TestClient

from backend.api import app

SECRET_KEY = "sk-or-v1-LEAKGUARD123"
SECRET_COOKIE = "auth_token=COOKIESECRET456"


def _drain_room_texts(room: dict) -> str:
    """İşlenmiş loglar + kuyrukta bekleyen ham mesajların hepsini tek metinde topla."""
    parts = list(room.get("logs", []))
    q = room.get("queue")
    if q is not None:
        waiting = list(q._queue)  # test amaçlı iç erişim
        for kind, payload in waiting:
            try:
                parts.append(json.dumps(payload, default=str, ensure_ascii=False))
            except Exception:
                parts.append(str(payload))
    return "\n".join(parts)


def test_no_secret_leak_in_logs_events_or_responses():
    cid = f"leak_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        # Anahtar + cookie mühürle
        r = client.post("/api/vault", json={
            "client_id": cid, "api_key": SECRET_KEY, "x_cookie": SECRET_COOKIE,
        })
        assert SECRET_KEY not in r.text and SECRET_COOKIE not in r.text
        # Sohbet tetikle (log + event üretir)
        client.post("/api/aspasia/chat", json={"client_id": cid, "user_message": "durum?"})
        time.sleep(0.3)  # sender task'in kuyruğu işlemesi için
        room = app.state.rooms[cid]  # lifespan kapanışı rooms'u temizler; referansı şimdi al

    # Tasarım: anahtar YALNIZCA gateway belleğinde yaşar (vault dict'ine yazılmaz);
    # cookie ise scraper rotasyonu için vault'ta tutulur. İkisi de LOGA SIZMAMALI:
    assert room["executor"].llm_gateway.api_key == SECRET_KEY  # çalışmak için bellekte
    assert "api_key" not in room["vault"]                        # kasaya persist edilmez
    assert room["vault"].get("x_cookie") == SECRET_COOKIE        # rotasyon için kasada
    # ...ama loglara/kuyruğa/eventlere SIZMAZ:
    all_logs = _drain_room_texts(room)
    assert SECRET_KEY not in all_logs, f"API anahtarı loga sızdı: {all_logs[:300]}"
    assert SECRET_COOKIE not in all_logs, f"Cookie loga sızdı: {all_logs[:300]}"

    events = room.get("events", [])
    ev_text = json.dumps([e.model_dump(mode="json") for e in events], default=str)
    assert SECRET_KEY not in ev_text and SECRET_COOKIE not in ev_text


def test_vault_response_never_echoes_secrets():
    cid = f"leak_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        r = client.post("/api/vault", json={"client_id": cid, "api_key": SECRET_KEY})
    assert r.status_code == 200
    assert r.json() == {"status": "secured"}
