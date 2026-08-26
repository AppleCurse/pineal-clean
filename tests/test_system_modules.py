import pytest
from unittest.mock import AsyncMock, MagicMock

from agent_core.psychology.dark_triad import DarkTriadAnalyzer, DarkTriadProfile
from agent_core.chat.dialogue_manager import DialogueManager
from agent_core.services.llm_gateway import LLMGateway


def test_dark_triad_analyzer_deterministic():
    """Anahtar-sayma analizi deterministik olmalı: aynı girdi, aynı skor."""
    analyzer = DarkTriadAnalyzer()
    profile = {"posts": ["Her şeyi ben yönetirim"], "bio": "Lider, strateji ve taktik"}
    r1 = analyzer.analyze(profile)
    r2 = analyzer.analyze(profile)
    assert isinstance(r1, DarkTriadProfile)
    assert r1.model_dump() == r2.model_dump()
    assert all(0.0 <= getattr(r1, f) <= 1.0 for f in ("machiavellianism", "narcissism", "psychopathy", "exploitability"))


def test_dark_triad_strategy_vector():
    analyzer = DarkTriadAnalyzer()
    res = analyzer.analyze({"posts": ["mükemmel benzersiz seçilmiş"], "bio": ""})
    strategy = analyzer.generate_strategy(res)
    # Kanıtsız "empathy" üretilmez; eşik altı işaret dürüstçe "unobserved"
    # işaretlenir. Eşik aşan işaretler gerçek strateji üretir.
    assert strategy["vector"] in ("mirroring", "alliance", "thrill", "unobserved")


@pytest.mark.asyncio
async def test_dialogue_manager_generate_response_roundtrip():
    """Session -> hedef mesajı -> (mock) LLM -> karşı-hamle + geçmişe yazım."""
    dm = DialogueManager()
    dm.start_session("task_dm", {"bio": "test"}, {"private_rituals": ["çay"]})

    async def fake_query_json(prompt, schema, **kwargs):
        return schema(stance="Savunmaci", internal_analysis="test", next_move="Test karşı-hamlesi")

    dm.llm = MagicMock(spec=LLMGateway)
    dm.llm.query_json = AsyncMock(side_effect=fake_query_json)

    res = await dm.generate_response("task_dm", "Sen kimsin?")
    assert res.stance == "Savunmaci"
    assert res.next_move == "Test karşı-hamlesi"
    # Geçmişe hedef + agent mesajı yazılmış olmalı
    roles = [m["role"] for m in dm.sessions["task_dm"].history]
    assert roles == ["target", "agent"]


@pytest.mark.asyncio
async def test_dialogue_manager_unknown_session_raises():
    dm = DialogueManager()
    with pytest.raises(ValueError):
        await dm.generate_response("yok_boyle_session", "merhaba")
