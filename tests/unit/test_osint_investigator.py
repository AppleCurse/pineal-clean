import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent_core.agents.osint_investigator import OsintInvestigatorAgent, OsintProfile
from agent_core.services.llm_gateway import LLMGateway

# --- HERMETIC TEST GUARD: blocks live LLM calls ---
@pytest.fixture(autouse=True)
def _hermetic_guard(monkeypatch):
    async def _blocked(self, *a, **k):
        raise RuntimeError("REAL_LLM_CALL_NOT_EXECUTED: unit test kipi")
    monkeypatch.setattr(LLMGateway, "query", _blocked)
    monkeypatch.setattr(LLMGateway, "query_json", _blocked)


@pytest.mark.asyncio
async def test_osint_empty_username():
    """Kullanıcı adı boş olduğunda doğrudan confidence=1.0 ile erken dönüş yapılmalıdır."""
    agent = OsintInvestigatorAgent()
    payload = {"target_profile": {"username": "", "bio": "Bir gezgin"}}
    res = await agent.execute(payload)
    assert isinstance(res, OsintProfile)
    assert res.confidence == 1.0
    assert res.connected_emails == []
    assert res.associated_platforms == []


@pytest.mark.asyncio
async def test_osint_no_api_key_returns_unavailable(monkeypatch):
    """P0: OSINT_INDUSTRIES_KEY yokken LLM çağrısı YAPILMAZ;
    UNAVAILABLE dönülür (boş kanıt + confidence=0.0). Uydurma e-posta/platform yok."""
    monkeypatch.delenv("OSINT_INDUSTRIES_KEY", raising=False)
    
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.query_json_chain = AsyncMock(side_effect=RuntimeError("REAL_LLM_CALL_NOT_EXECUTED"))
    
    agent = OsintInvestigatorAgent(llm_gateway=mock_gateway)
    payload = {
        "target_profile": {
            "username": "@tech_wanderer",
            "bio": "Open source coder, loves acoustic music and photography."
        }
    }
    
    res = await agent.execute(payload)
    assert isinstance(res, OsintProfile)
    assert res.confidence == 0.0
    assert res.data_confidence is False
    assert res.fallback_reason == "provider_credentials_unavailable"
    assert res.connected_emails == []
    assert res.connected_phones == []
    assert res.associated_platforms == []
    assert res.digital_footprint_score == 0.0
    assert res.dark_web_hits == 0
    
    mock_gateway.query_json_chain.assert_not_awaited()


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_osint_api_error_returns_unavailable(mock_get, monkeypatch):
    """P0: canlı OSINT API hatasında uydurma veri üretilmez;
    UNAVAILABLE dönülür (boş kanıt + confidence=0.0)."""
    monkeypatch.setenv("OSINT_INDUSTRIES_KEY", "sk-osint-valid-test-key")

    # Configure the mock
    mock_resp = AsyncMock()
    mock_resp.status = 500
    mock_resp.text = AsyncMock(return_value="internal server error")

    # Set __aenter__ to return the mock response object
    mock_get.return_value.__aenter__.return_value = mock_resp

    agent = OsintInvestigatorAgent()
    payload = {"target_profile": {"username": "test_target", "bio": "bio text"}}
    
    res = await agent.execute(payload)
    assert isinstance(res, OsintProfile)
    assert res.confidence == 0.0
    assert res.data_confidence is False
    assert res.fallback_reason == "api_error"
    assert res.connected_emails == []
    assert res.associated_platforms == []


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_osint_with_api_key_simulation(mock_get, monkeypatch):
    """OSINT_INDUSTRIES_KEY mevcutken canlı bağlantı simülasyonu çalışmalıdır."""
    monkeypatch.setenv("OSINT_INDUSTRIES_KEY", "sk-osint-valid-test-key")

    # Configure the mock
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "emails": ["test@example.com"],
        "phones": [],
        "platforms": ["X"]
    })

    # Set __aenter__ to return the mock response object
    mock_get.return_value.__aenter__.return_value = mock_resp

    agent = OsintInvestigatorAgent()
    payload = {"target_profile": {"username": "cyber_agent"}}
    
    res = await agent.execute(payload)
    assert isinstance(res, OsintProfile)
    assert res.confidence == 0.9
    assert res.data_confidence is True
    assert res.connected_emails == ["test@example.com"]
    assert res.associated_platforms == ["X"]
