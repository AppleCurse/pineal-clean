"""
ADIM 3 — Telemetri FIFO sıra garantisı (WebSocket).

Gerekçe (röntgen, canlı): eski loop.create_task deseninde eventler 'result'
mesajıyla yarışıyordu; ilk canlı testte istemciye HİÇ event uluşmadı,
ikincisinde hepsi uluştu (non-deterministik). Bu test kuyruk mimarisinin
sözleşmesini kilitler: mesajlar üretim sırasıyla, result EN SON iletilir.
"""
import uuid

from fastapi.testclient import TestClient

from backend.api import app


def _collect_for_client(client: TestClient, client_id: str) -> list:
    with client.websocket_connect(f"/ws/{client_id}") as ws:
        r = client.post("/api/initiate", json={
            "client_id": client_id,
            "url": "",  # scraper atlanır
            "rituals": "çay,kitap",
            "playlist": "neşet ertaş",
            "envies": "derin bağlantılar",
            "aggressiveness": 1.0,
            "evidence_th": 3,
        })
        assert r.status_code == 200

        types = []
        for _ in range(100):
            m = ws.receive_json()
            t = m.get("type") or (m.get("event") or {}).get("event_type")
            types.append(t)
            if t == "result":
                break
        return types


def test_events_arrive_in_order_and_result_is_last():
    with TestClient(app) as client:
        types = _collect_for_client(client, f"wsorder_{uuid.uuid4().hex[:8]}")

        assert "result" in types, "görev bitti ama result iletilmedi"
        assert types[-1] == "result", f"result son mesaj olmalı, gelen: {types}"

        # Telemetri eventleri result'tan ÖNCE ve gerçekten iletilmiş olmalı
        assert "TaskStarted" in types, f"TaskStarted iletilmedi: {types}"
        assert types.index("TaskStarted") < types.index("result")

        # Snapshot akışı da sıralı olmalı
        assert "snapshot_update" in types


def test_events_arrive_deterministically_across_runs():
    """Ardışık 2 koşu: her seferinde aynı sözleşme (yarış yok)."""
    with TestClient(app) as client:
        for i in range(2):
            types = _collect_for_client(client, f"wsdet_{i}_{uuid.uuid4().hex[:8]}")
            assert types[-1] == "result"
            assert "TaskStarted" in types

# --- HERMETIC TEST GUARD: blocks live LLM calls (money + consistency) ---
import pytest as _pytest
from agent_core.services.llm_gateway import LLMGateway as _LLMGateway

@_pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    async def _blocked(self, *a, **k):
        raise RuntimeError("REAL_LLM_CALL_NOT_EXECUTED: test kipi")
    monkeypatch.setattr(_LLMGateway, "query", _blocked)
