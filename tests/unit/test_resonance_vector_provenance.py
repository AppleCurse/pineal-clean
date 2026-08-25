import pytest

from agent_core.agents.resonance_calculator import ResonanceCalculationError, ResonanceCalculator


@pytest.mark.asyncio
async def test_achilles_score_cannot_be_converted_into_target_vector():
    calculator = ResonanceCalculator()
    with pytest.raises(ResonanceCalculationError, match="metin, achilles skoru"):
        await calculator.execute(
            {
                "user_authentic_vector": {"depth": 0.8, "energy": 0.4},
                "target_analysis": {"achilles_score": 85},
            },
            memory=None,
            llm_gateway=None,
        )
