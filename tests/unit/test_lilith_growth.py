import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.agents.lilith_growth import LilithGrowthAgent, LilithContentPackage

@pytest.mark.asyncio
async def test_lilith_growth_agent_execution():
    mock_gateway = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    
    mock_json = """{
      "hook": "Çoğu insan başarısızlıktan değil, parlamaktan korkar.",
      "psychological_angle": "Görünürlük kaygısı ve statü tehdidi",
      "content_body": "Gölgede kalmak konforludur. Ortaya çıktığınızda herkes sizi hedef alır.",
      "call_to_action": "Bu konfor alanını ne zaman terk edeceksiniz?",
      "pollinations_image_prompt": "cinematic dark moody photography of a silhouetted figure in spotlight",
      "confidence": 0.95
    }"""
    mock_message.content = mock_json
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_gateway.chat = AsyncMock(return_value=mock_response)

    agent = LilithGrowthAgent(llm_gateway=mock_gateway)
    
    payload = {
        "topic": "Görünürlük Korkusu",
        "platform": "x_twitter",
        "friction_profile": {
            "sensitivities": ["yargılanma korkusu"],
            "stress_triggers": ["aşırı dikkat çekme"]
        },
        "passion_profile": {
            "core_passions": ["özgünlük"],
            "energizing_topics": ["felsefe"]
        },
        "cognitive_style": {
            "communication_tone": "keskin"
        }
    }

    result = await agent.execute(payload)

    assert isinstance(result, LilithContentPackage)
    assert result.hook == "Çoğu insan başarısızlıktan değil, parlamaktan korkar."
    assert result.platform == "x_twitter"
    assert "https://image.pollinations.ai/prompt/" in result.pollinations_image_url
    assert result.data_confidence is True
    assert result.confidence == 0.95
