import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.task_executor import PinealExecutor
from agent_core.agents.resonance_calculator import ResonanceCalculator
from agent_core.agents.mirror_truth import MirrorReflection
from agent_core.agents.human_behavior import DigitalColdReading, MicroSignal
from agent_core.agents.autonomous_verifier import VerifierReport, VerificationResult
from agent_core.agents.pattern_interrupt import GeneratedMessage
from agent_core.services.uncertainty_engine import UncertaintyReport
from agent_core.services.canonical_memory import CanonicalMemory

@pytest.mark.asyncio
async def test_real_resonance_calculator_execution_in_executor(tmp_path):
    executor = PinealExecutor()
    executor.memory = CanonicalMemory(str(tmp_path))
    assert isinstance(executor.agents["resonance_calc"], ResonanceCalculator)
    
    executor.uncertainty.evaluate = MagicMock(
        return_value=UncertaintyReport(confidence=0.95, is_suspicious=False, reason="test")
    )
    
    mock_mirror_res = MirrorReflection(
        user_core_frequency="derin",
        surface_persona="analitik",
        alignment_score=0.9,
        authentic_anchors=["felsefe"]
    )
    mock_human_res = DigitalColdReading(
        observations=["Test gözlemi"],
        possible_interpretations=["Test hipotezi"],
        alternative_interpretations=[],
            unsupported_claims=[],
            confidence=0.8,
        micro_signals=[MicroSignal(signal_type="authentic", confidence=0.9, location="bio", evidence="gercek", psychological_weight=0.8)],
        achilles_score=85.0,
        resonance_potential=0.8
    )
    mock_verifier_res = VerifierReport(
        verifications=[VerificationResult(claim_text="test", truth_status="DOĞRULANDI", evidence_url="http://test.com", contradiction_detail="yok")],
        overall_authenticity_score=0.9
    )
    mock_pattern_res = GeneratedMessage(
        message="test hook",
        strategy="test strategy",
        confidence=0.9,
        compliance_score=0.9,
        dialogue_tree=[],
        data_confidence=True,  # gerçek LLM sonucu simülasyonu: açık beyan ([022])
        fallback_reason=None
    )
    
    executor.agents["mirror_truth"].execute = AsyncMock(return_value=mock_mirror_res)
    executor.agents["autonomous_verifier"].execute = AsyncMock(return_value=mock_verifier_res)
    # This test isolates executor-to-calculator wiring. Supply explicitly
    # calculated test vectors; production must not invent neutral defaults.
    executor._calculate_authentic_vector = AsyncMock(
        side_effect=[
            {"depth": 0.8, "energy": 0.4, "achilles_heel": "test", "core_wound": "test", "dark_detail": "test"},
            {"depth": 0.7, "energy": 0.5, "achilles_heel": "test", "core_wound": "test", "dark_detail": "test"},
        ]
    )
    executor.agents["human_behavior"].execute = AsyncMock(return_value=mock_human_res)
    executor.agents["pattern_interrupt"].execute = AsyncMock(return_value=mock_pattern_res)
    
    input_data = {
        "user_profile": {"bio": "Derin felsefe ve arayış"},
        "target_profile": {"bio": "Arayış ve yalnızlık"},
    }
    
    status = await executor.execute_task(input_data, task_id="test_resonance_sig_123")
    ran_agents = [step["agent"] for step in status.evidence_chain]
    assert "resonance_calc" in ran_agents
    
    res_step = next(step for step in status.evidence_chain if step["agent"] == "resonance_calc")
    assert "compatibility_score" in res_step["result"]
