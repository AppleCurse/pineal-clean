import pytest
from pydantic import BaseModel
from agent_core.services.llm_gateway import LLMGateway

class DummySchema(BaseModel):
    message: str
    confidence: float

@pytest.mark.asyncio
async def test_llm_gateway_json_repair():
    gateway = LLMGateway()
    # Mock LLM calls
    # Call 1: returns broken markdown JSON
    # Call 2 (repair): returns fixed JSON
    
    call_count = 0
    async def mock_query(prompt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "```json\n{\n\"message\": \"test\",\n\"confidence\": 0.9\n```"
        return "{\"message\": \"test\", \"confidence\": 0.9}"
        
    gateway.query = mock_query
    
    result = await gateway.query_json("Test prompt", DummySchema)
    
    assert result.message == "test"
    assert result.confidence == 0.9
    assert call_count == 2  # It should trigger repair
