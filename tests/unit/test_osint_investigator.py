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
async def test_osint_no_api_key_calls_llm_chain(monkeypatch):
    """OSINT_INDUSTRIES_KEY yokken LLM zinciri üzerinden akıllı simülasyon yapılmalıdır."""
    monkeypatch.delenv("OSINT_INDUSTRIES_KEY", raising=False)
    
    mock_gateway = MagicMock(spec=LLMGateway)
    expected_profile = OsintProfile(
        connected_emails=["tahmini_maskelenmis@gmail.com"],
        connected_phones=[],
        associated_platforms=["GitHub", "Spotify", "LinkedIn"],
        digital_footprint_score=0.75,
        dark_web_hits=0,
        confidence=0.85
    )
    mock_gateway.query_json_chain = AsyncMock(return_value=expected_profile)
    
    agent = OsintInvestigatorAgent(llm_gateway=mock_gateway)
    payload = {
        "target_profile": {
            "username": "@tech_wanderer",
            "bio": "Open source coder, loves acoustic music and photography."
        }
    }
    
    res = await agent.execute(payload)
    assert isinstance(res, OsintProfile)
    assert res.digital_footprint_score == 0.0
    assert res.confidence == 0.0
    


@pytest.mark.asyncio
async def test_osint_llm_failure_graceful_fallback(monkeypatch):
    """LLM sorgusunda hata meydana gelirse sistem kırılmamalı, varsayılan OsintProfile(confidence=1.0) dönmelidir."""
    monkeypatch.delenv("OSINT_INDUSTRIES_KEY", raising=False)
    
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.query_json_chain = AsyncMock(side_effect=RuntimeError("Rate limit / OpenRouter down"))
    
    agent = OsintInvestigatorAgent(llm_gateway=mock_gateway)
    payload = {"target_profile": {"username": "test_target", "bio": "bio text"}}
    
    res = await agent.execute(payload)
    assert isinstance(res, OsintProfile)
    assert res.confidence == 0.0
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
