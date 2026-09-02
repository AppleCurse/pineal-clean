from agent_core.services.llm_gateway import LLMGateway


def test_specialist_agent_chains_are_explicit():
    gateway = LLMGateway()
    assert gateway.get_agent_chain("cognitive_profiler", "depth")[0] == "upstage/solar-pro4"
    assert gateway.get_agent_chain("friction_detector", "fast")[0] == "inclusionai/ling-3.0-flash"
    assert gateway.get_agent_chain("passion_mapper", "depth")[0] == "deepseek/deepseek-v4-pro"
    assert gateway.get_agent_chain("vision_analyzer", "vision") == ["google/gemini-3.7-flash"]


def test_task_and_agent_capabilities_are_explicit():
    gateway = LLMGateway()
    assert "vision" in gateway.required_capabilities(task="vision")
    assert "vision" in gateway.required_capabilities(agent_name="vision_analyzer")
    assert "vision" in gateway.required_capabilities(task="fast", images=["data:image/png;base64,AA"])
    assert "vision" not in gateway.required_capabilities(task="fast")
    assert gateway.model_satisfies("google/gemini-3.7-flash", frozenset({"chat", "vision"}))
    assert not gateway.model_satisfies("inclusionai/ling-3.0-flash", frozenset({"chat", "vision"}))


def test_capable_chain_drops_text_only_models_for_vision():
    gateway = LLMGateway()
    assert gateway.capable_chain(task="vision") == ["google/gemini-3.7-flash"]
    assert gateway.capable_chain(agent_name="vision_analyzer", task="vision") == [
        "google/gemini-3.7-flash"
    ]
    try:
        gateway.capable_chain(task="fast", images=["data:image/png;base64,AA"])
        raise AssertionError("text-only fast chain must not accept vision")
    except RuntimeError as exc:
        assert "NO_CAPABLE_MODEL" in str(exc)
