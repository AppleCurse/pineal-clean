import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from agent_core.llm.claude_client import ClaudeAnalyzer

@pytest.fixture
def client():
    return ClaudeAnalyzer(api_key="test_key")

@pytest.fixture
def client_no_key():
    return ClaudeAnalyzer(api_key="")

@pytest.mark.asyncio
async def test_analyze_instagram_profile_success(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [
            {"text": '{"real_desire": "connection", "specific_detail": "book", "attachment_style": "secure", "core_wound": "none", "exploitability": 0.1, "dark_triad": {"machiavellianism": 0.1, "narcissism": 0.1, "psychopathy": 0.1}}'}
        ]
    }
    
    with patch('httpx.AsyncClient.post', return_value=mock_response):
        res = await client.analyze_instagram_profile("testuser", "bio", ["post1"], ["cap1"])
        assert res["real_desire"] == "connection"
        assert res["specific_detail"] == "book"
        assert res["exploitability"] == 0.1

@pytest.mark.asyncio
async def test_analyze_instagram_profile_no_key(client_no_key):
    # Should immediately return fallback when no api_key is present
    res = await client_no_key.analyze_instagram_profile("testuser", "bio", ["post1"], ["cap1"])
    assert res["real_desire"] == "API YOK - Fallback Data"
    assert res["attachment_style"] == "secure"

@pytest.mark.asyncio
async def test_analyze_instagram_profile_http_error(client):
    with patch('httpx.AsyncClient.post', side_effect=httpx.TimeoutException("Timeout")):
        res = await client.analyze_instagram_profile("testuser", "bio", ["post1"], ["cap1"])
        # Falls back to default response on error
        assert res["real_desire"] == "API YOK - Fallback Data"
