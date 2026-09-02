import pytest
from pydantic import BaseModel
from agent_core.services.llm_gateway import LLMGateway, SpendCapExceeded


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
        return '{"message": "test", "confidence": 0.9}'

    gateway.query = mock_query

    result = await gateway.query_json("Test prompt", DummySchema)

    assert result.message == "test"
    assert result.confidence == 0.9
    assert call_count == 2  # It should trigger repair


@pytest.mark.asyncio
async def test_json_repair_does_not_run_on_transport_errors():
    """Repair is scoped to parse/schema failures — not spend-cap / transport / auth."""
    gateway = LLMGateway()
    call_count = 0

    async def boom(prompt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise SpendCapExceeded("cap hit")

    gateway.query = boom

    with pytest.raises(SpendCapExceeded):
        await gateway.query_json("Test prompt", DummySchema)

    assert call_count == 1  # no second paid repair attempt


@pytest.mark.asyncio
async def test_json_repair_does_not_run_on_runtime_errors():
    gateway = LLMGateway()
    call_count = 0

    async def boom(prompt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("provider 503")

    gateway.query = boom

    with pytest.raises(RuntimeError, match="503"):
        await gateway.query_json("Test prompt", DummySchema)

    assert call_count == 1


@pytest.mark.asyncio
async def test_json_repair_runs_on_schema_validation_error():
    """A parseable-but-invalid payload still triggers one repair attempt."""
    gateway = LLMGateway()
    call_count = 0

    async def mock_query(prompt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Valid JSON, wrong types → ValidationError path
            return '{"message": 123, "confidence": "nope"}'
        return '{"message": "ok", "confidence": 0.5}'

    gateway.query = mock_query
    result = await gateway.query_json("Test prompt", DummySchema)
    assert result.message == "ok"
    assert call_count == 2
