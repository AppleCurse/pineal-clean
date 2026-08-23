import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from agent_core.services.llm_gateway import LLMGateway
from backend.api import app, _effective_scraper_type

def test_effective_scraper_type_url_aware():
    assert _effective_scraper_type("https://www.instagram.com/gokayte/", "cross") == "instagram"
    assert _effective_scraper_type("https://x.com/gokayte", "cross") == "x"
    assert _effective_scraper_type("https://twitter.com/gokayte", "instagram") == "x"
    assert _effective_scraper_type("https://ornek.com/profil", "cross") == "cross"
    assert _effective_scraper_type("", "cross") == "cross"

def test_vault_key_unlocks_live_llm_gate():
    """Kasa'ya anahtar -> gateway.live_unlocked True -> flag'siz canlı çağrıya izin."""
    cid = f"unlock_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        r = client.post("/api/vault", json={"client_id": cid, "api_key": "sk-or-v1-kullanici-anahtari"})
        assert r.status_code == 200
        room = app.state.rooms[cid]
        assert room["executor"].llm_gateway.api_key == "sk-or-v1-kullanici-anahtari"
        assert room["executor"].llm_gateway.live_unlocked is True

@pytest.mark.asyncio
async def test_unlocked_gateway_passes_gate_without_env_flag(monkeypatch):
    """live_unlocked=True iken LIVE_LLM_E2E bayrağı olmadan HTTP katmanına ulaşılır."""
    monkeypatch.delenv("LIVE_LLM_E2E", raising=False)

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "canlı"}}]})

    gw = LLMGateway()
    gw.set_key("sk-or-v1-test")
    gw.live_unlocked = True
    gw.client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-v1-test",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    res = await gw.query("ping")
    assert res == "canlı"
    assert "openrouter.ai" in captured["url"]

@pytest.mark.asyncio
async def test_locked_gateway_still_blocks_without_key_or_flag(monkeypatch):
    """Anahtar yok + bayrak yok + kilitli -> hâlâ RED (güvenlik korunur)."""
    monkeypatch.delenv("LIVE_LLM_E2E", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    gw = LLMGateway()
    gw.live_unlocked = False
    with pytest.raises(RuntimeError, match="REAL_LLM_CALL_NOT_EXECUTED"):
        await gw.query("ping")
