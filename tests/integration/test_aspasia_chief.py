import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.aspasia.aspasia_chief import AspasiaChief, AspasiaResponse
from agent_core.services.llm_gateway import LLMGateway
from agent_core.domain.memory_models import TaskSnapshot, AspasiaSession

@pytest.fixture
def mock_llm_gateway():
    gateway = MagicMock(spec=LLMGateway)
    gateway.query = AsyncMock(return_value="Mocked Socratic response")
    return gateway

@pytest.fixture
def aspasia(mock_llm_gateway):
    return AspasiaChief(llm_gateway=mock_llm_gateway)

def test_build_telemetry_summary_empty(aspasia):
    assert "Sistem beklemede" in aspasia.build_telemetry_summary(None)

def test_build_telemetry_summary(aspasia):
    snapshot = TaskSnapshot(task_id="test1", status="processing", current_agent="mirror_truth")
    summary = aspasia.build_telemetry_summary(snapshot)
    assert "test1" in summary
    assert "processing" in summary
    assert "mirror_truth" in summary

@pytest.mark.asyncio
async def test_chat_updates_session_and_calls_llm(aspasia):
    room_state = {"client_id": "client_1"}
    resp = await aspasia.chat("Ne yapiyorsun?", room_state)
    
    assert resp.message == "Mocked Socratic response"
    assert "aspasia_session" in room_state
    session = room_state["aspasia_session"]
    assert len(session.conversation_history) == 2
    assert session.conversation_history[0].role == "user"
    assert session.conversation_history[1].role == "aspasia"
