from agent_core.services.llm_gateway import LLMGateway


def test_specialist_agent_chains_are_explicit():
    gateway = LLMGateway()
    assert gateway.get_agent_chain("cognitive_profiler", "depth")[0] == "anthropic/claude-sonnet-5"
    assert gateway.get_agent_chain("friction_detector", "fast")[0] == "anthropic/claude-sonnet-5"
    assert gateway.get_agent_chain("passion_mapper", "depth")[0] == "anthropic/claude-sonnet-5"
    assert gateway.get_agent_chain("resonance_synthesizer", "depth")[0] == "anthropic/claude-sonnet-5"
    assert gateway.get_agent_chain("aspasia", "dialogue")[0] == "anthropic/claude-sonnet-5"
    assert gateway.get_agent_chain("vision_analyzer", "vision") == [
        "google/gemini-3.7-flash",
        "x-ai/grok-4.6",
    ]
    assert gateway.get_agent_chain("osint_investigator", "depth")[0] == "x-ai/grok-4.6"


def test_verifier_extract_and_judgment_use_distinct_chains():
    """Karar matrisi: extract mekanik/ucuz, hüküm kaliteli — ve farklı sağlayıcı."""
    gateway = LLMGateway()
    extract_chain = gateway.get_agent_chain("autonomous_verifier_extract", "fast")
    judge_chain = gateway.get_agent_chain("autonomous_verifier", "depth")
    assert extract_chain[0] == "deepseek/deepseek-v4-flash"
    assert judge_chain[0] == "anthropic/claude-sonnet-5"
    assert extract_chain[0].split("/")[0] != judge_chain[0].split("/")[0]


def test_retired_slugs_are_not_in_any_default_chain():
    retired = {"upstage/solar-pro4", "inclusionai/ling-3.0-flash", "z-ai/glm-5.2"}
    for chain in LLMGateway.CHAINS.values():
        assert retired.isdisjoint(chain)
    for chain in LLMGateway.AGENT_CHAINS.values():
        assert retired.isdisjoint(chain)


def test_task_and_agent_capabilities_are_explicit():
    gateway = LLMGateway()
    assert "vision" in gateway.required_capabilities(task="vision")
    assert "vision" in gateway.required_capabilities(agent_name="vision_analyzer")
    assert "vision" in gateway.required_capabilities(task="fast", images=["data:image/png;base64,AA"])
    assert "vision" not in gateway.required_capabilities(task="fast")
    assert gateway.model_satisfies("google/gemini-3.7-flash", frozenset({"chat", "vision"}))
    assert gateway.model_satisfies("x-ai/grok-4.6", frozenset({"chat", "vision"}))
    assert gateway.model_satisfies("anthropic/claude-sonnet-5", frozenset({"chat", "vision"}))
    assert not gateway.model_satisfies("inclusionai/ling-3.0-flash", frozenset({"chat", "vision"}))


def test_capable_chain_drops_text_only_models_for_vision():
    gateway = LLMGateway()
    # Vision zinciri: Gemini birincil, Grok 4.6 yedek — ikisi de vision'lı.
    assert gateway.capable_chain(task="vision") == [
        "google/gemini-3.7-flash",
        "x-ai/grok-4.6",
    ]
    assert gateway.capable_chain(agent_name="vision_analyzer", task="vision") == [
        "google/gemini-3.7-flash",
        "x-ai/grok-4.6",
    ]
    # Fast zincirinin metin-only birincili (deepseek-v4-flash) visionlı istekte
    # süzülür; vision yedeği (gemini) devreye girer — fail-closed yerine
    # fail-into-vision.
    assert gateway.capable_chain(task="fast", images=["data:image/png;base64,AA"]) == [
        "google/gemini-3.7-flash"
    ]
