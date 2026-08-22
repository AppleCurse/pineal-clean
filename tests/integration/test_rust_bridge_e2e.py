import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agent_core.agents.rust_bridge_agent import run_full_pipeline
from tests.integration.test_p2_release_gate import mock_query_json

@pytest.mark.asyncio
async def test_rust_bridge_e2e_pipeline():
    """
    Test that the Rust bridge can successfully trigger the Python executor and retrieve formatted results.
    """
    target_url = "https://instagram.com/test_target"
    scraped_data = {
        'bio': 'Sadece pozitif enerji ✨',
        'posts': ['Cuma akşamı evdeyim yorgunum 😴']
    }
    user_freq = {
        'rituals': ['çay', 'kitap', 'neset_ertas'],
        'playlist': ['neşet ertaş - gönül dağı'],
        'envies': ['derin bağlantılar', 'anlaşılmak']
    }

    with patch("agent_core.services.llm_gateway.LLMGateway.query_json", new=AsyncMock(side_effect=mock_query_json)):
        from agent_core.services.search_engine import SearchResult
        with patch("agent_core.services.search_engine.SearchEngine.search", new=AsyncMock(return_value=[SearchResult(query="dummy", content="Sadece pozitif", source_url="http://mock.com")])):
            import os
            with patch.dict(os.environ, {"TAVILY_API_KEY": "mock_key"}):
                result = await asyncio.to_thread(run_full_pipeline, target_url, scraped_data, user_freq)
                
                assert result["target_url"] == target_url
                assert result["status"] == "completed"
                assert "overall_authenticity_score" in result
                assert "alignment_score" in result
