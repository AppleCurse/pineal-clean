"""
ADIM 1 / G0.2 — /api/aspasia/chat HTTP regresyon testi.

Gerekçe (röntgen): backend/api.py:532 5 arguman gonderirken AspasiaChief.chat()
3 parametre kabul ediyordu -> canlı HTTP 500 (TypeError). Mevcut mock'lu
modül testleri bu hatayı yakalayamıyordu çünkü modülü DOĞRU imzayla çağırıyorlardı.
Bu testler gerçek ASGI transport ile ENDPOINT'i çağırır — imza kayması
bir daha asla sessiz kalamaz.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock

from backend.api import app


def _payload(client_id: str, **overrides) -> dict:
    base = {"client_id": client_id, "user_message": "Şu an sistemde ne oluyor?"}
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_aspasia_chat_http_200_fallback():
    """LLM anahtarı yok: endpoint yine de 200 + fallback mesaj dönmeli (500 DEĞİL)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/aspasia/chat", json=_payload("c_http_fix_1"))
    assert r.status_code == 200, f"chat() imza kayması geri gelebilir: {r.text[:300]}"
    data = r.json()
    assert data.get("message")
    assert data.get("confidence_assessment") in ("high", "fallback")


@pytest.mark.asyncio
async def test_aspasia_chat_with_image_data_http_200():
    """image_data (base64) ile çağrı: eski imza hatasının tetiklendiği vaka."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/aspasia/chat",
            json=_payload("c_http_fix_2", image_data="data:image/png;base64,AAAA"),
        )
    assert r.status_code == 200
    assert r.json().get("message")


@pytest.mark.asyncio
async def test_aspasia_chat_mocked_llm_high(monkeypatch):
    """LLM çalışıyorsa gerçek yanıt dönmeli ve oturuma yazmalı."""
    from agent_core.services.llm_gateway import LLMGateway
    monkeypatch.setattr(
        LLMGateway, "query",
        AsyncMock(return_value="Düşüncelerimizi sıraya dizelim, Mösyö. Sistem ayakta."),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/aspasia/chat", json=_payload("c_http_fix_3"))
    assert r.status_code == 200
    data = r.json()
    assert data["confidence_assessment"] == "high"
    assert "Mösyö" in data["message"]
