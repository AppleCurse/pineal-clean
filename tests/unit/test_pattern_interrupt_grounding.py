import pytest

from agent_core.agents.pattern_interrupt import PatternInterrupt


@pytest.mark.asyncio
async def test_pattern_interrupt_returns_unavailable_without_grounded_evidence():
    result = await PatternInterrupt().execute({"target_analysis": {}}, None, None)
    assert result.strategy == "UNAVAILABLE"
    assert result.confidence == 0.0
    assert result.data_confidence is False
    assert result.fallback_reason == "insufficient_grounded_evidence"
