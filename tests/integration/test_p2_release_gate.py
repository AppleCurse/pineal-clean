import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from agent_core.task_executor import PinealExecutor
from agent_core.agents.pattern_interrupt import PatternInterrupt
from agent_core.agents.autonomous_verifier import AutonomousVerifier
from agent_core.agents.mirror_truth import MirrorOfTruth
from agent_core.agents.human_behavior import HumanBehaviorAnalyzer
from agent_core.agents.resonance_calculator import ResonanceCalculator

# Import Pydantic models for mocking
from agent_core.agents.mirror_truth import MirrorReflection
from agent_core.agents.autonomous_verifier import VerifierReport, VerificationResult
from agent_core.agents.human_behavior import DigitalColdReading, MicroSignal
from agent_core.agents.pattern_interrupt import GeneratedMessage, ScenarioResponse
from agent_core.agents.resonance_calculator import ResonanceProfile

async def mock_query_json(prompt, response_model, **kwargs):
    if response_model.__name__ == "MirrorReflection":
        return MirrorReflection(
            user_core_frequency="derin_ruh",
            surface_persona="pozitif",
            alignment_score=0.9,
            authentic_anchors=["yalnizlik"]
        )
    elif response_model.__name__ == "VerifierReport":
        return VerifierReport(
            verifications=[VerificationResult(claim_text="test", truth_status="TRUE", evidence_url="http", contradiction_detail="none")],
            overall_authenticity_score=0.85,
            status="VERIFIED"
        )
    elif response_model.__name__ == "DigitalColdReading":
        return DigitalColdReading(
            surface_identity="sosyal",
            detected_wound="anlasilmama",
            defense_mechanism="mizah",
            micro_signals=[MicroSignal(signal_type="authentic", confidence=0.9, location="text_subtext", evidence="test", psychological_weight=90.0)],
            achilles_score=85.0,
            resonance_potential=0.9
        )
    elif response_model.__name__ == "GeneratedMessage":
        return GeneratedMessage(
            message="O sessiz sinyal, tesadüf değil.",
            strategy="void_resonance",
            confidence=0.95,
            compliance_score=100.0,
            dialogue_tree=[
                ScenarioResponse(scenario_type="agresif", expected_target_reaction="Ne diyorsun?", our_counter_move="Sadece bir gözlem.")
            ]
        )
    elif response_model.__name__ == "ClaimList":
        # It's dynamically defined in autonomous_verifier.py
        from agent_core.agents.autonomous_verifier import Claim
        return response_model(claims=[Claim(claim_text="Sadece pozitif enerji", category="bio")])
    elif response_model.__name__ == "VerificationResult":
        return VerificationResult(
            claim_text="test", truth_status="DOĞRULANDI", evidence_url="http", contradiction_detail="none"
        )
    elif response_model.__name__ == "AuthenticVectorResult":
        return response_model(
            depth=0.8, energy=0.4, achilles_heel="yalnizlik", core_wound="anlasilmama", dark_detail="sessizlik"
        )
    raise ValueError(f"Unknown model: {response_model.__name__}")


@pytest.mark.asyncio
async def test_p2_release_gate_e2e_integration():
    """
    P2 Release Gate: Test the full pipeline from PinealExecutor through the Cognitive Router, 
    all mapped agents (MirrorTruth, AutonomousVerifier, HumanBehavior, ResonanceCalc, PatternInterrupt),
    populating the evidence chain successfully and completing.
    """
    executor = PinealExecutor()
    # In main.py, pattern_interrupt is registered dynamically (though it's in PinealExecutor.__init__ too)
    executor.agents['pattern_interrupt'] = PatternInterrupt()
    executor.search_engine.tavily_key = "mock_tavily_key_for_test"
    
    # Mock search_engine to avoid real network call and empty results
    from agent_core.services.search_engine import SearchResult
    executor.search_engine.search = AsyncMock(return_value=[
        SearchResult(query="dummy", content="Sadece pozitif enerji", source_url="http://mock.com")
    ])
    
    # Input fixture that triggers both user and target routing logic
    task_input = {
        'user_profile': {
            'private_rituals': ['çay', 'kitap', 'neset_ertas'],
            'late_night_playlist': ['neşet ertaş - gönül dağı'],
            'secret_envies': ['derin bağlantılar', 'anlaşılmak'],
            'authenticity_score': 0.85
        },
        'target_profile': {
            'images': [],
            'bio': "Sadece pozitif enerji ✨",
            'posts': ["Cuma akşamı evdeyim yorgunum 😴"]
        }
    }
    
    # Patch LLMGateway.query_json to avoid real API calls and timeouts
    with patch("agent_core.services.llm_gateway.LLMGateway.query_json", new=AsyncMock(side_effect=mock_query_json)):
        # Run execution
        result = await executor.execute_task(task_input, task_id="p2_release_gate")
        
        # Assertions
        assert result.status == "completed", f"Expected 'completed', got {result.status}."
        
        # The chain should contain results from MirrorTruth, Verifier, HumanBehavior, ResonanceCalc, PatternInterrupt
        agent_names_in_chain = [step['agent'] for step in result.evidence_chain]
        
        assert "mirror_truth" in agent_names_in_chain
        assert "autonomous_verifier" in agent_names_in_chain
        assert "human_behavior" in agent_names_in_chain
        assert "resonance_calc" in agent_names_in_chain
        assert "pattern_interrupt" in agent_names_in_chain
        
        # Final result check
        final_message = result.evidence_chain[-1]['result'].get('message', '')
        assert "O sessiz sinyal" in final_message
