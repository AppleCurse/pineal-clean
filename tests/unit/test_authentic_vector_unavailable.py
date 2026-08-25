from types import SimpleNamespace

import pytest

from agent_core.agents.resonance_calculator import (
    ResonanceCalculationError,
    ResonanceCalculator,
)
from agent_core.task_executor import PinealExecutor


@pytest.mark.asyncio
async def test_vector_failure_returns_unavailable_not_neutral_defaults():
    """A provider failure must not become a decision-ready 0.5/0.5 vector."""
    executor = PinealExecutor.__new__(PinealExecutor)
    executor._log = lambda *_: None

    async def unavailable(*_, **__):
        raise RuntimeError("provider unavailable")

    executor.llm_gateway = SimpleNamespace(query_json=unavailable)

    vector = await executor._calculate_authentic_vector({"some": "profile data"})

    assert vector is None


@pytest.mark.asyncio
async def test_unavailable_vector_is_explicit_metadata_not_numeric_evidence():
    input_data = {"user_authentic_vector": {"depth": 0.5, "energy": 0.5}}

    PinealExecutor._store_authentic_vector(
        PinealExecutor.__new__(PinealExecutor), input_data, "user", None
    )

    assert "user_authentic_vector" not in input_data
    assert input_data["user_authentic_vector_status"] == {
        "available": False,
        "reason": "AUTHENTIC_VECTOR_UNAVAILABLE",
    }


@pytest.mark.asyncio
async def test_resonance_rejects_missing_user_vector_instead_of_using_default():
    calculator = ResonanceCalculator()

    with pytest.raises(ResonanceCalculationError, match="Kullanıcı authentic vector"):
        await calculator.execute(
            {"target_authentic_vector": {"depth": 0.7, "energy": 0.4}},
            memory=None,
            llm_gateway=None,
        )


@pytest.mark.asyncio
async def test_resonance_rejects_an_empty_target_instead_of_deriving_from_empty_dict():
    calculator = ResonanceCalculator()

    with pytest.raises(ResonanceCalculationError, match="ölçülebilir vektör"):
        await calculator.execute(
            {"user_authentic_vector": {"depth": 0.7, "energy": 0.4}, "target_analysis": {}},
            memory=None,
            llm_gateway=None,
        )
