import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.task_executor import PinealExecutor
from agent_core.domain.memory_models import (
    PassionProfile, FrictionProfile, CognitiveStyle, AuthenticBridge
)
from agent_core.services.llm_gateway import LLMGateway

@pytest.mark.asyncio
async def test_holistic_360_e2e_pipeline():
    executor = PinealExecutor()
    
    # Mock LLM Gateway to return valid Pydantic models for 360 agents
    mock_gateway = MagicMock(spec=LLMGateway)
    
    async def mock_query_json(prompt, schema=None, response_model=None, **kwargs):
        model = schema or response_model
        name = getattr(model, "__name__", "")
        if name == "PassionProfile":
            return PassionProfile(
                core_passions=["Mimari tasarımları estetik ve işlevsellikle birleştirmek", "Görsel ve kentsel algı üzerine derinlemesine analizler yapmak"],
                energizing_topics=["Minimalist kentsel dokular ve binalar", "Şehir planlamanın insan psikolojisine etkileri", "Sessiz mekan tasarımları"],
                passion_categories=["Estetik", "Mimari Tasarım", "Kentsel Psikoloji"],
                intensity_indicators=["Estetik her şeydir vurgusuyla net bir tavır sergilemesi", "Sürekli mekan ve huzur algısına referans vermesi"],
                anti_passions=["Yüzeysel tasarımlar", "Gürültülü yapılar"],
                evidence_strength="Güçlü (birden fazla gönderide tutarlı estetik algısı)",
                flow_triggers=["Sokak fotoğrafları çekmek"],
                sentiment_polarity=0.8,
                evidence_quotes=["Estetik her şeydir."],
                confidence=0.9
            )
        elif name == "FrictionProfile":
            return FrictionProfile(
                sensitivities=["Zaman İsrafı"],
                stress_triggers=["Gereksiz Toplantılar"],
                boundary_signals=["Özel Alan"],
                evidence_quotes=["Sessizlik huzurdur."],
                confidence=0.85
            )
        elif name == "CognitiveStyle":
            return CognitiveStyle(
                communication_tone="analitik",
                complexity_level="teknik",
                humor_style="kuru mizah",
                social_orientation="gözlemci",
                confidence=0.9
            )
        elif name == "AuthenticBridge":
            return AuthenticBridge(
                shared_passions=["Mimari Estetik"],
                complementary_perspectives=["Görsel Kompozisyon"],
                resonance_score=0.94,
                authentic_opening_topic="Kentsel Doku ve Mimari Detaylar",
                conversation_starter_rationale="Ortak görsel ilgi ve analitik yaklaşım.",
                suggested_opening_message="Merhaba, mimari kompozisyon paylaşımlarınızdaki detaylar çok ilham verici.",
                confidence=0.95
            )
        elif name == "MirrorReflection":
            from agent_core.agents.mirror_truth import MirrorReflection
            return MirrorReflection(
                user_core_frequency="derin tasarım ve estetik arayışlara dayalı, iç dünyasında mimari ve mekansal bir estetik arayan çok boyutlu bir yaşam frekansı",
                surface_persona="analitik, mantıklı, ölçülü ve dışa dönük teknik bir imaj çizen, insanlarla mesafeli ama aynı zamanda fikirlerini paylaşan",
                alignment_score=0.9,
                authentic_anchors=["estetik detaylar ve mimari güzellikler üzerine konuşmak", "teknik kusursuzluk ve tasarım felsefesi", "uzun mimari yürüyüşler", "şehir hatıraları"]
            )
        elif name == "ClaimList":
            from agent_core.agents.autonomous_verifier import Claim
            return model(claims=[Claim(claim_text="Mimar", category="bio")])
        elif name == "VerificationResult":
            from agent_core.agents.autonomous_verifier import VerificationResult
            return VerificationResult(
                claim_text="Mimar", truth_status="DOĞRULANDI", evidence_url="http", contradiction_detail=""
            )
        elif name == "DigitalColdReading":
            from agent_core.agents.human_behavior import DigitalColdReading, MicroSignal
            return DigitalColdReading(
                surface_identity="mimar",
                detected_wound="yüzeysellik",
                defense_mechanism="sessizlik",
                micro_signals=[MicroSignal(signal_type="authentic", confidence=0.9, location="text_subtext", evidence="test", psychological_weight=90.0)],
                achilles_score=85.0,
                resonance_potential=0.9
            )
        elif name == "GeneratedMessage":
            from agent_core.agents.pattern_interrupt import GeneratedMessage
            return GeneratedMessage(
                message="O sessiz sinyal, tesadüf değil.",
                strategy="void_resonance",
                confidence=0.95,
                compliance_score=100.0,
                dialogue_tree=[]
            )
        elif name == "AuthenticVectorResult":
            return model(
                depth=0.8, energy=0.5, achilles_heel="estetik", core_wound="yüzeysellik", dark_detail="sessizlik"
            )
        return model()

    mock_gateway.query_json = AsyncMock(side_effect=mock_query_json)
    mock_gateway.query = AsyncMock(return_value="Mocked LLM raw response")

    async def _qjc(prompt, schema=None, task="depth", **kw):
        return await mock_query_json(prompt, schema=schema, **kw)
    mock_gateway.query_json_chain = AsyncMock(side_effect=_qjc)
    mock_gateway.query_chain = AsyncMock(return_value="Mocked LLM raw response")
    
    from agent_core.services.search_engine import SearchResult
    executor.search_engine.tavily_key = "mock_tavily_key"
    executor.search_engine.search = AsyncMock(return_value=[
        SearchResult(query="dummy", content="Mimar", source_url="http://mock.com")
    ])

    executor.llm_gateway = mock_gateway
    for agent in executor.agents.values():
        if hasattr(agent, "llm_gateway"):
            agent.llm_gateway = mock_gateway
    
    payload = {
        "target_profile": {
            "username": "@mimardesign",
            "bio": "Mimar, fotoğrafçı ve estetik araştırmacısı.",
            "posts": [
                "Estetik her şeydir.",
                "Sessizlik huzurdur.",
                "Yeni kentsel dönüşüm projesinde mekan algısı üzerine çalıştık."
            ]
        },
        "user_profile": {
            "bio": "Şehir plancısı ve tasarımcı.",
            "posts": ["Mekanların insan psikolojisine etkisi."]
        },
        "sacred_rules": "Ucuz manipülasyondan kaçın, sahici rezonans kur."
    }
    
    from unittest.mock import patch
    with patch("agent_core.services.llm_gateway.LLMGateway.query_json", new=AsyncMock(side_effect=mock_query_json)), \
         patch("agent_core.services.llm_gateway.LLMGateway.query", new=AsyncMock(return_value="Mocked LLM raw response")), \
         patch("agent_core.services.llm_gateway.LLMGateway.query_json_chain", new=AsyncMock(side_effect=_qjc)), \
         patch("agent_core.services.llm_gateway.LLMGateway.query_chain", new=AsyncMock(return_value="Mocked LLM raw response")):
        
        res = await executor.execute_task(payload, task_id="test_holistic_001")
        
        # Since some non-critical agents might fail, partially_completed is also acceptable
        from agent_core.domain.pipeline_status import PipelineStatus
        assert res.status in ("completed", "partially_completed", PipelineStatus.COMPLETED, PipelineStatus.PARTIALLY_COMPLETED)
    assert res.holistic_profile is not None
    assert "passion_mapper" in res.completed_agents
    assert "friction_detector" in res.completed_agents
    assert "cognitive_profiler" in res.completed_agents
    assert "resonance_synthesizer" in res.completed_agents
    assert res.holistic_profile is not None
    assert res.holistic_profile.passions.core_passions == ["Mimari tasarımları estetik ve işlevsellikle birleştirmek", "Görsel ve kentsel algı üzerine derinlemesine analizler yapmak"]
    assert "Zaman İsrafı" in res.holistic_profile.frictions.sensitivities
    assert res.holistic_profile.cognitive.communication_tone == "analitik"
    assert res.holistic_profile.bridge.resonance_score == 0.94
