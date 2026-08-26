from agent_core.services.llm_gateway import LLMGateway


def test_specialist_agent_chains_are_explicit():
    gateway = LLMGateway()
    assert gateway.get_agent_chain("cognitive_profiler", "depth")[0] == "upstage/solar-pro4"
    assert gateway.get_agent_chain("friction_detector", "fast")[0] == "inclusionai/ling-3.0-flash"
    assert gateway.get_agent_chain("passion_mapper", "depth")[0] == "deepseek/deepseek-v4-pro"
    assert gateway.get_agent_chain("vision_analyzer", "vision") == ["google/gemini-3.7-flash"]
