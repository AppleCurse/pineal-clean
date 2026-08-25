import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.agents.friction_detector import FrictionDetectorAgent
from agent_core.agents.cognitive_profiler import CognitiveProfilerAgent
from agent_core.agents.authenticity_auditor import AuthenticityAuditorAgent
from agent_core.agents.depth_analyst import DepthAnalyst
from agent_core.services.llm_gateway import LLMGateway

@pytest.mark.asyncio
async def test_friction_detector_unavailable_contract():
    mock_gw = MagicMock(spec=LLMGateway)
    mock_gw.query_json_chain = AsyncMock(side_effect=RuntimeError("LLM offline"))
    agent = FrictionDetectorAgent(llm_gateway=mock_gw)
    res = await agent.execute({"target_profile": {"bio": "test"}, "visual_evidence": {"detected_objects": ["a"]}})
    assert res.confidence == 0.0
    assert res.data_confidence is False
    assert res.fallback_reason == "llm_unavailable"

@pytest.mark.asyncio
async def test_cognitive_profiler_unavailable_contract():
    mock_gw = MagicMock(spec=LLMGateway)
    mock_gw.query_json_chain = AsyncMock(side_effect=RuntimeError("LLM offline"))
    agent = CognitiveProfilerAgent(llm_gateway=mock_gw)
    res = await agent.execute({"target_profile": {"bio": "test"}})
    assert res.confidence == 0.0
    assert res.data_confidence is False
    assert res.fallback_reason == "llm_unavailable"

@pytest.mark.asyncio
async def test_authenticity_auditor_unavailable_contract():
    mock_gw = MagicMock(spec=LLMGateway)
    mock_gw.query_json_chain = AsyncMock(side_effect=RuntimeError("LLM offline"))
    agent = AuthenticityAuditorAgent(llm_gateway=mock_gw)
    res = await agent.execute({"target_profile": {"bio": "test"}, "visual_evidence": {"detected_objects": ["a"]}})
    assert res.authenticity_score == 0.0
    assert res.confidence == 0.0
    assert res.data_confidence is False
    assert res.fallback_reason == "llm_unavailable"

@pytest.mark.asyncio
async def test_depth_analyst_unavailable_contract():
    mock_gw = MagicMock(spec=LLMGateway)
    mock_gw.query_json_chain = AsyncMock(side_effect=RuntimeError("LLM offline"))
    agent = DepthAnalyst(llm_gateway=mock_gw)
    res = await agent.analyze({"target_profile": {"bio": "test"}}, [])
    assert res.reality_index == 0.0
    assert getattr(res, "data_confidence", False) is False
    assert getattr(res, "fallback_reason", "") == "llm_unavailable"
